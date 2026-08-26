# Made with ❤️ by [Vibey](https://adammatthewsteinberger.github.io/vibey/), Developed by [Adam Matthew Steinberger](https://hire.adam.matthewsteinberger.com/) ([@adammatthewsteinberger](https://github.com/adammatthewsteinberger/)).
"""Install the git hooks that enforce the automation into a consuming repository.

Installing is deliberately additive. A repository that already has its own `pre-push` or
`commit-msg` keeps it: the existing hook is moved aside to `<name>.local` and the
installed hook chains to it. Adopting this should never silently discard checks somebody
else thought were important.
"""

from __future__ import annotations

import json
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

from vibey_gh import __version__
from vibey_gh.config import GhConfig, load_config

TEMPLATES = Path(__file__).parent / "templates" / "githooks"
WORKFLOWS = Path(__file__).parent / "templates" / "workflows"
PACKAGED_RELEASE_ASSETS = Path(__file__).parent / "templates" / "release"
SOURCE_RELEASE_ASSETS = Path(__file__).parent.parent / "docs"
WORKFLOWS_DIR = ".github/workflows"
RELEASE_ASSETS_DIR = ".github/vibey-gh/release"
HOOKS = ("commit-msg", "pre-push")
HOOKS_DIR = ".githooks"
GITATTRIBUTES = ".gitattributes"
UNION_MARKER = "# vibey-gh: append-only files merge instead of conflicting"


@dataclass
class Action:
    hook: str
    outcome: str  # installed | updated | unchanged | chained


def _executable(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _managed_workflows(cfg: GhConfig) -> list[Path]:
    """The workflow templates this repository has asked to be responsible for.

    A repository that already has its own richer workflows sets `install.workflows = []`
    and takes only the hooks and the CLI. Without this, `check` would fail forever on
    workflows it never wanted — and a check that cannot pass is a check people route
    around.
    """
    every = sorted(WORKFLOWS.glob("*.yml"))
    if cfg.managed_workflows is None:
        return every
    wanted = set(cfg.managed_workflows)
    return [p for p in every if p.name in wanted]


def _release_assets(cfg: GhConfig) -> list[tuple[Path, str]]:
    """Theme files installed only with the release-surfaces workflow.

    Source checkouts use ``docs`` directly; wheels force-include the same bytes beside
    the workflow templates. This keeps one authored copy while making installed projects
    self-contained and independent of the vibey-gh repository.
    """
    if not any(path.name == "release-surfaces.yml" for path in _managed_workflows(cfg)):
        return []
    if PACKAGED_RELEASE_ASSETS.is_dir():
        return [
            (PACKAGED_RELEASE_ASSETS / "vibey.css", "vibey.css"),
            (PACKAGED_RELEASE_ASSETS / "channel.js", "channel.js"),
        ]
    return [
        (SOURCE_RELEASE_ASSETS / "stylesheets" / "vibey.css", "vibey.css"),
        (SOURCE_RELEASE_ASSETS / "javascripts" / "channel.js", "channel.js"),
    ]


def render_workflow(source: Path, cfg: GhConfig) -> str:
    wanted = source.read_text(encoding="utf-8")
    wanted = wanted.replace("__VIBEY_GH_INTEGRATION_BRANCH__", cfg.integration_branch)
    wanted = wanted.replace("__VIBEY_GH_RELEASE_BRANCH__", cfg.release_branch)
    wanted = wanted.replace("__VIBEY_GH_MODEL__", cfg.pr_automation.model)
    wanted = wanted.replace(
        "__VIBEY_GH_SANITIZED_PROGRESS__",
        "true" if cfg.pr_automation.observability.sanitized_progress else "false",
    )
    wanted = wanted.replace(
        "__VIBEY_GH_ARCHIVE_EXECUTION_FILE__",
        "true" if cfg.pr_automation.observability.archive_execution_file else "false",
    )
    wanted = wanted.replace(
        "__VIBEY_GH_ALLOW_PRIVATE_FULL_OUTPUT__",
        "true" if cfg.pr_automation.observability.allow_private_full_output else "false",
    )
    wanted = wanted.replace(
        "__VIBEY_GH_SYNC_ENABLED__", "true" if cfg.branch_sync.enabled else "false"
    )
    talk = cfg.conversation
    wanted = wanted.replace(
        "__VIBEY_GH_CONVERSATION_ENABLED__", "true" if talk.enabled else "false"
    )
    wanted = wanted.replace("__VIBEY_GH_CONVERSATION_TRIGGER__", talk.trigger)
    wanted = wanted.replace("__VIBEY_GH_CONVERSATION_MODEL__", talk.model)
    issues = cfg.issue_automation
    wanted = wanted.replace("__VIBEY_GH_ISSUE_ENABLED__", "true" if issues.enabled else "false")
    wanted = wanted.replace("__VIBEY_GH_ISSUE_MODEL__", issues.model)
    wanted = wanted.replace("__VIBEY_GH_ISSUE_MAX_TURNS__", str(issues.max_turns))
    wanted = wanted.replace("__VIBEY_GH_ISSUE_BRANCH_PREFIX__", issues.branch_prefix)
    wanted = wanted.replace("__VIBEY_GH_ISSUE_LABEL__", issues.required_label)
    wanted = wanted.replace(
        "__VIBEY_GH_ISSUE_OPEN_PR__", "true" if issues.open_pull_request else "false"
    )
    wanted = wanted.replace(
        "__VIBEY_GH_ISSUE_DRAFT_PR__", "true" if issues.draft_pull_request else "false"
    )
    wanted = wanted.replace(
        "  # __VIBEY_GH_ISSUE_SCHEDULE__",
        (
            '  schedule:\n    - cron: "19 */12 * * *"'
            if issues.retain_schedule_backstop
            else "  # schedule backstop disabled by .vibey-gh.toml"
        ),
    )
    wanted = wanted.replace(
        "__VIBEY_GH_PROFILE_ENABLED__",
        "true" if cfg.repository_profile.enabled else "false",
    )
    wanted = wanted.replace(
        "__VIBEY_GH_RULESETS_ENABLED__",
        "true" if cfg.rulesets.enabled else "false",
    )
    wanted = wanted.replace(
        "__VIBEY_GH_PROFILE_DESCRIPTION__",
        json.dumps(cfg.repository_profile.description),
    )
    wanted = wanted.replace(
        "__VIBEY_GH_PROFILE_TOPICS__",
        json.dumps({"names": list(cfg.repository_profile.topics)}, separators=(",", ":")),
    )
    profile_settings = {
        name: getattr(cfg.repository_profile, name)
        for name in (
            "has_issues",
            "has_projects",
            "has_wiki",
            "has_discussions",
            "allow_squash_merge",
            "allow_merge_commit",
            "allow_rebase_merge",
            "allow_auto_merge",
            "delete_branch_on_merge",
            "web_commit_signoff_required",
            "vulnerability_alerts",
            "automated_security_fixes",
        )
    }
    wanted = wanted.replace(
        "__VIBEY_GH_PROFILE_SETTINGS__",
        json.dumps(profile_settings, separators=(",", ":")),
    )
    wanted = wanted.replace(
        "__VIBEY_GH_DOCUMENTATION_AI__",
        "true" if cfg.documentation.ai_maintenance else "false",
    )
    wanted = wanted.replace("__VIBEY_GH_DOCUMENTATION_MODEL__", cfg.documentation.model)
    wanted = wanted.replace("__VIBEY_GH_DOC_PRODUCTION_LABEL__", cfg.documentation.production_label)
    wanted = wanted.replace("__VIBEY_GH_DOC_PREVIEW_LABEL__", cfg.documentation.preview_label)
    wanted = wanted.replace(
        "__VIBEY_GH_DOC_GOOGLE_ANALYTICS_ID__", cfg.documentation.google_analytics_id
    )
    wanted = wanted.replace(
        "__VIBEY_GH_DOCUMENTATION_FILES__",
        json.dumps(list(cfg.documentation.required_files)),
    )
    for marker, enabled in (
        ("__VIBEY_GH_DOC_ROBOTS__", cfg.documentation.generate_robots),
        ("__VIBEY_GH_DOC_SITEMAP_INDEX__", cfg.documentation.generate_sitemap_index),
        ("__VIBEY_GH_DOC_LLMS__", cfg.documentation.generate_llms_txt),
        ("__VIBEY_GH_DOC_LLMS_FULL__", cfg.documentation.generate_llms_full_txt),
        ("__VIBEY_GH_DOC_JSON_LD__", cfg.documentation.generate_json_ld),
        ("__VIBEY_GH_DOC_PRODUCTION_INDEX__", cfg.documentation.production_indexing),
        ("__VIBEY_GH_DOC_PREVIEW_INDEX__", cfg.documentation.preview_indexing),
    ):
        wanted = wanted.replace(marker, "true" if enabled else "false")
    if cfg.pin_version:
        # Only the floating fallback install is pinned. The self-hosting branch just
        # above it (`pip install --quiet -e .`) must keep installing from source: this
        # repository cannot pin itself to a published release that may not exist yet.
        wanted = wanted.replace(
            "python -m pip install --quiet vibey-gh\n",
            f'python -m pip install --quiet "vibey-gh=={__version__}"\n',
        )
    if source.name != "pr-automation.yml":
        return wanted
    workflows = json.dumps(list(cfg.pr_automation.scan_workflows))
    schedule = (
        '  schedule:\n    - cron: "47 */6 * * *"'
        if cfg.pr_automation.retain_schedule_backstop
        else "  # schedule backstop disabled by .vibey-gh.toml"
    )
    return wanted.replace("__VIBEY_GH_SCAN_WORKFLOWS__", workflows).replace(
        "  # __VIBEY_GH_SCHEDULE__", schedule
    )


def installation_notices() -> tuple[str, ...]:
    """Best-effort secret inventory plus settings the GitHub API cannot infer safely."""
    notices = [
        "enable Actions read/write permissions and allow Actions to create pull requests",
    ]
    run = subprocess.run(
        ["gh", "secret", "list", "--json", "name"], capture_output=True, text=True, check=False
    )
    if run.returncode == 0:
        try:
            present = {str(item["name"]) for item in json.loads(run.stdout)}
        except (json.JSONDecodeError, KeyError, TypeError):
            present = set()
        for name in ("ANTHROPIC_API_KEY", "AUTOMERGE_TOKEN"):
            if name not in present:
                notices.append(f"configure repository secret {name}")
    return tuple(notices)


def union_merge_lines(cfg: GhConfig) -> list[str]:
    return [f"{path} merge=union" for path in cfg.union_merge_paths]


def missing_union_merge_lines(cfg: GhConfig) -> list[str]:
    """Which `merge=union` declarations `.gitattributes` does not already carry."""
    path = cfg.root / GITATTRIBUTES
    existing = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    present = {line.strip() for line in existing}
    return [line for line in union_merge_lines(cfg) if line not in present]


def apply_union_merge(cfg: GhConfig) -> str | None:
    """Append the missing declarations, never rewriting what is already there.

    Every branch appends to the changelog, so two branches almost always touch the same
    lines and every merge strands the others — a conflict that carries no information and
    has to be resolved by hand each time. Git's `union` driver keeps both sides instead.

    It only works from the branch being merged *into*, so this file has to be committed on
    the integration branch to have any effect on the topic branches that follow.

    A repository's own `.gitattributes` is its own: this appends and never rewrites, so an
    adopter's existing rules survive adoption untouched.
    """
    missing = missing_union_merge_lines(cfg)
    if not missing:
        return None
    path = cfg.root / GITATTRIBUTES
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    outcome = "updated" if existing else "installed"
    block = "\n".join([UNION_MARKER, *missing])
    if existing and not existing.endswith("\n"):
        existing += "\n"
    prefix = f"{existing}\n" if existing else ""
    path.write_text(f"{prefix}{block}\n", encoding="utf-8")
    return outcome


def install(cfg: GhConfig | None = None, hooks_path: bool = True) -> list[Action]:
    cfg = cfg or load_config()
    target = cfg.root / HOOKS_DIR
    target.mkdir(parents=True, exist_ok=True)
    actions: list[Action] = []

    for hook in HOOKS:
        source = TEMPLATES / hook
        dest = target / hook
        wanted = source.read_text(encoding="utf-8")

        if dest.exists():
            existing = dest.read_text(encoding="utf-8")
            if existing == wanted:
                actions.append(Action(hook, "unchanged"))
                continue
            # Someone else's hook: preserve it and chain rather than overwrite.
            if "vibey-gh" not in existing:
                local = target / f"{hook}.local"
                if not local.exists():
                    shutil.move(str(dest), str(local))
                    _executable(local)
                    actions.append(Action(hook, "chained"))
                dest.write_text(wanted, encoding="utf-8")
                _executable(dest)
                continue
            dest.write_text(wanted, encoding="utf-8")
            _executable(dest)
            actions.append(Action(hook, "updated"))
            continue

        dest.write_text(wanted, encoding="utf-8")
        _executable(dest)
        actions.append(Action(hook, "installed"))

    # Workflows are copied, not chained: a workflow file is standalone and a stale copy
    # is worse than none, so an out-of-date one is replaced outright.
    wf_target = cfg.root / WORKFLOWS_DIR
    wf_target.mkdir(parents=True, exist_ok=True)
    for source in _managed_workflows(cfg):
        dest = wf_target / source.name
        wanted = render_workflow(source, cfg)
        if dest.exists() and dest.read_text(encoding="utf-8") == wanted:
            actions.append(Action(f"{WORKFLOWS_DIR}/{source.name}", "unchanged"))
            continue
        outcome = "updated" if dest.exists() else "installed"
        dest.write_text(wanted, encoding="utf-8")
        actions.append(Action(f"{WORKFLOWS_DIR}/{source.name}", outcome))

    asset_target = cfg.root / RELEASE_ASSETS_DIR
    for source, name in _release_assets(cfg):
        asset_target.mkdir(parents=True, exist_ok=True)
        dest = asset_target / name
        wanted = source.read_text(encoding="utf-8")
        if dest.exists() and dest.read_text(encoding="utf-8") == wanted:
            actions.append(Action(f"{RELEASE_ASSETS_DIR}/{name}", "unchanged"))
            continue
        outcome = "updated" if dest.exists() else "installed"
        dest.write_text(wanted, encoding="utf-8")
        actions.append(Action(f"{RELEASE_ASSETS_DIR}/{name}", outcome))

    attributes = apply_union_merge(cfg)
    actions.append(Action(GITATTRIBUTES, attributes or "unchanged"))

    if hooks_path:
        subprocess.run(
            ["git", "config", "core.hooksPath", HOOKS_DIR],
            cwd=cfg.root,
            check=False,
            capture_output=True,
        )
    return actions


def installed(cfg: GhConfig | None = None, local: bool = True) -> tuple[bool, list[str]]:
    """Whether the hooks are present, current, and — when `local` — actually wired up.

    The two halves are deliberately separable. Whether the hook FILES are committed and
    current is repository state, and CI can and should check it. Whether `core.hooksPath`
    points at them is per-clone local git config that no CI checkout will ever have, so
    asserting it on a runner would fail every build for a condition that cannot hold there.
    """
    cfg = cfg or load_config()
    problems: list[str] = []
    target = cfg.root / HOOKS_DIR

    for hook in HOOKS:
        dest = target / hook
        if not dest.exists():
            problems.append(f"{HOOKS_DIR}/{hook} is missing")
        elif dest.read_text(encoding="utf-8") != (TEMPLATES / hook).read_text(encoding="utf-8"):
            problems.append(f"{HOOKS_DIR}/{hook} is out of date")

    for source in _managed_workflows(cfg):
        dest = cfg.root / WORKFLOWS_DIR / source.name
        if not dest.exists():
            problems.append(f"{WORKFLOWS_DIR}/{source.name} is missing")
        elif dest.read_text(encoding="utf-8") != render_workflow(source, cfg):
            problems.append(f"{WORKFLOWS_DIR}/{source.name} is out of date")

    for source, name in _release_assets(cfg):
        dest = cfg.root / RELEASE_ASSETS_DIR / name
        if not dest.exists():
            problems.append(f"{RELEASE_ASSETS_DIR}/{name} is missing")
        elif dest.read_text(encoding="utf-8") != source.read_text(encoding="utf-8"):
            problems.append(f"{RELEASE_ASSETS_DIR}/{name} is out of date")

    for line in missing_union_merge_lines(cfg):
        problems.append(f"{GITATTRIBUTES} is missing `{line}`")

    if local:
        import subprocess

        result = subprocess.run(
            ["git", "config", "--get", "core.hooksPath"],
            cwd=cfg.root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout.strip() != HOOKS_DIR:
            problems.append(f"core.hooksPath is not {HOOKS_DIR} — run `vibey-gh install`")

    return (not problems), problems
