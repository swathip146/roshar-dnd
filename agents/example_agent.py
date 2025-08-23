from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.dataclasses import ChatMessage
from haystack.tools.tool import Tool
from haystack.components.agents import Agent
from typing import List

# Tool Function
def calculate(expression: str) -> dict:
    try:
        result = eval(expression, {"__builtins__": {}})
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}

# Tool Definition
calculator_tool = Tool(
    name="calculator",
    description="Evaluate basic math expressions.",
    parameters={
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "Math expression to evaluate"}
        },
        "required": ["expression"]
    },
    function=calculate,
    outputs_to_state={"calc_result": {"source": "result"}}
)

# Agent Setup
agent = Agent(
    chat_generator=OpenAIChatGenerator(),
    tools=[calculator_tool],
    exit_conditions=["calculator"],
    state_schema={
        "calc_result": {"type": int},
    }
)

# Run the Agent
agent.warm_up()
response = agent.run(messages=[ChatMessage.from_user("What is 7 * (4 + 2)?")])

# Output
print(response["messages"])
print("Calc Result:", response.get("calc_result"))