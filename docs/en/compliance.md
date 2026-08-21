---
icon: lucide/scale
---

# Compliance

This page maps piighost's detectors and modes onto two regulatory frameworks, HIPAA Safe Harbor and the GDPR, so you can see what piighost covers and where the boundary falls.

!!! warning "This is guidance, not a certification"
    This page shows how piighost's parts line up with two frameworks. It is not a compliance certification. Meeting HIPAA or the GDPR also depends on how you store the restoration mapping, who can reach it, your legal basis, and the residual risk in the text piighost did not touch. piighost is one tool in that chain, not a guarantee.

## HIPAA Safe Harbor

HIPAA is the United States health-data law. Its Safe Harbor method says that once you remove 18 categories of identifiers from a record, and hold no actual knowledge that the remainder could re-identify someone, the record is no longer protected health information and leaves the scope of the rule. Safe Harbor is destructive for data that depends on exact dates or places, so it is a de-identification target, not a lossless transform.

The table below maps each of the 18 identifiers onto the detectors piighost ships. "Custom" means piighost has no prebuilt pattern for it, but a `RegexDetector` pattern for your local format, or the `LLMDetector`, covers it.

<div class="wide-table" markdown="1">

| Safe Harbor identifier | Coverage | How |
|------------------------|----------|-----|
| 1. Names | Yes | `Gliner2PiiDetector` (`PERSON`), `SpacyDetector`, `TransformersDetector` |
| 2. Geographic units below a state (street, city, ZIP) | Partial | `US_ZIP` regex, `Gliner2PiiDetector` (`LOCATION`, `ADDRESS`); city and county depend on the NER model |
| 3. Dates finer than a year, and ages over 89 | Partial | `Gliner2PiiDetector` (`DATE_OF_BIRTH`); a generic date needs a custom regex, ages over 89 are not special-cased |
| 4. Telephone numbers | Yes | `US_PHONE`, `FR_PHONE` regex, `Gliner2PiiDetector` (`PHONE`) |
| 5. Fax numbers | Partial | matched by the phone patterns on shape, not distinguished as fax |
| 6. Email addresses | Yes | `EMAIL` regex, `Gliner2PiiDetector` (`EMAIL`) |
| 7. Social security numbers | Yes | `US_SSN`, `FR_NIR` regex, `Gliner2PiiDetector` (`SSN`) |
| 8. Medical record numbers | Custom | supply a `RegexDetector` pattern for the local format |
| 9. Health plan beneficiary numbers | Custom | supply a `RegexDetector` pattern |
| 10. Account numbers | Partial | `IBAN` regex and `Gliner2PiiDetector` (`IBAN`); other account numbers need a custom pattern |
| 11. Certificate and license numbers | Partial | `Gliner2PiiDetector` (`DRIVER_LICENSE`, `PASSPORT`); other certificates need a custom pattern |
| 12. Vehicle identifiers and plates | Custom | supply a `RegexDetector` pattern |
| 13. Device identifiers and serials | Custom | supply a `RegexDetector` pattern |
| 14. URLs | Yes | `URL` regex |
| 15. IP addresses | Yes | `IPV4` regex, `Gliner2PiiDetector` (`IP_ADDRESS`); IPv6 needs a custom pattern |
| 16. Biometric identifiers | No | outside text, not in scope |
| 17. Full-face photographs and comparable images | No | multimodal, a [non-goal](roadmap.md#non-goals) |
| 18. Any other unique identifying number or code | Custom | a `RegexDetector` pattern or the `LLMDetector`; `TAX_ID`, `CRYPTO`, `API_KEY` are also covered by `Gliner2PiiDetector` |

</div>

The prebuilt regex catalogs match on shape alone, with no checksum validation, so they never drop an OCR-mangled value but they also accept a well-shaped non-value. See [Limitations](limitations.md).

## GDPR

The GDPR draws a line between two treatments, and they are often confused.

- **Pseudonymization** replaces a value but keeps a way back, so it is reversible. Pseudonymized data stays personal data under the GDPR, and its obligations still apply.
- **Anonymization** is permanent and irreversible. Truly anonymous data falls outside the GDPR.

Where piighost sits depends on the mode you choose.

- The default reversible tokens, restored from the conversation memory, `<<PERSON:1>>`{ .placeholder } deanonymized back to `Patrick`{ .pii }, are **pseudonymization**. The mapping exists, so the data stays personal data. Protecting that mapping, the memory backend and its at-rest crypto, is what keeps the pseudonymization meaningful. See [Security](security.md).
- A `RedactPlaceholderFactory` or a mask used with no memory drops the mapping, so it moves toward **anonymization**. Whether the result is truly anonymous still depends on the residual re-identification risk in the surrounding text.

## See also

- [Security](security.md): the threat model, the memory backends, and the at-rest crypto that protects the restoration mapping.
- [Limitations](limitations.md): the shape-only regex and what it does not validate.
- [Placeholder factories](placeholder-factories.md): which modes are reversible and which are not.
- [Roadmap](roadmap.md): what is pending and what is deliberately out of scope.
