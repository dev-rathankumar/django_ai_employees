from anthropic import Anthropic
from decouple import config

client = Anthropic(
    api_key=config("ANTHROPIC_API_KEY"),  # This is the default and can be omitted
)

message = client.messages.create(
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": "Give me 5 names of animals",
        }
    ],
    model=config("ANTHROPIC_MODEL"),
)
print(message.content)