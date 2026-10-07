"""Source templates for the decision-guard benchmark, French and English.

Each template is a realistic short document with slots. A slot names a
fictitious value the generator fills in:

- {P1} a person's full name, {P1F} the first name alone, {P1L} the surname
  alone, {P1C} a civility and the surname ("Mme Dubois", "Ms Carter"). Up to P8.
- {E1}, {E2} the email of P1, P2. {T1}, {T2} the phone of P1, P2.
- {I1} an IBAN, {A1}, {A2} a postal address, {N1} an ID number (French NIR,
  UK National Insurance or NHS number).
- {ORG} a fictitious company, {REF} a reference number, {DAY} a weekday,
  {AMOUNT} a sum. These are not personal data and stay in clear.

Templates are kept under Laya's 512-token window.
"""

FR: list[tuple[str, str]] = [
    (
        "email",
        """Objet : Relance facture F-2026-{REF}

Bonjour {P1F},

Je reviens vers vous au sujet de la facture F-2026-{REF} d'un montant de {AMOUNT} euros, toujours impayée à ce jour. Le virement peut se faire sur le compte {I1}, ouvert au nom de {P2}.

Pour toute question, vous pouvez me joindre au {T2} ou par courriel à {E2}. Merci de mettre en copie {P3C}, qui suit le dossier côté comptabilité.

Cordialement,
{P2}
Service recouvrement, {ORG}""",
    ),
    (
        "email",
        """De : {P1} <{E1}>
À : {P2} <{E2}>
Objet : Changement d'adresse

Bonjour,

Je vous informe de mon déménagement. Ma nouvelle adresse est {A1}. Pouvez-vous mettre à jour mon dossier et m'envoyer le prochain relevé à cette adresse ?

Je reste joignable au {T1} en journée.

Bien à vous,
{P1}""",
    ),
    (
        "support_chat",
        """[Client] Bonjour, ma commande {REF} n'est jamais arrivée.
[Agent {P2F}] Bonjour, je regarde ça tout de suite. Pouvez-vous me confirmer votre nom et l'adresse de livraison ?
[Client] {P1}, {A1}.
[Agent {P2F}] Merci {P1C}. Le colis est bloqué au dépôt. Je vous propose une nouvelle livraison {DAY}.
[Client] D'accord. Le livreur peut m'appeler au {T1}.
[Agent {P2F}] C'est noté. Vous recevrez une confirmation sur {E1}.""",
    ),
    (
        "support_chat",
        """[Client] Bonjour, on m'a prélevé deux fois l'abonnement ce mois-ci.
[Agent] Bonjour, je suis désolé. Pour retrouver le contrat, j'ai besoin du titulaire et de l'IBAN débité.
[Client] Le contrat est au nom de {P1}, IBAN {I1}.
[Agent] Merci. Je vois bien deux prélèvements de {AMOUNT} euros. Je lance le remboursement du second.
[Client] Parfait. Mon conjoint, {P2}, a reçu le même courrier, c'est normal ?
[Agent] Oui, {P2C} est cotitulaire, il reçoit une copie. Le remboursement arrivera sous cinq jours ouvrés.""",
    ),
    (
        "contract",
        """CONTRAT DE BAIL D'HABITATION

Entre les soussignés :
{P1}, demeurant {A1}, ci-après « le bailleur »,
et {P2}, numéro de sécurité sociale {N1}, ci-après « le locataire ».

Article 1. Le bailleur loue au locataire le logement situé {A2}, pour une durée de trois ans.
Article 2. Le loyer mensuel est fixé à {AMOUNT} euros, payable par virement sur le compte {I1}.
Article 3. Toute correspondance sera adressée à {P1C} par courriel à {E1}.

Fait en deux exemplaires.""",
    ),
    (
        "contract",
        """AVENANT AU CONTRAT DE TRAVAIL n° {REF}

Entre la société {ORG}, représentée par {P2}, directrice des ressources humaines,
et {P1}, salarié, numéro de sécurité sociale {N1},

il est convenu ce qui suit.

Article 1. À compter du 1er novembre, {P1C} exercera ses fonctions en télétravail trois jours par semaine.
Article 2. Le salaire continue d'être versé sur le compte {I1}.
Article 3. Le salarié reste joignable au {T1} pendant les plages fixes.""",
    ),
    (
        "medical",
        """COMPTE RENDU DE CONSULTATION

Patient : {P1}, NIR {N1}
Adresse : {A1}
Médecin traitant : Dr {P2L}

Motif : douleurs lombaires depuis trois semaines, sans traumatisme.
Examen : pas de déficit neurologique. Contracture paravertébrale droite.
Conduite à tenir : kinésithérapie, dix séances. Antalgiques de palier 1.

{P1C} sera revu dans un mois. En cas d'aggravation, contacter le secrétariat au {T2}.

Dr {P2}""",
    ),
    (
        "medical",
        """Lettre de liaison, service de cardiologie

Cher confrère,

J'ai vu en consultation {P1}, adressé par le Dr {P2}, pour une fibrillation atriale découverte lors d'un bilan. Le traitement anticoagulant a été débuté. {P1C} est autonome et vit avec son épouse.

Un holter est prévu {DAY}. Le patient peut être joint au {T1}, son épouse {P3} au {T2}.

Bien confraternellement,
Dr {P4}""",
    ),
    (
        "hr",
        """Note RH, entretien annuel

Collaboratrice : {P1}
Manager : {P2}

{P1C} a atteint quatre objectifs sur cinq. Elle souhaite évoluer vers un poste de cheffe de projet. {P2C} appuie la demande et propose une formation au premier semestre.

Points d'attention : charge de travail élevée en septembre.
Coordonnées à jour : {E1}, {T1}, {A1}.""",
    ),
    (
        "hr",
        """Signalement au service RH

Le {DAY} matin, {P1} a signalé un conflit avec son responsable, {P2}. Selon {P1C}, les échanges se sont tendus lors de la réunion d'équipe. Deux témoins étaient présents, {P3} et {P4}.

Le service propose une médiation. {P1F} souhaite être contacté par courriel uniquement, à l'adresse {E1}.

Dossier suivi par {P5}.""",
    ),
    (
        "minutes",
        """Compte rendu, comité de pilotage du projet {REF}

Présents : {P1}, {P2}, {P3}, {P4}, {P5}, {P6}
Excusés : {P7}, {P8}

1. Planning. {P1C} présente le nouveau calendrier. {P3C} signale un retard sur les tests.
2. Budget. {P2} rappelle que l'enveloppe de {AMOUNT} euros est consommée à 70 %.
3. Recrutement. {P4} et {P5} conduiront les entretiens.
4. Divers. {P6C} demande que le compte rendu soit envoyé à {E1}.

Prochaine réunion {DAY}.""",
    ),
    (
        "minutes",
        """Liste de diffusion, astreinte de novembre

Semaine 1 : {P1} ({T1})
Semaine 2 : {P2} ({T2})
Semaine 3 : {P3}
Semaine 4 : {P4}
Suppléants : {P5}, {P6}

En cas d'absence, prévenir {P7}, coordinatrice, à {E1}, avec {P8} en copie.
Les échanges d'astreinte se font entre collègues, sans validation préalable.""",
    ),
    (
        "email",
        """Objet : Dossier de sinistre {REF}

Madame, Monsieur,

Suite au dégât des eaux du {DAY}, je vous transmets les pièces du dossier. L'assuré, {P1}, demeure {A1}. Le voisin du dessus, {P2}, a reconnu sa responsabilité.

L'expert peut contacter {P1C} au {T1} ou par courriel à {E1}. L'indemnité sera versée sur le compte {I1}.

Cordialement,
{P3}, gestionnaire sinistres, {ORG}""",
    ),
    (
        "support_chat",
        """[Utilisateur] Je n'arrive plus à me connecter à mon espace.
[Support {P2F}] Bonjour ! Pour vérifier votre identité, quel est l'e-mail du compte ?
[Utilisateur] {E1}
[Support {P2F}] Merci. Le compte est au nom de {P1}, c'est bien ça ?
[Utilisateur] Oui.
[Support {P2F}] Je vous envoie un code par SMS au {T1}. Vous pourrez ensuite choisir un nouveau mot de passe.
[Utilisateur] Reçu, merci beaucoup.""",
    ),
]

EN: list[tuple[str, str]] = [
    (
        "email",
        """Subject: Overdue invoice INV-{REF}

Hi {P1F},

Following up on invoice INV-{REF} for {AMOUNT} GBP, which is still unpaid. Payment can be made by transfer to {I1}, account holder {P2}.

If you have any questions, call me on {T2} or email {E2}. Please copy {P3C}, who handles the account on your side.

Kind regards,
{P2}
Credit control, {ORG}""",
    ),
    (
        "email",
        """From: {P1} <{E1}>
To: {P2} <{E2}>
Subject: Change of address

Hello,

I have moved house. My new address is {A1}. Could you update my file and send the next statement there?

I can be reached on {T1} during the day.

Best,
{P1}""",
    ),
    (
        "support_chat",
        """[Customer] Hi, my order {REF} never arrived.
[Agent {P2F}] Hi, let me check. Can you confirm your name and the delivery address?
[Customer] {P1}, {A1}.
[Agent {P2F}] Thanks {P1C}. The parcel is held at the depot. I can book a new delivery for {DAY}.
[Customer] OK. The driver can call me on {T1}.
[Agent {P2F}] Noted. You will get a confirmation at {E1}.""",
    ),
    (
        "support_chat",
        """[Customer] Hello, I was charged twice for my subscription this month.
[Agent] Sorry about that. To find the contract I need the account holder and the IBAN that was debited.
[Customer] It's under {P1}, IBAN {I1}.
[Agent] Thank you. I can see two debits of {AMOUNT} GBP. I'm refunding the second one now.
[Customer] Great. My partner, {P2}, got the same letter, is that normal?
[Agent] Yes, {P2C} is a joint holder and receives a copy. The refund will arrive within five working days.""",
    ),
    (
        "contract",
        """ASSURED SHORTHOLD TENANCY AGREEMENT

This agreement is made between
{P1}, of {A1} (the Landlord),
and {P2}, National Insurance number {N1} (the Tenant).

1. The Landlord lets the property at {A2} to the Tenant for a term of twelve months.
2. The rent is {AMOUNT} GBP per month, paid by transfer to {I1}.
3. Notices to the Landlord shall be sent to {P1C} by email at {E1}.

Signed in two copies.""",
    ),
    (
        "contract",
        """CONTRACT VARIATION No. {REF}

Between {ORG}, represented by {P2}, HR Director,
and {P1}, employee, National Insurance number {N1},

the parties agree as follows.

1. From 1 November, {P1C} will work remotely three days a week.
2. Salary continues to be paid into account {I1}.
3. The employee remains reachable on {T1} during core hours.""",
    ),
    (
        "medical",
        """CLINIC LETTER

Patient: {P1}, NHS number {N1}
Address: {A1}
GP: Dr {P2L}

Reason: lower back pain for three weeks, no trauma.
Examination: no neurological deficit. Right paravertebral spasm.
Plan: ten sessions of physiotherapy, simple analgesia.

{P1C} will be reviewed in one month. If symptoms worsen, contact the clinic on {T2}.

Dr {P2}""",
    ),
    (
        "medical",
        """Discharge summary, cardiology

Dear colleague,

I saw {P1}, referred by Dr {P2}, for atrial fibrillation found on routine screening. Anticoagulation has been started. {P1C} is independent and lives with his wife.

A Holter monitor is booked for {DAY}. The patient can be reached on {T1}, his wife {P3} on {T2}.

Yours sincerely,
Dr {P4}""",
    ),
    (
        "hr",
        """HR note, annual review

Employee: {P1}
Manager: {P2}

{P1C} met four of five objectives and would like to move into a project lead role. {P2C} supports the request and suggests training in the first half of the year.

Watch point: heavy workload in September.
Current contact details: {E1}, {T1}, {A1}.""",
    ),
    (
        "hr",
        """Report to HR

On {DAY} morning, {P1} reported a conflict with their line manager, {P2}. According to {P1C}, the discussion became heated during the team meeting. Two witnesses were present, {P3} and {P4}.

HR proposes mediation. {P1F} asks to be contacted by email only, at {E1}.

Case owner: {P5}.""",
    ),
    (
        "minutes",
        """Minutes, steering committee for project {REF}

Present: {P1}, {P2}, {P3}, {P4}, {P5}, {P6}
Apologies: {P7}, {P8}

1. Schedule. {P1C} presented the new timeline. {P3C} flagged a delay in testing.
2. Budget. {P2} noted that 70% of the {AMOUNT} GBP budget is spent.
3. Hiring. {P4} and {P5} will run the interviews.
4. AOB. {P6C} asked for the minutes to be sent to {E1}.

Next meeting {DAY}.""",
    ),
    (
        "minutes",
        """On-call rota, November

Week 1: {P1} ({T1})
Week 2: {P2} ({T2})
Week 3: {P3}
Week 4: {P4}
Backups: {P5}, {P6}

If you are unavailable, tell {P7}, the coordinator, at {E1}, with {P8} in copy.
Swaps between colleagues need no prior approval.""",
    ),
    (
        "email",
        """Subject: Claim {REF}

Dear Sir or Madam,

Following the water damage on {DAY}, please find the claim documents attached. The policyholder, {P1}, lives at {A1}. The upstairs neighbour, {P2}, has accepted liability.

The loss adjuster can contact {P1C} on {T1} or by email at {E1}. The settlement will be paid into {I1}.

Yours faithfully,
{P3}, claims handler, {ORG}""",
    ),
    (
        "support_chat",
        """[User] I can't log in to my account any more.
[Support {P2F}] Hi! To verify your identity, what is the email on the account?
[User] {E1}
[Support {P2F}] Thanks. The account is under {P1}, is that right?
[User] Yes.
[Support {P2F}] I'm sending a code by text to {T1}. You can then choose a new password.
[User] Got it, thanks a lot.""",
    ),
]


GENDER: dict[tuple[str, int], dict[str, str]] = {
    ("fr", 3): {"P2": "m"},
    ("fr", 5): {"P1": "m", "P2": "f"},
    ("fr", 6): {"P1": "m"},
    ("fr", 7): {"P1": "m", "P3": "f"},
    ("fr", 8): {"P1": "f"},
    ("fr", 9): {"P1": "m"},
    ("fr", 11): {"P7": "f"},
    ("en", 7): {"P1": "m", "P3": "f"},
}
"""Grammatical gender a template's wording requires, by language and index."""
