# Made with ❤️ by [Vibey](https://adammatthewsteinberger.github.io/vibey/), Developed by [Adam Matthew Steinberger](https://hire.adam.matthewsteinberger.com/) ([@adammatthewsteinberger](https://github.com/adammatthewsteinberger/)).
"""Comprehensive documentation configuration and deterministic contracts."""

import json
from pathlib import Path

import pytest

from vibey_gh.config import DocumentationConfig, GhConfig, load_config
from vibey_gh.documentation import (
    GITHUB_README_SECTIONS,
    MERMAID_REQUIRED_TERMS,
    README_PROVENANCE,
    README_SECTIONS,
    check,
)


def test_documentation_can_be_disabled(tmp_path: Path):
    assert check(GhConfig(root=tmp_path, documentation=DocumentationConfig(enabled=False))).ok


def test_documentation_reports_missing_empty_invalid_and_provenance(tmp_path: Path):
    required = ("README.md", "docs/index.md", ".claude/settings.json", "EMPTY.md", "MISSING.md")
    (tmp_path / "docs").mkdir()
    (tmp_path / ".claude").mkdir()
    (tmp_path / "README.md").write_text("plain")
    (tmp_path / "docs/index.md").write_text("plain")
    (tmp_path / ".claude/settings.json").write_text("[]")
    (tmp_path / "EMPTY.md").write_text("")
    report = check(
        GhConfig(root=tmp_path, documentation=DocumentationConfig(required_files=required))
    )
    assert "MISSING.md is missing" in report.problems
    assert "EMPTY.md is empty" in report.problems
    assert ".claude/settings.json must contain a JSON object" in report.problems
    assert "README.md has no Vibey provenance" in report.problems
    assert "docs/index.md has no Vibey provenance" in report.problems
    (tmp_path / ".claude/settings.json").write_text("{")
    assert (
        ".claude/settings.json is invalid JSON"
        in check(
            GhConfig(root=tmp_path, documentation=DocumentationConfig(required_files=required))
        ).problems
    )


def test_documentation_rejects_incomplete_mermaid_project_map(tmp_path: Path):
    diagram = tmp_path / "docs/project.mmd"
    diagram.parent.mkdir()
    diagram.write_text("flowchart TB\n  CLI --> API\n")
    report = check(
        GhConfig(
            root=tmp_path,
            documentation=DocumentationConfig(required_files=("docs/project.mmd",)),
        )
    )
    assert any("missing required project surface" in problem for problem in report.problems)
    assert any("not comprehensive enough" in problem for problem in report.problems)


def test_documentation_rejects_placeholder_github_automation_guide(tmp_path: Path):
    guide = tmp_path / ".github/README.md"
    guide.parent.mkdir()
    guide.write_text("# GitHub automation\n\nSee docs/workflows.md.\n")
    report = check(
        GhConfig(
            root=tmp_path,
            documentation=DocumentationConfig(required_files=(".github/README.md",)),
        )
    )
    for heading in GITHUB_README_SECTIONS:
        assert any(heading in problem for problem in report.problems)
    assert any("at least 500 words" in problem for problem in report.problems)
    assert any("exact Vibey provenance" in problem for problem in report.problems)


def test_documentation_validates_and_loads_configuration(tmp_path: Path):
    (tmp_path / ".vibey-gh.toml").write_text(
        '[documentation]\nmodel="opus"\nrequired_files=["README.md"]\n'
        'production_label="Stable"\npreview_label="Next"\nproduction_indexing=false\n'
        "preview_indexing=true\ngenerate_robots=false\ngenerate_sitemap_index=false\n"
        "generate_llms_txt=false\ngenerate_llms_full_txt=false\ngenerate_json_ld=false\n"
        'author_name="Maintainer"\nauthor_url="https://example.test"\n'
    )
    value = load_config(tmp_path).documentation
    assert value.model == "opus"
    assert value.required_files == ("README.md",)
    assert value.production_label == "Stable" and value.preview_label == "Next"
    assert not value.production_indexing and value.preview_indexing
    assert not value.generate_robots and not value.generate_sitemap_index
    assert not value.generate_llms_txt and not value.generate_llms_full_txt
    assert not value.generate_json_ld
    assert value.author_name == "Maintainer" and value.author_url == "https://example.test"


def test_documentation_validates_complete_marketplace_shape(tmp_path: Path):
    marketplace = tmp_path / ".claude-plugin/marketplace.json"
    marketplace.parent.mkdir()
    required = (".claude-plugin/marketplace.json",)
    cfg = GhConfig(root=tmp_path, documentation=DocumentationConfig(required_files=required))
    marketplace.write_text("{")
    assert "marketplace.json is invalid JSON" in check(cfg).problems[0]
    marketplace.write_text('{"plugins":[]}')
    assert "has no plugins" in check(cfg).problems[0]
    marketplace.write_text('{"plugins":[null,{"source":"../bad"},{"source":"./plugins/one"}]}')
    problems = check(cfg).problems
    assert any("unsafe source" in problem for problem in problems)
    assert any("plugin.json is missing" in problem for problem in problems)
    assert any("has no skills" in problem for problem in problems)


def test_documentation_treats_repo_root_source_as_safe(tmp_path: Path):
    marketplace = tmp_path / ".claude-plugin/marketplace.json"
    marketplace.parent.mkdir()
    required = (".claude-plugin/marketplace.json",)
    cfg = GhConfig(root=tmp_path, documentation=DocumentationConfig(required_files=required))
    marketplace.write_text('{"plugins":[{"source":"."}]}')
    problems = check(cfg).problems
    assert not any("unsafe source" in problem for problem in problems)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"required_files": ("../outside",)},
        {"required_files": ("/absolute",)},
        {"model": ""},
        {"production_label": " "},
        {"preview_label": ""},
        {"author_name": ""},
        {"author_url": ""},
    ],
)
def test_documentation_rejects_unsafe_or_empty_configuration(kwargs):
    with pytest.raises(ValueError):
        DocumentationConfig(**kwargs)


def test_this_repository_documentation_contract_is_complete():
    root = Path(__file__).resolve().parent.parent
    report = check(load_config(root))
    assert report.ok, report.problems
    marketplace = json.loads((root / ".claude-plugin/marketplace.json").read_text())
    assert len(marketplace["plugins"]) >= 4
    for plugin in marketplace["plugins"]:
        path = root / plugin["source"]
        assert (path / ".claude-plugin/plugin.json").is_file()
        assert list((path / "skills").glob("*/SKILL.md"))
    readme = (root / "README.md").read_text()
    assert readme.rstrip().endswith(README_PROVENANCE)
    assert all(section in readme for section in README_SECTIONS)
    github_readme = (root / ".github/README.md").read_text()
    assert all(section in github_readme for section in GITHUB_README_SECTIONS)
    assert len(github_readme.split()) >= 500
    assert github_readme.rstrip().endswith(README_PROVENANCE)
    diagram = (root / "docs/project.mmd").read_text()
    assert all(term in diagram for term in MERMAID_REQUIRED_TERMS)
    assert diagram.count("-->") >= 20
