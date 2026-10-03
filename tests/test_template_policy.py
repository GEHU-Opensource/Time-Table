from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
FORBIDDEN = ("<script", "<style", "style=", "hx-on", "js:", "!=", "!{", "|safe")


def pug_files():
    return sorted(TEMPLATES.rglob("*.pug"))


def test_templates_exist():
    assert pug_files()


@pytest.mark.parametrize("template", pug_files(), ids=lambda p: str(p.relative_to(TEMPLATES)))
def test_template_has_no_inline_code_or_unsafe_output(template):
    source = template.read_text()
    offences = [token for token in FORBIDDEN if token in source]
    assert offences == [], f"{template.relative_to(TEMPLATES)} contains {offences}"


@pytest.mark.parametrize("template", pug_files(), ids=lambda p: str(p.relative_to(TEMPLATES)))
def test_template_uses_two_space_indentation(template):
    for number, line in enumerate(template.read_text().splitlines(), start=1):
        indent = len(line) - len(line.lstrip(" "))
        assert "\t" not in line[:indent], f"{template.name}:{number} is tab indented"
        assert indent % 2 == 0, f"{template.name}:{number} has an odd indent"
