# Not shown: the server the page assumes at localhost:8000, which the test starts
# on a free port.
from _offline import serve_locally

serve_locally()

# Not shown: the import of step 1, whose main() holds this fragment.
from piighost.integrations.client import PIIGhostClient

# isort: split
# --8<-- [start:example]
async with PIIGhostClient("http://localhost:8000") as client:
    result = await client.anonymize("Patrick lives in Paris.", "thread-42")
    print(result.text)

    restored = await client.deanonymize(result.text, "thread-42")
    print(restored)
# --8<-- [end:example]
