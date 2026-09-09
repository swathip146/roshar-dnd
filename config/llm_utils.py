"""
LLM Utility Components
Provides utility components for LLM integration
"""

import os
import re
from typing import List, Dict, Any, Optional

from config.logging_config import get_logger

# Initialize logger
logger = get_logger(__name__)


# Import Haystack components if available
try:
    from haystack import component
    from haystack.dataclasses import ChatMessage
    HAYSTACK_AVAILABLE = True
except (ImportError, TypeError, AttributeError) as e:
    HAYSTACK_AVAILABLE = False
    _HAYSTACK_IMPORT_ERROR = str(e)
    
    # Create fallback component decorator and ChatMessage class
    class component:
        """Fallback component decorator when Haystack is not available"""
        def __init__(self, cls):
            self.cls = cls
        
        def __call__(self, *args, **kwargs):
            return self.cls(*args, **kwargs)
        
        @staticmethod
        def output_types(**kwargs):
            def decorator(func):
                return func
            return decorator
    
    class ChatMessage:
        """Fallback ChatMessage class when Haystack is not available"""
        def __init__(self, content: str, role: str = "user"):
            self.text = content  # Primary property for newer Haystack API
            self.content = content  # For backward compatibility
            self.role = role
        
        @classmethod
        def from_user(cls, content: str):
            return cls(content, "user")
        
        @classmethod
        def from_assistant(cls, content: str):
            return cls(content, "assistant")

# Plan 4: use the CURRENT Gemini SDK.
#
# This module used `google.generativeai`, which prints "All support for the
# google.generativeai package has ended" on every run, while requirements.txt
# already declared `google-genai` as its replacement. Ported to the new SDK:
#   genai.configure() + GenerativeModel  ->  genai.Client()
#   model.generate_content(prompt)       ->  client.models.generate_content(...)
#   generation_config dict               ->  types.GenerateContentConfig
#
# The port also fixes a real defect the old SDK forced on us: it had no system
# role, so system prompts were flattened into user text. The new SDK has a real
# `system_instruction`, so the DM's system prompt is now actually a system
# prompt.
GEMINI_AVAILABLE = False
GEMINI_SDK = None
genai = None
genai_types = None

try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
    GEMINI_SDK = "google-genai"
except ImportError:
    pass


@component
class StringToChatMessages:
    """
    Converts a string prompt into a list of ChatMessage objects.
    
    This component ensures that string prompts are properly formatted as ChatMessage objects
    which is required for proper LLM integration.
    """
    
    @component.output_types(messages=List[ChatMessage])
    def run(self, prompt: str) -> dict:
        """
        Convert a string prompt to ChatMessage list.
        
        Args:
            prompt: The input prompt string
            
        Returns:
            Dictionary containing list of ChatMessage objects
        """
        return {"messages": [ChatMessage.from_user(prompt)]}


@component
class ChatMessagesToString:
    """
    Converts ChatMessage objects back to string format if needed.
    """
    
    @component.output_types(text=str)
    def run(self, messages: List[ChatMessage]) -> dict:
        """
        Convert ChatMessage list to string.
        
        Args:
            messages: List of ChatMessage objects
            
        Returns:
            Dictionary containing concatenated text
        """
        if not messages:
            return {"text": ""}
        
        # Extract text content from messages
        text_parts = []
        for msg in messages:
            if hasattr(msg, 'text') and msg.text:
                text_parts.append(msg.text)
            elif hasattr(msg, 'content') and msg.content:  # Fallback for older versions
                text_parts.append(msg.content)
        
        return {"text": "\n".join(text_parts)}


@component  
class MessageFormatter:
    """
    Formats messages for different LLM providers.
    """
    
    def __init__(self, provider: str = "gemini"):
        """
        Initialize the message formatter.
        
        Args:
            provider: The LLM provider ("gemini", "openai", etc.)
        """
        self.provider = provider
    
    @component.output_types(formatted_messages=List[ChatMessage])
    def run(self, messages: List[ChatMessage]) -> dict:
        """
        Format messages for the specified provider.
        
        Args:
            messages: List of input ChatMessage objects
            
        Returns:
            Dictionary containing formatted messages
        """
        # Default formatting (can be extended for provider-specific formatting)
        return {"formatted_messages": messages}


# Utility functions for creating compatible generators
def create_message_conversion_pipeline():
    """
    Create a pipeline that handles string to ChatMessage conversion.
    
    Returns:
        Pipeline for message conversion
    """
    if not HAYSTACK_AVAILABLE:
        raise ImportError("Haystack not available for pipeline creation")
        
    from haystack import Pipeline
    
    pipeline = Pipeline()
    pipeline.add_component("string_to_messages", StringToChatMessages())
    
    return pipeline


# Keys that are valid JSON Schema but that Gemini's function-calling dialect
# rejects outright with 400 INVALID_ARGUMENT "Unknown name ...: Cannot find
# field". `default` was already stripped; the rest were not, and only surfaced
# on the NPC pipeline, whose tools take Dict[str, Any] and Optional[...] params.
_GEMINI_UNSUPPORTED_SCHEMA_KEYS = (
    "default",
    "additionalProperties",  # produced by Dict[str, Any]
    "title",
    "$schema",
    "examples",
)


def _sanitize_schema_for_gemini(schema: Any) -> Any:
    """
    Recursively strip JSON-Schema keys Gemini's tool dialect cannot parse.

    Two shapes broke real calls, and neither was caught by the previous cleaner
    because it only looked at the top level of each property:

      Dict[str, Any]  -> {"additionalProperties": true, "type": "object"}
      Optional[Dict]  -> {"anyOf": [{...,"type":"object"}, {"type":"null"}]}

    Gemini has no null type and no anyOf here, so an Optional collapses to its
    first non-null branch — the parameter is simply treated as optional, which is
    what `required` already conveys.
    """
    if isinstance(schema, list):
        return [_sanitize_schema_for_gemini(item) for item in schema]
    if not isinstance(schema, dict):
        return schema

    # Collapse anyOf/oneOf to the first non-null branch.
    for union_key in ("anyOf", "oneOf"):
        if union_key in schema:
            branches = [b for b in schema[union_key]
                        if not (isinstance(b, dict) and b.get("type") == "null")]
            chosen = branches[0] if branches else {"type": "string"}
            merged = {k: v for k, v in schema.items()
                      if k not in (union_key, "anyOf", "oneOf")}
            merged.update(chosen if isinstance(chosen, dict) else {})
            return _sanitize_schema_for_gemini(merged)

    cleaned = {}
    for key, value in schema.items():
        if key in _GEMINI_UNSUPPORTED_SCHEMA_KEYS:
            continue
        if key == "properties" and isinstance(value, dict):
            cleaned[key] = {k: _sanitize_schema_for_gemini(v)
                            for k, v in value.items()}
        elif key == "items":
            cleaned[key] = _sanitize_schema_for_gemini(value)
        else:
            cleaned[key] = _sanitize_schema_for_gemini(value)

    # An object with no usable properties is rejected too; give it a free-form
    # string field so the declaration stays valid.
    if cleaned.get("type") == "object" and not cleaned.get("properties"):
        cleaned["properties"] = {
            "value": {"type": "string", "description": "JSON-encoded payload"}
        }
    return cleaned


class GeminiAPIError(RuntimeError):
    """
    A Gemini call failed.

    This exists because the failure used to be returned AS THE ASSISTANT'S REPLY:
    a 403 became the string "Gemini API error: 403 Forbidden", which flowed
    downstream until the intent parser rejected it and logged "Failed to parse
    intent data from structured output: No JSON object found in response" against
    pipeline_integration.py. The reported error named the wrong subsystem, and a
    transient network fault was indistinguishable from a model that wrote prose
    instead of JSON.

    `status_code` is parsed off the message where possible so callers can tell a
    retryable fault (429/5xx) from a permanent one (400/403).
    """

    def __init__(self, message: str, *, status_code: Optional[int] = None,
                 cause: Optional[BaseException] = None):
        super().__init__(message)
        self.status_code = status_code
        self.cause = cause

    @property
    def retryable(self) -> bool:
        """True for rate limits and server faults, which are worth retrying."""
        return self.status_code in (408, 429, 500, 502, 503, 504)


def _status_code_of(error: BaseException) -> Optional[int]:
    """Best-effort HTTP status for an SDK exception."""
    for attribute in ("code", "status_code"):
        value = getattr(error, attribute, None)
        if isinstance(value, int):
            return value
    match = re.search(r"\b(4\d{2}|5\d{2})\b", str(error))
    return int(match.group(1)) if match else None


def _empty_response_reason(response: Any) -> str:
    """
    Explain why a Gemini response carried no text.

    MAX_TOKENS and SAFETY are the common causes and need opposite fixes (raise
    the cap vs. rephrase the prompt), so the distinction is worth reporting.
    """
    try:
        feedback = getattr(response, "prompt_feedback", None)
        blocked = getattr(feedback, "block_reason", None)
        if blocked:
            return f"prompt blocked: {blocked}"

        for candidate in (getattr(response, "candidates", None) or []):
            finish = getattr(candidate, "finish_reason", None)
            if finish is None:
                continue
            finish_name = getattr(finish, "name", str(finish))
            if "MAX_TOKENS" in finish_name.upper():
                return ("finish_reason=MAX_TOKENS — the reply was truncated; "
                        "raise max_output_tokens")
            if "SAFETY" in finish_name.upper() or "RECITATION" in finish_name.upper():
                return f"finish_reason={finish_name} — candidate was filtered"
            return f"finish_reason={finish_name}"
    except Exception:  # pragma: no cover - diagnostics must never mask the error
        pass
    return "no candidates and no finish_reason"


@component
class GeminiChatGenerator:
    """
    A chat generator wrapper for Google's Gemini API that provides Haystack-compatible interface.
    Supports structured output via JSON schema for reliable JSON generation.
    """

    def __init__(self, model_name: str, generation_config: Optional[Dict[str, Any]] = None,
                 response_schema: Optional[Dict[str, Any]] = None):
        """
        Initialize the Gemini chat generator.

        Args:
            model_name: The Gemini model name (e.g., "gemini-2.5-flash")
            generation_config: Configuration for text generation
            response_schema: JSON schema for structured output (forces valid JSON)
        """
        if not GEMINI_AVAILABLE:
            raise ImportError(
                "google-genai package not available (pip install google-genai)")

        self.model_name = model_name
        self.generation_config = generation_config or {}
        self.response_schema = response_schema

        # If response_schema provided, configure for JSON mode
        if response_schema:
            self.generation_config['response_mime_type'] = 'application/json'
            self.generation_config['response_schema'] = response_schema
            logger.info(f"🎯 GeminiChatGenerator initialized with structured output schema")

        # Initialize the client. The new SDK is client-based: the model name is
        # passed per call rather than baked into a model object.
        try:
            # The client reads GEMINI_API_KEY / GOOGLE_API_KEY from the
            # environment, which is how run_game.sh already supplies it.
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            self.client = genai.Client(api_key=api_key) if api_key else genai.Client()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Gemini client: {e}")
    
    @component.output_types(replies=List[ChatMessage])
    def run(self, messages: List[ChatMessage], tools: Optional[List[Any]] = None) -> Dict[str, Any]:
        """
        Generate chat completion using Gemini API.

        Args:
            messages: List of ChatMessage objects
            tools: List of tools for function calling

        Returns:
            Dictionary containing generated replies
        """
        try:
            # Convert messages to Gemini format
            gemini_messages = self._convert_messages_to_gemini(messages)

            logger.debug(f"🔧 Gemini Messages: {len(gemini_messages)} messages")

            # Convert Haystack tools to Gemini function declarations
            gemini_tools = None
            if tools:
                gemini_tools = self._convert_tools_to_gemini(tools)
                logger.debug(f"🔧 Gemini Tools: {len(gemini_tools)} tools")

            # New SDK: one call shape, with config carrying schema and tools.
            #
            # System messages become a real `system_instruction` instead of
            # being flattened into user text (the old SDK had no system role).
            # Haystack removed ChatMessage.content in favour of .text; read
            # .text first and fall back for older message objects.
            def _text_of(message):
                value = getattr(message, "text", None)
                if value:
                    return value
                return getattr(message, "content", "") or ""

            def _role_of(message):
                role = getattr(message, "role", "")
                return getattr(role, "value", role)

            system_text = "\n".join(
                _text_of(m) for m in messages
                if str(_role_of(m)).lower() == "system" and _text_of(m)
            )
            conversation = [m for m in messages
                            if str(_role_of(m)).lower() != "system"]
            prompt = self._convert_messages_to_prompt(conversation or messages)

            config_kwargs = dict(self.generation_config)
            if system_text:
                config_kwargs["system_instruction"] = system_text
            if gemini_tools:
                config_kwargs["tools"] = gemini_tools
                # Gemini rejects tools combined with JSON mode:
                #   400 INVALID_ARGUMENT "Function calling with a response mime
                #   type: 'application/json' is unsupported"
                # The scenario agent is configured with BOTH (a response_schema
                # for parseable output, plus the 13 DM tools added in 3.1/3.2),
                # so every scenario turn 400'd and fell back to a canned scene.
                #
                # Tools win: they let the model read real state and roll real
                # dice, which is the whole point of the agentic loop, whereas the
                # schema only guaranteed shape — and the retry path in
                # retry_with_reasoning already recovers malformed JSON.
                dropped = [k for k in ("response_mime_type", "response_schema")
                           if config_kwargs.pop(k, None) is not None]
                if dropped:
                    logger.debug(
                        f"🔧 Tools present: dropped {dropped} for this call "
                        f"(Gemini forbids function calling with JSON mode)"
                    )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=genai_types.GenerateContentConfig(**config_kwargs),
            )

            logger.debug(f"🔧 Response: {response}")

            # Check if response contains function calls
            function_calls = []
            text_response = ""

            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                    for part in candidate.content.parts:
                        # Check for function call
                        if hasattr(part, "function_call") and part.function_call:
                            fc = part.function_call
                            function_calls.append({
                                "name": fc.name,
                                "arguments": dict(fc.args) if hasattr(fc, "args") else {}
                            })
                            logger.debug(f"🔧 FUNCTION CALL: {fc.name}({dict(fc.args) if hasattr(fc, 'args') else {}})")
                        # Check for text
                        elif hasattr(part, "text") and part.text:
                            text_response += part.text

            # If we have function calls, format them for Haystack Agent
            if function_calls:
                # Use Haystack's ToolCall API (available in v2.21.0+)
                from haystack.dataclasses import ToolCall
                tool_call_objects = [
                    ToolCall(
                        id=f"call_{i}",
                        tool_name=fc["name"],
                        arguments=fc["arguments"]
                    )
                    for i, fc in enumerate(function_calls)
                ]
                # Return ChatMessage with tool_calls using from_assistant factory method
                response_msg = ChatMessage.from_assistant(
                    text="",
                    tool_calls=tool_call_objects  # Pass tool_calls directly
                )
                logger.debug(f"🔧 Returning {len(function_calls)} function calls via ToolCall objects")
                return {"replies": [response_msg]}

            # Otherwise return text response
            if not text_response:
                # Try direct text access as fallback
                try:
                    if hasattr(response, "text") and response.text:
                        text_response = response.text
                except Exception:
                    pass

            if not text_response:
                # An empty reply is almost never "the model had nothing to say":
                # it means the candidate was blocked, or hit the token cap
                # mid-JSON. Surfacing the finish_reason turns a baffling empty
                # string into an actionable message.
                reason = _empty_response_reason(response)
                logger.error(f"❌ GEMINI EMPTY RESPONSE: {reason}")
                raise GeminiAPIError(f"Gemini returned no text ({reason})")

            return {"replies": [ChatMessage.from_assistant(text_response)]}
                
        except GeminiAPIError:
            # Already classified (e.g. an empty-response raise below).
            raise
        except Exception as e:
            status = _status_code_of(e)
            error_message = f"Gemini API error: {e}"
            # Log the status explicitly: "403 Forbidden" and "429 rate limited"
            # demand completely different responses from an operator, and the old
            # message flattened both into unparseable reply text.
            logger.error(
                f"❌ GEMINI ERROR"
                f"{f' (HTTP {status})' if status else ''}: {error_message}"
            )
            # RAISE rather than returning the error as the assistant's reply.
            # Returning it made every API fault surface as a downstream JSON
            # parse error blamed on the wrong component, and made the failure
            # invisible to generate_with_retry, which treats a reply as success.
            raise GeminiAPIError(error_message, status_code=status, cause=e) from e
    
    def _convert_messages_to_prompt(self, messages: List[ChatMessage]) -> str:
        """
        Convert ChatMessage objects to a single prompt string for Gemini.
        
        Args:
            messages: List of ChatMessage objects
            
        Returns:
            Combined prompt string
        """
        prompt_parts = []
        
        for message in messages:
            # Get message content (prefer text for newer Haystack API)
            content = ""
            if hasattr(message, 'text') and message.text:
                content = message.text
            elif hasattr(message, 'content') and message.content:
                content = message.content
            
            if content:
                # Add role prefix for context
                if hasattr(message, 'role'):
                    if message.role == "user":
                        prompt_parts.append(f"User: {content}")
                    elif message.role == "assistant":
                        prompt_parts.append(f"Assistant: {content}")
                    elif message.role == "system":
                        prompt_parts.append(f"System: {content}")
                    else:
                        prompt_parts.append(content)
                else:
                    prompt_parts.append(content)
        
        return "\n\n".join(prompt_parts)
    
    def _convert_tool_to_function_declaration(self, tool) -> Optional[Dict[str, Any]]:
        """
        Convert a Haystack Tool to Gemini function declaration format.
        
        Args:
            tool: Haystack Tool object
            
        Returns:
            Gemini function declaration dict or None if conversion fails
        """
        try:
            # Extract tool information
            name = tool.name
            description = tool.description
            parameters = tool.parameters
            
            # Build Gemini function declaration
            func_declaration = {
                "name": name,
                "description": description
            }
            
            # Convert parameters schema to Gemini format
            if parameters and isinstance(parameters, dict):
                # Gemini expects parameters in a specific format
                gemini_parameters = {
                    "type": "object",
                    "properties": {},
                    "required": []
                }

                # Copy properties, sanitising each one for Gemini's schema
                # dialect (see _sanitize_schema_for_gemini).
                if "properties" in parameters:
                    gemini_parameters["properties"] = {
                        prop_name: _sanitize_schema_for_gemini(prop_schema)
                        for prop_name, prop_schema in parameters["properties"].items()
                    }

                # Copy required fields
                if "required" in parameters:
                    gemini_parameters["required"] = parameters["required"]

                func_declaration["parameters"] = gemini_parameters
            
            logger.debug(f"🔧 CONVERTED TOOL: {name} -> {func_declaration}")
            return func_declaration

        except Exception as e:
            logger.error(f"Failed to convert tool {getattr(tool, 'name', 'unknown')}: {e}")
            return None

    def _convert_tools_to_gemini(self, tools: List[Any]) -> List[Any]:
        """
        Convert Haystack tools to Gemini function calling format.

        Args:
            tools: List of Haystack Tool objects

        Returns:
            List of Gemini-compatible tool declarations
        """
        try:
            # New SDK: FunctionDeclaration and Tool live in google.genai.types.
            FunctionDeclaration = genai_types.FunctionDeclaration
            GeminiTool = genai_types.Tool

            function_declarations = []
            for tool in tools:
                func_dict = self._convert_tool_to_function_declaration(tool)
                if func_dict:
                    # Create FunctionDeclaration from dict
                    func_decl = FunctionDeclaration(
                        name=func_dict["name"],
                        description=func_dict["description"],
                        parameters=func_dict.get("parameters")
                    )
                    function_declarations.append(func_decl)

            if not function_declarations:
                return None

            # Wrap in Gemini Tool format
            gemini_tool = GeminiTool(function_declarations=function_declarations)
            logger.debug(f"🔧 Created Gemini Tool with {len(function_declarations)} functions")
            return [gemini_tool]

        except Exception as e:
            logger.error(f"Failed to convert tools to Gemini format: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _convert_messages_to_gemini(self, messages: List[ChatMessage]) -> List[Any]:
        """
        Convert Haystack ChatMessage objects to Gemini Content format.

        Args:
            messages: List of ChatMessage objects

        Returns:
            List of Gemini Content objects
        """
        try:
            gemini_messages = []
            for message in messages:
                # Get message content
                content = ""
                if hasattr(message, 'text') and message.text:
                    content = message.text
                elif hasattr(message, 'content') and message.content:
                    content = message.content

                if not content:
                    continue

                # Map Haystack roles to Gemini roles
                role = "user"  # Default
                if hasattr(message, 'role'):
                    if message.role == "assistant" or message.role == "model":
                        role = "model"
                    elif message.role == "system":
                        # Gemini doesn't have system role, prepend to first user message
                        content = f"System Instructions: {content}"
                        role = "user"
                    else:
                        role = "user"

                # New SDK: Content/Part come from google.genai.types, not
                # genai.protos.
                gemini_messages.append(genai_types.Content(
                    role=role,
                    parts=[genai_types.Part(text=content)]
                ))

            return gemini_messages

        except Exception as e:
            logger.error(f"Failed to convert messages to Gemini format: {e}")
            return []


def create_gemini_compatible_generator(model: str, **kwargs) -> GeminiChatGenerator:
    """
    Create a Gemini generator with proper configuration.
    
    Args:
        model: The model identifier
        **kwargs: Additional parameters for the generator
        
    Returns:
        Configured Gemini generator
    """
    if not GEMINI_AVAILABLE:
        raise ImportError("google-genai not available for Gemini generator")
    
    # Extract generation config from kwargs
    generation_config = kwargs.get('generation_config', {})
    
    return GeminiChatGenerator(
        model_name=model,
        generation_config=generation_config
    )


# Example usage and testing
if __name__ == "__main__":
    print("=== LLM Utility Components Test ===")
    
    # Test StringToChatMessages
    converter = StringToChatMessages()
    result = converter.run("Test prompt for conversion")
    
    logger.info(f"String to Messages conversion:")
    logger.debug(f"  Input: 'Test prompt for conversion'")
    logger.debug(f"  Output: {len(result['messages'])} messages")
    logger.debug(f"  First message: {result['messages'][0].content}")
    
    # Test ChatMessagesToString
    string_converter = ChatMessagesToString()
    back_to_string = string_converter.run(result['messages'])
    
    logger.info(f"\nMessages to String conversion:")
    logger.debug(f"  Output: '{back_to_string['text']}'")
    
    # Test MessageFormatter
    formatter = MessageFormatter("gemini")
    formatted_result = formatter.run(result['messages'])
    
    logger.info(f"\nMessage formatting:")
    logger.debug(f"  Formatted {len(formatted_result['formatted_messages'])} messages for gemini")
    
    print("\n✅ All utility components working correctly!")