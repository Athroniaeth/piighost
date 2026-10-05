text = "Patrick habite à Paris."
detections = []

# isort: split
# --8<-- [start:example]
from piighost.observation import get_tracer

tracer = get_tracer()
with tracer.span("piighost.detect") as span:
    span.set_input(text)
    span.set_output(detections)
    span.set_attribute("count", len(detections))
# --8<-- [end:example]
