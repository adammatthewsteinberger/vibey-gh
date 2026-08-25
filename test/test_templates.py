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

from vibey_gh.config import DocumentationConfig, GhConfig, load_config
from vibey_gh.install import TEMPLATES, WORKFLOWS, installed, render_workflow

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
    assert len(schemas) == 6


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


def test_release_surfaces_google_analytics_is_generic_and_off_by_default(tmp_path: Path):
    text = (WORKFLOWS / "release-surfaces.yml").read_text(encoding="utf-8")
    assert "__VIBEY_GH_DOC_GOOGLE_ANALYTICS_ID__" in text
    assert "googletagmanager.com/gtag/js" in text
    assert "__GA_SNIPPET__" in text
    disabled = render_workflow(WORKFLOWS / "release-surfaces.yml", load_config())
    assert "__VIBEY_GH_DOC_GOOGLE_ANALYTICS_ID__" not in disabled
    assert 'GA_ID=""' in disabled
    enabled = render_workflow(
        WORKFLOWS / "release-surfaces.yml",
        GhConfig(
            root=tmp_path,
            documentation=DocumentationConfig(google_analytics_id="G-ABC1234567"),
        ),
    )
    assert 'GA_ID="G-ABC1234567"' in enabled


def test_documentation_workflow_authors_guarded_refresh_prs():
    text = (WORKFLOWS / "documentation.yml").read_text(encoding="utf-8")
    assert "name: Docs" in text
    assert "vibey-gh check --ci" in text
    assert (
        "anthropics/claude-code-action@8569a83495a3f6f0c50a90e46351d3816fed1a75" in text
    )
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
    assert "--disallowedTools Agent" in text
    assert "Bash(gh pr diff:*)" in text
    assert "Bash(gh:pr:diff:*)" not in text


def test_security_and_api_drift_workflows_are_real_managed_gates():
    text = (WORKFLOWS / "pr-automation.yml").read_text(encoding="utf-8")
    codeql = (WORKFLOWS / "codeql.yml").read_text(encoding="utf-8")
    drift = (WORKFLOWS / "api-drift.yml").read_text(encoding="utf-8")
    assert "name: CodeQL" in codeql
    assert (
        "github/codeql-action/init@6d786de4d6f3531a740e445b53a42b622bbbace8" in codeql
    )
    assert (
        "github/codeql-action/analyze@6d786de4d6f3531a740e445b53a42b622bbbace8"
        in codeql
    )
    assert "name: API drift (Cloud Agents OpenAPI)" in drift
    assert "MCP, API, CLI, SDK, and webhook parity" in drift
    assert "from vibey_gh.surfaces import CAPABILITIES, SURFACES, parity" in drift
    assert "if tuple(actual) != expected_capabilities:" in drift
    assert "if tuple(surfaces) != expected_surfaces" in drift
    assert "if tuple(actual) != tuple(SURFACES):" not in drift
    assert "Do not spawn subagents" in text
    assert text.count("GH_REPO: ${{ github.repository }}") >= 2
    assert "isolated temporary" in text
    assert text.count("Create credential-free Claude git context") == 3
    assert text.count("Remove credential-free Claude git context") == 3
    assert (
        text.count('git remote add origin "https://github.com/${{ github.repository }}.git"') == 3
    )
    assert text.count('allowed_non_write_users: "__vibey_gh_no_nonwrite_users__"') == 3
    assert text.count("persist-credentials: false") >= 3
    assert "gitdir: $GITHUB_WORKSPACE/target/.git" not in text
    assert "TRUSTED: ${{ needs.evaluate.outputs.trusted }}" not in text
    assert '[ "$STATE" = ready ] || [ "$STATE" = review ]' in text
    # Only an explicit `true` verdict may pass the gate; every other value, including
    # the empty string a failed review job leaves behind, fails closed.
    assert re.search(
        r'case "\$REVIEW_PASSED" in\n\s+true\)\n\s+conclusion=success\n', text
    )
    assert "full_claude_output:" in text
    assert "Validate diagnostic output policy" in text
    assert "github.event.repository.visibility == 'private'" in text
    assert text.count("track_progress: ${{ __VIBEY_GH_SANITIZED_PROGRESS__ &&") == 3
    assert text.count("github.event_name == 'pull_request_review'") == 3
    assert "github.event_name == 'workflow_dispatch') }}" not in text
    assert text.count("show_full_output:") == 3
    assert text.count("__VIBEY_GH_ALLOW_PRIVATE_FULL_OUTPUT__") == 4
    assert text.count("__VIBEY_GH_ARCHIVE_EXECUTION_FILE__") == 3
    assert "Full Claude output is disabled or unsafe" in text
    assert "Collect exact-head failed-check evidence" in text
    assert "repos/${REPO}/commits/${HEAD_SHA}/check-runs" in text
    assert "diagnostics/failed-checks.txt" in text
    assert "--log-failed" in text
    assert "diagnostic bundle truncated at 200000 bytes" in text
    assert "Read that file before" in text
    for field in (
        "complete",
        "accurate",
        "human_readable",
        "architecture_diagram_complete",
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
    # Only an explicit `true` verdict may pass the gate; every other value, including
    # the empty string a failed review job leaves behind, fails closed.
    assert re.search(
        r'case "\$REVIEW_PASSED" in\n\s+true\)\n\s+conclusion=success\n', text
    )


def test_branch_intake_reopens_a_reused_branch_name_without_duplicating_open_prs():
    text = (WORKFLOWS / "branch-intake.yml").read_text(encoding="utf-8")
    assert "github.event.created == true" not in text
    assert "github.event.deleted != true" in text
    assert 'gh pr list --repo "$REPO" --state open --head "$HEAD_REF"' in text
    assert "historical closed PR must never suppress intake" in text


def test_automation_bootstrap_is_explicit_exact_head_and_permanent_branch_safe():
    text = (WORKFLOWS / "automation-bootstrap.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "inputs.authorize == true" in text
    assert 'test "$permission" = admin' in text
    assert 'test "$(jq -r .headRefOid' in text
    assert '--match-head-commit "$EXPECTED_SHA"' in text
    for required in (
        "Documentation contract",
        "Provenance",
        "Build",
        "Lint",
        "Analyze Python",
        "MCP, API, CLI, SDK, and webhook parity",
    ):
        assert required in text
    assert '[ "$head" != "$INTEGRATION_BRANCH" ]' in text
    assert '[ "$head" != "$RELEASE_BRANCH" ]' in text
    assert '[ "$head" != develop ]' in text
    assert '[ "$head" != main ]' in text
    assert "--delete-branch" not in text


def test_automation_bootstrap_scope_check_rejects_files_outside_automation_core():
    import subprocess

    text = (WORKFLOWS / "automation-bootstrap.yml").read_text(encoding="utf-8")
    match = re.search(
        r"if grep -Ev '([^']+)' changed-files\.txt; then\n"
        r"\s*echo \"::error::changed files are not confined to automation-core paths\" >&2\n"
        r"\s*exit 1\n"
        r"\s*fi",
        text,
    )
    assert match, "expected a fail-closed scope check in automation-bootstrap.yml"
    pattern = match.group(1)

    in_scope_only = (
        "vibey_gh/templates/workflows/automation-bootstrap.yml\ntest/test_templates.py\n"
    )
    mixed_scope = in_scope_only + "vibey_gh/versioning.py\n"

    def confinement_check_passes(changed_files: str) -> bool:
        # Mirrors the workflow's own gate: `if grep -Ev ...; then <fail>; fi` fails the
        # step when grep finds an out-of-scope line (exit 0), and passes when grep finds
        # none (exit 1, no matches).
        script = f"grep -Ev '{pattern}' <<'EOF'\n{changed_files}EOF\n"
        result = subprocess.run(
            ["sh", "-c", script], capture_output=True, text=True, check=False
        )
        return result.returncode != 0

    assert confinement_check_passes(in_scope_only)
    assert not confinement_check_passes(mixed_scope)


def test_pr_review_requires_verified_repository_paths():
    text = (WORKFLOWS / "pr-automation.yml").read_text(encoding="utf-8")

    assert "Inspect target/ with Read, Glob, and Grep only" in text
    assert "verify its path exists under target/ with Read or Glob" in text
    assert "Never return schema" in text
    assert "fail the review action so infrastructure recovery can retry it" in text


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
    assert "link.href = pagesRoot" in script
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
    assert "Create credential-free Claude git context" in text
    assert "Remove credential-free Claude git context" in text
    assert (
        'git remote add origin "https://github.com/${{ github.repository }}.git"'
        in text
    )
    assert 'allowed_non_write_users: "__vibey_gh_no_nonwrite_users__"' in text
    assert "persist-credentials: false" in text
    assert "gitdir: $GITHUB_WORKSPACE/target/.git" not in text
    assert 'repair_branch="vibey-gh/repair/release-' in text
    assert 'git -C target push origin "HEAD:refs/heads/${REPAIR_BRANCH}"' in text
    assert 'gh pr create --repo "$REPO" --base "$BASE_BRANCH"' in text
    assert "git push --delete" not in text
    assert "git branch -D" not in text
    assert "HEAD:refs/heads/${BASE_BRANCH}" not in text


@pytest.mark.parametrize(
    "paths,match",
    [
        (("/abs/CHANGELOG.md",), "repository-relative"),
        (("../outside.md",), "repository-relative"),
        (("a", "a"), "must be unique"),
        ((" ",), "must be non-empty"),
    ],
)
def test_unsafe_union_merge_paths_are_rejected(tmp_path, paths, match):
    from vibey_gh.config import GhConfig

    with pytest.raises(ValueError, match=match):
        GhConfig(root=tmp_path, union_merge_paths=paths)


def test_a_repository_can_decline_the_union_merge_rule_entirely(tmp_path):
    from vibey_gh.config import GhConfig
    from vibey_gh.install import apply_union_merge, missing_union_merge_lines

    cfg = GhConfig(root=tmp_path, union_merge_paths=())
    assert apply_union_merge(cfg) is None
    assert missing_union_merge_lines(cfg) == []
    assert not (tmp_path / ".gitattributes").exists()


def test_append_only_files_merge_instead_of_conflicting(tmp_path):
    """Every branch appends to the changelog, so every merge stranded every other branch
    on a conflict carrying no information. `merge=union` keeps both sides."""
    import subprocess

    from vibey_gh.config import GhConfig
    from vibey_gh.install import apply_union_merge

    def git(*args, cwd=tmp_path):
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)

    git("init", "-q", "-b", "main", ".")
    git("config", "user.email", "t@e.com")
    git("config", "user.name", "t")
    cfg = GhConfig(root=tmp_path)
    assert apply_union_merge(cfg) == "installed"
    log = tmp_path / "CHANGELOG.md"
    log.write_text("# Changelog\n\n## Unreleased\n\n- base\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "base")

    git("switch", "-qc", "topic")
    log.write_text("# Changelog\n\n## Unreleased\n\n- base\n- from the topic\n", encoding="utf-8")
    git("commit", "-qam", "topic")
    git("switch", "-q", "main")
    log.write_text("# Changelog\n\n## Unreleased\n\n- base\n- from develop\n", encoding="utf-8")
    git("commit", "-qam", "develop")

    git("switch", "-q", "topic")
    assert git("rebase", "main").returncode == 0, "the union driver should absorb this"
    settled = log.read_text(encoding="utf-8")
    assert "- from develop" in settled and "- from the topic" in settled
    assert "<<<<<<<" not in settled


def test_the_union_declaration_never_rewrites_an_adopters_own_attributes(tmp_path):
    from vibey_gh.config import GhConfig
    from vibey_gh.install import GITATTRIBUTES, apply_union_merge, missing_union_merge_lines

    theirs = tmp_path / GITATTRIBUTES
    theirs.write_text("*.png binary\n", encoding="utf-8")
    cfg = GhConfig(root=tmp_path)
    assert apply_union_merge(cfg) == "updated"
    text = theirs.read_text(encoding="utf-8")
    assert "*.png binary" in text, "an adopter's own rules must survive adoption"
    assert "CHANGELOG.md merge=union" in text
    # Idempotent: a second install changes nothing and reports nothing missing.
    assert apply_union_merge(cfg) is None
    assert missing_union_merge_lines(cfg) == []
    assert theirs.read_text(encoding="utf-8") == text


def test_an_attributes_file_without_a_trailing_newline_is_appended_safely(tmp_path):
    from vibey_gh.config import GhConfig
    from vibey_gh.install import GITATTRIBUTES, apply_union_merge

    (tmp_path / GITATTRIBUTES).write_text("*.png binary", encoding="utf-8")
    cfg = GhConfig(root=tmp_path)
    apply_union_merge(cfg)
    lines = (tmp_path / GITATTRIBUTES).read_text(encoding="utf-8").splitlines()
    assert lines[0] == "*.png binary"
    assert "CHANGELOG.md merge=union" in lines


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


def test_conventional_commits_self_heal_only_guarded_topic_history():
    text = (WORKFLOWS / "conventional-commits.yml").read_text(encoding="utf-8")
    assert "pull_request_target:" in text
    assert "vibey-gh conventional-check" in text
    assert "vibey-gh conventional-message" in text
    assert "working-directory: target" in text
    assert '--force-with-lease="refs/heads/${HEAD_REF}:${HEAD_SHA}"' in text
    assert '"$INTEGRATION_BRANCH"|"$RELEASE_BRANCH"|develop|main' in text
    assert "permanent branch history is never rewritten" in text
    assert (
        "github.event.pull_request.head.ref != '__VIBEY_GH_INTEGRATION_BRANCH__'"
        in text
    )
    assert "github.event.pull_request.head.ref != '__VIBEY_GH_RELEASE_BRANCH__'" in text
    assert "Refusing automatic rewrite of merge commits" in text
    assert "./target" not in text
    assert "git push --delete" not in text
    assert "--delete-branch" not in text


def test_conventional_commits_installs_the_published_package_not_the_adopting_repo():
    """A repo with `dependencies = []` that only pulls in vibey-gh as a CI tool must not
    have this step assume its own `pip install .` yields the vibey-gh CLI.
    """
    text = (WORKFLOWS / "conventional-commits.yml").read_text(encoding="utf-8")
    assert "pip install --quiet ./automation" not in text
    assert 'grep -qE \'^name = "vibey-(gh|bootstrap)"\' pyproject.toml' in text
    assert "python -m pip install --quiet -e ." in text
    assert "python -m pip install --quiet vibey-gh" in text
    assert "name: Check out trusted automation" in text
    assert "name: Check out trusted normalizer" not in text

    # The step that actually decides whether commits conform must fail loudly, not
    # treat "vibey-gh: command not found" as a false `if` condition that then barrels
    # ahead into a doomed git filter-branch.
    normalize = text.split("name: Normalize every nonconforming commit message", 1)[1]
    guard = normalize.split("if vibey-gh conventional-check", 1)[0]
    assert "command -v vibey-gh" in guard
    assert "exit 1" in guard


def test_pr_automation_never_assumes_the_adopting_repos_own_package_is_vibey_gh():
    """Every `automation/` checkout of the adopting repo's default branch must detect
    self-hosting before installing from it, the same class of bug as the conventional-
    commits template: a repo with `dependencies = []` does not yield the vibey-gh CLI
    from `pip install ./automation`.
    """
    text = (WORKFLOWS / "pr-automation.yml").read_text(encoding="utf-8")
    assert "pip install --quiet ./automation" not in text
    checks = re.findall(
        r"""grep -qE '\^name = "vibey-gh"' automation/pyproject\.toml""", text
    )
    assert len(checks) == 4
    installs = re.findall(r"python -m pip install --quiet vibey-gh\b", text)
    assert len(installs) == 5  # the four guarded installs above plus the evaluate job's own


def test_promotion_checks_provenance_without_rewriting_or_reauditing_history():
    text = (WORKFLOWS / "provenance.yml").read_text(encoding="utf-8")
    assert 'if [ "$HEAD_REF" = "$INTEGRATION_BRANCH" ]' in text
    assert '[ "$BASE_REF" = "$RELEASE_BRANCH" ]' in text
    assert "Promotion PR: checking repository provenance" in text
    assert "vibey-gh check --ci" in text
    assert 'vibey-gh check --ci --commits "${BASE_SHA}..HEAD"' in text


def test_every_managed_third_party_action_is_immutably_pinned():
    for path in [*WORKFLOW_TEMPLATES, *REPO_WORKFLOWS]:
        for action, revision in re.findall(
            r"uses:\s+([^@\s]+)@([^\s#]+)", path.read_text()
        ):
            assert re.fullmatch(
                r"[0-9a-f]{40}", revision
            ), f"{path.name}: {action}@{revision}"


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
    assert "Skipping stale repair: expected $EXPECTED_SHA, found $current" in text
    assert "Discarding stale repair after concurrent update to $current" in text
    assert (
        "Skipping stale conflict resolution: expected $EXPECTED_SHA, found $current"
        in text
    )
    assert (
        "Discarding stale conflict resolution after concurrent update to $current"
        in text
    )
    assert "if: steps.publish.outputs.stale != 'true'" in text
    assert "git -C target push --force" not in text


def test_ai_state_persistence_uses_the_native_github_token():
    text = (WORKFLOWS / "pr-automation.yml").read_text(encoding="utf-8")
    assert "steps.claude.outputs.github_token" not in text
    assert text.count("GH_TOKEN: ${{ github.token }}") >= 6


def test_a_review_that_returned_no_verdict_is_not_reported_as_a_source_defect():
    """A failing gate whose summary says everything passed sends people hunting a bug
    that is not there. An unfinished review is an operator failure and must read as one.
    """
    text = (WORKFLOWS / "pr-automation.yml").read_text(encoding="utf-8")
    assert "REVIEW_RESULT: ${{ needs.review.result }}" in text
    # Each review outcome gets its own honest title; only `true` may pass the gate.
    assert 'case "$REVIEW_PASSED" in' in text
    assert "conclusion=success" in text
    assert 'title="PR automation: review findings"' in text
    assert "returned actionable findings" in text
    assert 'title="PR automation: review incomplete"' in text
    assert "infrastructure or operator failure rather than a defect" in text
    assert "API credit balance, credentials, or model availability" in text
    assert '-f "output[title]=${title}"' in text
    assert '-f "output[summary]=${summary} Run ' in text
    assert "review_passed=${REVIEW_PASSED:-<none>}" in text


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
    assert (
        "needs.evaluate.outputs.evaluated_head_sha == needs.evaluate.outputs.head_sha"
        in text
    )
    assert "reason=${REASON}" in text
    assert 'select(.state == "open")' in text
    assert "github.event.workflow_run.pull_requests[0].number" in text


def test_draft_evaluation_is_nonterminal_until_ready_draft_promotes_it():
    source = (Path(__file__).resolve().parent.parent / "vibey_gh/pr_automation.py").read_text(
        encoding="utf-8"
    )
    assert (
        'return result("pending", "pull request is a draft awaiting a stable head")'
        in source
    )


def test_new_branch_intake_is_draft_idempotent_and_excludes_permanent_branches():
    text = (WORKFLOWS / "branch-intake.yml").read_text(encoding="utf-8")
    assert "github.event.created == true" not in text
    assert "github.event.deleted != true" in text
    assert "gh pr list" in text
    assert "gh pr create" in text and "--draft" in text
    assert "secrets.AUTOMERGE_TOKEN || github.token" in text
    assert "__VIBEY_GH_INTEGRATION_BRANCH__" in text
    assert "__VIBEY_GH_RELEASE_BRANCH__" in text
    assert '"vibey-gh/repair/**"' in text
    assert '"__VIBEY_GH_ISSUE_BRANCH_PREFIX__/**"' in text


@pytest.mark.parametrize("path", WORKFLOW_TEMPLATES, ids=lambda p: p.name)
def test_every_rendered_run_block_is_valid_shell(path):
    """The same argument as the hooks: a broken script fails in somebody else's repo.

    Templates are checked *rendered*, because a marker substituted into the middle of a
    `case` arm or a quoted string is exactly where a syntax error would be introduced.
    """
    import subprocess

    parsed = yaml.safe_load(render_workflow(path, load_config()))
    for job, definition in parsed["jobs"].items():
        for step in definition.get("steps", []):
            script = step.get("run")
            if not script:
                continue
            result = subprocess.run(
                ["bash", "-n"],
                input=script,
                text=True,
                capture_output=True,
                check=False,
            )
            assert (
                result.returncode == 0
            ), f"{path.name}:{job}:{step.get('name')}: {result.stderr}"


def test_the_configured_formatters_agree_with_each_other(tmp_path):
    """`ruff` and `isort` both enforce import order, and left unmatched they disagree.

    A repository whose formatters reject each other's output cannot be made green by any
    number of attempts — which is exactly how an automated repair budget gets spent
    without converging. The shape below is the one that first exposed it: a module
    imported both plainly and under an alias.
    """
    import shutil
    import subprocess

    root = Path(__file__).resolve().parent.parent
    if not shutil.which("ruff") or not shutil.which("isort"):  # pragma: no cover
        pytest.skip("formatters are not installed")
    shutil.copy(root / "pyproject.toml", tmp_path / "pyproject.toml")
    probe = tmp_path / "probe.py"
    probe.write_text(
        "from __future__ import annotations\n\n"
        "from vibey_gh import github_release, merge_train\n"
        "from vibey_gh import realign as realign_mod\n"
        "from vibey_gh import reconcile\n\n"
        "USED = (github_release, merge_train, realign_mod, reconcile)\n",
        encoding="utf-8",
    )

    def run(*command):
        return subprocess.run(command, cwd=tmp_path, capture_output=True, check=False)

    run("isort", "-q", str(probe))
    run("ruff", "check", "--fix", "-q", str(probe))
    run("isort", "-q", str(probe))
    settled = probe.read_text(encoding="utf-8")

    assert run("ruff", "check", str(probe)).returncode == 0, "ruff rejects isort's output"
    assert run("isort", "--check-only", str(probe)).returncode == 0, "isort rejects ruff's"
    # And the pair is stable: another pass of either changes nothing.
    run("ruff", "check", "--fix", "-q", str(probe))
    run("isort", "-q", str(probe))
    assert probe.read_text(encoding="utf-8") == settled, "the formatters oscillate"


def test_a_solution_attempt_that_produced_nothing_still_says_so_on_the_issue():
    """Silence costs the same tokens and minutes as a refusal but leaves the issue looking
    untouched, so nobody knows an attempt was made or why it stopped."""
    text = (WORKFLOWS / "issue-automation.yml").read_text(encoding="utf-8")
    assert "AGENT_RESULT: ${{ steps.claude.outcome }}" in text
    assert 'if [ -z "${STRUCTURED:-}" ]; then' in text
    assert "vibey-gh-issue-attempt-failed" in text
    assert "returned no result (agent step: ${AGENT_RESULT})" in text
    # The advice names the cause the observed failure actually had.
    assert "too large to complete in one attempt" in text
    assert "exhausted API credit balance" in text
    # Commented exactly once, and the issue is labelled so it is visible in a listing.
    assert 'grep -Fq "$marker"' in text
    assert "--add-label vibey-gh:solve-blocked" in text
    # The turn budget is configuration, not a constant nobody can reach.
    assert "--max-turns __VIBEY_GH_ISSUE_MAX_TURNS__" in text


def test_the_repair_job_normalizes_formatting_it_cannot_ask_the_agent_to_run():
    """The agent has no shell, so formatting is the one failure it cannot fix itself."""
    text = (WORKFLOWS / "pr-automation.yml").read_text(encoding="utf-8")
    assert "Normalize formatting deterministically" in text
    assert "working-directory: target" in text
    assert "ruff check --fix ." in text
    assert "isort ." in text
    assert "black ." in text
    # It must read the repository's own settings rather than guess, and run before the
    # commit that publishes the repair.
    assert text.index("Normalize formatting") < text.index("Publish one guarded repair commit")
    assert "python -m pip install --quiet -e ./target" not in text
    assert "do not execute repository code" in text.lower()


@pytest.mark.parametrize("name", ["pre-push", "commit-msg"])
def test_every_shipped_hook_is_valid_shell(name):
    import subprocess

    result = subprocess.run(
        ["sh", "-n", str(TEMPLATES / name)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
