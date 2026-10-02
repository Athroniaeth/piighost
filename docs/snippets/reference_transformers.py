from piighost.components.detector.ner import TransformersDetector

detector = TransformersDetector(
    pipeline="dslim/bert-base-NER",
    labels={"PERSON": "PER", "LOCATION": "LOC"},
)
