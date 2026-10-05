from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import ThreadAnonymizationPipeline

pipeline = ThreadAnonymizationPipeline(ExactMatchDetector({"Patrick": "PERSON"}))

# isort: split
# --8<-- [start:example]
from piighost.integrations.langchain import (
    EntityCreateByAssistantStrategy,
    InventedPlaceholderStrategy,
    PIIAnonymizationMiddleware,
    ToolCallStrategy,
)

middleware = PIIAnonymizationMiddleware(
    pipeline,  # jetons PreservesRecognizableIdentity, sinon UnrecognizableFactoryError
    tool_strategy=ToolCallStrategy.FULL,
    invented_strategy=InventedPlaceholderStrategy.DROP,
    assistant_strategy=EntityCreateByAssistantStrategy.PRESERVE,
)
# --8<-- [end:example]
