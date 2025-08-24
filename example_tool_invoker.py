from haystack.dataclasses import ChatMessage
from haystack.components.tools import ToolInvoker
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.components.routers import ConditionalRouter
from haystack.tools import Tool
from haystack import Pipeline
from typing import List  # Ensure List is imported

# Define a dummy weather tool
import random

def dummy_weather(location: str):
    return {"temp": f"{random.randint(-10, 40)} °C",
            "humidity": f"{random.randint(0, 100)}%"}

weather_tool = Tool(
    name="weather",
    description="A tool to get the weather",
    function=dummy_weather,
    parameters={
        "type": "object",
        "properties": {"location": {"type": "string"}},
        "required": ["location"],
    },
)

# Initialize the ToolInvoker with the weather tool
tool_invoker = ToolInvoker(tools=[weather_tool])

# Initialize the ChatGenerator
chat_generator = OpenAIChatGenerator(model="gpt-4o-mini", tools=[weather_tool])

# Define routing conditions
routes = [
    {
        "condition": "{{replies[0].tool_calls | length > 0}}",
        "output": "{{replies}}",
        "output_name": "there_are_tool_calls",
        "output_type": List[ChatMessage],  # Use direct type
    },
    {
        "condition": "{{replies[0].tool_calls | length == 0}}",
        "output": "{{replies}}",
        "output_name": "final_replies",
        "output_type": List[ChatMessage],  # Use direct type
    },
]

# Initialize the ConditionalRouter
router = ConditionalRouter(routes, unsafe=True)

# Create the pipeline
pipeline = Pipeline()
pipeline.add_component("generator", chat_generator)
pipeline.add_component("router", router)
pipeline.add_component("tool_invoker", tool_invoker)

# Connect components
pipeline.connect("generator.replies", "router")
pipeline.connect("router.there_are_tool_calls", "tool_invoker.messages")  # Correct connection

# Example user message
user_message = ChatMessage.from_user("What is the weather in Berlin?")

# Run the pipeline
result = pipeline.run({"messages": [user_message]})

# Print the result
print(result)