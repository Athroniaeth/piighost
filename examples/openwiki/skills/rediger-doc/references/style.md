# Style : règles communes

## Phrases

- Une idée par phrase et un sujet par paragraphe. Moins de 25 mots par phrase, et moins de 20 dans la doc métier.
- Commencer chaque section et chaque paragraphe par l'information principale.
- Voix active, avec un acteur explicite : « Le système envoie l'e-mail », pas « L'e-mail est envoyé ». Le passif reste acceptable quand l'acteur est inconnu ou sans intérêt.
- S'adresser au lecteur avec « vous ». Mettre les consignes à l'impératif (« Cliquez », « Lancez »). Le « nous » est réservé aux tutoriels.
- Écrire au présent, pour décrire le comportement comme pour donner les résultats.
- Garder un terme par concept dans tout le document. Si l'écran dit « Session », le doc dit « Session », jamais « formation » à la ligne suivante.
- Développer chaque sigle à sa première occurrence : « DPC (développement professionnel continu) ».

## Ce qu'on supprime

| Supprimer | Remplacer par |
|---|---|
| « permet de », « offre la possibilité de » | le verbe : « X exporte… » |
| « simplement », « il suffit de », « facilement », « bien sûr », « évidemment » | rien, ou la consigne précise |
| phrases de narrateur : « Voyons maintenant… », « Dans cette section, nous allons… », « Pour conclure… » | rien : la phrase factuelle suivante devient l'ouverture |
| mots creux : « robuste », « puissant », « intuitif », « solution », « écosystème », « optimisé », « fluide », « de manière efficace » | un fait : acteur, action, contrainte, chiffre |
| « N'hésitez pas à… » | l'action, à l'impératif |
| affirmation sans preuve (« plus rapide », « plus fiable ») | la mesure, ou le passage supprimé |

**Evidence-first.** Une affirmation forte s'accompagne de ce qui la prouve : fichier, commande, mesure ou ticket. Si la preuve manque, le dire : « Sous réserve de… », « À vérifier : … ».

## Mise en forme (Markdown)

- Un seul H1 par document. Ne jamais sauter de niveau. Titres en casse de phrase, sans point final. Au-delà du H3, découper le document.
- Les titres seuls doivent permettre de comprendre et de parcourir la page. Préférer des titres en forme de tâche (« Ajouter un e-mail automatique ») ou de réponse.
- Listes numérotées pour les étapes, à puces pour le reste. Les éléments d'une liste ont la même forme grammaticale.
- Un tableau sert à comparer ou à donner des valeurs (de 3 à 5 colonnes), pas à mettre en page de la prose.
- Code inline pour les fichiers, commandes, variables et valeurs. Toujours indiquer le langage sur un bloc de code.
- Libellés d'interface en **gras** et reproduits à l'identique, avec le chemin de navigation : **Sessions > Modifier > Questionnaire**.
- Encadrés (`> [!NOTE]`, `> [!WARNING]`) : 2 au maximum par page. WARNING est réservé à la perte de données, à la sécurité et aux actions irréversibles. Une page qui a besoin de beaucoup d'avertissements signale un problème d'ergonomie à remonter.
- Liens descriptifs (jamais « cliquez ici »), relatifs pour les liens internes.
- Images : un texte alternatif, et un texte qui dit déjà l'essentiel (l'image complète, elle ne remplace pas). Aucune information portée par la seule couleur.
- Dates : JJ/MM/AAAA en doc métier, AAAA-MM-JJ en doc technique.

## Exemples

- Le plus petit exemple réaliste qui prouve le point. Des données crédibles (`dr.martin@example.com`, « session du 12/03/2026 »), jamais `foo` ou `test1`.
- Un exemple de code tourne tel quel : imports, variables définies, pas de `...` sur le chemin critique. Marquer explicitement les valeurs à remplacer : `VOTRE_CLE_API`.
- Montrer la sortie ou le résultat attendu.
