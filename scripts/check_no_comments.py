import io
import sys
import tokenize
from pathlib import Path

SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "migrations",
        "staticfiles",
        "__pycache__",
        ".pytest_cache",
        ".hypothesis",
        ".ruff_cache",
        ".mypy_cache",
    }
)
ALLOWED_PRAGMAS = ("noqa",)


def python_violations(path, text):
    found = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        for token in tokens:
            if token.type != tokenize.COMMENT:
                continue
            line_number = token.start[0]
            body = token.string[1:].strip()
            if line_number == 1 and token.string.startswith("#!"):
                continue
            if any(body.startswith(pragma) for pragma in ALLOWED_PRAGMAS):
                continue
            found.append((line_number, token.string))
    except (tokenize.TokenError, SyntaxError) as error:
        found.append((1, f"unparseable: {error}"))
    return found


def prefixed_line_violations(text, prefixes, skip_first_shebang=False):
    found = []
    for index, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if skip_first_shebang and index == 1 and stripped.startswith("#!"):
            continue
        if any(stripped.startswith(prefix) for prefix in prefixes):
            found.append((index, line.strip()))
    return found


def kind_of(path):
    name = path.name
    if path.suffix == ".py":
        return "python"
    if path.suffix == ".pug":
        return "pug"
    if path.suffix == ".sql":
        return "sql"
    if path.suffix == ".sh":
        return "shell"
    if path.suffix in {".yml", ".yaml"}:
        return "yaml"
    if name.startswith("Dockerfile") or name == "Caddyfile":
        return "hash"
    return None


def violations_for(path):
    kind = kind_of(path)
    if kind is None:
        return []
    text = path.read_text(encoding="utf-8")
    if kind == "python":
        return python_violations(path, text)
    if kind == "pug":
        return prefixed_line_violations(text, ("//",))
    if kind == "sql":
        return prefixed_line_violations(text, ("--",))
    if kind == "shell":
        return prefixed_line_violations(text, ("#",), skip_first_shebang=True)
    return prefixed_line_violations(text, ("#",))


def walk(root):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        yield path


def scan(root):
    root = Path(root).resolve()
    report = []
    for path in walk(root):
        for line_number, content in violations_for(path):
            report.append(f"{path.relative_to(root)}:{line_number}: {content}")
    return report


def main(argv=None):
    args = sys.argv[1:] if argv is None else list(argv)
    root = Path(args[0]) if args else Path(__file__).resolve().parent.parent
    report = scan(root)
    for entry in report:
        print(entry)
    if report:
        print(f"{len(report)} comment line(s) found; explain through names, tests and docs/")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
