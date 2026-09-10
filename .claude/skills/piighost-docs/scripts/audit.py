#!/usr/bin/env python3
"""Audit docs/en and docs/fr against the mechanical rules of the piighost-docs skill.

Run from the repository root:

    python3 .claude/skills/piighost-docs/scripts/audit.py

Checks, in order:

- mechanical rules: semicolon, em dash, guillemets, bold brand, bare package name,
  apposition colon, attr_list on bare text, cross-language link
- terminology: anonymisation / anonymization left in prose, and the banned inverse
  vocabulary (desanonymiser, re-anonymiser, deanonymize outside code)
- EN/FR parity: same files, same heading skeleton, same number of code and mermaid
  blocks, same admonition sequence
- links: every relative markdown link resolves to a file that exists
- nav: every page is declared in its language's nav, and every nav entry has a page

Prose only. Fenced code blocks, inline code spans, whole markdown links and YAML
frontmatter are excluded, so identifiers such as Anonymizer or deanonymize never
trigger a prose rule.

Exit code is 1 when anything is found and 0 otherwise, so the script doubles as a
gate; the count is printed rather than returned, since an exit code wraps at 256.
"""

from __future__ import annotations

import pathlib
import re
import sys
import tomllib

EN = pathlib.Path("docs/en")
FR = pathlib.Path("docs/fr")

PROTECT = re.compile(r"(`[^`]*`|\[[^\]]*\]\([^)]*\)|<[^>]+>)")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})\s*(\w*)")
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

# The nav config of each language, paired with the docs_dir it addresses.
NAVS = (("zensical.toml", EN), ("zensical.fr.toml", FR))

# Pages the nav never lists: an include is pulled in by a snippet, not navigated to.
NAV_EXEMPT = ("includes/",)

# Lines that deliberately contrast de-identification with anonymisation. Keyed by
# the marker they carry, so the list survives a page being re-flowed.
CONTRAST = re.compile(
    r"pseudonymi[sz]ation"                       # the sentence that draws the line
    r"|anonymi[sz]ation,\s+(not|pas)"            # "anonymisation, pas ..."
    r"|(pas|not)\s+(de\s+l\'|d\'|an?\s+|une\s+)?anonymi[sz]ation"   # "... pas anonymisation"
    r"|(word|mot|terme)\s+anonymi[sz]ation"
    r"|\*\*anonymi[sz]ation\*\*"
    r"|^anonymi[sz]ation\b"                      # the glossary entry itself
    r"|k-anonymity"
    r"|(dataset\s+anonymi[sz]ers|anonymi[sz]eurs\s+de\s+dataset)"
    r"|redact|caviardage",                       # redaction genuinely anonymises
    re.IGNORECASE,
)


def prose_lines(path: pathlib.Path):
    """Yield (lineno, raw line) for prose lines: no frontmatter, no fenced code."""
    lines = path.read_text(encoding="utf-8").split("\n")
    start = 0
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                start = j + 1
                break
    infence, fence = False, None
    for i in range(start, len(lines)):
        line = lines[i]
        m = FENCE.match(line)
        if m:
            tok = m.group(1)[0]
            if not infence:
                infence, fence = True, tok
            elif tok == fence:
                infence, fence = False, None
            continue
        if infence:
            continue
        yield i + 1, line


def strip_protected(line: str) -> str:
    """Drop inline code, whole links and html so only prose is left."""
    return "".join(p for p in PROTECT.split(line) if p and not PROTECT.fullmatch(p))


def _is_apposition(head: str, tail: str) -> bool:
    """True when a prose colon joins one clause to another, rather than opening a list.

    Three shapes are legitimate and stay:
    - a lead-in label, at most four words before the colon ("Built-in:", "Notes :")
    - an enumeration, two or more comma-separated items after the colon
    - two coordinated alternatives ("a score from a model, or the residual detections")
    """
    if len(head.split()) <= 4:
        return False
    if tail.count(",") >= 2:
        return False
    if re.search(r"\s(or|and|ou|et)\s", tail):
        return False
    return True


def mechanical(findings: list[str]) -> None:
    for lang in ("en", "fr"):
        for path in sorted(pathlib.Path(f"docs/{lang}").rglob("*.md")):
            for n, raw in prose_lines(path):
                stripped = raw.lstrip()
                prose = strip_protected(raw)
                where = f"{path}:{n}"
                if ";" in prose:
                    findings.append(f"{where}: point-virgule en prose")
                if "—" in prose or "–" in prose:
                    findings.append(f"{where}: tiret cadratin")
                if "«" in prose or "»" in prose:
                    findings.append(f"{where}: guillemets francais, utiliser \"")
                if re.search(r"\*\*PIIGhost\*\*", prose):
                    findings.append(f"{where}: PIIGhost en gras, utiliser `piighost`")
                if not raw.startswith("#") and re.search(r"\bpiighost\b", prose):
                    findings.append(f"{where}: piighost hors police code")
                if re.search(r"(?<!`)\{ \.(placeholder|pii) \}", raw):
                    findings.append(f"{where}: attr_list sur du texte nu")
                if re.search(r"\]\(\.\./(en|fr)/", raw):
                    findings.append(f"{where}: lien inter-langue")
                # apposition colon: a colon mid-sentence whose right side is one clause
                if not stripped.startswith(("#", "|", ":", "!!!", "???", "*[", "<", "-", "*")):
                    m = re.search(r'[a-zà-ÿ)\]"]\s?:\s+\S', prose)
                    if m and not re.search(r":\s*$", raw):
                        head, tail = prose[: m.start() + 1], prose[m.end() - 1:]
                        findings.extend(
                            [f"{where}: deux-points d'apposition"]
                            if _is_apposition(head, tail)
                            else []
                        )


def terminology(findings: list[str]) -> None:
    banned = re.compile(
        r"\bdés?[- ]?anonymis|\bré[- ]?anonymis|\bde[- ]?anonymiz|\bre[- ]?anonymiz",
        re.IGNORECASE,
    )
    for lang, word in (("fr", r"\banonymis"), ("en", r"\banonymiz")):
        for path in sorted(pathlib.Path(f"docs/{lang}").rglob("*.md")):
            for n, raw in prose_lines(path):
                prose = strip_protected(raw)
                if banned.search(prose):
                    findings.append(
                        f"{path}:{n}: vocabulaire inverse interdit, ecrire restaurer/restore"
                    )
                elif re.search(word, prose, re.IGNORECASE) and not CONTRAST.search(prose):
                    if not re.search(r"anonymi[sz]er|anonymiseur", prose, re.IGNORECASE):
                        findings.append(
                            f"{path}:{n}: anonymisation en prose, verifier la direction"
                        )


def parse_structure(path: pathlib.Path):
    heads, codes, mermaid, adm = [], [], [], []
    infence, fence, lang, buf = False, None, None, []
    for line in path.read_text(encoding="utf-8").split("\n"):
        m = FENCE.match(line)
        if m:
            tok = m.group(1)[0]
            if not infence:
                infence, fence, lang, buf = True, tok, m.group(2), []
            elif tok == fence:
                infence = False
                (mermaid if lang == "mermaid" else codes).append(lang)
            continue
        if infence:
            buf.append(line)
            continue
        h = re.match(r"^(#{1,6})\s", line)
        if h:
            heads.append(len(h.group(1)))
        a = re.match(r"^(!!!|\?\?\?)\s+(\w+)", line)
        if a:
            adm.append(a.group(2))
    return heads, codes, mermaid, adm


def parity(findings: list[str]) -> None:
    en_files = {p.relative_to(EN) for p in EN.rglob("*.md")}
    fr_files = {p.relative_to(FR) for p in FR.rglob("*.md")}
    for missing in sorted(en_files - fr_files):
        findings.append(f"docs/fr/{missing}: absent, le miroir FR manque")
    for missing in sorted(fr_files - en_files):
        findings.append(f"docs/en/{missing}: absent, le miroir EN manque")
    for rel in sorted(en_files & fr_files):
        eh, ec, em, ea = parse_structure(EN / rel)
        fh, fc, fm, fa = parse_structure(FR / rel)
        if eh != fh:
            findings.append(f"{rel}: structure de titres differente")
        if ec != fc:
            findings.append(f"{rel}: blocs de code differents ({len(ec)} EN, {len(fc)} FR)")
        if len(em) != len(fm):
            findings.append(f"{rel}: {len(em)} mermaid EN, {len(fm)} FR")
        if ea != fa:
            findings.append(f"{rel}: sequence d'admonitions differente")


def links(findings: list[str]) -> None:
    """Flag a relative markdown link whose target does not exist on disk.

    Only relative targets are resolved. An external scheme and a bare anchor are
    left to a link checker with network access, which this script is not.
    """
    for lang in ("en", "fr"):
        for path in sorted(pathlib.Path(f"docs/{lang}").rglob("*.md")):
            for n, raw in prose_lines(path):
                for m in LINK.finditer(raw):
                    target = m.group(1).split("#")[0].strip()
                    external = target.startswith(("http://", "https://", "mailto:"))
                    if not target or external:
                        continue
                    if not (path.parent / target).exists():
                        findings.append(f"{path}:{n}: lien mort vers {target}")


def nav_pages(entries: object) -> list[str]:
    """Flatten a zensical nav array into the page paths it declares."""
    if isinstance(entries, str):
        return [entries] if entries.endswith(".md") else []
    if isinstance(entries, list):
        return [page for entry in entries for page in nav_pages(entry)]
    if isinstance(entries, dict):
        return [page for entry in entries.values() for page in nav_pages(entry)]
    return []


def nav(findings: list[str]) -> None:
    """Flag a page absent from its language's nav, and a nav entry with no page.

    A page reachable by nothing is invisible on the built site, and an entry
    pointing at a moved page breaks the build. Skipped when the nav config is
    absent, so the other checks still run over a bare docs tree.
    """
    for config, root in NAVS:
        conf = pathlib.Path(config)
        if not conf.exists() or not root.exists():
            continue
        parsed = tomllib.loads(conf.read_text(encoding="utf-8"))
        declared = set(nav_pages(parsed.get("project", {}).get("nav", [])))
        found = {str(p.relative_to(root)) for p in root.rglob("*.md")}
        present = {p for p in found if not p.startswith(NAV_EXEMPT)}
        for missing in sorted(declared - present):
            findings.append(f"{config}: {missing} declare dans le nav, page absente")
        for orphan in sorted(present - declared):
            findings.append(f"{root}/{orphan}: absent du nav de {config}")


def main() -> int:
    findings: list[str] = []
    mechanical(findings)
    terminology(findings)
    parity(findings)
    links(findings)
    nav(findings)
    for f in findings:
        print(f)
    print(f"\n{len(findings)} finding(s)")
    return len(findings)


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
