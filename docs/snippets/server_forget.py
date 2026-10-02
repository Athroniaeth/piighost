# Not shown: the server the page assumes at localhost:8000, which the test starts
# on a free port.
from _offline import serve_locally

serve_locally()

# Not shown: the message of the previous step, in the thread forgotten here.
from piighost.integrations.client import PIIGhostClient

async with PIIGhostClient("http://localhost:8000") as client:
    await client.anonymize("Patrick habite à Paris.", "thread-42")

# isort: split
# --8<-- [start:example]
async with PIIGhostClient("http://localhost:8000") as client:
    forgotten = await client.forget_thread("thread-42")
    print(forgotten)
    # Forgotten(messages=1, detections=2)
# --8<-- [end:example]
# Not shown: what the comments above say.
from piighost.conversation_memory import Forgotten

assert forgotten == Forgotten(messages=1, detections=2)
