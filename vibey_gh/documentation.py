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
# Retained for the repositories that import them directly; the contract itself now comes
# from configuration. `vibey_gh.config` holds this repository's own declaration.
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
                repo_root = cfg.root.resolve()
                if not source or (root != repo_root and repo_root not in root.parents):
                    problems.append(f"marketplace plugin has unsafe source: {source!r}")
                    continue
                if not (root / ".claude-plugin/plugin.json").is_file():
                    problems.append(f"{source}/.claude-plugin/plugin.json is missing")
                if not list((root / "skills").glob("*/SKILL.md")):
                    problems.append(f"{source} has no skills")
        except json.JSONDecodeError:
            problems.append(".claude-plugin/marketplace.json is invalid JSON")
    # Everything below is what THIS repository asks of its own documentation. A project
    # that installs vibey-gh documents its own product, not this tool's internals, so each
    # requirement is empty until the repository declares it in `.vibey-gh.toml`.
    if cfg.documentation.require_provenance:
        for relative in cfg.documentation.provenance_files:
            path = cfg.root / relative
            if path.is_file() and "Made with" not in path.read_text(encoding="utf-8"):
                problems.append(f"{relative} has no Vibey provenance")

    readme = cfg.root / "README.md"
    if readme.is_file() and (
        cfg.documentation.readme_sections or cfg.documentation.require_provenance
    ):
        text = readme.read_text(encoding="utf-8")
        for heading in cfg.documentation.readme_sections:
            if heading not in text:
                problems.append(f"README.md is missing human documentation section: {heading}")
        if cfg.documentation.require_provenance and not text.rstrip().endswith(README_PROVENANCE):
            problems.append("README.md must end with the exact Vibey provenance sentence")

    github_readme = cfg.root / ".github/README.md"
    if github_readme.is_file() and (
        cfg.documentation.github_readme_sections
        or cfg.documentation.github_readme_min_words
        or cfg.documentation.require_provenance
    ):
        text = github_readme.read_text(encoding="utf-8")
        for heading in cfg.documentation.github_readme_sections:
            if heading not in text:
                problems.append(
                    f".github/README.md is missing automation documentation section: {heading}"
                )
        minimum = cfg.documentation.github_readme_min_words
        if minimum and len(text.split()) < minimum:
            problems.append(
                f".github/README.md is not comprehensive enough: expected at least {minimum} words"
            )
        if cfg.documentation.require_provenance and not text.rstrip().endswith(README_PROVENANCE):
            problems.append(".github/README.md must end with the exact Vibey provenance sentence")

    diagram = cfg.root / "docs/project.mmd"
    if diagram.is_file() and (
        cfg.documentation.mermaid_terms or cfg.documentation.mermaid_min_edges
    ):
        text = diagram.read_text(encoding="utf-8")
        for term in cfg.documentation.mermaid_terms:
            if term not in text:
                problems.append(f"docs/project.mmd is missing required project surface: {term}")
        edges = cfg.documentation.mermaid_min_edges
        if edges and text.count("-->") < edges:
            problems.append(
                f"docs/project.mmd is not comprehensive enough: expected at least {edges} edges"
            )
    return DocumentationReport(tuple(problems))
