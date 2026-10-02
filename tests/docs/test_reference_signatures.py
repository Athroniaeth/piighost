"""The signatures and classes a page shows are the ones the code has.

A reference page writes a constructor as a signature, `Anonymizer(ph_factory:
..., escape_existing_tokens: bool = True)`, and a port as a class whose methods
end in `...`. Neither runs, so neither can come from docs/snippets/. This test
reads every Python block of every page, in both languages, and compares each
signature and each shown class with the source of piighost, through its syntax
tree: no optional package is imported, so a page about spaCy is checked
without spaCy installed. A block written as a doctest runs as one.
"""

import ast
import copy
import doctest
import re
import textwrap
from collections.abc import Iterator
from functools import cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
"""The repository root."""

SRC_DIR = ROOT / "src" / "piighost"
"""The code the pages describe."""

DOCS_DIR = ROOT / "docs"
"""The documentation, one folder per language."""

LANGUAGES = ("en", "fr")
"""Every language of the documentation."""

FENCE = re.compile(r"^([ \t]*)```python\n(.*?)^\1```", re.MULTILINE | re.DOTALL)
"""A Python block of a page, its indentation captured."""

SIGNATURE = re.compile(r"\s*(\w+)(?:\.(\w+))?\((.*)\)(\s*->\s*.+?)?\s*", re.DOTALL)
"""A signature block: `Class(params)` or `Class.method(params) -> Return`."""


def _blocks() -> Iterator[tuple[str, str]]:
    for language in LANGUAGES:
        for page in sorted((DOCS_DIR / language).rglob("*.md")):
            text = page.read_text(encoding="utf-8")
            for match in FENCE.finditer(text):
                line = text.count("\n", 0, match.start()) + 2
                code = textwrap.dedent(match.group(2))
                # A block that includes a file is tested through that file.
                if "--8<--" not in code:
                    yield f"{page.relative_to(DOCS_DIR)}:{line}", code


def _is_signature(code: str) -> bool:
    try:
        ast.parse(code)
    except SyntaxError:
        return SIGNATURE.fullmatch(code) is not None
    return False


def _is_class(code: str) -> bool:
    try:
        body = ast.parse(code).body
    except SyntaxError:
        return False
    return bool(body) and all(isinstance(node, ast.ClassDef) for node in body)


def _is_import(code: str) -> bool:
    try:
        body = ast.parse(code).body
    except SyntaxError:
        return False
    return bool(body) and all(isinstance(node, ast.ImportFrom) for node in body)


def _is_doctest(code: str) -> bool:
    return code.lstrip().startswith(">>>")


BLOCKS = list(_blocks())
"""Every Python block written in a page, as (page:line, code)."""

SIGNATURES = [(where, code) for where, code in BLOCKS if _is_signature(code)]
"""The blocks that write a signature."""

CLASSES = [(where, code) for where, code in BLOCKS if _is_class(code)]
"""The blocks that show a class, a port or a template."""

IMPORTS = [(where, code) for where, code in BLOCKS if _is_import(code)]
"""The blocks that only list what a module exports."""

DOCTESTS = [(where, code) for where, code in BLOCKS if _is_doctest(code)]
"""The blocks written as an interactive session."""

CHECKED_PAGES = ("reference/", "security.md")
"""The pages whose every Python block is a signature, a class, an import or a session."""


@cache
def _source() -> dict[str, list[tuple[ast.ClassDef, dict[str, ast.expr]]]]:
    """Every class of piighost by name, with the constants of its module."""
    classes: dict[str, list[tuple[ast.ClassDef, dict[str, ast.expr]]]] = {}
    for path in SRC_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        constants = dict(filter(None, map(_constant, tree.body)))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.setdefault(node.name, []).append((node, constants))
    return classes


def _constant(node: ast.stmt) -> tuple[str, ast.expr] | None:
    """A module constant, `NAME = value` or `NAME: T = value`."""
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        target, value = node.targets[0], node.value
    elif isinstance(node, ast.AnnAssign) and node.value is not None:
        target, value = node.target, node.value
    else:
        return None
    return (target.id, value) if isinstance(target, ast.Name) else None


def _class(name: str) -> tuple[ast.ClassDef, dict[str, ast.expr]]:
    found = _source().get(name, [])
    assert len(found) == 1, f"{name}: {len(found)} classes of that name in piighost"
    return found[0]


def _method(
    name: str, method: str
) -> tuple[ast.FunctionDef | ast.AsyncFunctionDef, dict[str, ast.expr]] | None:
    """A method of a class and its module's constants, looked up through its bases."""
    owner, constants = _class(name)
    for node in owner.body:
        is_function = isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        if is_function and node.name == method:
            return node, constants
    for base in owner.bases:
        base_name = ast.unparse(base).split("[")[0].rpartition(".")[2]
        found = (
            base_name != name and base_name in _source() and _method(base_name, method)
        )
        if found:
            return found
    return None


def _annotation(node: ast.expr | None) -> str | None:
    """An annotation as text, a quoted one read as the code it quotes."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return ast.unparse(ast.parse(node.value, mode="eval").body)
    return ast.unparse(node) if node else None


def _default(node: ast.expr, constants: dict[str, ast.expr]) -> ast.expr:
    """A default, a module constant replaced by its value as a page writes it."""
    if isinstance(node, ast.Name):
        return constants.get(node.id, node)
    return node


def _parameters(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    drop: int = 0,
    constants: dict[str, ast.expr] | None = None,
) -> str:
    """The parameters of a function as one line, the first `drop` left out."""
    constants = constants or {}
    arguments = copy.deepcopy(function.args)
    positional = [*arguments.posonlyargs, *arguments.args]
    # Defaults align on the last positional parameters.
    defaults = [None] * (len(positional) - len(arguments.defaults)) + arguments.defaults
    del positional[:drop], defaults[:drop]
    for argument in [*positional, *arguments.kwonlyargs]:
        text = _annotation(argument.annotation)
        argument.annotation = ast.parse(text, mode="eval").body if text else None
    shown = ast.arguments(
        posonlyargs=[],
        args=positional,
        vararg=arguments.vararg,
        kwonlyargs=arguments.kwonlyargs,
        kw_defaults=[
            node and _default(node, constants) for node in arguments.kw_defaults
        ],
        kwarg=arguments.kwarg,
        defaults=[_default(node, constants) for node in defaults if node is not None],
    )
    return ast.unparse(shown)


def _returns(
    function: ast.FunctionDef | ast.AsyncFunctionDef, owner: str
) -> str | None:
    returned = _annotation(function.returns)
    return owner if returned == "Self" else returned


@pytest.mark.parametrize(("where", "code"), SIGNATURES, ids=[w for w, _ in SIGNATURES])
def test_a_signature_a_page_writes_is_the_code_s(where: str, code: str) -> None:
    """Its parameters, their types and defaults, and its return type match the source."""
    match = SIGNATURE.fullmatch(code)
    assert match
    owner, method, parameters, returns = match.groups()
    shown = ast.parse(f"def _({parameters}){returns or ''}: ...").body[0]
    assert isinstance(shown, ast.FunctionDef)
    found = _method(owner, method or "__init__")
    assert found, f"{owner}.{method or '__init__'} is not in piighost"
    real, constants = found
    is_static = any(ast.unparse(node) == "staticmethod" for node in real.decorator_list)
    assert _parameters(shown) == _parameters(real, 0 if is_static else 1, constants)
    if method:
        assert _returns(shown, owner) == _returns(real, owner)


def _unparsed(nodes: list[ast.expr]) -> list[str]:
    return [ast.unparse(node) for node in nodes]


def _fields(owner: ast.ClassDef) -> dict[str, str | None]:
    return {
        node.target.id: _annotation(node.annotation)
        for node in owner.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }


def _assert_same_method(
    owner: str, shown: ast.FunctionDef | ast.AsyncFunctionDef
) -> None:
    """A method a page shows is the code's, async, decorators and signature."""
    found = _method(owner, shown.name)
    assert found, f"{owner}.{shown.name} is not in piighost"
    real, constants = found
    assert type(shown) is type(real), f"{owner}.{shown.name}: async differs"
    assert _unparsed(shown.decorator_list) == _unparsed(real.decorator_list)
    assert _parameters(shown) == _parameters(real, 0, constants)
    assert _returns(shown, owner) == _returns(real, owner)


def _required(owner: ast.ClassDef) -> set[str]:
    """What an implementer must write: every method of a port, the abstract ones of a template."""
    methods = [
        node
        for node in owner.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if any(ast.unparse(base).startswith("Protocol") for base in owner.bases):
        return {node.name for node in methods}
    return {
        node.name
        for node in methods
        if "abstractmethod" in _unparsed(node.decorator_list)
    }


@pytest.mark.parametrize(("where", "code"), CLASSES, ids=[w for w, _ in CLASSES])
def test_a_class_a_page_shows_is_the_code_s(where: str, code: str) -> None:
    """Its bases, decorators, fields and methods match the source, signatures included."""
    for shown in ast.parse(code).body:
        assert isinstance(shown, ast.ClassDef)
        real, _ = _class(shown.name)
        assert _unparsed(shown.bases) == _unparsed(real.bases)
        assert _unparsed(shown.decorator_list) == _unparsed(real.decorator_list)
        shown_methods = {
            node.name
            for node in shown.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        missing = _required(real) - shown_methods
        assert not missing, f"{shown.name} leaves out {sorted(missing)}"
        fields = _fields(real)
        for name, annotation in _fields(shown).items():
            assert annotation == fields.get(name), f"{shown.name}.{name}"
        for node in shown.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                _assert_same_method(shown.name, node)


def _exported(module: str) -> set[str]:
    """What a module of piighost exports: its `__all__`, else every name it binds."""
    path = SRC_DIR.parent.joinpath(*module.split("."))
    source = path / "__init__.py" if path.is_dir() else path.with_suffix(".py")
    tree = ast.parse(source.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        target, value = _constant(node) or (None, None)
        if target == "__all__" and isinstance(value, (ast.List, ast.Tuple)):
            return {
                element.value
                for element in value.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            }
        if target:
            names.add(target)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names |= {alias.asname or alias.name for alias in node.names}
    return names


@pytest.mark.parametrize(("where", "code"), IMPORTS, ids=[w for w, _ in IMPORTS])
def test_an_import_a_page_shows_names_what_the_module_exports(
    where: str, code: str
) -> None:
    """Each name is exported by the module it is imported from, its extra installed or not."""
    for node in ast.parse(code).body:
        assert isinstance(node, ast.ImportFrom)
        assert node.module
        missing = {alias.name for alias in node.names} - _exported(node.module)
        assert not missing, f"{node.module} does not export {sorted(missing)}"


@pytest.mark.parametrize(("where", "code"), DOCTESTS, ids=[w for w, _ in DOCTESTS])
def test_an_interactive_session_a_page_shows_replays(where: str, code: str) -> None:
    """Each `>>>` line prints what the page shows under it."""
    test = doctest.DocTestParser().get_doctest(code, {}, where, where, 0)
    runner = doctest.DocTestRunner(optionflags=doctest.ELLIPSIS)
    runner.run(test)
    assert runner.failures == 0


def test_every_block_of_a_reference_page_is_checked() -> None:
    """A reference page writes no Python a test does not read, the rest comes from docs/snippets/."""
    checked = {where for where, _ in [*SIGNATURES, *CLASSES, *IMPORTS, *DOCTESTS]}
    unchecked = [
        where
        for where, _ in BLOCKS
        if where.split("/", 1)[1].startswith(CHECKED_PAGES) and where not in checked
    ]
    assert unchecked == []
