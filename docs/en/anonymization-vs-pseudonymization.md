---
icon: lucide/spell-check
description: Anonymization, pseudonymization, redaction and masking compared. Which are reversible, what the GDPR says, and why piighost pseudonymizes PII for LLMs.
seo_title: Anonymization vs pseudonymization, redaction and masking
---

# Anonymization, pseudonymization, redaction, masking: the differences

Anonymization removes personal data for good, while pseudonymization replaces it with a placeholder that a separate mapping can reverse. Redaction deletes a value from a text, and masking hides part of it. Only pseudonymization keeps a way back, and it is what `piighost` does by default.

The examples below start from the same sentence, "`Patrick`{ .pii } lives in Paris."

## Four terms

Anonymization
:   Personal data turned into information that no longer relates to an identifiable person, by anyone, with any means reasonably likely to be used. It is irreversible. Replacing `Patrick`{ .pii } is not enough on its own if the rest of the text still points to him, as in "the mayor who resigned in March".

Pseudonymization
:   The value is replaced, and the information that links it back is kept separately. `Patrick`{ .pii } becomes `<<PERSON:1>>`{ .placeholder }, and a mapping kept apart turns `<<PERSON:1>>`{ .placeholder } back into `Patrick`{ .pii }. It is reversible for whoever holds the mapping.

Redaction
:   The value is deleted or replaced by a fixed marker, as with a black bar on paper. `Patrick`{ .pii } becomes `<<REDACT>>`{ .placeholder }, and every other name becomes the same marker. Nothing records what was there, so it cannot be restored.

Masking
:   Part of the value is hidden and the rest stays visible. `Patrick`{ .pii } becomes `P******`{ .placeholder }. A fragment leaks, and two values with the same first letter and length look the same, so it cannot be restored either.

Tokenization
:   The value is replaced by a token, and a vault keeps the link between the two. It is a form of pseudonymization under another name. A `piighost` placeholder is a token in this sense.

## Summary

| Term | `Patrick`{ .pii } becomes | Reversible | Under the GDPR |
|---|---|---|---|
| Anonymization | nothing that leads back to him | no | outside the regulation (recital 26) |
| Pseudonymization | `<<PERSON:1>>`{ .placeholder }, mapping kept apart | yes, with the mapping | still personal data (article 4(5), recital 26) |
| Redaction | `<<REDACT>>`{ .placeholder } | no | not defined, personal data while the person stays identifiable |
| Masking | `P******`{ .placeholder } | no | not defined, personal data while the person stays identifiable |
| Tokenization | a token, link kept in a vault | yes, with the vault | a form of pseudonymization |

Redaction and masking reach anonymization only when nothing left in the data, the context included, identifies the person.

## What the GDPR says

The GDPR defines pseudonymization and leaves anonymous information out of its scope.

- [Article 4(5)](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng#art_4) defines pseudonymization as processing personal data "in such a manner that the personal data can no longer be attributed to a specific data subject without the use of additional information, provided that such additional information is kept separately" and protected by technical and organisational measures.
- [Recital 26](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng#rct_26) states that pseudonymized data which could be attributed to a person with additional information "should be considered to be information on an identifiable natural person". The same recital says the principles of data protection "should therefore not apply to anonymous information".

The EDPB guidelines, the case law and what they mean for a deployment are on the [Compliance](compliance.md) page.

## What piighost does

By default, `piighost` pseudonymizes. Each value becomes a placeholder such as `<<PERSON:1>>`{ .placeholder }, and the conversation memory keeps the mapping that restores `Patrick`{ .pii } in the reply. For you, the controller holding that mapping, the de-identified text stays personal data.

A redacting or masking placeholder factory used without a memory keeps no mapping, so the text moves toward anonymization. Whether it is truly anonymous still depends on what the rest of the text reveals. See [Placeholder factories](placeholder-factories.md) for which factories are reversible.

In a privacy notice or a DPIA, call the default processing pseudonymization, its legal name.

## See also

- [Compliance](compliance.md): the GDPR and HIPAA in detail, with the EDPB guidelines and the case law.
- [Glossary](glossary.md): the other terms of these pages.
- [How piighost compares](comparison.md): which tools restore values and which only mask them.
