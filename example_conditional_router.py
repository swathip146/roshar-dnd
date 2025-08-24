from haystack import Pipeline
from haystack.components.routers import ConditionalRouter
from haystack.components.builders.chat_prompt_builder import ChatPromptBuilder
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.dataclasses import ChatMessage

# Two routes, each returning two outputs: the text and its length
routes = [
    {
        "condition": "{{ query|length > 10 }}",
        "output": ["{{ query }}", "{{ query|length }}"],
        "output_name": ["ok_query", "length"],
        "output_type": [str, int],
    },
    {
        "condition": "{{ query|length <= 10 }}",
        "output": ["query too short: {{ query }}", "{{ query|length }}"],
        "output_name": ["too_short_query", "length"],
        "output_type": [str, int],
    },
]

router = ConditionalRouter(routes=routes)

pipe = Pipeline()
pipe.add_component("router", router)
pipe.add_component(
    "prompt_builder",
    ChatPromptBuilder(
        template=[ChatMessage.from_user("Answer the following query: {{ query }}")],
        required_variables={"query"},
    ),
)
pipe.add_component("generator", OpenAIChatGenerator())

pipe.connect("router.ok_query", "prompt_builder.query")
pipe.connect("prompt_builder.prompt", "generator.messages")


# Short query: length ≤ 10 ⇒ fallback route fires.
print(pipe.run(data={"router": {"query": "Berlin"}}))
# {'router': {'too_short_query': 'query too short: Berlin', 'length': 6}}

# Long query: length > 10 ⇒ first route fires.
print(pipe.run(data={"router": {"query": "What is the capital of Italy?"}}))
# {'generator': {'replies': ['The capital of Italy is Rome.'], …}}