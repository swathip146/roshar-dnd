"""
LLM Utility Components
Provides utility components for LLM integration
"""

import os
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

            return {"replies": [ChatMessage.from_assistant(text_response or "")]}
                
        except Exception as e:
            error_message = f"Gemini API error: {str(e)}"
            logger.error(f"GEMINI ERROR: {error_message}")
            return {"replies": [ChatMessage.from_assistant(error_message)]}
    
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

                # Copy properties, but strip out "default" fields (not supported by Gemini)
                if "properties" in parameters:
                    cleaned_properties = {}
                    for prop_name, prop_schema in parameters["properties"].items():
                        # Create a copy without the "default" field
                        cleaned_schema = {k: v for k, v in prop_schema.items() if k != "default"}
                        cleaned_properties[prop_name] = cleaned_schema
                    gemini_parameters["properties"] = cleaned_properties

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