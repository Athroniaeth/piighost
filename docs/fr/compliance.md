---
icon: lucide/scale
---

# Conformité

Les détecteurs et les modes de `piighost` se placent face à deux cadres réglementaires, HIPAA Safe Harbor et le RGPD. La mise en regard ci-dessous montre ce qui est couvert et où passe la frontière.

!!! warning "Un repère, ni une certification ni un conseil juridique"
    Ce n'est pas une certification de conformité. Atteindre HIPAA ou le RGPD dépend aussi de la façon dont vous stockez la correspondance de restauration, de qui peut l'atteindre, de votre base légale, et du risque résiduel dans le texte que `piighost` n'a pas touché. `piighost` est un outil de cette chaîne, pas une garantie. Cette page n'est pas non plus un conseil juridique. Les résumés des textes et de la jurisprudence ci-dessous sont une aide à la lecture, à vérifier sur les sources officielles et avec votre conseil.

## HIPAA Safe Harbor

HIPAA est la loi américaine sur les données de santé. Sa méthode Safe Harbor pose deux conditions. Les 18 catégories d'identifiants sont retirées d'un dossier, et vous n'avez pas connaissance effective que le reste pourrait ré-identifier une personne. Le dossier n'est alors plus une donnée de santé protégée et sort du champ de la règle. Safe Harbor est une cible de dé-identification, pas une transformation sans perte, parce qu'il détruit les données qui dépendent de dates ou de lieux exacts.

Le tableau ci-dessous met chacun des 18 identifiants en regard des détecteurs livrés par `piighost` et des catalogues regex du hub. "Custom" signifie qu'aucun catalogue du hub n'a de pattern pour cet identifiant. Vous le couvrez avec un pattern `RegexDetector` pour votre format local, ou avec le `LLMDetector`.

<div class="wide-table" markdown="1">

| Identifiant Safe Harbor | Couverture | Par |
|-------------------------|------------|-----|
| 1. Noms | Yes | `Gliner2PiiDetector` (`PERSON`), `SpacyDetector`, `TransformersDetector` |
| 2. Unités géographiques sous l'État (rue, ville, code postal) | Partial | regex `US_ZIP`, `Gliner2PiiDetector` (`LOCATION`, `ADDRESS`). Ville et comté dépendent du modèle NER |
| 3. Dates plus fines que l'année, et âges au-delà de 89 ans | Partial | `Gliner2PiiDetector` (`DATE_OF_BIRTH`). Une date générique demande une regex custom, les âges au-delà de 89 ans ne sont pas traités à part |
| 4. Numéros de téléphone | Yes | regex `US_PHONE`, `FR_PHONE`, `Gliner2PiiDetector` (`PHONE`) |
| 5. Numéros de fax | Partial | reconnus par les patterns de téléphone sur la forme, non distingués comme fax |
| 6. Adresses e-mail | Yes | regex `EMAIL`, `Gliner2PiiDetector` (`EMAIL`) |
| 7. Numéros de sécurité sociale | Yes | regex `US_SSN`, `FR_NIR`, `Gliner2PiiDetector` (`SSN`) |
| 8. Numéros de dossier médical | Custom | fournir un pattern `RegexDetector` pour le format local |
| 9. Numéros de bénéficiaire d'assurance santé | Custom | fournir un pattern `RegexDetector` |
| 10. Numéros de compte | Partial | regex `IBAN` et `Gliner2PiiDetector` (`IBAN`). Les autres numéros de compte demandent un pattern custom |
| 11. Numéros de certificat et de licence | Partial | `Gliner2PiiDetector` (`DRIVER_LICENSE`, `PASSPORT`). Les autres certificats demandent un pattern custom |
| 12. Identifiants de véhicule et plaques | Custom | fournir un pattern `RegexDetector` |
| 13. Identifiants d'appareil et numéros de série | Custom | fournir un pattern `RegexDetector` |
| 14. URLs | Yes | regex `URL` |
| 15. Adresses IP | Yes | regex `IPV4`, `Gliner2PiiDetector` (`IP_ADDRESS`). L'IPv6 demande un pattern custom |
| 16. Identifiants biométriques | No | hors texte, hors périmètre |
| 17. Photographies plein visage et images comparables | No | multimodal, un [hors-périmètre](roadmap.md#hors-perimetre) |
| 18. Tout autre numéro ou code identifiant unique | Custom | un pattern `RegexDetector` ou le `LLMDetector`. `TAX_ID`, `CRYPTO`, `API_KEY` sont aussi couverts par `Gliner2PiiDetector` |

</div>

Les catalogues regex du hub reconnaissent une valeur sur sa forme seule, sans validation de checksum. Ils ne lâchent donc jamais une valeur abîmée par l'OCR, mais ils acceptent aussi une chaîne qui a la bonne forme sans être une vraie valeur. Voir [Limites](limitations.md).

## RGPD

Le RGPD trace une ligne entre deux traitements, souvent confondus.

- **Pseudonymisation** : la valeur est remplacée mais une correspondance subsiste, donc c'est réversible. Pour qui détient cette correspondance, une donnée pseudonymisée reste une donnée personnelle au sens du RGPD, et ses obligations continuent de s'appliquer.
- **Anonymisation** : modification permanente et irréversible. Une donnée vraiment anonyme sort du champ du RGPD.

Où tombe `piighost` dépend du mode choisi.

- Par défaut, les jetons sont réversibles. La mémoire de conversation les restaure, par exemple `<<PERSON:1>>`{ .placeholder } en `Patrick`{ .pii }. Ce mode relève de la **pseudonymisation**. La correspondance existe, donc la donnée reste personnelle. La pseudonymisation n'a de sens que si cette correspondance est protégée, par le backend de mémoire et son chiffrement au repos. Voir [Sécurité](security.md).
- Un `RedactPlaceholderFactory` ou un masque utilisé sans mémoire abandonne la correspondance, donc se rapproche de l'**anonymisation**. Que le résultat soit vraiment anonyme dépend encore du risque de ré-identification résiduel dans le texte alentour.

!!! note "Le mot qu'emploie cette documentation"
    Ces pages disent dé-identification pour ce que fait le pipeline, un terme technique qui couvre les deux modes ci-dessus. Ce n'est pas une catégorie juridique. Dans le mode réversible par défaut, le nom juridique est pseudonymisation, et c'est le mot à employer envers les personnes concernées, dans une mention d'information ou une AIPD. Le Comité européen de la protection des données (EDPB) demande aux responsables du traitement de ne pas qualifier de "dé-identifiées" des données tant que les personnes restent identifiables (lignes directrices 02/2026, paragraphe 40, voir [plus bas](#ce-que-dit-le-comite-europeen-depuis-larret)).

### Ce que dit le règlement

Le RGPD encadre cette distinction dans les dispositions suivantes.

- **L'article 4, point 5)** définit la pseudonymisation comme le traitement de données personnelles "de telle façon que celles-ci ne puissent plus être attribuées à une personne concernée précise sans avoir recours à des informations supplémentaires", pour autant que ces informations "soient conservées séparément" et soumises à des mesures techniques et organisationnelles. Dans un déploiement `piighost`, l'information supplémentaire est la correspondance de `<<PERSON:1>>`{ .placeholder } vers `Patrick`{ .pii }.
- **Le considérant 26** pose que les données pseudonymisées qui pourraient être attribuées à une personne physique par le recours à des informations supplémentaires "devraient être considérées comme des informations concernant une personne physique identifiable". L'identifiabilité s'apprécie au regard de l'ensemble des moyens raisonnablement susceptibles d'être utilisés, par le responsable du traitement ou par toute autre personne, compte tenu du coût, du temps et des technologies disponibles. Les informations anonymes sortent du champ du règlement.
- **Les considérants 28 et 29** présentent la pseudonymisation comme un moyen de réduire les risques pour les personnes concernées, qui n'exclut aucune autre mesure. Elle est possible chez un même responsable du traitement, pourvu que les informations supplémentaires soient conservées séparément et que le responsable indique les personnes autorisées.
- **L'article 25, paragraphe 1**, protection des données dès la conception et par défaut, cite la pseudonymisation comme exemple de mesure technique et organisationnelle appropriée. Le considérant 78 compte parmi ces mesures le fait de "pseudonymiser les données à caractère personnel dès que possible".
- **L'article 32, paragraphe 1, point a)**, sécurité du traitement, range "la pseudonymisation et le chiffrement des données à caractère personnel" parmi les mesures qui garantissent un niveau de sécurité adapté au risque.
- **L'article 35** impose une analyse d'impact relative à la protection des données (AIPD) avant un traitement susceptible d'engendrer un risque élevé, "en particulier par le recours à de nouvelles technologies". Le paragraphe 3 nomme trois cas où elle est requise en particulier, le paragraphe 4 charge chaque autorité de contrôle de publier la liste des traitements qui en exigent une, et le paragraphe 7 fixe son contenu minimal. [Comment documenter `piighost` dans une AIPD](dpia.md) fournit la matière de ce contenu.

### Ce que dit le Comité européen sur la pseudonymisation

Le Comité européen de la protection des données (EDPB) a adopté ses lignes directrices 01/2025 sur la pseudonymisation le 16 janvier 2025, en version soumise à consultation publique. Les passages ci-dessous traduisent librement la version anglaise. Cinq points touchent directement `piighost`.

- Les données pseudonymisées qui pourraient être attribuées à une personne par des informations supplémentaires sont des données personnelles, et cela vaut aussi lorsque les données pseudonymisées et les informations supplémentaires ne sont pas entre les mains de la même personne (paragraphe 22).
- Les informations supplémentaires comprennent les tables de correspondance entre les pseudonymes et les attributs identifiants qu'ils remplacent, ainsi que les clés cryptographiques (paragraphe 20). La mémoire de conversation et la clé de chiffrement sont ces informations supplémentaires.
- La levée de la pseudonymisation devrait être réservée à des personnes spécialement autorisées, conformément au considérant 29 (paragraphe 32).
- Les lignes directrices appellent "domaine de pseudonymisation" le contexte dans lequel l'attribution doit être empêchée (paragraphe 35). Les informations supplémentaires ne devraient pas entrer dans ce domaine (paragraphe 40). Avec `piighost`, le fournisseur du LLM se trouve dans ce domaine et la correspondance reste en dehors.
- Avant de transmettre des données pseudonymisées à un tiers, il faut au minimum identifier et prendre en compte les moyens dont dispose le destinataire pour attribuer les données (paragraphe 70). Pour `piighost`, ce tiers est le fournisseur du LLM.

### Ce qu'a jugé la Cour de justice dans CEPD/CRU

Le Conseil de résolution unique (CRU) avait recueilli les commentaires des actionnaires et créanciers d'une banque mise en résolution. Il en a transmis une partie à Deloitte, la société chargée d'une valorisation. Ces commentaires étaient pseudonymisés sous un code alphanumérique que seul le CRU pouvait relier à un auteur. Des auteurs se sont plaints auprès du Contrôleur européen de la protection des données (CEPD, à ne pas confondre avec le Comité), qui a jugé que le CRU avait manqué à son obligation de les informer que Deloitte recevrait leurs données. Le Tribunal a annulé cette décision (T-557/20, 26 avril 2023). Sur pourvoi du CEPD, la Cour de justice a annulé cet arrêt le 4 septembre 2025 (C-413/23 P, ECLI:EU:C:2025:645).

L'arrêt interprète le règlement 2018/1725, qui régit les institutions et organes de l'Union, et non le RGPD. La Cour relève que la définition des données à caractère personnel de ce règlement est en substance identique à celle du RGPD et appelle une interprétation identique (point 52). La définition de la pseudonymisation qu'elle applique reprend mot pour mot l'article 4, point 5).

La Cour a jugé ce qui suit.

- La pseudonymisation ne relève pas de la définition des données personnelles. Elle renvoie à des mesures qui réduisent le risque de corrélation d'un ensemble de données avec l'identité des personnes concernées (point 72).
- Pour le responsable du traitement qui détient les informations supplémentaires, les données conservent leur caractère personnel en dépit de la pseudonymisation (point 76).
- Pour un destinataire, les données peuvent ne pas présenter de caractère personnel, sous deux conditions. Le destinataire ne doit pas être en mesure de lever les mesures de pseudonymisation, et ces mesures doivent l'empêcher d'attribuer les données à la personne concernée, y compris par d'autres moyens comme un recoupement avec d'autres éléments (point 77).
- Des données pseudonymisées "ne doivent pas être considérées comme constituant, en toute hypothèse et pour toute personne, des données à caractère personnel" (point 86).
- Lorsqu'il n'est pas exclu qu'un tiers qui reçoit les données soit raisonnablement en mesure de les attribuer, par exemple par recoupement avec d'autres données dont il dispose, les données présentent un caractère personnel pour ce transfert et pour le traitement de ce tiers (point 85).
- La perspective pertinente pour apprécier l'identifiabilité dépend des circonstances de chaque cas (point 100). Pour l'obligation d'informer les personnes des destinataires de leurs données, elle s'apprécie au moment de la collecte et du point de vue du responsable du traitement (point 111). L'obligation du CRU s'appliquait en amont du transfert, que les données aient ou non un caractère personnel du point de vue de Deloitte (point 112).
- Les opinions ou points de vue personnels, en tant qu'expression de la pensée d'une personne, sont nécessairement intimement liés à celle-ci (point 58).

La Cour n'a pas jugé ce qui suit.

- Elle n'a pas décidé que les commentaires étaient anonymes pour Deloitte, et n'a pas examiné si Deloitte pouvait en fait identifier leurs auteurs (point 116).
- Elle n'a pas fait sortir les données pseudonymisées du règlement pour le responsable du traitement qui les a pseudonymisées.
- Elle n'a pas dispensé ce responsable de son obligation d'informer les personnes concernées des destinataires.

La Cour a statué elle-même sur le moyen tiré de ce que les commentaires n'étaient pas des données personnelles, et l'a rejeté (point 120). Elle a renvoyé l'autre moyen, tiré du droit à une bonne administration, devant le Tribunal (point 122).

### Ce que dit le Comité européen depuis l'arrêt

Le Comité a réuni les parties prenantes le 12 décembre 2025, à la suite de l'arrêt, pour nourrir ses travaux sur les lignes directrices 01/2025 sur la pseudonymisation et sur des lignes directrices consacrées à l'anonymisation. Les participants se sont divisés sur la perspective applicable à un sous-traitant, les uns pour celle du sous-traitant, les autres pour celle du responsable du traitement.

Le Comité a ensuite adopté ses lignes directrices 02/2026 sur l'anonymisation le 7 juillet 2026, en version soumise à consultation publique jusqu'au 30 octobre 2026. Elles tiennent compte de l'arrêt, qui portait sur la pseudonymisation. Trois points touchent `piighost`. Les passages ci-dessous traduisent librement la version anglaise.

- L'anonymat s'apprécie du point de vue de chaque entité concernée, et la question de départ est de savoir pour qui les données sont censées être anonymes (paragraphes 11 et 12).
- Une entité qui traite des informations pour le compte d'un responsable du traitement s'apprécie du point de vue de ce responsable. Une information qui est une donnée personnelle pour le responsable l'est aussi pour son sous-traitant (paragraphe 15).
- Les responsables du traitement ne devraient pas qualifier des données par les termes "anonymes", "dé-identifiées" ou "dépersonnalisées" si les personnes restent identifiables (paragraphe 40).

### Ce que cela implique pour un déploiement `piighost`

- Pour vous, responsable du traitement qui détient la correspondance, le texte dé-identifié reste une donnée personnelle. Toutes les obligations du RGPD s'appliquent à l'ensemble du traitement, correspondance comprise.
- Un fournisseur de LLM qui traite le texte pour votre compte est votre sous-traitant. Selon les lignes directrices 02/2026, le texte s'apprécie alors de votre point de vue, et reste donc une donnée personnelle pour le fournisseur aussi.
- Un fournisseur de LLM qui utilise le texte pour ses propres finalités s'apprécie de son propre point de vue. L'arrêt laisse ouverte la possibilité que le texte ne soit pas une donnée personnelle pour lui, mais seulement si les deux conditions du point 77 sont réunies. `piighost` remplit la première condition par construction, puisque la correspondance ne quitte jamais votre périmètre. La seconde condition dépend de deux choses. D'abord, ce que le texte porte encore en clair, c'est-à-dire le contexte, les quasi-identifiants, une PII que le détecteur a manquée. Ensuite, ce que le fournisseur peut recouper avec ce texte. Voir [Sécurité](security.md) et [Limites](limitations.md).
- Vous devez informer les personnes que leurs messages parviennent à un fournisseur de LLM. Cette obligation s'apprécie de votre point de vue, au moment de la collecte. Elle vaut donc quelle que soit la position du fournisseur. Dans cette information, qualifiez le traitement de pseudonymisation, et non d'anonymisation ou de dé-identification, comme le demande le paragraphe 40 des lignes directrices 02/2026.
- Une AIPD qui traite le texte dé-identifié comme une donnée personnelle pour le fournisseur reste valable quelle que soit l'issue de ces questions.

### Sources

- [RGPD, règlement (UE) 2016/679](https://eur-lex.europa.eu/eli/reg/2016/679/oj)
- [Règlement (UE) 2018/1725, applicable aux institutions et organes de l'Union](https://eur-lex.europa.eu/eli/reg/2018/1725/oj)
- [Comité européen de la protection des données, lignes directrices 01/2025 sur la pseudonymisation, version soumise à consultation publique, en anglais](https://www.edpb.europa.eu/public-consultations/guidelines-012025-on-pseudonymisation_en)
- [Comité européen de la protection des données, compte rendu de la réunion des parties prenantes sur l'anonymisation et la pseudonymisation du 12 décembre 2025, en anglais](https://www.edpb.europa.eu/system/files/2026-02/edpb-report-stakeholder-event-anonymisation-pseudonymisation_en.pdf)
- [Comité européen de la protection des données, lignes directrices 02/2026 sur l'anonymisation, version soumise à consultation publique, en anglais](https://www.edpb.europa.eu/public-consultations/guidelines-on-anonymisation_en)
- [Cour de justice, arrêt du 4 septembre 2025, CEPD/CRU, C-413/23 P](https://eur-lex.europa.eu/legal-content/FR/TXT/?uri=CELEX:62023CJ0413)
- [Cour de justice, communiqué de presse n° 107/25](https://curia.europa.eu/site/upload/docs/application/pdf/2025-09/cp250107fr.pdf)

## Voir aussi

- [Sécurité](security.md) : le modèle de menace, les backends de mémoire, et le chiffrement au repos qui protège la correspondance de restauration.
- [Comment documenter `piighost` dans une AIPD](dpia.md) : le traitement, les flux de données, les mesures et les risques résiduels, avec un modèle à remplir.
- [Limites](limitations.md) : la regex par forme seule et ce qu'elle ne valide pas.
- [Placeholder factories](placeholder-factories.md) : quels modes sont réversibles et lesquels ne le sont pas.
- [Roadmap](roadmap.md) : ce qui est en attente et ce qui est volontairement hors périmètre.
