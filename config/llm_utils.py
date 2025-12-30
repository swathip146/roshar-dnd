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

# Import Google AI if available
try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


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
    Uses the new google.genai SDK.
    """

    def __init__(self, model_name: str, generation_config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Gemini chat generator.

        Args:
            model_name: The Gemini model name (e.g., "gemini-2.0-flash-exp")
            generation_config: Configuration for text generation
        """
        if not GEMINI_AVAILABLE:
            raise ImportError("google-genai package not available")

        self.model_name = model_name
        self.generation_config = generation_config or {}

        # Initialize the client with API key from environment
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")

        try:
            self.client = genai.Client(api_key=api_key)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Gemini client: {e}")
    
    @component.output_types(replies=List[ChatMessage])
    def run(self, messages: List[ChatMessage], tools: Optional[List[Any]] = None) -> Dict[str, Any]:
        """
        Generate chat completion using Gemini API (new SDK).

        Args:
            messages: List of ChatMessage objects
            tools: List of tools for function calling

        Returns:
            Dictionary containing generated replies
        """
        try:
            # Convert messages to prompt string
            prompt = self._convert_messages_to_prompt(messages)

            logger.debug(f"🔧 Gemini Prompt: {prompt[:100]}...")
            if tools:
                logger.debug(f"🔧 Tools provided: {len(tools)} tools")

            # Convert Haystack tools to Gemini Tool objects if provided
            gemini_tools = None
            if tools:
                gemini_tools = []
                for tool in tools:
                    gemini_tool = self._convert_haystack_tool_to_gemini(tool)
                    if gemini_tool:
                        gemini_tools.append(gemini_tool)

                if gemini_tools:
                    logger.debug(f"🔧 Converted {len(gemini_tools)} tools for Gemini")

            # Build generation config with tools included
            config = types.GenerateContentConfig(
                temperature=self.generation_config.get('temperature', 0.7),
                max_output_tokens=self.generation_config.get('max_output_tokens', 2000),
                tools=gemini_tools if gemini_tools else None
            )

            # Generate content using new SDK
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )

            logger.debug(f"🔧 Response received")

            # Check if response contains function calls
            if hasattr(response, 'candidates') and response.candidates:
                first_candidate = response.candidates[0]
                if hasattr(first_candidate, 'content') and hasattr(first_candidate.content, 'parts'):
                    for part in first_candidate.content.parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            # Return function call in Haystack format
                            function_call = part.function_call
                            logger.debug(f"🔧 Function call detected: {function_call.name}")

                            # Format as ChatMessage with tool_call using Haystack's ToolCall
                            from haystack.dataclasses.chat_message import ToolCall

                            tool_call = ToolCall(
                                id=function_call.name,  # Use function name as ID
                                tool_name=function_call.name,
                                arguments=dict(function_call.args) if function_call.args else {}
                            )

                            msg = ChatMessage.from_assistant("", tool_calls=[tool_call])
                            return {"replies": [msg]}

            # Extract text response
            text_response = response.text if hasattr(response, 'text') else ""

            return {"replies": [ChatMessage.from_assistant(text_response or "")]}

        except Exception as e:
            error_message = f"Gemini API error: {str(e)}"
            logger.error(f"GEMINI ERROR: {error_message}")
            logger.exception(e)
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

    def _convert_haystack_tool_to_gemini(self, tool) -> Optional[Any]:
        """
        Convert a Haystack Tool to Gemini Tool format for new SDK.

        Args:
            tool: Haystack Tool object

        Returns:
            Gemini Tool object or None if conversion fails
        """
        try:
            from google.genai.types import Tool as GeminiTool, FunctionDeclaration, Schema

            # Extract tool information
            name = tool.name
            description = tool.description
            parameters = tool.parameters

            # Build Schema for function parameters
            schema = None
            if parameters and isinstance(parameters, dict):
                # Create Schema object with proper fields
                schema_params = {
                    "type": "OBJECT",  # Use string constant instead of type_
                    "properties": {},
                    "required": parameters.get("required", [])
                }

                if "properties" in parameters:
                    # Convert each property to Schema format
                    for prop_name, prop_schema in parameters["properties"].items():
                        # Map JSON schema types to Gemini types
                        prop_type = prop_schema.get("type", "STRING").upper()
                        prop_description = prop_schema.get("description", "")

                        schema_params["properties"][prop_name] = Schema(
                            type=prop_type,
                            description=prop_description
                        )

                # Create main Schema
                schema = Schema(**schema_params)

            # Create function declaration
            func_decl = FunctionDeclaration(
                name=name,
                description=description,
                parameters=schema
            )

            # Wrap in Tool object
            gemini_tool = GeminiTool(function_declarations=[func_decl])

            logger.debug(f"🔧 Converted Haystack tool '{name}' to Gemini Tool")
            return gemini_tool

        except Exception as e:
            logger.error(f"Failed to convert tool {getattr(tool, 'name', 'unknown')}: {e}")
            logger.exception(e)
            return None

    def _convert_tool_to_function_declaration(self, tool) -> Optional[Dict[str, Any]]:
        """
        Convert a Haystack Tool to Gemini function declaration format.
        (Kept for potential future use with new SDK)

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

    # Note: Tool calling support for new SDK will be added in future update
    # The new google.genai SDK has different tool calling patterns


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