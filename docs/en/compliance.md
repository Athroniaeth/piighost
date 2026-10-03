---
icon: lucide/scale
---

# Compliance

The detectors and modes `piighost` ships line up against two regulatory frameworks, HIPAA Safe Harbor and the GDPR. The mapping below shows what is covered and where the boundary falls.

!!! warning "This is guidance, not a certification or legal advice"
    This is not a compliance certification. Meeting HIPAA or the GDPR also depends on how you store the restoration mapping, who can reach it, your legal basis, and the residual risk in the text `piighost` did not touch. `piighost` is one tool in that chain, not a guarantee. Nor is this page legal advice. The summaries of the texts and of the case law below are a reading aid, to check against the official sources and with your counsel.

## HIPAA Safe Harbor

HIPAA is the United States health-data law. Its Safe Harbor method sets two conditions: you remove 18 categories of identifiers from a record, and you hold no actual knowledge that the remainder could re-identify someone. The record is then no longer protected health information and leaves the scope of the rule. Safe Harbor is a de-identification target, not a lossless transform, because it destroys data that depends on exact dates or places.

The table below maps each of the 18 identifiers onto the detectors `piighost` ships and the regex catalogs of the hub. "Custom" means no hub catalog carries a pattern for that identifier. You cover it with a `RegexDetector` pattern for your local format, or with the `LLMDetector`.

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

The regex catalogs of the hub match a value on its shape alone, with no checksum validation. So they never drop an OCR-mangled value, but they also accept a string that has the right shape without being a real value. See [Limitations](limitations.md).

## GDPR

The GDPR draws a line between two treatments, and they are often confused.

- **Pseudonymization** replaces a value but keeps a way back, so it is reversible. For whoever holds that way back, pseudonymized data stays personal data under the GDPR, and its obligations still apply.
- **Anonymization** is permanent and irreversible. Truly anonymous data falls outside the GDPR.

Where `piighost` sits depends on the mode you choose.

- By default, tokens are reversible. The conversation memory restores them, for example `<<PERSON:1>>`{ .placeholder } back to `Patrick`{ .pii }. This mode is **pseudonymization**. The mapping exists, so the data stays personal data. The pseudonymization only means something if that mapping is protected, by the memory backend and its at-rest crypto. See [Security](security.md).
- A `RedactPlaceholderFactory` or a mask used with no memory drops the mapping, so it moves toward **anonymization**. Whether the result is truly anonymous still depends on the residual re-identification risk in the surrounding text.

!!! note "The word this documentation uses"
    These pages say de-identification for what the pipeline does, a technical term covering both modes above. It is not a legal category. In the reversible default the legal name is pseudonymization, and it is the word to use toward data subjects, in a privacy notice or a DPIA. The European Data Protection Board (EDPB) asks controllers not to describe data as "de-identified" while individuals stay identifiable (Guidelines 02/2026, paragraph 40, see [below](#what-the-edpb-says-since-the-judgment)).

### What the regulation says

The GDPR frames that distinction in the following provisions.

- **Article 4(5)** defines pseudonymization as processing personal data so that they "can no longer be attributed to a specific data subject without the use of additional information", provided that this information "is kept separately" and is subject to technical and organizational measures. In a `piighost` deployment, the additional information is the mapping from `<<PERSON:1>>`{ .placeholder } to `Patrick`{ .pii }.
- **Recital 26** states that pseudonymized data which could be attributed to a natural person by the use of additional information "should be considered to be information on an identifiable natural person". Identifiability weighs all the means reasonably likely to be used, by the controller or by another person, given the cost, the time and the technology available. Anonymous information falls outside the regulation.
- **Recitals 28 and 29** present pseudonymization as a way to reduce the risks to data subjects, one that does not preclude any other measure. It can be applied within a single controller, provided the additional information is kept separately and the controller indicates the authorized persons.
- **Article 25(1)**, data protection by design and by default, names pseudonymization as an example of the appropriate technical and organizational measures. Recital 78 counts "pseudonymising personal data as soon as possible" among such measures.
- **Article 32(1)(a)**, security of processing, lists "the pseudonymisation and encryption of personal data" among the measures that ensure a level of security appropriate to the risk.
- **Article 35** requires a data protection impact assessment (DPIA) before a processing that is likely to result in a high risk, "in particular using new technologies". Paragraph 3 names three cases where it is required in particular, paragraph 4 has each supervisory authority publish a list of the processing operations that require one, and paragraph 7 sets its minimum content. [How to document `piighost` in a DPIA](dpia.md) supplies the material for that content.

### What the EDPB says on pseudonymization

The European Data Protection Board (EDPB) adopted its Guidelines 01/2025 on pseudonymisation on 16 January 2025, as a version for public consultation. Five points bear directly on `piighost`.

- Pseudonymized data that could be attributed to a person with additional information is personal data, and this "also holds true if pseudonymised data and additional information are not in the hands of the same person" (paragraph 22).
- The additional information includes "tables matching pseudonyms with the identifying attributes they replace" and cryptographic keys (paragraph 20). The conversation memory and the cipher key are that additional information.
- Reversal should be performed by persons specifically authorized for it, as per Recital 29 (paragraph 32).
- The guidelines call the context in which attribution is to be precluded the "pseudonymisation domain" (paragraph 35). The additional information should not enter that domain (paragraph 40). With `piighost`, the LLM provider sits in that domain and the mapping stays out of it.
- Before pseudonymized data is transmitted to a third party, "the means available to the recipient for attribution of the data need to be identified and taken into account" (paragraph 70). For `piighost`, the third party is the LLM provider.

### What the Court of Justice held in EDPS v SRB

The Single Resolution Board (SRB) had collected comments from the shareholders and creditors of a failed bank. It sent some of them to Deloitte, the firm it had tasked with a valuation. These comments were pseudonymized under an alphanumeric code that only the SRB could link to an author. Some authors complained to the European Data Protection Supervisor (EDPS), who found that the SRB had failed to tell them that Deloitte would receive their data. The General Court annulled that decision (T-557/20, 26 April 2023). On the appeal of the EDPS, the Court of Justice set aside that judgment on 4 September 2025 (C-413/23 P, ECLI:EU:C:2025:645).

The judgment interprets Regulation 2018/1725, which governs the EU institutions and bodies, not the GDPR. The Court notes that this regulation's definition of personal data is essentially identical to that of the GDPR and must be interpreted in the same way (paragraph 52). The definition of pseudonymization it applies is worded exactly as Article 4(5).

The Court held the following.

- Pseudonymization is not part of the definition of personal data. It refers to measures that reduce the risk of a data set being correlated with the identity of the data subjects (paragraph 72).
- For the controller that holds the additional information, the data stay personal in spite of the pseudonymization (paragraph 76).
- For a recipient, the data may not be personal, under two conditions. The recipient must not be in a position to lift the pseudonymization measures, and those measures must prevent it from attributing the data to the data subject, including by other means such as cross-checking with other factors (paragraph 77).
- Pseudonymized data "must not be regarded as constituting, in all cases and for every person, personal data" (paragraph 86).
- Where it cannot be ruled out that a third party receiving the data has means reasonably allowing it to attribute them, such as cross-checking with other data at its disposal, the data are personal for that transfer and for that party's processing (paragraph 85).
- The relevant perspective for assessing identifiability depends on the circumstances of each case (paragraph 100). For the duty to inform data subjects of the recipients of their data, it is assessed at the time of collection and from the controller's point of view (paragraph 111). The SRB's duty applied before the transfer, whether or not the data were personal from Deloitte's point of view (paragraph 112).
- Personal opinions or views, as the expression of a person's thinking, are necessarily closely linked to that person (paragraph 58).

The Court did not hold the following.

- It did not decide that the comments were anonymous for Deloitte, and it did not examine whether Deloitte could in fact identify their authors (paragraph 116).
- It did not take pseudonymized data out of the regulation for the controller that pseudonymized them.
- It did not relieve that controller of its duty to inform the data subjects of the recipients.

The Court gave final judgment itself on the plea that the comments were not personal data, and rejected it (paragraph 120). It referred the other plea, on the right to good administration, back to the General Court (paragraph 122).

### What the EDPB says since the judgment

The EDPB held a stakeholder event on 12 December 2025, following the judgment, to inform its work on Guidelines 01/2025 on pseudonymisation and on guidelines on anonymisation. Participants disagreed on the perspective that applies to a processor, some arguing for the processor's own, others for the controller's.

The EDPB then adopted its Guidelines 02/2026 on anonymisation on 7 July 2026, as a version for public consultation open until 30 October 2026. They take the judgment into account. Three points bear on `piighost`.

- Anonymity is assessed from the perspective of each relevant entity, and the basic question is for whom the data is intended to be anonymous (paragraphs 11 and 12).
- An entity that processes information on behalf of a controller is assessed from that controller's perspective. Information that is personal data for the controller is personal data for its processor too (paragraph 15).
- Controllers should not describe data as "anonymous", "de-identified" or "de-personalised" if individuals are still identifiable (paragraph 40).

### What this means for a `piighost` deployment

- For you, the controller holding the mapping, the de-identified text stays personal data. Every obligation of the GDPR applies to the whole processing, the mapping included.
- An LLM provider that processes the text on your behalf is your processor. Under Guidelines 02/2026, the text is then assessed from your perspective, so it stays personal data for the provider too.
- An LLM provider that uses the text for its own purposes is assessed from its own perspective. The judgment leaves open that the text is not personal data for it, but only if both conditions of paragraph 77 hold. `piighost` meets the first condition by design, since the mapping never leaves your side. The second condition depends on two things. First, what the text still carries in clear: the context, the quasi-identifiers, a PII the detector missed. Second, what the provider can cross-check the text with. See [Security](security.md) and [Limitations](limitations.md).
- You must tell data subjects that their messages reach an LLM provider. This duty is assessed from your point of view, at the time of collection. So it holds whatever the provider's position. In that notice, call the processing pseudonymization, not anonymization or de-identification, as paragraph 40 of Guidelines 02/2026 asks.
- A DPIA that treats the de-identified text as personal data for the provider stays valid whichever way these questions are settled.

### Sources

- [GDPR, Regulation (EU) 2016/679](https://eur-lex.europa.eu/eli/reg/2016/679/oj)
- [Regulation (EU) 2018/1725, on the EU institutions and bodies](https://eur-lex.europa.eu/eli/reg/2018/1725/oj)
- [EDPB, Guidelines 01/2025 on pseudonymisation, version for public consultation](https://www.edpb.europa.eu/public-consultations/guidelines-012025-on-pseudonymisation_en)
- [EDPB, report on the stakeholder event on anonymisation and pseudonymisation of 12 December 2025](https://www.edpb.europa.eu/system/files/2026-02/edpb-report-stakeholder-event-anonymisation-pseudonymisation_en.pdf)
- [EDPB, Guidelines 02/2026 on anonymisation, version for public consultation](https://www.edpb.europa.eu/public-consultations/guidelines-on-anonymisation_en)
- [Court of Justice, judgment of 4 September 2025, EDPS v SRB, C-413/23 P](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:62023CJ0413)
- [Court of Justice, press release No 107/25](https://curia.europa.eu/site/upload/docs/application/pdf/2025-09/cp250107en.pdf)

## See also

- [Security](security.md): the threat model, the memory backends, and the at-rest crypto that protects the restoration mapping.
- [How to document `piighost` in a DPIA](dpia.md): the processing, the data flows, the measures and the residual risks, with a template to fill in.
- [Limitations](limitations.md): the shape-only regex and what it does not validate.
- [Placeholder factories](placeholder-factories.md): which modes are reversible and which are not.
- [Roadmap](roadmap.md): what is pending and what is deliberately out of scope.
