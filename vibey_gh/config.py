# Made with ❤️ by [Vibey](https://adammatthewsteinberger.github.io/vibey/), Developed by [Adam Matthew Steinberger](https://hire.adam.matthewsteinberger.com/) ([@adammatthewsteinberger](https://github.com/adammatthewsteinberger/)).
# Made with ❤️ by [Vibey](https://adammatthewsteinberger.github.io/vibey/), Developed by [Adam Matthew Steinberger](https://hire.adam.matthewsteinberger.com/) ([@adammatthewsteinberger](https://github.com/adammatthewsteinberger/)).
"""Configuration for the GitHub automation, read from `.vibey-gh.toml`.

Every project-specific decision lives here so the logic beside it can stay general:

    [fingerprint]
    text     = "Made with love by Vibey, ..."      # the source-header comment
    trailer  = "Made-With: Made with ❤️ by ..."    # the commit trailer
    sources  = ["tools/*.py", ".github/workflows/*.yml"]

    [version]
    files         = ["src/pkg/__init__.py", "manifest.json"]
    content_paths = ["plugins/"]     # a change here is a MINOR release
    code_paths    = ["src/"]         # a change here alone is a PATCH

    [branches]
    integration = "develop"
    release     = "main"

    [install]
    workflows = []          # omit for all of them; [] for hooks and the CLI only

Absent keys fall back to the defaults below, so a repository that agrees with them needs
no file at all. `tomllib` is stdlib from 3.11, which this package already requires.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_NAME = ".vibey-gh.toml"

DEFAULT_TEXT = (
    "Made with ❤️ by [Vibey](https://adammatthewsteinberger.github.io/vibey/), "
    "Developed by [Adam Matthew Steinberger](https://hire.adam.matthewsteinberger.com/) "
    "([@adammatthewsteinberger](https://github.com/adammatthewsteinberger/))."
)
DEFAULT_TRAILER_KEY = "Made-With"
DEFAULT_TRAILER = f"{DEFAULT_TRAILER_KEY}: {DEFAULT_TEXT}"
DEFAULT_SOURCES = ("tools/*.py", "src/**/*.py", ".github/workflows/*.yml")
DEFAULT_SCAN_WORKFLOWS = (
    "CI",
    "Provenance",
    "CodeQL",
    "Docs",
    "API drift (Cloud Agents OpenAPI)",
)
DEFAULT_IGNORED_CHECKS = ("PR automation / gate", "gate", "Merge train / merge")
DEFAULT_DOCUMENTATION_FILES = (
    ".claude-plugin/marketplace.json",
    ".claude/settings.json",
    ".claude/skills/README.md",
    ".cursor/rules/project.mdc",
    ".agents/skills/README.md",
    ".agent/rules/project.md",
    ".githooks/README.md",
    ".github/README.md",
    "docs/index.md",
    "AGENTS.md",
    "CHANGELOG.md",
    "CLAUDE.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "GEMINI.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "SUPPORT.md",
)


@dataclass(frozen=True)
class PrAutomationConfig:
    enabled: bool = True
    scan_workflows: tuple[str, ...] = DEFAULT_SCAN_WORKFLOWS
    ignored_checks: tuple[str, ...] = DEFAULT_IGNORED_CHECKS
    max_repair_attempts: int = 3
    model: str = "claude-sonnet-5"
    review_untrusted_authors: bool = True
    repair_untrusted_authors: bool = True
    replace_fork_prs: bool = True
    retain_schedule_backstop: bool = True

    def __post_init__(self) -> None:
        _unique_nonempty("pr_automation.scan_workflows", self.scan_workflows)
        _unique_nonempty("pr_automation.ignored_checks", self.ignored_checks)
        if self.enabled and not self.scan_workflows:
            raise ValueError("pr_automation.scan_workflows must not be empty when enabled")
        if not 1 <= self.max_repair_attempts <= 10:
            raise ValueError("pr_automation.max_repair_attempts must be between 1 and 10")
        if not self.model.strip():
            raise ValueError("pr_automation.model must not be empty")


def _unique_nonempty(name: str, values: tuple[str, ...]) -> None:
    if any(not value.strip() for value in values):
        raise ValueError(f"{name} entries must be non-empty")
    if len(set(values)) != len(values):
        raise ValueError(f"{name} entries must be unique")


@dataclass(frozen=True)
class GithubReleaseConfig:
    enabled: bool = True
    tag_prefix: str = "v"
    generate_notes: bool = True

    def __post_init__(self) -> None:
        if not self.tag_prefix or any(char.isspace() for char in self.tag_prefix):
            raise ValueError(
                "github_release.tag_prefix must be non-empty and contain no whitespace"
            )


@dataclass(frozen=True)
class RepositoryProfileConfig:
    enabled: bool = True
    description: str = ""
    topics: tuple[str, ...] = (
        "automation",
        "continuous-delivery",
        "documentation",
        "github-actions",
        "release-automation",
    )
    has_issues: bool = True
    has_projects: bool = True
    has_wiki: bool = False
    has_discussions: bool = True
    allow_squash_merge: bool = True
    allow_merge_commit: bool = False
    allow_rebase_merge: bool = True
    allow_auto_merge: bool = True
    delete_branch_on_merge: bool = False
    web_commit_signoff_required: bool = True
    vulnerability_alerts: bool = True
    automated_security_fixes: bool = True

    def __post_init__(self) -> None:
        if len(self.description) > 350:
            raise ValueError("repository_profile.description must be at most 350 characters")
        _unique_nonempty("repository_profile.topics", self.topics)
        if len(self.topics) > 20:
            raise ValueError("repository_profile.topics must contain at most 20 entries")
        if any(topic != topic.lower() or " " in topic for topic in self.topics):
            raise ValueError("repository_profile.topics must be lowercase and contain no spaces")


@dataclass(frozen=True)
class DocumentationConfig:
    enabled: bool = True
    ai_maintenance: bool = True
    model: str = "claude-sonnet-5"
    required_files: tuple[str, ...] = DEFAULT_DOCUMENTATION_FILES
    production_label: str = "Production"
    preview_label: str = "Preview"
    production_indexing: bool = True
    preview_indexing: bool = False
    generate_robots: bool = True
    generate_sitemap_index: bool = True
    generate_llms_txt: bool = True
    generate_llms_full_txt: bool = True
    generate_json_ld: bool = True
    author_name: str = "Adam Matthew Steinberger"
    author_url: str = "https://hire.adam.matthewsteinberger.com"

    def __post_init__(self) -> None:
        _unique_nonempty("documentation.required_files", self.required_files)
        if any(
            Path(value).is_absolute() or ".." in Path(value).parts for value in self.required_files
        ):
            raise ValueError("documentation.required_files must be repository-relative paths")
        for name, value in (
            ("model", self.model),
            ("production_label", self.production_label),
            ("preview_label", self.preview_label),
            ("author_name", self.author_name),
            ("author_url", self.author_url),
        ):
            if not value.strip():
                raise ValueError(f"documentation.{name} must not be empty")


@dataclass(frozen=True)
class GhConfig:
    root: Path
    text: str = DEFAULT_TEXT
    trailer: str = DEFAULT_TRAILER
    sources: tuple[str, ...] = DEFAULT_SOURCES
    version_files: tuple[str, ...] = ()
    content_paths: tuple[str, ...] = ()
    code_paths: tuple[str, ...] = ("src/",)
    integration_branch: str = "develop"
    release_branch: str = "main"
    owner: str = ""
    trusted_authors: tuple[str, ...] = ()
    pr_automation: PrAutomationConfig = PrAutomationConfig()
    github_release: GithubReleaseConfig = GithubReleaseConfig()
    repository_profile: RepositoryProfileConfig = RepositoryProfileConfig()
    documentation: DocumentationConfig = DocumentationConfig()
    # Which bundled workflow templates this repository wants installed and kept current.
    # None means all of them, which is the right default for a repository adopting the
    # whole thing. A repository with its own richer workflows sets `workflows = []` and
    # keeps only the hooks and the CLI — otherwise `check` reports a permanent failure
    # for workflows it deliberately does not want.
    managed_workflows: tuple[str, ...] | None = None

    @property
    def header(self) -> str:
        """The fingerprint as it appears at the top of a source file."""
        return f"# {self.text}"

    @property
    def trailer_key(self) -> str:
        return self.trailer.split(":", 1)[0].strip() or DEFAULT_TRAILER_KEY


def find_root(start: Path | None = None) -> Path:
    """The repository root — where `.git` lives — walking up from `start`."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / ".git").exists():
            return candidate
    return here


def load_config(root: Path | None = None) -> GhConfig:
    root = find_root(root)
    path = root / CONFIG_NAME
    data: dict = {}
    if path.is_file():
        data = tomllib.loads(path.read_text(encoding="utf-8"))

    fp = data.get("fingerprint", {})
    ver = data.get("version", {})
    br = data.get("branches", {})
    tr = data.get("merge_train", {})
    inst = data.get("install", {})
    auto = data.get("pr_automation", {})
    release = data.get("github_release", {})
    profile = data.get("repository_profile", {})
    documentation = data.get("documentation", {})
    automation = PrAutomationConfig(
        enabled=auto.get("enabled", True),
        scan_workflows=tuple(auto.get("scan_workflows", DEFAULT_SCAN_WORKFLOWS)),
        ignored_checks=tuple(auto.get("ignored_checks", DEFAULT_IGNORED_CHECKS)),
        max_repair_attempts=auto.get("max_repair_attempts", 3),
        model=auto.get("model", "claude-sonnet-5"),
        review_untrusted_authors=auto.get("review_untrusted_authors", True),
        repair_untrusted_authors=auto.get("repair_untrusted_authors", True),
        replace_fork_prs=auto.get("replace_fork_prs", True),
        retain_schedule_backstop=auto.get("retain_schedule_backstop", True),
    )
    return GhConfig(
        root=root,
        text=fp.get("text", DEFAULT_TEXT),
        trailer=fp.get("trailer", DEFAULT_TRAILER),
        sources=tuple(fp.get("sources", DEFAULT_SOURCES)),
        version_files=tuple(ver.get("files", ())),
        content_paths=tuple(ver.get("content_paths", ())),
        code_paths=tuple(ver.get("code_paths", ("src/",))),
        managed_workflows=(tuple(inst["workflows"]) if "workflows" in inst else None),
        integration_branch=br.get("integration", "develop"),
        release_branch=br.get("release", "main"),
        owner=tr.get("owner", ""),
        trusted_authors=tuple(tr.get("trusted_authors", ())),
        pr_automation=automation,
        github_release=GithubReleaseConfig(
            enabled=release.get("enabled", True),
            tag_prefix=release.get("tag_prefix", "v"),
            generate_notes=release.get("generate_notes", True),
        ),
        repository_profile=RepositoryProfileConfig(
            enabled=profile.get("enabled", True),
            description=profile.get("description", ""),
            topics=tuple(profile.get("topics", RepositoryProfileConfig().topics)),
            has_issues=profile.get("has_issues", True),
            has_projects=profile.get("has_projects", True),
            has_wiki=profile.get("has_wiki", False),
            has_discussions=profile.get("has_discussions", True),
            allow_squash_merge=profile.get("allow_squash_merge", True),
            allow_merge_commit=profile.get("allow_merge_commit", False),
            allow_rebase_merge=profile.get("allow_rebase_merge", True),
            allow_auto_merge=profile.get("allow_auto_merge", True),
            delete_branch_on_merge=profile.get("delete_branch_on_merge", False),
            web_commit_signoff_required=profile.get("web_commit_signoff_required", True),
            vulnerability_alerts=profile.get("vulnerability_alerts", True),
            automated_security_fixes=profile.get("automated_security_fixes", True),
        ),
        documentation=DocumentationConfig(
            enabled=documentation.get("enabled", True),
            ai_maintenance=documentation.get("ai_maintenance", True),
            model=documentation.get("model", "claude-sonnet-5"),
            required_files=tuple(documentation.get("required_files", DEFAULT_DOCUMENTATION_FILES)),
            production_label=documentation.get("production_label", "Production"),
            preview_label=documentation.get("preview_label", "Preview"),
            production_indexing=documentation.get("production_indexing", True),
            preview_indexing=documentation.get("preview_indexing", False),
            generate_robots=documentation.get("generate_robots", True),
            generate_sitemap_index=documentation.get("generate_sitemap_index", True),
            generate_llms_txt=documentation.get("generate_llms_txt", True),
            generate_llms_full_txt=documentation.get("generate_llms_full_txt", True),
            generate_json_ld=documentation.get("generate_json_ld", True),
            author_name=documentation.get("author_name", "Adam Matthew Steinberger"),
            author_url=documentation.get("author_url", "https://hire.adam.matthewsteinberger.com"),
        ),
    )


def normalise_actor(login: str) -> str:
    """`app/claude` and `claude[bot]` are the same account spelled two ways.

    `gh` reports a bot author with the `app/` prefix; the rest of GitHub writes `[bot]`.
    A literal allow-list matches whichever spelling it happens to contain and silently
    distrusts the other — which once caused an automation to quarantine its own pull
    request as an outside contribution.
    """
    login = login.removeprefix("app/")
    return login.removesuffix("[bot]")
