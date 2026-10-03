from pathlib import Path

from scripts import check_no_comments, check_templates

ROOT = Path(__file__).resolve().parent.parent


def test_repository_has_no_comment_lines():
    assert check_no_comments.scan(ROOT) == []


def test_repository_has_no_forbidden_template_constructs():
    assert check_templates.scan(ROOT) == []


def test_main_functions_report_success_for_repository():
    assert check_no_comments.main([str(ROOT)]) == 0
    assert check_templates.main([str(ROOT)]) == 0


def test_python_comment_is_reported_but_shebang_and_noqa_are_not(tmp_path):
    (tmp_path / "ok.py").write_text(
        '#!/usr/bin/env python\nx = "# not a comment"\nimport os  # noqa: F401\n'
    )
    (tmp_path / "bad.py").write_text("# explains itself\nx = 1\n")
    assert check_no_comments.scan(tmp_path) == ["bad.py:1: # explains itself"]


def test_pug_sql_shell_yaml_and_dockerfile_comments_are_reported(tmp_path):
    (tmp_path / "a.pug").write_text("p hello\n  //- hidden\n// shown\n")
    (tmp_path / "b.sql").write_text("SELECT 1;\n-- why\n")
    (tmp_path / "c.sh").write_text("#!/bin/sh\n# why\necho ok\n")
    (tmp_path / "d.yml").write_text("a: 1\n# why\n")
    (tmp_path / "Dockerfile").write_text("FROM scratch\n# why\n")
    (tmp_path / "Caddyfile").write_text("# why\n")
    report = check_no_comments.scan(tmp_path)
    assert report == [
        "Caddyfile:1: # why",
        "Dockerfile:2: # why",
        "a.pug:2: //- hidden",
        "a.pug:3: // shown",
        "b.sql:2: -- why",
        "c.sh:2: # why",
        "d.yml:2: # why",
    ]


def test_migrations_and_venv_are_skipped(tmp_path):
    (tmp_path / "app" / "migrations").mkdir(parents=True)
    (tmp_path / ".venv").mkdir()
    (tmp_path / "app" / "migrations" / "0001.py").write_text("# generated\n")
    (tmp_path / ".venv" / "lib.py").write_text("# vendored\n")
    assert check_no_comments.scan(tmp_path) == []


def test_forbidden_template_tokens_are_reported(tmp_path):
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "x.pug").write_text(
        'p(style="color:red") hi\nscript.\n  js:alert(1)\n'
    )
    report = check_templates.scan(tmp_path)
    assert len(report) == 2
    assert report[0].startswith("templates/x.pug:1: forbids 'style=':")
    assert report[1].startswith("templates/x.pug:3: forbids 'js:':")
