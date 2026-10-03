import sys
from pathlib import Path

FORBIDDEN = ("<script", "<style", "style=", "hx-on", "js:", "!=", "!{", "|safe")


def violations_for(path):
    found = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        for token in FORBIDDEN:
            if token in line:
                found.append((index, token, line.strip()))
    return found


def scan(root):
    root = Path(root).resolve()
    templates = root / "templates"
    report = []
    for path in sorted(templates.rglob("*.pug")):
        for line_number, token, content in violations_for(path):
            report.append(f"{path.relative_to(root)}:{line_number}: forbids {token!r}: {content}")
    return report


def main(argv=None):
    args = sys.argv[1:] if argv is None else list(argv)
    root = Path(args[0]) if args else Path(__file__).resolve().parent.parent
    report = scan(root)
    for entry in report:
        print(entry)
    if report:
        print(f"{len(report)} forbidden template construct(s); see docs/SECURITY.md")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
