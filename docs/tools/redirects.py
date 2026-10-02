"""Write the redirects that replace the old GitHub Pages documentation.

The documentation moved to docs.piighost.dev, where the guide sits under
/en/guide/ and /fr/guide/. GitHub Pages cannot answer a redirect status, so each
old page becomes a small HTML file that sends the reader to its new address,
the anchor kept, with a canonical link for search engines. Any other old path
lands on 404.html, which sends it to the guide's home in its language.

    uv run python docs/tools/redirects.py docs/site
"""

import sys
from html import escape
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1]
"""The docs folder, with one subfolder per language."""

NEW_SITE = "https://docs.piighost.dev"
"""Where the documentation lives now."""

LANGUAGES = {"en": "", "fr": "fr/"}
"""Each language, by the prefix its pages had under the old site."""

PAGE = """<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<title>piighost documentation moved</title>
<link rel="canonical" href="{target}">
<meta name="robots" content="noindex">
<meta http-equiv="refresh" content="0; url={target}">
<script>location.replace({target_js} + location.hash)</script>
</head>
<body>
<p>The documentation moved to <a href="{target}">{target}</a>.</p>
</body>
</html>
"""
"""A redirect page. The script keeps the anchor, which the meta refresh drops."""

NOT_FOUND = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>piighost documentation moved</title>
<meta name="robots" content="noindex">
<script>
location.replace({site_js} + (location.pathname.startsWith("/piighost/fr/") ? "/fr/guide/" : "/en/guide/"))
</script>
</head>
<body>
<p>The documentation moved to <a href="{site}/en/guide/">{site}</a>.</p>
</body>
</html>
"""
"""The page GitHub Pages answers for any other path."""


def old_and_new(lang: str, page: Path) -> tuple[str, str]:
    """The folder a page had under the old site, and its new URL.

    Zensical gave foo/bar.md the folder foo/bar/ and foo/index.md the folder
    foo/, and the new site keeps the same paths under /<lang>/guide/.
    """
    path = page.parent if page.stem == "index" else page.with_suffix("")
    folder = "" if path == Path() else f"{path.as_posix()}/"
    return f"{LANGUAGES[lang]}{folder}", f"{NEW_SITE}/{lang}/guide/{folder}"


def write(out: Path) -> int:
    """Write every redirect page into out, and return how many were written."""
    count = 0
    for lang in LANGUAGES:
        root = DOCS / lang
        for page in sorted(root.rglob("*.md")):
            relative = page.relative_to(root)
            if relative.parts[0] in {"includes", "snippets"}:
                continue
            old, target = old_and_new(lang, relative)
            file = out / old / "index.html"
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(
                PAGE.format(lang=lang, target=escape(target), target_js=repr(target)),
                encoding="utf-8",
            )
            count += 1
    (out / "404.html").write_text(
        NOT_FOUND.format(site=NEW_SITE, site_js=repr(NEW_SITE)), encoding="utf-8"
    )
    return count


if __name__ == "__main__":
    print(f"{write(Path(sys.argv[1]))} redirects written")
