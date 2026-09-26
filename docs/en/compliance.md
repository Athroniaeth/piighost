---
icon: lucide/scale
---

# Compliance

The detectors and modes `piighost` ships line up against two regulatory frameworks, HIPAA Safe Harbor and the GDPR. The mapping below shows what is covered and where the boundary falls.

!!! warning "This is guidance, not a certification or legal advice"
    This is not a compliance certification. Meeting HIPAA or the GDPR also depends on how you store the restoration mapping, who can reach it, your legal basis, and the residual risk in the text `piighost` did not touch. `piighost` is one tool in that chain, not a guarantee. Nor is this page legal advice. The summaries of the texts and of the case law below are a reading aid, to check against the official sources and with your counsel.

## HIPAA Safe Harbor

HIPAA is the United States health-data law. Its Safe Harbor method says that once you remove 18 categories of identifiers from a record, and hold no actual knowledge that the remainder could re-identify someone, the record is no longer protected health information and leaves the scope of the rule. Safe Harbor is destructive for data that depends on exact dates or places, so it is a de-identification target, not a lossless transform.

The table below maps each of the 18 identifiers onto the detectors `piighost` ships. "Custom" means `piighost` has no prebuilt pattern for it, but a `RegexDetector` pattern for your local format, or the `LLMDetector`, covers it.

<div class="wide-table" markdown="1">

| Safe Harbor identifier | Coverage | How |
|------------------------|----------|-----|
| 1. Names | Yes | `Gliner2PiiDetector` (`PERSON`), `SpacyDetector`, `TransformersDetector` |
| 2. Geographic units below a state (street, city, ZIP) | Partial | `US_ZIP` regex, `Gliner2PiiDetector` (`LOCATION`, `ADDRESS`). City and county depend on the NER model |
| 3. Dates finer than a year, and ages over 89 | Partial | `Gliner2PiiDetector` (`DATE_OF_BIRTH`). A generic date needs a custom regex, ages over 89 are not special-cased |
| 4. Telephone numbers | Yes | `US_PHONE`, `FR_PHONE` regex, `Gliner2PiiDetector` (`PHONE`) |
| 5. Fax numbers | Partial | matched by the phone patterns on shape, not distinguished as fax |
| 6. Email addresses | Yes | `EMAIL` regex, `Gliner2PiiDetector` (`EMAIL`) |
| 7. Social security numbers | Yes | `US_SSN`, `FR_NIR` regex, `Gliner2PiiDetector` (`SSN`) |
| 8. Medical record numbers | Custom | supply a `RegexDetector` pattern for the local format |
| 9. Health plan beneficiary numbers | Custom | supply a `RegexDetector` pattern |
| 10. Account numbers | Partial | `IBAN` regex and `Gliner2PiiDetector` (`IBAN`). Other account numbers need a custom pattern |
| 11. Certificate and license numbers | Partial | `Gliner2PiiDetector` (`DRIVER_LICENSE`, `PASSPORT`). Other certificates need a custom pattern |
| 12. Vehicle identifiers and plates | Custom | supply a `RegexDetector` pattern |
| 13. Device identifiers and serials | Custom | supply a `RegexDetector` pattern |
| 14. URLs | Yes | `URL` regex |
| 15. IP addresses | Yes | `IPV4` regex, `Gliner2PiiDetector` (`IP_ADDRESS`). IPv6 needs a custom pattern |
| 16. Biometric identifiers | No | outside text, not in scope |
| 17. Full-face photographs and comparable images | No | multimodal, a [non-goal](roadmap.md#non-goals) |
| 18. Any other unique identifying number or code | Custom | a `RegexDetector` pattern or the `LLMDetector`. `TAX_ID`, `CRYPTO`, `API_KEY` are also covered by `Gliner2PiiDetector` |

</div>

The prebuilt regex catalogs match on shape alone, with no checksum validation, so they never drop an OCR-mangled value but they also accept a well-shaped non-value. See [Limitations](limitations.md).

## GDPR

The GDPR draws a line between two treatments, and they are often confused.

- **Pseudonymization** replaces a value but keeps a way back, so it is reversible. For whoever holds that way back, pseudonymized data stays personal data under the GDPR, and its obligations still apply.
- **Anonymization** is permanent and irreversible. Truly anonymous data falls outside the GDPR.

Where `piighost` sits depends on the mode you choose.

- The default reversible tokens, restored from the conversation memory, `<<PERSON:1>>`{ .placeholder } restored back to `Patrick`{ .pii }, are **pseudonymization**. The mapping exists, so the data stays personal data. Protecting that mapping, the memory backend and its at-rest crypto, is what keeps the pseudonymization meaningful. See [Security](security.md).
- A `RedactPlaceholderFactory` or a mask used with no memory drops the mapping, so it moves toward **anonymization**. Whether the result is truly anonymous still depends on the residual re-identification risk in the surrounding text.

### What the regulation says

The GDPR frames that distinction in the following provisions.

- **Article 4(5)** defines pseudonymization as processing personal data so that they "can no longer be attributed to a specific data subject without the use of additional information", provided that this information "is kept separately" and protected by technical and organisational measures. In a `piighost` deployment, the additional information is the mapping from `<<PERSON:1>>`{ .placeholder } to `Patrick`{ .pii }.
- **Recital 26** states that pseudonymized data which could be attributed to a person by the use of additional information is information on an identifiable person. Identifiability weighs all the means reasonably likely to be used, by the controller or by another person, given the cost, the time and the technology available. Anonymous information falls outside the regulation.
- **Recitals 28 and 29** present pseudonymization as a way to reduce the risks to data subjects, without excluding any other measure. It can be applied within a single controller, provided the additional information is kept separately and the controller indicates who is authorised to use it.
- **Article 25(1)**, data protection by design and by default, names pseudonymization as an example of the technical and organisational measures a controller puts in place. Recital 78 counts pseudonymizing personal data as soon as possible among such measures.
- **Article 32(1)(a)**, security of processing, lists the pseudonymization and encryption of personal data among the measures that ensure a level of security appropriate to the risk.
- **Article 35** requires a data protection impact assessment (DPIA) before a processing likely to result in a high risk, in particular one using new technologies. Paragraph 3 lists cases where it is always required, and paragraph 7 sets its minimum content. [How to document `piighost` in a DPIA](dpia.md) supplies the material for that content.

### What the EDPB says

The European Data Protection Board adopted its Guidelines 01/2025 on pseudonymisation on 16 January 2025, in a version for public consultation. Four points bear directly on `piighost`.

- Pseudonymized data that could be attributed to a person with additional information is personal data, and the guidelines add that this "also holds true if pseudonymised data and additional information are not in the hands of the same person" (paragraph 22).
- The additional information includes "tables matching pseudonyms with the identifying attributes they replace" and cryptographic keys (paragraph 20). The conversation memory and the cipher key are exactly that.
- Reversal should be performed by persons specifically authorised for it, following Recital 29 (paragraph 32).
- Before pseudonymized data is transmitted to a third party, "the means available to the recipient for attribution of the data need to be identified and taken into account" (paragraph 70). For `piighost`, the third party is the LLM provider.

These guidelines predate the judgment below. The EDPB held a stakeholder event on 12 December 2025, following that judgment, to inform its ongoing work on them and on forthcoming guidelines on anonymisation.

### What the Court of Justice held in EDPS v SRB

The Single Resolution Board (SRB) had sent comments from shareholders and creditors, in pseudonymized form, to Deloitte, a firm it had engaged. Some authors complained that they had not been told. The European Data Protection Supervisor (EDPS) found that Deloitte was a recipient of personal data and that the SRB had breached its duty to inform. On appeal, the Court of Justice ruled in case C-413/23 P on 4 September 2025 (ECLI:EU:C:2025:645).

The judgment interprets Regulation 2018/1725, which governs the EU institutions and bodies, not the GDPR itself. Its definitions of personal data and of pseudonymization are worded like those of the GDPR, and the EDPB consulted stakeholders on the judgment for its GDPR guidelines.

The Court held the following.

- Pseudonymized data "must not be regarded as constituting, in all cases and for every person, personal data". Pseudonymization may, depending on the circumstances, prevent persons other than the controller from identifying the data subject, so that for them the data subject is not or is no longer identifiable (paragraph 86).
- For the recipient, that outcome presupposes two conditions. The recipient must not be in a position to lift the pseudonymization measures, and those measures must prevent it from attributing the data to the data subject, including by other means such as cross-checking with other factors (paragraph 77).
- The controller that holds the additional information still processes personal data, in spite of the pseudonymization (paragraph 76).
- For the controller's duty to inform data subjects of the recipients of their data, identifiability is assessed at the time of collection and from the controller's point of view. That duty applied before the transfer, whether or not the data were personal from the recipient's point of view.
- Personal opinions and views, as the expression of a person's thinking, are necessarily closely linked to that person. Comments that express them relate to their author without their content, purpose or effects having to be examined.

The Court did not hold the following.

- It did not decide that the comments were anonymous for Deloitte. It set aside the General Court's judgment and referred the case back to it.
- It did not take pseudonymized data out of the regulation for the controller that pseudonymized it.
- It did not relieve that controller of its duty to inform the data subjects of the recipients.

### What this means for a `piighost` deployment

- For you, the controller holding the mapping, the de-identified text stays personal data. Every obligation of the GDPR applies to the whole processing, the mapping included.
- For the LLM provider, which receives `<<PERSON:1>>`{ .placeholder } without the mapping, the judgment leaves open that the text is not personal data, but only if both conditions of paragraph 77 hold. `piighost` addresses the first by design, since the mapping never leaves your side. The second depends on what the text still carries in clear, the context, the quasi-identifiers, a PII the detector missed, and what the provider can cross-check it with. See [Security](security.md) and [Limitations](limitations.md).
- Your duty to tell data subjects that their messages reach an LLM provider is assessed from your point of view at collection, so it holds whatever the provider's position.
- The judgment does not settle whether a processor acting on your behalf is assessed from its own point of view or from yours. Participants at the EDPB stakeholder event raised differing views on exactly that point. A DPIA that treats the de-identified text as personal data for the provider does not depend on the answer.

### Sources

- GDPR, Regulation (EU) 2016/679: [EUR-Lex](https://eur-lex.europa.eu/eli/reg/2016/679/oj)
- EDPB, Guidelines 01/2025 on pseudonymisation, version for public consultation: [edpb.europa.eu](https://www.edpb.europa.eu/system/files/2025-01/edpb_guidelines_202501_pseudonymisation_en.pdf)
- EDPB, report on the stakeholder event on anonymisation and pseudonymisation of 12 December 2025: [edpb.europa.eu](https://www.edpb.europa.eu/system/files/2026-02/edpb-report-stakeholder-event-anonymisation-pseudonymisation_en.pdf)
- Court of Justice, judgment of 4 September 2025, EDPS v SRB, C-413/23 P: [EUR-Lex](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:62023CJ0413)
- Court of Justice, press release No 107/25: [curia.europa.eu](https://curia.europa.eu/site/upload/docs/application/pdf/2025-09/cp250107en.pdf)

## See also

- [Security](security.md): the threat model, the memory backends, and the at-rest crypto that protects the restoration mapping.
- [Limitations](limitations.md): the shape-only regex and what it does not validate.
- [Placeholder factories](placeholder-factories.md): which modes are reversible and which are not.
- [Roadmap](roadmap.md): what is pending and what is deliberately out of scope.
