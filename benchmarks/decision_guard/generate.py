# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost"]
#
# [tool.uv.sources]
# piighost = { path = "../..", editable = true }
# ///
"""Build the decision-guard data set: de-identified texts, half of them leaking.

Every text starts as a synthetic source document (templates.py, filled with
fictitious values). piighost then de-identifies it. The detector is an
ExactMatchDetector given the values the generator put in, so the ground truth
is exact: a clean text has no value left in clear, by construction, and a
leaking text has exactly the leak the generator chose.

A leak is made the way a real pipeline misses a value. The detector is not told
about it (a name, an email, a phone, an IBAN, an address or an ID number left
in clear), is told about only part of it (a first name beside a surname
placeholder, the tail of an IBAN), is told about the full name but not the
surname alone (a later "Mme Dubois"), or the source breaks the value across a
line in a way an exact match cannot follow (a wrap after the @ of an email, in
the middle of an IBAN group, a hyphenated surname or street name).

Every text is checked after de-identification. A clean text with any value
left, or a leaking text whose leak is missing or which leaks something else, is
rejected and redrawn, so no label is a guess.

Run with:
uv run benchmarks/decision_guard/generate.py
"""

import asyncio
import json
import random
import re
import unicodedata
from pathlib import Path

from templates import EN, FR, GENDER

from piighost.components.detector import ExactMatchDetector
from piighost.components.overlap_resolver.merge import MergeOverlapResolver
from piighost.pipeline import AnonymizationPipeline

SEED = 20261006
PER_LANGUAGE = 100
"""Texts per language, half clean and half leaking."""

OUT = Path(__file__).parent / "data" / "texts.jsonl"
TWINS = Path(__file__).parent / "data" / "twins.jsonl"
"""Each leaking text with its leak replaced by a placeholder, for a paired test."""

LEAK_TYPES = (
    "name",
    "email",
    "phone",
    "iban",
    "address",
    "id",
    "partial",
    "split",
    "variant",
)

SUBTYPES = {
    "partial": ("first_name_left", "iban_tail"),
    "split": (
        "email_after_at",
        "iban_mid_group",
        "surname_hyphenated",
        "street_hyphenated",
    ),
}
"""The ways a partial or split leak is made, taken in turn."""

NAMES = {
    "fr": {
        "f": [
            "Claire",
            "Sophie",
            "Camille",
            "Élodie",
            "Léa",
            "Manon",
            "Inès",
            "Nadia",
            "Margaux",
            "Aurélie",
            "Chloé",
            "Fatima",
            "Hélène",
            "Agathe",
            "Sabrina",
            "Pauline",
        ],
        "m": [
            "Julien",
            "Mathieu",
            "Nicolas",
            "Thomas",
            "Antoine",
            "Hugo",
            "Karim",
            "Yannick",
            "Bastien",
            "Sébastien",
            "Romain",
            "Olivier",
            "Damien",
            "Florent",
            "Mehdi",
            "Grégoire",
        ],
        "last": [
            "Dubois",
            "Lefèvre",
            "Moreau",
            "Garnier",
            "Rousseau",
            "Fontaine",
            "Chevalier",
            "Mercier",
            "Bertrand",
            "Lambert",
            "Girard",
            "Bonnet",
            "Faure",
            "Mallet",
            "Benali",
            "Nguyen",
            "Perrin",
            "Marchand",
            "Roche",
            "Collet",
            "Vidal",
            "Lemaire",
            "Caron",
            "Delacroix",
            "Besnard",
            "Texier",
            "Guillot",
            "Ferrand",
            "Haddad",
            "Morvan",
        ],
    },
    "en": {
        "f": [
            "Emily",
            "Olivia",
            "Hannah",
            "Sarah",
            "Megan",
            "Laura",
            "Priya",
            "Grace",
            "Rachel",
            "Chloe",
            "Aisha",
            "Natalie",
            "Fiona",
            "Imogen",
            "Bethany",
            "Zoe",
        ],
        "m": [
            "James",
            "Daniel",
            "Michael",
            "Ryan",
            "David",
            "Kevin",
            "Samuel",
            "Owen",
            "Marcus",
            "Liam",
            "Patrick",
            "Callum",
            "Joseph",
            "Ethan",
            "Nathan",
            "Rhys",
        ],
        "last": [
            "Carter",
            "Whitfield",
            "Bennett",
            "Hughes",
            "Sullivan",
            "Thornton",
            "Gallagher",
            "Patel",
            "Morrison",
            "Reyes",
            "Fletcher",
            "Donovan",
            "Brooks",
            "Kowalski",
            "Okafor",
            "Lindqvist",
            "Chambers",
            "Holloway",
            "Pearce",
            "Nolan",
            "Wainwright",
            "Delgado",
            "Sinclair",
            "Ashworth",
            "Pemberton",
            "Radcliffe",
            "Mahmood",
            "Fitzgerald",
            "Hargreaves",
            "Quinlan",
        ],
    },
}

CIVILITY = {"fr": {"f": "Mme", "m": "M."}, "en": {"f": "Ms", "m": "Mr"}}

DOMAINS = {
    "fr": [
        "gmail.com",
        "orange.fr",
        "free.fr",
        "laposte.net",
        "outlook.fr",
        "yahoo.fr",
        "sfr.fr",
    ],
    "en": [
        "gmail.com",
        "outlook.com",
        "yahoo.co.uk",
        "icloud.com",
        "hotmail.co.uk",
        "proton.me",
        "btinternet.com",
    ],
}

ORGS = {
    "fr": [
        "Assurances Valmont",
        "Groupe Arceaux",
        "Logistique Belleville",
        "Mutuelle Horizon",
        "Éditions Cassini",
    ],
    "en": [
        "Northwind Lettings",
        "Harbourside Insurance",
        "Kestrel Logistics",
        "Brightwater Mutual",
        "Ashgrove Software",
    ],
}

DAYS = {
    "fr": ["lundi", "mardi", "mercredi", "jeudi", "vendredi"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
}

STREETS = {
    "fr": [
        "rue des Marronniers",
        "avenue Jean-Jaurès",
        "rue de la République",
        "boulevard Voltaire",
        "impasse des Tilleuls",
        "chemin des Vignes",
        "rue Pasteur",
        "allée des Peupliers",
    ],
    "en": [
        "Elm Grove",
        "Station Road",
        "Kingsley Avenue",
        "Mill Lane",
        "Chesterfield Road",
        "Willow Crescent",
        "Victoria Street",
        "Orchard Close",
    ],
}

CITIES = {
    "fr": [
        ("69003", "Lyon"),
        ("33000", "Bordeaux"),
        ("44000", "Nantes"),
        ("31000", "Toulouse"),
        ("67000", "Strasbourg"),
        ("59000", "Lille"),
        ("35000", "Rennes"),
        ("13006", "Marseille"),
    ],
    "en": [
        ("Leeds", "LS6 2AB"),
        ("Bristol", "BS7 8QT"),
        ("Manchester", "M14 5RG"),
        ("Sheffield", "S10 2HW"),
        ("Norwich", "NR2 3LP"),
        ("York", "YO10 4DE"),
        ("Cardiff", "CF24 4HQ"),
        ("Brighton", "BN2 1TL"),
    ],
}

PLACEHOLDER = re.compile(r"<<[A-Z_]+:\d+>>")


def ascii_lower(text: str) -> str:
    """Strip accents and lowercase, for the local part of an email."""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", folded.lower())


def mod97_check(country: str, bban: str) -> str:
    """Return the two IBAN check digits for a country and a BBAN."""
    rearranged = bban + country + "00"
    digits = "".join(str(int(c, 36)) for c in rearranged)
    return f"{98 - int(digits) % 97:02d}"


def group4(text: str) -> str:
    """Write an IBAN in groups of four, as it is printed."""
    return " ".join(text[i : i + 4] for i in range(0, len(text), 4))


class Faker:
    """Draw fictitious values for one language, from a seeded generator."""

    def __init__(self, lang: str, rng: random.Random) -> None:
        """Store the language and the seeded random generator to draw from."""
        self.lang = lang
        self.rng = rng

    def person(self, gender: str, used: set[str]) -> dict[str, str]:
        """Draw a person whose first name and surname are unused in the text."""
        pool = NAMES[self.lang]
        while True:
            first = self.rng.choice(pool[gender])
            last = self.rng.choice(pool["last"])
            if first not in used and last not in used:
                used.update((first, last))
                civ = CIVILITY[self.lang][gender]
                return {
                    "full": f"{first} {last}",
                    "first": first,
                    "last": last,
                    "civ": f"{civ} {last}",
                }

    def email(self, person: dict[str, str]) -> str:
        """An address built from the name, in a form a word match on it misses."""
        first, last = ascii_lower(person["first"]), ascii_lower(person["last"])
        local = self.rng.choice(
            [
                f"{first}_{last}",
                f"{first[0]}{last}",
                f"{first}{last}{self.rng.randint(10, 99)}",
                f"{last}_{first}",
            ]
        )
        return f"{local}@{self.rng.choice(DOMAINS[self.lang])}"

    def phone(self) -> str:
        """Draw a phone number, a French mobile or a UK drama-range number."""
        r = self.rng
        if self.lang == "fr":
            prefix = r.choice(["06", "07", "01", "04", "05"])
            return prefix + "".join(f" {r.randint(10, 99)}" for _ in range(4))
        # Ofcom's drama ranges: never assigned to a real line.
        return r.choice(
            [
                f"07700 900{r.randint(100, 999)}",
                f"020 7946 0{r.randint(100, 999)}",
                f"0113 496 0{r.randint(100, 999)}",
            ]
        )

    def iban(self) -> str:
        """Draw an IBAN, French or UK, with a valid mod-97 check digit."""
        r = self.rng
        if self.lang == "fr":
            bban = "".join(str(r.randint(0, 9)) for _ in range(23))
            return group4("FR" + mod97_check("FR", bban) + bban)
        bank = r.choice(["NWBK", "BARC", "LOYD", "MIDL"])
        bban = bank + "".join(str(r.randint(0, 9)) for _ in range(14))
        return group4("GB" + mod97_check("GB", bban) + bban)

    def address(self) -> str:
        """Draw a postal address for the language, with a street, city and code."""
        r = self.rng
        street = r.choice(STREETS[self.lang])
        if self.lang == "fr":
            zip_code, city = r.choice(CITIES["fr"])
            return f"{r.randint(2, 140)} {street}, {zip_code} {city}"
        city, postcode = r.choice(CITIES["en"])
        return f"{r.randint(2, 140)} {street}, {city} {postcode}"

    def id_number(self, genre: str) -> str:
        """Draw a French NIR, or a UK NHS or National Insurance number by genre."""
        r = self.rng
        if self.lang == "fr":
            body = f"{r.choice('12')}{r.randint(60, 99)}{r.randint(1, 12):02d}{r.randint(1, 95):02d}{r.randint(1, 999):03d}{r.randint(1, 999):03d}"
            key = 97 - int(body) % 97
            return f"{body[0]} {body[1:3]} {body[3:5]} {body[5:7]} {body[7:10]} {body[10:13]} {key:02d}"
        if genre == "medical":
            return f"999 {r.randint(100, 999)} {r.randint(1000, 9999)}"  # NHS-style, no valid check digit
        # QQ is the prefix the DWP reserves for examples.
        return f"QQ {r.randint(10, 99)} {r.randint(10, 99)} {r.randint(10, 99)} {r.choice('ABCD')}"


SLOT = re.compile(r"\{([A-Z]+)(\d*)([FLC]?)\}")


def slots(template: str) -> set[str]:
    """Return the slot names found in a template, such as P1 or E2."""
    return {m.group(0)[1:-1] for m in SLOT.finditer(template)}


def fill(
    lang: str, index: int, genre: str, template: str, faker: Faker
) -> tuple[str, dict]:
    """Fill a template; return the source and the values it holds, by kind."""
    found = slots(template)
    constraints = GENDER.get((lang, index), {})
    used: set[str] = set()
    persons = {}
    for k in sorted(
        {int(m.group(2)) for m in SLOT.finditer(template) if m.group(1) == "P"}
    ):
        gender = constraints.get(f"P{k}") or faker.rng.choice("fm")
        persons[k] = faker.person(gender, used)
    emails = {
        k: faker.email(persons.get(k) or faker.person("f", used))
        for k in (1, 2)
        if f"E{k}" in found
    }
    phones = {k: faker.phone() for k in (1, 2) if f"T{k}" in found}
    addresses = {k: faker.address() for k in (1, 2) if f"A{k}" in found}
    iban = faker.iban() if "I1" in found else None
    id_number = faker.id_number(genre) if "N1" in found else None

    r = faker.rng
    plain = {
        "REF": str(r.randint(10000, 99999)),
        "ORG": r.choice(ORGS[lang]),
        "DAY": r.choice(DAYS[lang]),
        "AMOUNT": f"{r.randint(40, 2400)}",
    }

    def value(match: re.Match) -> str:
        kind, k, form = match.group(1), match.group(2), match.group(3)
        if kind == "P":
            person = persons[int(k)]
            return {
                "": person["full"],
                "F": person["first"],
                "L": person["last"],
                "C": person["civ"],
            }[form]
        if kind == "E":
            return emails[int(k)]
        if kind == "T":
            return phones[int(k)]
        if kind == "A":
            return addresses[int(k)]
        if kind == "I":
            return iban
        if kind == "N":
            return id_number
        return plain[kind]

    source = SLOT.sub(value, template)
    return source, {
        "persons": persons,
        "emails": emails,
        "phones": phones,
        "addresses": addresses,
        "iban": iban,
        "id": id_number,
    }


def detector_values(values: dict) -> dict[str, str]:
    """Every value the generator put in, mapped to its piighost label."""
    out: dict[str, str] = {}
    for person in values["persons"].values():
        for form in ("full", "first", "last"):
            out[person[form]] = "PERSON"
    for email in values["emails"].values():
        out[email] = "EMAIL"
    for phone in values["phones"].values():
        out[phone] = "PHONE"
    for address in values["addresses"].values():
        out[address] = "ADDRESS"
    if values["iban"]:
        out[values["iban"]] = "IBAN"
    if values["id"]:
        out[values["id"]] = "ID_NUMBER"
    return out


def hyphenate(word: str) -> str:
    """Break a word over two lines with a hyphen, as PDF extraction leaves it."""
    cut = max(2, len(word) // 2)
    return word[:cut] + "-\n" + word[cut:]


def inject(
    leak: str,
    template: str,
    source: str,
    values: dict,
    rng: random.Random,
    prefer: str | None,
) -> tuple[str, dict[str, str], str, set[str], str] | None:
    """Apply one leak to the source or the detector's values.

    Returns the new source, the detector values, the subtype, the strings the
    detector was not told about, and the leaked string expected in the output,
    or None when the template cannot carry this leak. prefer names the subtype
    of a partial or split leak, so the subtypes are spread evenly.
    """
    found = slots(template)
    known = detector_values(values)
    persons = values["persons"]
    full_slots = sorted(int(s[1:]) for s in found if re.fullmatch(r"P\d", s))

    def withhold(*strings: str) -> None:
        for s in strings:
            known.pop(s, None)

    if leak == "name" and full_slots:
        p = persons[rng.choice(full_slots)]
        withhold(p["full"], p["first"], p["last"])
        return source, known, "full_name", {p["full"], p["first"], p["last"]}, p["full"]
    if leak == "variant":
        ks = [k for k in full_slots if f"P{k}C" in found or f"P{k}L" in found]
        if ks:
            p = persons[rng.choice(ks)]
            withhold(p["last"])
            return source, known, "surname_alone", {p["last"]}, p["last"]
    if leak == "partial":
        options = []
        if full_slots:
            options.append("first_name_left")
        if values["iban"]:
            options.append("iban_tail")
        if prefer in options:
            sub = prefer
            if sub == "first_name_left":
                p = persons[rng.choice(full_slots)]
                withhold(p["full"], p["first"])
                return source, known, sub, {p["full"], p["first"]}, p["first"]
            iban = values["iban"]
            groups = iban.split(" ")
            withhold(iban)
            known[" ".join(groups[:3])] = "IBAN"
            return source, known, sub, {iban}, " ".join(groups[3:])
    if leak == "email" and values["emails"]:
        email = rng.choice(list(values["emails"].values()))
        withhold(email)
        return source, known, "email", {email}, email
    if leak == "phone" and values["phones"]:
        phone = rng.choice(list(values["phones"].values()))
        withhold(phone)
        return source, known, "phone", {phone}, phone
    if leak == "iban" and values["iban"]:
        withhold(values["iban"])
        return source, known, "iban", {values["iban"]}, values["iban"]
    if leak == "address" and values["addresses"]:
        address = rng.choice(list(values["addresses"].values()))
        withhold(address)
        return source, known, "address", {address}, address
    if leak == "id" and values["id"]:
        withhold(values["id"])
        return source, known, "id_number", {values["id"]}, values["id"]
    if leak == "split":
        options = []
        if values["emails"]:
            options.append("email_after_at")
        if values["iban"]:
            options.append("iban_mid_group")
        if full_slots:
            options.append("surname_hyphenated")
        if values["addresses"]:
            options.append("street_hyphenated")
        if prefer in options:
            sub = prefer
            if sub == "email_after_at":
                original = rng.choice(list(values["emails"].values()))
                broken = original.replace("@", "@\n")
            elif sub == "iban_mid_group":
                original = values["iban"]
                cut = 12  # inside the third group: "FR76 3000 40\n00 ..."
                broken = original[:cut] + "\n" + original[cut:]
            elif sub == "surname_hyphenated":
                p = persons[rng.choice(full_slots)]
                original = p["full"]
                broken = f"{p['first']} {hyphenate(p['last'])}"
            else:
                original = rng.choice(list(values["addresses"].values()))
                _number, rest = original.split(" ", 1)
                words = [w for w in rest.split(",")[0].split(" ") if "-" not in w]
                word = max(words, key=len)
                broken = original.replace(word, hyphenate(word), 1)
            if original not in source:
                return None
            source = source.replace(original, broken, 1)
            leaked = broken
            if sub == "surname_hyphenated":
                leaked = broken.split(" ", 1)[1]  # the first name is still matched
            return source, known, sub, set(), leaked
    return None


def word_found(value: str, text: str) -> bool:
    """Check whether value appears in text as a whole word, case-insensitively."""
    return (
        re.search(r"(?<![\w-])" + re.escape(value) + r"(?![\w-])", text, re.IGNORECASE)
        is not None
    )


def sensitive(values: dict) -> list[str]:
    """Return the sensitive values the generator put in, without their labels."""
    return list(detector_values(values))


async def deidentify(source: str, known: dict[str, str]) -> str:
    """De-identify source with an exact-match detector seeded with known values."""
    pipeline = AnonymizationPipeline(
        ExactMatchDetector(known), overlap_resolver=MergeOverlapResolver()
    )
    result = await pipeline.anonymize(source)
    return result.text


def valid(output: str, values: dict, withheld: set[str], leaked: str | None) -> bool:
    """Check the label: nothing left in clear but the leak the generator chose."""
    left = [v for v in sensitive(values) if word_found(v, output)]
    if leaked is None:
        return not left
    if leaked not in output:
        return False
    return all(v in withheld or v in leaked for v in left)


async def build(lang: str, rng: random.Random) -> list[dict]:
    """Build the de-identified rows for one language, half clean and half leaking."""
    templates = FR if lang == "fr" else EN
    faker = Faker(lang, rng)
    rows = []
    half = PER_LANGUAGE // 2
    plan = [None] * half + [LEAK_TYPES[i % len(LEAK_TYPES)] for i in range(half)]
    turns = {"partial": 0, "split": 0}
    for n, leak in enumerate(plan):
        prefer = None
        if leak in SUBTYPES:
            prefer = SUBTYPES[leak][turns[leak] % len(SUBTYPES[leak])]
            turns[leak] += 1
        for _attempt in range(200):
            index = (
                n % len(templates) if leak is None else rng.randrange(len(templates))
            )
            genre, template = templates[index]
            source, values = fill(lang, index, genre, template, faker)
            if leak is None:
                known, subtype, withheld, leaked = (
                    detector_values(values),
                    None,
                    set(),
                    None,
                )
            else:
                injected = inject(leak, template, source, values, rng, prefer)
                if injected is None:
                    continue
                source, known, subtype, withheld, leaked = injected
            output = await deidentify(source, known)
            if valid(output, values, withheld, leaked):
                break
        else:
            raise RuntimeError(f"could not build a valid {lang} text for {leak}")
        start = output.find(leaked) if leaked else -1
        rows.append(
            {
                "id": f"{lang}-{n:03d}",
                "lang": lang,
                "genre": genre,
                "template": index,
                "leak": leak is not None,
                "leak_type": leak,
                "leak_subtype": subtype,
                "leaked_value": leaked,
                "leak_span": [start, start + len(leaked)] if leaked else None,
                "placeholders": len(PLACEHOLDER.findall(output)),
                "chars": len(output),
                "text": output,
                "source": source,
            }
        )
    return rows


TWIN_LABEL = {
    "name": "PERSON",
    "variant": "PERSON",
    "first_name_left": "PERSON",
    "surname_hyphenated": "PERSON",
    "email": "EMAIL",
    "email_after_at": "EMAIL",
    "phone": "PHONE",
    "iban": "IBAN",
    "iban_mid_group": "IBAN",
    "address": "ADDRESS",
    "street_hyphenated": "ADDRESS",
    "id": "ID_NUMBER",
}
"""The placeholder that takes the leak's place in its clean twin."""


def twin(row: dict) -> dict:
    """The same leaking text with its leak replaced by a placeholder.

    The pair differs only by the leak, so a guard that reads the leak scores
    the leaking text above its twin. A guard that reacts to the template, the
    genre or the placeholders scores them alike.
    """
    text, leaked = row["text"], row["leaked_value"]
    if row["leak_subtype"] == "iban_tail":
        clean = text.replace(" " + leaked, "")
    else:
        key = (
            row["leak_subtype"]
            if row["leak_type"] in ("partial", "split")
            else row["leak_type"]
        )
        label = TWIN_LABEL[key]
        used = [int(n) for n in re.findall(rf"<<{label}:(\d+)>>", text)]
        token = f"<<{label}:{max(used, default=0) + 1}>>"
        clean = text.replace(leaked, token)
        if row["leak_type"] == "name":
            for part in leaked.split(" "):
                clean = re.sub(rf"(?<![\w-]){re.escape(part)}(?![\w-])", token, clean)
    assert leaked not in clean, row["id"]
    return {
        **row,
        "id": row["id"] + "-twin",
        "twin_of": row["id"],
        "leak": False,
        "text": clean,
        "placeholders": len(PLACEHOLDER.findall(clean)),
        "chars": len(clean),
        "leak_span": None,
    }


async def main() -> None:
    """Generate the French and English rows and write texts.jsonl and twins.jsonl."""
    rng = random.Random(SEED)
    rows = await build("fr", rng) + await build("en", rng)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with TWINS.open("w", encoding="utf-8") as handle:
        for row in rows:
            if row["leak"]:
                handle.write(json.dumps(twin(row), ensure_ascii=False) + "\n")
    leaks = sum(r["leak"] for r in rows)
    print(
        f"{len(rows)} texts, {leaks} leaking, written to {OUT}, and their {leaks} clean twins to {TWINS}"
    )


if __name__ == "__main__":
    asyncio.run(main())
