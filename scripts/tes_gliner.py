from gliner2 import GLiNER2

# Load model once, use everywhere
extractor = GLiNER2.from_pretrained("fastino/gliner2-base-v1")
print("Finish load")
# Extract entities in one line
text = "Apple CEO Tim Cook announced iPhone 15 in Cupertino yesterday."
result = extractor.extract_entities(text, ["company", "person", "product", "location"])

print(result)


# Basic entity extraction
entities = extractor.extract_entities(
    "Patient received 400mg ibuprofen for severe headache at 2 PM.",
    ["medication", "dosage", "symptom", "time"]
)
print(entities)
# Output: {'entities': {'medication': ['ibuprofen'], 'dosage': ['400mg'], 'symptom': ['severe headache'], 'time': ['2 PM']}}

# Enhanced with descriptions for medical accuracy
entities = extractor.extract_entities(
    "Patient received 400mg ibuprofen for severe headache at 2 PM.",
    {
        "medication": "Names of drugs, medications, or pharmaceutical substances",
        "dosage": "Specific amounts like '400mg', '2 tablets', or '5ml'",
        "symptom": "Medical symptoms, conditions, or patient complaints",
        "time": "Time references like '2 PM', 'morning', or 'after lunch'"
    }
)
print(entities)
# Same output but with higher accuracy due to context descriptions

# With confidence scores
entities = extractor.extract_entities(
    "Apple Inc. CEO Tim Cook announced iPhone 15 in Cupertino.",
    ["company", "person", "product", "location"],
    include_confidence=True
)
print(entities)
# Output: {
#     'entities': {
#         'company': [{'text': 'Apple Inc.', 'confidence': 0.95}],
#         'person': [{'text': 'Tim Cook', 'confidence': 0.92}],
#         'product': [{'text': 'iPhone 15', 'confidence': 0.88}],
#         'location': [{'text': 'Cupertino', 'confidence': 0.90}]
#     }
# }

# With character positions (spans)
entities = extractor.extract_entities(
    "Apple Inc. CEO Tim Cook announced iPhone 15 in Cupertino.",
    ["company", "person", "product"],
    include_spans=True
)
print(entities)
# Output: {
#     'entities': {
#         'company': [{'text': 'Apple Inc.', 'start': 0, 'end': 9}],
#         'person': [{'text': 'Tim Cook', 'start': 15, 'end': 23}],
#         'product': [{'text': 'iPhone 15', 'start': 35, 'end': 44}]
#     }
# }

# With both confidence and spans
entities = extractor.extract_entities(
    "Apple Inc. CEO Tim Cook announced iPhone 15 in Cupertino.",
    ["company", "person", "product"],
    include_confidence=True,
    include_spans=True
)
print(entities)
# Output: {
#     'entities': {
#         'company': [{'text': 'Apple Inc.', 'confidence': 0.95, 'start': 0, 'end': 9}],
#         'person': [{'text': 'Tim Cook', 'confidence': 0.92, 'start': 15, 'end': 23}],
#         'product': [{'text': 'iPhone 15', 'confidence': 0.88, 'start': 35, 'end': 44}]
#     }
# }