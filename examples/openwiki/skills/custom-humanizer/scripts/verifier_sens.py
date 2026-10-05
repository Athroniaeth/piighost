#!/usr/bin/env python3
"""Compare un texte source et sa réécriture : faits durs et mots qui portent le sens.

Usage : verifier_sens.py AVANT AFTER     (code retour 1 si un fait dur est perdu ou ajouté)
        verifier_sens.py --selftest

Faits durs : nombres, code en ligne, blocs de code, URL. Toute différence = à corriger ou justifier.
Mots porteurs : négations, conditions, quantificateurs, modalité, personne grammaticale.
Un écart n'est pas forcément une erreur : c'est une phrase à relire.
"""
import re
import sys
from collections import Counter

PORTEURS = {
    "fr": {
        "négation": "ne n pas jamais aucun aucune rien sans sauf ni",
        "condition": "si sous_réserve tant_que à_condition_que",
        "quantité": "seul seule seuls seules seulement uniquement tous toutes chaque environ quelques certains "
                    "certaines au_moins au_plus plus_de moins_de",
        "modalité": "peut peuvent pourrait doit doivent devrait",
        "personne": "je j me moi nous on vous tu",
    },
    "en": {
        "négation": "not no never none nothing without except nor",
        "condition": "if unless until provided_that",
        "quantité": "only all every each some any about approximately most few several at_least at_most "
                    "more_than less_than",
        "modalité": "may might must should can could would",
        "personne": "i me my we our us you your",
    },
}

def normaliser(texte):
    texte = texte.replace("’", "\'").replace("\u00a0", " ").replace("\u202f", " ")
    return texte

def nombres(texte):
    # « 1 200 », « 1,200 » et « 1200 » sont le même nombre ; « 2,5 » reste décimal.
    bruts = re.findall(r"\d{1,3}(?:[ .,]\d{3})+(?:[.,]\d+)?(?!\d)|\d+(?:[.,]\d+)?", texte)
    sortie = Counter()
    for n in bruts:
        n = re.sub(r"[ .,](?=\d{3}(?!\d))", "", n)
        sortie[n] += 1
    return sortie

def faits_durs(texte):
    t = normaliser(texte)
    blocs = Counter(re.findall(r"```.*?```", t, re.S))
    sans_blocs = re.sub(r"```.*?```", " ", t, flags=re.S)
    return {
        "nombres": nombres(re.sub(r"https?://\S+", " ", sans_blocs)),
        "code": Counter(re.findall(r"`[^`\n]+`", sans_blocs)),
        "blocs de code": blocs,
        "URL": Counter(re.findall(r"https?://[^\s)>\]]+", t)),
    }

def langue(texte):
    mots = re.findall(r"\w+", texte.lower())
    fr = sum(m in {"le", "la", "les", "et", "des", "est", "une"} for m in mots)
    en = sum(m in {"the", "and", "of", "is", "to", "a"} for m in mots)
    return "fr" if fr >= en else "en"

def porteurs(texte, lang):
    t = normaliser(texte).lower()
    t = re.sub(r"```.*?```|`[^`\n]+`|https?://\S+", " ", t, flags=re.S)
    t = re.sub(r"\b(?:not only|non seulement)\b", " ", t)  # tournure de contraste, pas une négation
    sortie = {}
    for famille, liste in PORTEURS[lang].items():
        compte = Counter()
        for terme in liste.split():
            n = len(re.findall(r"(?<!\w)" + terme.replace("_", r"\s+") + r"(?!\w)", t))
            if n:
                compte[terme.replace("_", " ")] = n
        sortie[famille] = compte
    return sortie

def comparer(avant, apres):
    lignes, bloquant = [], False
    fa, fb = faits_durs(avant), faits_durs(apres)
    for cle in fa:
        perdus, ajoutes = fa[cle] - fb[cle], fb[cle] - fa[cle]
        if perdus or ajoutes:
            bloquant = True
            if perdus:
                lignes.append(f"PERDU   {cle} : {', '.join(sorted(perdus.elements()))}")
            if ajoutes:
                lignes.append(f"AJOUTÉ  {cle} : {', '.join(sorted(ajoutes.elements()))}")
    lang = langue(avant)
    pa, pb = porteurs(avant, lang), porteurs(apres, lang)
    for famille in pa:
        diff = [f"{m} {pa[famille][m]}→{pb[famille][m]}"
                for m in sorted(set(pa[famille]) | set(pb[famille])) if pa[famille][m] != pb[famille][m]]
        if diff:
            lignes.append(f"RELIRE  {famille} : {', '.join(diff)}")
    if not lignes:
        lignes.append("OK      aucun écart sur les faits durs ni sur les mots porteurs")
    return bloquant, lignes

def selftest():
    avant = "La bascule a lieu le 4 novembre, sous réserve de validation. 1 200 tests, `make test`."
    apres = "On bascule le 4 novembre si la recette passe. 1200 tests, `make test`."
    bloquant, lignes = comparer(avant, apres)
    texte = "\n".join(lignes)
    assert not bloquant, texte                      # 1 200 == 1200, code identique
    assert "sous réserve 1→0" in texte, texte       # condition reformulée -> à relire
    assert "on 0→1" in texte, texte                 # changement de personne -> à relire
    bloquant, lignes = comparer("Some of the emails go to 3 sessions.", "The emails go to 4 sessions.")
    assert bloquant and any("PERDU   nombres : 3" in l for l in lignes), lignes
    assert any("some 1→0" in l for l in lignes), lignes
    _, lignes = comparer("This is not only fast but also cheap.", "This is fast and cheap.")
    assert not any("not" in l or "only" in l for l in lignes), lignes
    assert nombres("2,5 et 1,247 et 15 000") == Counter({"2,5": 1, "1247": 1, "15000": 1})
    print("selftest OK")

if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        selftest()
        sys.exit(0)
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as a, open(sys.argv[2], encoding="utf-8") as b:
        bloquant, lignes = comparer(a.read(), b.read())
    print("\n".join(lignes))
    sys.exit(1 if bloquant else 0)
