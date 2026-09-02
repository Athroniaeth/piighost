---
icon: lucide/scale
---

# Conformité

Cette page met en regard les détecteurs et les modes de piighost avec deux cadres réglementaires, HIPAA Safe Harbor et le GDPR, pour que vous voyiez ce que piighost couvre et où passe la frontière.

!!! warning "Un repère, pas une certification"
    Cette page montre comment les briques de piighost s'alignent avec deux cadres. Ce n'est pas une certification de conformité. Atteindre HIPAA ou le GDPR dépend aussi de la façon dont vous stockez la map de restauration, de qui peut l'atteindre, de votre base légale, et du risque résiduel dans le texte que piighost n'a pas touché. piighost est un outil de cette chaîne, pas une garantie.

## HIPAA Safe Harbor

HIPAA est la loi américaine sur les données de santé. Sa méthode Safe Harbor établit qu'une fois retirées 18 catégories d'identifiants d'un dossier, et sans connaissance effective que le reste pourrait ré-identifier une personne, le dossier n'est plus une donnée de santé protégée et sort du champ de la règle. Safe Harbor est destructif pour les données qui dépendent de dates ou de lieux exacts, c'est donc une cible de dé-identification, pas une transformation sans perte.

Le tableau ci-dessous met chacun des 18 identifiants en regard des détecteurs livrés par piighost. « Custom » signifie que piighost n'a pas de pattern préétabli, mais qu'un pattern `RegexDetector` pour votre format local, ou le `LLMDetector`, le couvre.

<div class="wide-table" markdown="1">

| Identifiant Safe Harbor | Couverture | Par |
|-------------------------|------------|-----|
| 1. Noms | Yes | `Gliner2PiiDetector` (`PERSON`), `SpacyDetector`, `TransformersDetector` |
| 2. Unités géographiques sous l'État (rue, ville, code postal) | Partial | regex `US_ZIP`, `Gliner2PiiDetector` (`LOCATION`, `ADDRESS`); ville et comté dépendent du modèle NER |
| 3. Dates plus fines que l'année, et âges au-delà de 89 ans | Partial | `Gliner2PiiDetector` (`DATE_OF_BIRTH`); une date générique demande une regex custom, les âges au-delà de 89 ans ne sont pas traités à part |
| 4. Numéros de téléphone | Yes | regex `US_PHONE`, `FR_PHONE`, `Gliner2PiiDetector` (`PHONE`) |
| 5. Numéros de fax | Partial | reconnus par les patterns de téléphone sur la forme, non distingués comme fax |
| 6. Adresses e-mail | Yes | regex `EMAIL`, `Gliner2PiiDetector` (`EMAIL`) |
| 7. Numéros de sécurité sociale | Yes | regex `US_SSN`, `FR_NIR`, `Gliner2PiiDetector` (`SSN`) |
| 8. Numéros de dossier médical | Custom | fournir un pattern `RegexDetector` pour le format local |
| 9. Numéros de bénéficiaire d'assurance santé | Custom | fournir un pattern `RegexDetector` |
| 10. Numéros de compte | Partial | regex `IBAN` et `Gliner2PiiDetector` (`IBAN`); les autres numéros de compte demandent un pattern custom |
| 11. Numéros de certificat et de licence | Partial | `Gliner2PiiDetector` (`DRIVER_LICENSE`, `PASSPORT`); les autres certificats demandent un pattern custom |
| 12. Identifiants de véhicule et plaques | Custom | fournir un pattern `RegexDetector` |
| 13. Identifiants d'appareil et numéros de série | Custom | fournir un pattern `RegexDetector` |
| 14. URLs | Yes | regex `URL` |
| 15. Adresses IP | Yes | regex `IPV4`, `Gliner2PiiDetector` (`IP_ADDRESS`); l'IPv6 demande un pattern custom |
| 16. Identifiants biométriques | No | hors texte, hors périmètre |
| 17. Photographies plein visage et images comparables | No | multimodal, un [hors-périmètre](roadmap.md#hors-perimetre) |
| 18. Tout autre numéro ou code identifiant unique | Custom | un pattern `RegexDetector` ou le `LLMDetector`; `TAX_ID`, `CRYPTO`, `API_KEY` sont aussi couverts par `Gliner2PiiDetector` |

</div>

Les catalogues regex préétablis reconnaissent sur la forme seule, sans validation de checksum, donc ils ne lâchent jamais une valeur abîmée par l'OCR mais acceptent aussi une non-valeur bien formée. Voir [Limites](limitations.md).

## GDPR

Le GDPR trace une ligne entre deux traitements, souvent confondus.

- **Pseudonymisation** : la valeur est remplacée mais une correspondance subsiste, donc c'est réversible. Une donnée pseudonymisée reste une donnée personnelle au sens du GDPR, et ses obligations continuent de s'appliquer.
- **Anonymisation** : modification permanente et irréversible. Une donnée vraiment anonyme sort du champ du GDPR.

Où tombe piighost dépend du mode choisi.

- Les jetons réversibles par défaut, restaurés depuis la mémoire de conversation, `<<PERSON:1>>`{ .placeholder } désanonymisé en `Patrick`{ .pii }, relèvent de la **pseudonymisation**. La correspondance existe, donc la donnée reste personnelle. Protéger cette correspondance, le backend de mémoire et son chiffrement au repos, est ce qui donne son sens à la pseudonymisation. Voir [Sécurité](security.md).
- Un `RedactPlaceholderFactory` ou un masque utilisé sans mémoire abandonne la correspondance, donc se rapproche de l'**anonymisation**. Que le résultat soit vraiment anonyme dépend encore du risque de ré-identification résiduel dans le texte alentour.

## Voir aussi

- [Sécurité](security.md) : le modèle de menace, les backends de mémoire, et le chiffrement au repos qui protège la map de restauration.
- [Limites](limitations.md) : la regex par forme seule et ce qu'elle ne valide pas.
- [Placeholder factories](placeholder-factories.md) : quels modes sont réversibles et lesquels ne le sont pas.
- [Roadmap](roadmap.md) : ce qui est en attente et ce qui est volontairement hors périmètre.
