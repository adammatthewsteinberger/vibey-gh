# Made with ❤️ by [Vibey](https://adammatthewsteinberger.github.io/vibey/), Developed by [Adam Matthew Steinberger](https://hire.adam.matthewsteinberger.com/) ([@adammatthewsteinberger](https://github.com/adammatthewsteinberger/)).
"""Deterministic documentation contract checks used locally and before AI maintenance."""

from __future__ import annotations

import json
from dataclasses import dataclass

from vibey_gh.config import GhConfig

README_PROVENANCE = (
    "Made with ❤️ by [Vibey](https://adammatthewsteinberger.github.io/vibey/), "
    "Developed by [Adam Matthew Steinberger]"
    "(https://hire.adam.matthewsteinberger.com/) "
    "([@adammatthewsteinberger](https://github.com/adammatthewsteinberger/))."
)
README_SECTIONS = (
    "## Why vibey-gh",
    "## Requirements",
    "## Quick start",
    "## Architecture",
    "## Security model",
    "## Commands",
    "## Configuration",
    "## Workflows",
    "## Troubleshooting",
    "## Contributing",
    "## Licence",
)
GITHUB_README_SECTIONS = (
    "## Delivery model",
    "## Workflow inventory",
    "## Exact-head PR automation",
    "## AI trust boundary",
    "## Credentials and settings",
    "## Permanent-branch safety",
    "## Failure recovery",
    "## Changing workflows",
)
MERMAID_REQUIRED_TERMS = (
    "flowchart",
    "CLI",
    "SDK",
    "API",
    "MCP",
    "Webhook",
    "PR Automation",
    "develop",
    "main",
    "TestPyPI",
    "PyPI",
    "GitHub Pages",
    "Provenance",
    "Realign",
    "Security Boundary",
)


@dataclass(frozen=True)
class DocumentationReport:
    problems: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.problems


def check(cfg: GhConfig) -> DocumentationReport:
    if not cfg.documentation.enabled:
        return DocumentationReport(())
    problems: list[str] = []
    for relative in cfg.documentation.required_files:
        path = cfg.root / relative
        if not path.is_file():
            problems.append(f"{relative} is missing")
        elif not path.read_text(encoding="utf-8").strip():
            problems.append(f"{relative} is empty")
    settings = cfg.root / ".claude/settings.json"
    if settings.is_file():
        try:
            value = json.loads(settings.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                problems.append(".claude/settings.json must contain a JSON object")
        except json.JSONDecodeError:
            problems.append(".claude/settings.json is invalid JSON")
    marketplace = cfg.root / ".claude-plugin/marketplace.json"
    if marketplace.is_file():
        try:
            value = json.loads(marketplace.read_text(encoding="utf-8"))
            plugins = value.get("plugins", []) if isinstance(value, dict) else []
            if not plugins:
                problems.append(".claude-plugin/marketplace.json has no plugins")
            for plugin in plugins:
                source = plugin.get("source", "") if isinstance(plugin, dict) else ""
                root = (cfg.root / source).resolve()
                if not source or cfg.root.resolve() not in root.parents:
                    problems.append(f"marketplace plugin has unsafe source: {source!r}")
                    continue
                if not (root / ".claude-plugin/plugin.json").is_file():
                    problems.append(f"{source}/.claude-plugin/plugin.json is missing")
                if not list((root / "skills").glob("*/SKILL.md")):
                    problems.append(f"{source} has no skills")
        except json.JSONDecodeError:
            problems.append(".claude-plugin/marketplace.json is invalid JSON")
    for relative in ("README.md", "docs/index.md"):
        path = cfg.root / relative
        if path.is_file() and "Made with" not in path.read_text(encoding="utf-8"):
            problems.append(f"{relative} has no Vibey provenance")
    readme = cfg.root / "README.md"
    if readme.is_file():
        text = readme.read_text(encoding="utf-8")
        for heading in README_SECTIONS:
            if heading not in text:
                problems.append(f"README.md is missing human documentation section: {heading}")
        if not text.rstrip().endswith(README_PROVENANCE):
            problems.append("README.md must end with the exact Vibey provenance sentence")
    github_readme = cfg.root / ".github/README.md"
    if github_readme.is_file():
        text = github_readme.read_text(encoding="utf-8")
        for heading in GITHUB_README_SECTIONS:
            if heading not in text:
                problems.append(
                    f".github/README.md is missing automation documentation section: {heading}"
                )
        if len(text.split()) < 500:
            problems.append(
                ".github/README.md is not comprehensive enough: expected at least 500 words"
            )
        if not text.rstrip().endswith(README_PROVENANCE):
            problems.append(".github/README.md must end with the exact Vibey provenance sentence")
    diagram = cfg.root / "docs/project.mmd"
    if diagram.is_file():
        text = diagram.read_text(encoding="utf-8")
        for term in MERMAID_REQUIRED_TERMS:
            if term not in text:
                problems.append(f"docs/project.mmd is missing required project surface: {term}")
        if text.count("-->") < 20:
            problems.append(
                "docs/project.mmd is not comprehensive enough: expected at least 20 edges"
            )
    return DocumentationReport(tuple(problems))
