# Not shown: the model the page names, replaced by a scripted one.
from _offline import offline_langchain

offline_langchain("Noted.", secrets=("Patrick Martin", "patrick@example.com"))

# isort: split
# --8<-- [start:before]
from langchain.chat_models import init_chat_model
from langchain_experimental.data_anonymizer import PresidioReversibleAnonymizer

anonymizer = PresidioReversibleAnonymizer(analyzed_fields=["PERSON", "EMAIL_ADDRESS"])
model = init_chat_model("openai:gpt-5.6-terra")

safe_text = anonymizer.anonymize("Patrick Martin wrote from patrick@example.com.")
reply = model.invoke(safe_text)
print(anonymizer.deanonymize(reply.content))

anonymizer.save_deanonymizer_mapping("mapping.json")
# --8<-- [end:before]
