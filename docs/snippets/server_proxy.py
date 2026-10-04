# Not shown: the server the page assumes at 127.0.0.1:8000, which the test starts
# on a free port.
from _offline import serve_locally

serve_locally()

# isort: split
# --8<-- [start:client]
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8000/openai/v1",
    api_key="sk-...",
)
response = client.chat.completions.create(
    model="gpt-5.6-terra",
    messages=[
        {
            "role": "user",
            "content": "Write a short greeting to Jane Doe, jane.doe@example.com.",
        }
    ],
)
print(response.choices[0].message.content)
# --8<-- [end:client]


# isort: split
# --8<-- [start:thread]
response = client.chat.completions.create(
    model="gpt-5.6-terra",
    messages=[{"role": "user", "content": "I am Jane Doe"}],
    extra_headers={"X-PIIGhost-Thread-Id": "user-42"},
)
# --8<-- [end:thread]


# isort: split
# --8<-- [start:stream]
stream = client.chat.completions.create(
    model="gpt-5.6-terra",
    messages=[{"role": "user", "content": "I am Jane Doe"}],
    stream=True,
)
for chunk in stream:
    if chunk.choices:
        print(chunk.choices[0].delta.content or "", end="")
# --8<-- [end:stream]
