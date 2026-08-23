# Made with ❤️ by [Vibey](https://adammatthewsteinberger.github.io/vibey/), Developed by [Adam Matthew Steinberger](https://hire.adam.matthewsteinberger.com/) ([@adammatthewsteinberger](https://github.com/adammatthewsteinberger/)).
"""The shipped templates are product, so they get tested like product.

A workflow template that does not parse installs cleanly and then fails in the consuming
repository, where GitHub reports it only as the file path with no log — which is a
miserable thing to debug from the other end. Cheaper to catch here.
"""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

import pytest
import yaml

from vibey_gh.config import load_config
from vibey_gh.install import TEMPLATES, WORKFLOWS, installed

WORKFLOW_TEMPLATES = sorted(WORKFLOWS.glob("*.yml"))
REPO_WORKFLOWS = sorted(
    (Path(__file__).resolve().parent.parent / ".github/workflows").glob("*.yml")
)


@pytest.mark.parametrize("path", WORKFLOW_TEMPLATES, ids=lambda p: p.name)
def test_every_shipped_workflow_template_parses(path):
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    assert parsed.get("jobs")


def test_every_claude_json_schema_survives_argument_tokenization():
    schemas = []
    for path in WORKFLOW_TEMPLATES:
        for line in path.read_text(encoding="utf-8").splitlines():
            if "--json-schema " not in line:
                continue
            tokens = shlex.split(line.strip())
            index = tokens.index("--json-schema")
            schema = json.loads(tokens[index + 1])
            assert schema["type"] == "object"
            assert schema["properties"]
            schemas.append((path.name, schema))
    assert len(schemas) == 5


@pytest.mark.parametrize("path", REPO_WORKFLOWS, ids=lambda p: p.name)
def test_this_repository_s_own_workflows_parse(path):
    """Dogfooding: the tool's own CI is subject to the rule it enforces elsewhere."""
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    assert parsed.get("jobs")


def test_release_environments_are_disjoint_by_branch():
    """main must never request TestPyPI, whose environment permits only develop."""
    release = yaml.safe_load(
        (Path(__file__).resolve().parent.parent / ".github/workflows/release.yml").read_text(
            encoding="utf-8"
        )
    )
    jobs = release["jobs"]
    assert jobs["testpypi"]["if"] == "github.ref == 'refs/heads/develop'"
    assert jobs["testpypi"]["environment"] == "testpypi"
    assert jobs["testpypi"]["needs"] == "build"
    assert jobs["pypi"]["if"] == "github.ref == 'refs/heads/main'"
    assert jobs["pypi"]["environment"] == "pypi"
    assert jobs["pypi"]["needs"] == "build"
    assert "verify" not in jobs


def test_release_surfaces_preserve_both_docs_channels_and_publish_oci_packages():
    text = (WORKFLOWS / "release-surfaces.yml").read_text(encoding="utf-8")
    assert 'workflows: ["Release"]' in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "channel=develop" in text and "channel=main" in text
    assert "pages/${CHANNEL}" in text
    assert "pages/${OTHER_CHANNEL}" in text
    assert "while read -r other_run" in text
    assert '--name "docs-${OTHER_CHANNEL}"' in text
    assert "docs-${OTHER_CHANNEL}" in text
    assert "properdocs==1.6.7" in text
    assert "properdocs-theme-mkdocs==1.6.7" in text
    assert "packages: write" in text
    assert "ghcr.io/${GITHUB_REPOSITORY,,}/python" in text
    assert "application/vnd.pypi.project.release.v1" in text
    assert 'oras tag "${package}:${VERSION}" "$CHANNEL" "sha-${RELEASE_SHA}"' in text
    assert 'oras tag "${package}:${VERSION}" latest' in text
    assert "--delete" not in text
    assert "Build boldly." in text
    assert "prefers-reduced-motion" in text
    assert "Documentation channels" in text
    assert "color-scheme: dark" in text
    assert "__REPOSITORY_NAME__" in text
    assert "__REPOSITORY_URL__" in text
    assert "__RELEASE_SHA__" in text
    assert "vibey-gh:repository" in text
    assert "managed release theme is missing" in text
    assert "Made with ❤️ by" in text
    assert "https://adammatthewsteinberger.github.io/vibey/" in text
    assert "https://hire.adam.matthewsteinberger.com" in text
    assert "pages/robots.txt" in text
    assert "pages/sitemap.xml" in text
    assert "pages/llms.txt" in text and "pages/llms-full.txt" in text
    assert 'rel="canonical"' in text
    assert "application/ld+json" in text
    assert "noindex,nofollow" in text


def test_documentation_workflow_authors_guarded_refresh_prs():
    text = (WORKFLOWS / "documentation.yml").read_text(encoding="utf-8")
    assert "name: Docs" in text
    assert "vibey-gh check --ci" in text
    assert "anthropics/claude-code-action@8569a83495a3f6f0c50a90e46351d3816fed1a75" in text
    assert "This is an authoring" in text
    assert "--allowedTools Read,Glob,Grep,Edit,Write" in text
    assert 'branch="vibey-gh/docs/refresh-${RUN_ID}"' in text
    assert 'git push origin "HEAD:refs/heads/${BRANCH}"' in text
    assert "gh pr create" in text
    assert ".complete == true" in text
    assert "gaps_remaining // []" in text
    assert "gh pr create" in text and '--body "$body" || true' not in text
    assert "Never execute repository code" in text
    assert "git push --delete" not in text
    assert "--force" not in text


def test_pr_gate_requires_exact_head_semantic_documentation_review_for_every_author():
    text = (WORKFLOWS / "pr-automation.yml").read_text(encoding="utf-8")
    assert "Exact-head code and documentation review" in text
    assert "needs.evaluate.outputs.state == 'ready'" in text
    assert "repository-wide semantic documentation audit" in text
    assert "complete, approachable guide" in text
    for field in (
        "complete",
        "accurate",
        "human_readable",
        "all_capabilities_documented",
        "all_commands_documented",
        "all_configuration_documented",
        "examples_sufficient",
        "onboarding_sufficient",
        "operations_sufficient",
        "security_sufficient",
        "release_process_sufficient",
        "links_valid",
    ):
        assert f'"{field}"' in text
        assert f".{field} == true" in text
    assert "((.findings // []) | length == 0)" in text
    assert "Exact-head semantic review result:" in text
    assert '[ "$REVIEW_PASSED" = true ]' in text


def test_properdocs_theme_is_channel_aware_and_accessible():
    root = Path(__file__).resolve().parent.parent
    config = (root / "properdocs.yml").read_text(encoding="utf-8")
    css = (root / "docs/stylesheets/vibey.css").read_text(encoding="utf-8")
    script = (root / "docs/javascripts/channel.js").read_text(encoding="utf-8")
    assert "stylesheets/vibey.css" in config
    assert "javascripts/channel.js" in config
    assert "md_in_html" in config and "attr_list" in config
    assert 'body[data-release-channel="main"]' in css
    assert 'body[data-release-channel="develop"]' in css
    assert "prefers-reduced-motion" in css
    assert "padding-top: 0" in css
    assert "position: sticky" in css
    assert "top: 0" in css
    assert 'dataset.bsTheme = "dark"' in script
    assert 'segments.includes("develop")' in script
    assert "/edit/${channel}/" in script
    assert "__REPOSITORY__@__SHORT_SHA__" in script
    assert "__RELEASE_BRANCH__" in script
    assert "__RELEASE_CHANNEL__" in script
    assert "Made with ❤️ by" in script
    assert "https://adammatthewsteinberger.github.io/vibey/" in script
    assert "https://hire.adam.matthewsteinberger.com" in script
    assert "https://github.com/adammatthewsteinberger/" in script
    assert "__PAGES_ROOT__" in script
    assert '["__PRODUCTION_LABEL__", "main"]' in script
    assert '["__PREVIEW_LABEL__", "develop"]' in script
    assert "Release channels: release-channels.md" not in config
    index = (root / "docs/index.md").read_text(encoding="utf-8")
    assert 'data-release-target="main"' in index
    assert 'data-release-target="develop"' in index
    assert "link.dataset.releaseTarget" in script


def test_repository_profile_is_configurable_and_never_mutates_branches():
    text = (WORKFLOWS / "repository-profile.yml").read_text(encoding="utf-8")
    assert 'workflows: ["Release surfaces"]' in text
    assert "__VIBEY_GH_PROFILE_DESCRIPTION__" in text
    assert "__VIBEY_GH_PROFILE_TOPICS__" in text
    assert '--arg homepage "$pages_url"' in text
    assert "repos/${REPO}/topics" in text
    assert "__VIBEY_GH_PROFILE_SETTINGS__" in text
    assert "vulnerability-alerts" in text
    assert "automated-security-fixes" in text
    assert text.count("secrets.AUTOMERGE_TOKEN || github.token") == 2
    assert "Unable to verify ${setting}" in text
    assert "HTTP 404" in text
    assert "branches/${branch}" in text
    assert "--jq .protected" in text
    assert "https://${OWNER}.github.io/${REPO_NAME}/" in text
    assert "curl --fail --silent --show-error" in text
    assert "repos/${REPO}/releases?per_page=1" in text
    assert "repos/${REPO}/deployments?per_page=1" in text
    assert "scope=repository:${package}:pull" in text
    assert "https://ghcr.io/v2/${package}/manifests/${channel}" in text
    assert "git push" not in text
    assert "--delete" not in text


def test_failed_permanent_branch_scans_use_a_guarded_repair_pr():
    text = (WORKFLOWS / "release-repair.yml").read_text(encoding="utf-8")
    assert (
        'workflows: ["CI", "Provenance", "Release", "Release surfaces", "GitHub Release"]' in text
    )
    assert "github.event.workflow_run.conclusion == 'failure'" in text
    assert '"$INTEGRATION_BRANCH"|"$RELEASE_BRANCH"' in text
    assert "mcp__github_ci__download_job_log" in text
    assert "Never execute package managers" in text
    assert "Never lower coverage" in text
    assert 'repair_branch="vibey-gh/repair/release-' in text
    assert 'git -C target push origin "HEAD:refs/heads/${REPAIR_BRANCH}"' in text
    assert 'gh pr create --repo "$REPO" --base "$BASE_BRANCH"' in text
    assert "git push --delete" not in text
    assert "git branch -D" not in text
    assert "HEAD:refs/heads/${BASE_BRANCH}" not in text


def test_repository_dogfoods_the_exact_rendered_workflows_and_hooks():
    root = Path(__file__).resolve().parent.parent
    ok, problems = installed(load_config(root), local=False)
    assert ok, problems


def test_managed_automation_can_update_but_never_delete_develop_or_main():
    text = "\n".join(path.read_text(encoding="utf-8") for path in WORKFLOW_TEMPLATES)
    assert "HEAD:refs/heads/${HEAD_REF}" in text
    assert "--delete-branch" not in text
    assert "git push --delete" not in text
    assert "git branch -D" not in text
    assert "DELETE /git/refs" not in text


def test_every_managed_third_party_action_is_immutably_pinned():
    for path in [*WORKFLOW_TEMPLATES, *REPO_WORKFLOWS]:
        for action, revision in re.findall(r"uses:\s+([^@\s]+)@([^\s#]+)", path.read_text()):
            assert re.fullmatch(r"[0-9a-f]{40}", revision), f"{path.name}: {action}@{revision}"


def test_privileged_agent_cannot_mutate_git_or_execute_pr_code():
    text = (WORKFLOWS / "pr-automation.yml").read_text(encoding="utf-8")
    assert "Bash(git:" not in text
    assert "Never execute package\n" in text
    assert "python -m pip install --quiet ./target" not in text
    assert "run: ./target" not in text
    assert "Resolve merge conflicts" in text
    assert "--allowedTools Read,Glob,Grep,Edit" in text
    assert 'git -C target push origin "HEAD:refs/heads/${HEAD_REF}"' in text
    assert "resolver edited non-conflict path" in text
    assert text.count("secrets.AUTOMERGE_TOKEN || github.token") >= 3


def test_cancelled_or_pending_evaluations_cannot_publish_a_gate():
    text = (WORKFLOWS / "pr-automation.yml").read_text(encoding="utf-8")
    assert "pull_request_target:" in text
    assert "types: [opened, reopened, synchronize, ready_for_review]" in text
    assert "github.event.pull_request.number" in text
    assert "github.event.pull_request.head.sha" in text
    assert "always() && !cancelled()" in text
    assert "needs.evaluate.result == 'success'" in text
    assert "needs.evaluate.outputs.state != 'pending'" in text
    assert "needs.evaluate.outputs.state != ''" in text
    assert "needs.evaluate.outputs.evaluated_head_sha == needs.evaluate.outputs.head_sha" in text
    assert "reason=${REASON}" in text
    assert 'select(.state == "open")' in text
    assert "github.event.workflow_run.pull_requests[0].number" in text


def test_new_branch_intake_is_draft_idempotent_and_excludes_permanent_branches():
    text = (WORKFLOWS / "branch-intake.yml").read_text(encoding="utf-8")
    assert "github.event.created == true" in text
    assert "gh pr list" in text
    assert "gh pr create" in text and "--draft" in text
    assert "secrets.AUTOMERGE_TOKEN || github.token" in text
    assert "__VIBEY_GH_INTEGRATION_BRANCH__" in text
    assert "__VIBEY_GH_RELEASE_BRANCH__" in text
    assert '"vibey-gh/repair/**"' in text


@pytest.mark.parametrize("name", ["pre-push", "commit-msg"])
def test_every_shipped_hook_is_valid_shell(name):
    import subprocess

    result = subprocess.run(
        ["sh", "-n", str(TEMPLATES / name)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
