from piighost.components.anonymizer import Anonymizer

# --8<-- [start:factories]
from piighost.components.placeholder import (
    LabelHashPlaceholderFactory,
    LabelPlaceholderFactory,
)

# Opaque token, a sha256 of label:ordinal and never of the value: <<PERSON:a1b2c3d4>>
hash_factory = LabelHashPlaceholderFactory()
Anonymizer(hash_factory)

# Label only, no counter: <<PERSON>>
label_factory = LabelPlaceholderFactory()
Anonymizer(label_factory)
# --8<-- [end:factories]
