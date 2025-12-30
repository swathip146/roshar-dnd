import json
from typing import List

from haystack import Pipeline
from haystack.components.converters import OutputAdapter
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.components.joiners import BranchJoiner
from haystack.components.validators import JsonSchemaValidator
from haystack.dataclasses import ChatMessage

person_schema = {
    "type": "object",
    "properties": {
        "first_name": {"type": "string", "pattern": "^[A-Z][a-z]+$"},
        "last_name": {"type": "string", "pattern": "^[A-Z][a-z]+$"},
        "nationality": {"type": "string", "enum": ["Italian", "Portuguese", "American"]},
    },
    "required": ["first_name", "last_name", "nationality"]
}

# Initialize a pipeline
pipe = Pipeline()

# Add components to the pipeline
pipe.add_component('joiner', BranchJoiner(List[ChatMessage]))
pipe.add_component('fc_llm', OpenAIChatGenerator(model="gpt-4o-mini"))
pipe.add_component('validator', JsonSchemaValidator(json_schema=person_schema))
pipe.add_component('adapter', OutputAdapter("{{chat_message}}", List[ChatMessage], unsafe=True))

# Connect components
pipe.connect("adapter", "joiner")
pipe.connect("joiner", "fc_llm")
pipe.connect("fc_llm.replies", "validator.messages")
pipe.connect("validator.validation_error", "joiner")

result = pipe.run(data={
    "fc_llm": {"generation_kwargs": {"response_format": {"type": "json_object"}}},
    "adapter": {"chat_message": [ChatMessage.from_user("Create json object from Peter Parker")]}
})

print(json.loads(result["validator"]["validated"][0].text))

# Output:
# {'first_name': 'Peter', 'last_name': 'Parker', 'nationality': 'American', 'name': 'Spider-Man', 'occupation':
# 'Superhero', 'age': 23, 'location': 'New York City'}
