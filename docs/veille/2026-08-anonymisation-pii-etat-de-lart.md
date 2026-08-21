# Veille — état de l'art de l'anonymisation / dé-identification de PII

> Note interne de veille (août 2026). **Pas** une page du site zensical.
> Source : harnais deep-research (5 angles → fetch ~15 sources → vérification
> adversariale des affirmations). La synthèse automatique du workflow a échoué
> (limite de session) ; ce document est reconstruit à partir des ~70 affirmations
> vérifiées (votes majoritairement 3-0). Sources listées en fin de document.

## Résumé exécutif

- La **substitution par surrogate réaliste** (Faker/synthétique) est le thème le plus fort du marché, et bat le remplacement par token à la fois en **utilité** et en **confidentialité** (les tokens visibles exposent l'emplacement des slots). piighost ne l'a pas.
- Les **proxies de dé-identification OpenAI-compatibles** (Philter, PrivAiTe) sont une tendance nette côté agents. Déjà en roadmap chez nous.
- La **généralisation cross-domaine de la détection reste non résolue** (meilleur système ≈ F1 0,14 sur PIIBench, 10 datasets, 48 types).
- Forces piighost : intégrations agents (dé-id des tool-calls), mémoire conversationnelle thread-stable chiffrée, guard rail, observation, architecture composable.

## 1. Librairies / frameworks

- **Microsoft Presidio** (OSS, MIT) : opérateurs `Replace/Redact/Mask/Hash(salé)/Encrypt/Custom/Keep` + `Surrogate` médical (Azure Health Data Services) ; **désanonymisation réversible** (`DeanonymizeEngine`, déchiffre l'`Encrypt`) ; pseudonymisation **cohérente par valeur** via `InstanceCounterAnonymizer/Deanonymizer` (mapping) — **non thread-safe**. Recommandé surtout comme **infra d'orchestration** (brancher tout détecteur en custom recognizer), pas pour sa précision.
- **Google Cloud DLP** (API cloud) : **FPE** (même longueur/charset, réversible), **chiffrement déterministe** réversible + **intégrité référentielle**, **tokenisation déterministe** cohérente (même valeur → même token, relie texte libre ↔ colonne).
- **Philterd — Philter AI Proxy** (commercial) : **proxy OpenAI/Anthropic/Bedrock** (wire protocol), redaction transparente sans changer le SDK ; substitution synthétique cohérente ; tokenisation réversible ou masquage irréversible ; masques *format-preserving* (carte 4 derniers, date-shift) ; détection **non-LLM déterministe**. Cadre « egress gateway » (HIPAA/GDPR : PII atteignant un tiers = franchissement de frontière de traitement).
- **PrivAiTe** (OSS) : **proxy OpenAI-compatible auto-hébergé**, pseudonymise avant le provider + restaure dans la réponse ; scanne les **args JSON des tool-calls + multimodal** ; restaure sur **tous les canaux** (contenu, tool-calls, reasoning, refus, audio, streaming) ; **policies par type** (restore/mask/destroy) + regex hard-block.
- **LlamaIndex** (OSS, MIT) : dé-id PII **native RAG** en node postprocessors (`NERPIINodePostprocessor` transformers-NER, `PIINodePostprocessor` LLM **flaggé beta**, backend Presidio) ; map placeholder→valeur.
- **Azure de-identification service** : meilleur F1 (0,939) sur un benchmark médical UK, proche de l'accord inter-annotateurs (0,977).

## 2. Modèles NER/PII

- **GLiNER2** (déjà utilisé chez nous) : NER + classification + extraction structurée schema-driven, **efficace CPU**, pip-installable.
- **GLiNER2-PII** (`fastino/gliner2-privacy-filter-PII-multi`, 0,3B, **42 types** en 7 catégories, char-span, multilingue) : **meilleur F1 span-level** sur SPY, devant l'OpenAI Privacy Filter (vote 2-1).
- **Piiranha-v1** (mdeberta-v3, 6 langues, 17 types) : F1 rapportés élevés MAIS **licence cc-by-nc-nd (non commerciale)** → à ne pas embarquer ; **chute forte hors-distribution** (0,780 AI4Privacy → 0,169 finance).
- **Constat transverse** : aucun modèle ne domine (micro-F1 : Piiranha 0,542, GLiNER v1 0,535, Presidio 0,481, GLiNER v2 0,478, regex 0,171) ; **GLiNER généralise mieux OOD** ; LLM compétitifs seulement en few-shot (GPT-4 10-shot 0,898), avec risque d'hallucination.

## 3. Techniques au-delà du remplacement par token

- **Surrogates réalistes (Faker)** — renverse une intuition : ils battent la redaction **en utilité** (+13,26 pts BERTScore : 81,59 → 94,85 % ; NER-training F1 0,656 vs **0,000** pour la redaction) **et en confidentialité** (attaque LLM adversariale : **0 %** de PII récupérée sur surrogates vs 1,53 % sur placeholders). **Faker >> LLM** pour générer (SLM 41,2 s/doc vs 1,6 s, vocabulaire 3,1× plus étroit). Générateurs type-spécifiques + **checksums valides** (Luhn, ABA, Base58) + unicité par session ; **locale-aware**.
- **FPE** (`python-fpe`, FF3/FF3-1, NIST SP 800-38G) : réversible, préserve format/longueur. ⚠️ **FF3 et FF3-1 retirés du standard NIST** (vulnérabilités ; draft fév. 2025 les supprime).
- **Modèles de confidentialité** : k-anonymity / l-diversity / t-closeness ; **quasi-identifiants** (Sweeney : ZIP+DOB+sexe ré-identifie **87 %** des US) ; **differential privacy** (gold standard analytique) ; données synthétiques.

## 4. Agents / RAG

- **Proxies de dé-id au gateway** : redact **avant** le provider, restauration multi-canal, scan des **tool-call args**.
- **RAG** : LlamaIndex traite la dé-id comme un **stage d'ingestion/requête** de première classe.

## 5. Conformité / benchmarks

- **HIPAA Safe Harbor** : retirer **18 catégories** d'identifiants + clause « no actual knowledge » de ré-identification résiduelle ; alternative **Expert Determination** (statisticien, risque « très faible »). Safe Harbor **destructif** pour données dépendant de dates/lieux exacts.
- **GDPR** : pseudonymisation = réversible → **reste de la donnée personnelle** ; anonymisation = modification **permanente et irréversible**.
- **Benchmarks** : **PIIBench** (10 datasets, 2,37 M séquences, 48 types) → **best F1 0,14** ⇒ cross-domaine non résolu. Datasets : `ai4privacy/pii-masking-400k`, Gretel Finance, Nemotron-PII, SPY, i2b2/MIMIC/n2c2 (US-centrés). Restauration par placeholder peut échouer sur désalignement de spans (Presidio 64 % vs 100 % pour placeholders typés).

## 6. Comparatif par librairie

| Librairie | Nature / licence | Détection | Remplacement | Réversibilité / cohérence | Conversation + mémoire | Agents / RAG / proxy |
|---|---|---|---|---|---|---|
| **piighost** | Lib OSS, composable, agents LLM | regex (sans checksum) + spaCy + transformers + GLiNER2 + LLM + composite/chunked | redact / label / mask / counter / hash — pas de surrogate | map mémoire, tokens **thread-stables** (100 % restore) ; pas déterministe cross-corpus | **thread-stable** + InMemory/Redis/SQLAlchemy chiffré | **LangChain + Pydantic AI** (dé-id **tool-calls**), client HTTP, décodeur streaming non câblé ; pas de proxy/LlamaIndex ; guard rail + OTel |
| **Presidio** | Lib OSS (MIT), orchestration | regex + NER + recognizers custom | + **Surrogate médical**, Encrypt, Custom lambda | **Encrypt→Deanonymize** + pseudonymisation par mapping (**non thread-safe**) | aucune | pas natif ; back-end de LlamaIndex |
| **Cloud DLP** | API cloud | infoTypes managés (regex+ML) | redact/mask + tokenisation crypto | **déterministe + FPE**, intégrité référentielle | stateless | — ; orienté conformité |
| **Philter** | Proxy + on-prem, commercial | NLP + patterns, non-LLM | + substitution synthétique cohérente, **format-preserving + date-shift** | tokenisation réversible ou masquage | ? | **proxy OpenAI/Anthropic/Bedrock** |
| **PrivAiTe** | Proxy OpenAI-compatible OSS | pseudonymise | policies **restore/mask/destroy par type** | restauration multi-canal | par requête | **proxy + dé-id args tool-calls + multimodal + restore streaming** |
| **LlamaIndex** | Composant framework RAG OSS | NER + LLM (beta) + Presidio | placeholders typés + mapping | par mapping (par doc) | — | **PII first-class en node postprocessor RAG** |

## 7. Exemples concrets des pistes envisagées

Fil rouge : *« Patrick habite à Paris, carte 4539 1488 0343 6467, mail patrick@acme.com »*.

- **Faker (surrogates)** : `"Patrick habite à Paris."` → `"Julien Moreau habite à Lyon."` (vs `<<PERSON:1>> habite à <<LOCATION:1>>`).
- **Encrypt-token** : `"Patrick"` → `"<<PERSON:gAAAAAB…>>"`, restauré en déchiffrant (token autoportant, sans map).
- **Hash déterministe** : `"Patrick"` → `<<PERSON:9f3ab2c1>>` **identique** dans tous les docs + la requête (jointures cross-corpus).
- **Proxy OpenAI** : le client change juste `base_url` ; OpenAI reçoit `"…<<PERSON:1>>… <<EMAIL:1>>"`, le client reçoit la réponse restaurée.
- **date-shift** : `2024-03-12 … 2024-03-19` → `2024-04-18 … 2024-04-25` (intervalle préservé). **format-preserving** : `4539 1488 0343 6467` → `**** **** **** 6467`.
- **Policies par type** : PERSON→restore, EMAIL→mask, SSN→destroy, CREDIT_CARD→hard-block.
- **LlamaIndex** : `index.as_query_engine(node_postprocessors=[PiiHostPostprocessor(pipeline)])`.
- **GLiNER2-PII** : `Gliner2PiiDetector()` (42 types préconfigurés) vs lister les labels à la main.

## 8. Décisions piighost (au 2026-08)

**À faire** (roadmap) : proxy OpenAI-compatible, intégration LlamaIndex, normalisation de texte, cache de résultat optionnel, préset GLiNER2-PII (en cours).

**Hors périmètre** (voir aussi la section Non-goals de la roadmap) :
- Surrogates réalistes / Faker — collisions et réversibilité non fiable.
- Chiffrer la valeur dans le jeton — tokens longs à recracher ; la restauration passe par le cache.
- Hachage déterministe de la valeur — réversible par dictionnaire, fuite d'égalité ; la stabilité par thread suffit à nos cas d'usage.
- Bloquer des requêtes / supprimer des PII — relève de la politique de l'appelant, pas du rôle de sécurisation de piighost.
- Schémas transformant la valeur (date-shift, FPE) — hors du modèle token restaurable ; FF3/FF3-1 retirés du NIST.
- Differential privacy / données synthétiques — autre classe de problème (confidentialité au niveau dataset).

**Le plus rentable × visible** : surrogates Faker (écarté ici pour les collisions) et le **proxy OpenAI** ; sinon, à faible effort, LlamaIndex et le préset GLiNER2-PII.

## Sources

- Presidio anonymizer/deanonymizer : microsoft.github.io/presidio/anonymizer, deepwiki.com/microsoft/presidio, microsoft.github.io/presidio/samples/python/pseudonymization
- Google Cloud DLP : cloud.google.com/blog/products/identity-security/take-charge-of-your-data…, docs.cloud.google.com/sensitive-data-protection
- Philter : philterd.ai/blog/redact-pii-before-sending-to-an-llm
- PrivAiTe : github.com/crp4222/PrivAiTe
- LlamaIndex : docs.llamaindex.ai/en/stable/api_reference/postprocessor/PII
- GLiNER2 : arxiv.org/abs/2507.18546 ; GLiNER2-PII : researchgate.net/publication/404753981 ; huggingface.co/fastino/gliner2-privacy-filter-PII-multi ; huggingface.co/knowledgator/gliner-pii-large-v1.0
- Piiranha : huggingface.co/iiiorg/piiranha-v1-detect-personal-information
- Benchmarks : albertsikkema.com/…/benchmarking-open-source-pii-detection.html ; PIIBench (arxiv)
- Surrogates : cell.com/iscience (SurrogateShield) ; MimicGen
- FPE : github.com/mysto/python-fpe ; csrc.nist.gov/News/2017/Recent-Cryptanalysis-of-FF3
- Médical LLM de-id : arxiv.org/pdf/2606.29567
- Conformité : casrai.org/guides/18-hipaa-identifiers ; calawyers.org/privacy-law/…
