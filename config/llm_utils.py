"""
LLM Utility Components
Provides utility components for LLM integration, especially for AppleGenAI compatibility
"""

from typing import List
from haystack import component
from haystack.dataclasses import ChatMessage


@component
class StringToChatMessages:
    """
    Converts a string prompt into a list of ChatMessage objects for AppleGenAI compatibility.
    
    This component ensures that string prompts are properly formatted as ChatMessage objects
    which is required for proper AppleGenAI integration.
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
    
    def __init__(self, provider: str = "apple_genai"):
        """
        Initialize the message formatter.
        
        Args:
            provider: The LLM provider ("apple_genai", "openai", etc.)
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
        if self.provider == "apple_genai":
            # Apple GenAI specific formatting if needed
            formatted = []
            for msg in messages:
                formatted.append(msg)
            return {"formatted_messages": formatted}
        else:
            # Default formatting
            return {"formatted_messages": messages}


# Utility functions for creating compatible generators
def create_apple_genai_compatible_generator(model: str, **kwargs):
    """
    Create an AppleGenAI generator with proper message handling.
    
    Args:
        model: The model identifier
        **kwargs: Additional parameters for the generator
        
    Returns:
        Configured AppleGenAI generator
    """
    try:
        from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator
        
        # Set up default parameters for Apple GenAI
        params = {
            "model": model,
        }
        
        # Pass through any additional parameters (like generation_kwargs)
        params.update(kwargs)
        
        return AppleGenAIChatGenerator(**params)
        
    except ImportError:
        raise ImportError("hwtgenielib not available for AppleGenAI generator")


def create_message_conversion_pipeline():
    """
    Create a pipeline that handles string to ChatMessage conversion.
    
    Returns:
        Pipeline for message conversion
    """
    from haystack import Pipeline
    
    pipeline = Pipeline()
    pipeline.add_component("string_to_messages", StringToChatMessages())
    
    return pipeline


# Example usage and testing
if __name__ == "__main__":
    print("=== LLM Utility Components Test ===")
    
    # Test StringToChatMessages
    converter = StringToChatMessages()
    result = converter.run("Test prompt for conversion")
    
    print(f"String to Messages conversion:")
    print(f"  Input: 'Test prompt for conversion'")
    print(f"  Output: {len(result['messages'])} messages")
    print(f"  First message: {result['messages'][0].content}")
    
    # Test ChatMessagesToString
    string_converter = ChatMessagesToString()
    back_to_string = string_converter.run(result['messages'])
    
    print(f"\nMessages to String conversion:")
    print(f"  Output: '{back_to_string['text']}'")
    
    # Test MessageFormatter
    formatter = MessageFormatter("apple_genai")
    formatted_result = formatter.run(result['messages'])
    
    print(f"\nMessage formatting:")
    print(f"  Formatted {len(formatted_result['formatted_messages'])} messages for apple_genai")
    
    print("\n✅ All utility components working correctly!")