from langfuse import Langfuse


def export_piighost_spans(span) -> bool:
    scope = span.instrumentation_scope
    if scope is None:
        return False
    return (
        scope.name == "langfuse-sdk"
        or scope.name == "piighost"
        or scope.name.startswith("piighost.")
    )


client = Langfuse(should_export_span=export_piighost_spans)
