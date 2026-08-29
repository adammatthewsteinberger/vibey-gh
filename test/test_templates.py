# Made with ❤️ by [Vibey](https://adammatthewsteinberger.github.io/vibey/), Developed by [Adam Matthew Steinberger](https://vibewithadam.matthewsteinberger.com/) ([@adammatthewsteinberger](https://github.com/adammatthewsteinberger/)).
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

from vibey_gh.config import (
    DEFAULT_SCAN_WORKFLOWS,
    AiConfig,
    DocumentationConfig,
    GhConfig,
    load_config,
)
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
    assert len(schemas) == 7


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
    # Both the version and any extra site packages are rendered from configuration, so the
    # template carries placeholders rather than a pinned literal.
    assert "properdocs==__VIBEY_GH_PROPERDOCS_VERSION__" in text
    assert "properdocs-theme-mkdocs==__VIBEY_GH_PROPERDOCS_VERSION__" in text
    assert "__VIBEY_GH_DOC_SITE_REQUIREMENTS__" in text
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
    assert "https://vibewithadam.matthewsteinberger.com" in text
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
    # An explicitly-default config, NOT load_config(): that read this repository's own
    # .vibey-gh.toml, so the assertion silently tested repo state rather than the default
    # — and broke the day the repo legitimately configured its own analytics id.
    disabled = render_workflow(WORKFLOWS / "release-surfaces.yml", GhConfig(root=tmp_path))
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


def test_release_surfaces_installs_the_packages_the_site_actually_declares(tmp_path: Path):
    """ProperDocs depends on none of the plugins a real site configures.

    The install line named exactly `properdocs` and its theme, with no way to extend it, so
    a repository whose `properdocs.yml` declared `mkdocs-gen-files` or `pymdownx.*` failed
    `--strict` on the first one it met — the packages are simply absent. A site's
    dependencies follow from its own configuration, so they can only be the adopter's to
    declare.
    """
    rendered = render_workflow(
        WORKFLOWS / "release-surfaces.yml",
        GhConfig(
            root=tmp_path,
            documentation=DocumentationConfig(
                site_requirements=(
                    "mkdocs-gen-files",
                    "pymdown-extensions>=10.7",
                    "mkdocs-material[imaging] >= 9.5",
                ),
                properdocs_version="1.7.0",
            ),
        ),
    )
    assert "__VIBEY_GH" not in rendered
    assert "'properdocs==1.7.0'" in rendered
    assert "mkdocs-gen-files" in rendered
    # Quoted, so a specifier carrying spaces or brackets stays one argument to pip rather
    # than splitting into three or being read as a glob.
    assert shlex.quote("mkdocs-material[imaging] >= 9.5") in rendered
    assert shlex.quote("pymdown-extensions>=10.7") in rendered
    install_line = next(line for line in rendered.split("\n") if "mkdocs-material[imaging]" in line)
    assert shlex.split(install_line) == [
        "properdocs==1.7.0",
        "properdocs-theme-mkdocs==1.7.0",
        "mkdocs-gen-files",
        "pymdown-extensions>=10.7",
        "mkdocs-material[imaging] >= 9.5",
    ]


def test_release_surfaces_adds_nothing_to_the_install_by_default(tmp_path: Path):
    """The default must stay a no-op: an adopter declaring nothing installs nothing extra."""
    rendered = render_workflow(WORKFLOWS / "release-surfaces.yml", GhConfig(root=tmp_path))
    assert "__VIBEY_GH" not in rendered
    assert "'properdocs==1.6.7'" in rendered
    # The requirements-file hook is guarded by its own existence check, so a repository
    # without one runs an install of exactly the two packages and nothing else.
    assert 'if [ -n "docs/requirements.txt" ]' in rendered
    assert '[ -f "docs/requirements.txt" ]' in rendered


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
    assert "--disallowedTools Agent" in text
    assert "Bash(gh pr diff:*)" in text
    assert "Bash(gh:pr:diff:*)" not in text


def test_the_five_surface_self_test_is_this_project_s_own_and_ships_to_nobody():
    """`api-drift.yml` tests vibey-gh, so it is hand-authored here and shipped to no one.

    It ran `from vibey_gh.surfaces import …` and asserted *this* project's capability
    registry — while being installed into every adopting repository as a managed workflow
    and named in the default `scan_workflows`. An adopter got a required-looking gate that
    tested a library rather than their product, and had to work out for themselves that it
    should come back out. `ci.yml` and `release.yml` set the precedent: what is specific to
    one repository is that repository's to author.
    """
    assert not (WORKFLOWS / "api-drift.yml").exists()
    assert "API drift (Cloud Agents OpenAPI)" not in DEFAULT_SCAN_WORKFLOWS
    drift = Path(__file__).resolve().parent.parent / ".github/workflows/api-drift.yml"
    assert drift.is_file(), "this repository still needs its own five-surface self-test"
    text = drift.read_text(encoding="utf-8")
    assert "name: API drift (Cloud Agents OpenAPI)" in text
    assert "MCP, API, CLI, SDK, and webhook parity" in text
    assert "from vibey_gh.surfaces import CAPABILITIES, SURFACES, parity" in text
    assert "if tuple(actual) != expected_capabilities:" in text
    assert "if tuple(surfaces) != expected_surfaces" in text
    assert "if tuple(actual) != tuple(SURFACES):" not in text


def test_security_and_api_drift_workflows_are_real_managed_gates():
    text = (WORKFLOWS / "pr-automation.yml").read_text(encoding="utf-8")
    codeql = (WORKFLOWS / "codeql.yml").read_text(encoding="utf-8")
    assert "name: CodeQL" in codeql
    assert "github/codeql-action/init@6d786de4d6f3531a740e445b53a42b622bbbace8" in codeql
    assert "github/codeql-action/analyze@6d786de4d6f3531a740e445b53a42b622bbbace8" in codeql
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
    assert re.search(r'case "\$REVIEW_PASSED" in\n\s+true\)\n\s+conclusion=success\n', text)
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
        "opening_accessible",
        "opening_bluf",
        "audience_order",
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
    assert re.search(r'case "\$REVIEW_PASSED" in\n\s+true\)\n\s+conclusion=success\n', text)


def test_readability_gate_judges_the_opening_and_the_audience_order():
    """The three copy-doctrine judgments: the README's first screen must survive a reader
    with zero project context (opening_accessible), state the problem before any project
    vocabulary (opening_bluf), and the whole document must serve beginners first, then
    engineers, then scholars, with executive framing essentially absent (audience_order).
    Each is a required schema boolean the jq aggregation folds into `.pass`, so a reviewer
    cannot skip the judgment and still pass the gate."""
    text = (WORKFLOWS / "pr-automation.yml").read_text(encoding="utf-8")
    # The reviewer is told to judge the opening as a stranger, on ordering alone.
    assert "as if you had never seen this repository" in text
    assert "BEFORE any project vocabulary" in text
    assert "opens with what it IS before what it FIXES fails" in text
    # The audience-order doctrine: beginner -> engineer -> scholar, BLUF throughout,
    # executive copy essentially absent.
    assert "beginner-accessible material first" in text
    assert "engineering depth second" in text
    assert "scholarly material (citations, formal references, theory) third" in text
    assert "essentially absent" in text
    # The judgments gate `.pass` in the aggregation, not just the schema.
    for field in ("opening_accessible", "opening_bluf", "audience_order"):
        assert f".{field} == true" in text
    # The local fallback never asserts them: a diff-only model has no basis to certify a
    # README's opening, so they are reported unevaluated instead.
    from vibey_gh import local_review

    for field in ("opening_accessible", "opening_bluf", "audience_order"):
        assert field in local_review.UNEVALUATED_FIELDS
        assert field not in local_review.REVIEW_SCHEMA["properties"]


def test_release_surfaces_smoke_checks_search_at_build_time():
    """A channel site can build --strict with a dead search: assets that 404 or an index
    with zero documents only surface when a human types a query into a silent box. The
    build step must therefore prove the index parses and is non-empty, and that every
    search asset landed, before the site is uploaded."""
    text = (WORKFLOWS / "release-surfaces.yml").read_text(encoding="utf-8")
    smoke = text.index("search smoke:")
    build = text.index("properdocs build --strict --config-file .properdocs-channel.yml")
    assert build < smoke, "the smoke test must run against the built channel site"
    for asset in (
        "search/search_index.json",
        "search/lunr.js",
        "search/main.js",
        "search/worker.js",
    ):
        assert asset in text
    assert "the index contains zero documents" in text
    assert "documents indexed, all assets present" in text


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
        result = subprocess.run(["sh", "-c", script], capture_output=True, text=True, check=False)
        return result.returncode != 0

    assert confinement_check_passes(in_scope_only)
    assert not confinement_check_passes(mixed_scope)


def test_pr_review_requires_verified_repository_paths():
    text = (WORKFLOWS / "pr-automation.yml").read_text(encoding="utf-8")

    assert "Inspect target/ with Read, Glob, and Grep only" in text
    assert "verify its path exists under target/ with Read or Glob" in text
    assert "Never return schema" in text
    assert "fail the review action so infrastructure recovery can retry it" in text


def _relative_luminance(hex_colour: str) -> float:
    value = hex_colour.lstrip("#")
    channels = [int(value[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(foreground: str, background: str) -> float:
    first, second = _relative_luminance(foreground), _relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.mark.parametrize("hook", ["pre-push", "commit-msg"])
def test_a_repository_that_is_vibey_gh_runs_its_own_working_tree(hook):
    """An installed copy must never be what validates the tool's own repository.

    `develop` here is ahead of the last release nearly always, so a globally installed
    vibey-gh compares this repository's managed assets against the older ones it bundles,
    calls them out of date, and refuses the push. That is not hypothetical: installing the
    CLI the obvious way to satisfy an adopter's hook immediately made every push from this
    repository fail, with a provenance error that had nothing wrong behind it.

    The package is dependency-free stdlib, so running the checkout needs no install and no
    virtualenv — only that this branch is tried before `command -v`.
    """
    text = (TEMPLATES / hook).read_text(encoding="utf-8")
    self_hosting = text.find("grep -qE '^name = \"vibey-gh\"' pyproject.toml")
    installed_copy = text.find("command -v vibey-gh")
    assert self_hosting != -1, "the self-hosting branch is gone"
    assert installed_copy != -1
    assert self_hosting < installed_copy, (
        "an installed vibey-gh would shadow the working tree and judge this repository "
        "against whatever it last released"
    )
    # Narrow on purpose: an adopting repository must fall straight through to its
    # installed CLI, so the test is the package name *and* the package directory.
    assert "[ -d vibey_gh ]" in text


def test_no_code_token_can_keep_a_colour_meant_for_a_white_page():
    """The gap the contrast test alone could not close.

    Measuring the colours a stylesheet declares says nothing about the tokens it never
    mentions. The first pass at this passed green while `.hljs-subst` was still inheriting
    github-light's near-black — so `$(git rev-parse HEAD)` sat at 1.33:1 inside the very
    example that tells a reader how to list their check names.

    A catch-all fixes the class rather than the instance: any token, including ones this
    stylesheet has never heard of, starts legible. It has to come *before* the palette,
    because an attribute selector and a class have equal specificity and source order is
    what decides between them.
    """
    css = (Path(__file__).resolve().parent.parent / "docs/stylesheets/vibey.css").read_text(
        encoding="utf-8"
    )
    catch_all = css.find('[class*="hljs-"]')
    assert catch_all != -1, "no catch-all: an unlisted token would inherit the light theme"
    assert ".highlight span" in css, "Pygments needs the same catch-all"
    first_token_rule = css.find(".hljs-string,")
    assert first_token_rule != -1
    assert catch_all < first_token_rule, (
        "the catch-all must precede the palette, or equal specificity lets it win and "
        "every token collapses to one colour"
    )


def test_code_blocks_are_legible_against_the_background_this_theme_forces():
    """Forcing a dark code background obliges this stylesheet to own the token colours.

    The mkdocs theme ships two highlight.js palettes and enables the *light* one by
    default — `#hljs-dark` carries `disabled` — so its tokens are picked for a white page.
    This stylesheet then paints the block `#080c17`. github-light renders a string as
    `#032f62`, which against that background is 1.48:1: not low-contrast but genuinely
    unreadable, and every configuration sample in these docs is mostly string literals.

    Measured rather than eyeballed, because "looks fine to me" is what shipped it.
    """
    css = (Path(__file__).resolve().parent.parent / "docs/stylesheets/vibey.css").read_text(
        encoding="utf-8"
    )
    background = re.search(r"background:\s*(#[0-9a-fA-F]{6})\s*!important", css)
    assert background, "the forced code-block background is gone; this test needs rewriting"
    dark = background.group(1)
    # Every colour declared in a rule that mentions a syntax token, whichever highlighter
    # produced it: `.hljs-*` for the client-side theme, `.highlight .x` for Pygments.
    tokens = re.findall(
        r"((?:[^{}]*(?:\.hljs-|\.highlight\s+\.)[^{}]*)\{[^}]*?color:\s*(#[0-9a-fA-F]{6}))",
        css,
    )
    assert len(tokens) >= 8, f"expected the token palette to be present, found {len(tokens)}"
    for rule, colour in tokens:
        ratio = _contrast(colour, dark)
        selector = rule.split("{")[0].strip().splitlines()[-1].strip()
        assert ratio >= 4.5, f"{selector} {colour} is {ratio:.2f}:1 on {dark}, below AA"


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
    assert "https://vibewithadam.matthewsteinberger.com" in script
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
    # A cap, not a count: every occurrence is a step handed the elevated token, so the
    # number may grow as this workflow reconciles more repository state, but not
    # unnoticed. Raising it should be a deliberate decision about privileged surface.
    assert text.count("secrets.AUTOMERGE_TOKEN || github.token") <= 5
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
    assert 'git remote add origin "https://github.com/${{ github.repository }}.git"' in text
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


AI_TEMPLATES = (
    "conversation.yml",
    "documentation.yml",
    "issue-automation.yml",
    "pr-automation.yml",
    "release-repair.yml",
)


def test_every_ai_step_can_be_pointed_at_another_endpoint():
    """One marker per AI step, or a repository can only redirect some of its spending.

    Claude Code honours `ANTHROPIC_BASE_URL`, so a gateway serving the Anthropic Messages
    API is the whole of what it takes to run this somewhere other than Anthropic. That is
    only true if *every* step carries the hook: a missed one keeps billing the original
    endpoint, and silently.
    """
    marked = tokens = 0
    for name in AI_TEMPLATES:
        text = (WORKFLOWS / name).read_text(encoding="utf-8")
        marked += text.count("# __VIBEY_GH_AI_ENV__")
        tokens += text.count("secrets.__VIBEY_GH_AI_AUTH_SECRET__")
    call_sites = sum(
        (WORKFLOWS / name).read_text(encoding="utf-8").count("uses: anthropics/claude-code-action")
        for name in AI_TEMPLATES
    )
    assert call_sites == 7
    assert marked == call_sites
    assert tokens == call_sites


@pytest.mark.parametrize("name", AI_TEMPLATES)
def test_the_default_endpoint_is_unchanged_and_no_base_url_is_set(name, tmp_path: Path):
    """Empty is not the same as unset: an empty `ANTHROPIC_BASE_URL` points at nothing."""
    rendered = render_workflow(WORKFLOWS / name, GhConfig(root=tmp_path))
    assert "__VIBEY_GH" not in rendered
    assert yaml.safe_load(rendered)
    assert "ANTHROPIC_BASE_URL" not in rendered
    assert "${{ secrets.ANTHROPIC_API_KEY }}" in rendered


@pytest.mark.parametrize("name", AI_TEMPLATES)
def test_a_gateway_endpoint_reaches_every_step_with_both_header_conventions(name, tmp_path: Path):
    rendered = render_workflow(
        WORKFLOWS / name,
        GhConfig(
            root=tmp_path,
            ai=AiConfig(base_url="https://gateway.example.test/v1", auth_secret="LITELLM_KEY"),
        ),
    )
    assert "__VIBEY_GH" not in rendered
    assert yaml.safe_load(rendered)
    calls = rendered.count("uses: anthropics/claude-code-action")
    assert rendered.count('ANTHROPIC_BASE_URL: "https://gateway.example.test/v1"') == calls
    # Claude Code sends `x-api-key`; some gateways read `Authorization`. One secret fills
    # both, so a gateway works without the repository having to know which it wants.
    assert rendered.count("ANTHROPIC_AUTH_TOKEN: ${{ secrets.LITELLM_KEY }}") == calls
    assert "ANTHROPIC_API_KEY" not in rendered


@pytest.mark.parametrize(
    "kwargs,match",
    [
        # A name that could close the expression and append another would be an injection
        # into a privileged workflow, so only a bare secret identifier is accepted.
        ({"auth_secret": "A }} ${{ secrets.OTHER"}, "not a valid secret name"),
        ({"auth_secret": "9LEADING_DIGIT"}, "not a valid secret name"),
        ({"auth_secret": ""}, "not a valid secret name"),
        ({"base_url": "ftp://gateway.example.test"}, "must be an http"),
        ({"base_url": "gateway.example.test"}, "must be an http"),
        ({"base_url": "https://gateway.example.test\nkey: value"}, "no whitespace"),
    ],
)
def test_an_unsafe_ai_endpoint_is_rejected(kwargs, match):
    with pytest.raises(ValueError, match=match):
        AiConfig(**kwargs)


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"site_requirements": ("a", "a")}, "must be unique"),
        ({"site_requirements": (" ",)}, "must be non-empty"),
        # Quoting makes ordinary specifier punctuation safe, but a newline would end the
        # `pip install` line and start an arbitrary command inside the workflow.
        ({"site_requirements": ("mkdocs\nrm -rf /",)}, "spans lines"),
        ({"site_requirements": ("mkdocs\rwhoami",)}, "spans lines"),
        ({"site_requirements_file": "/etc/requirements.txt"}, "repository-relative"),
        ({"site_requirements_file": "../elsewhere/requirements.txt"}, "repository-relative"),
        ({"properdocs_version": "  "}, "must not be empty"),
    ],
)
def test_unsafe_site_requirements_are_rejected(kwargs, match):
    with pytest.raises(ValueError, match=match):
        DocumentationConfig(**kwargs)


def test_a_repository_may_decline_the_site_requirements_file_entirely(tmp_path):
    """An empty path is a supported way to say "no requirements file", not a broken one."""
    rendered = render_workflow(
        WORKFLOWS / "release-surfaces.yml",
        GhConfig(root=tmp_path, documentation=DocumentationConfig(site_requirements_file="")),
    )
    assert "__VIBEY_GH" not in rendered
    # The guard survives with an empty operand, so the branch is simply never taken.
    assert 'if [ -n "" ]' in rendered


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
    assert "github.event.pull_request.head.ref != '__VIBEY_GH_INTEGRATION_BRANCH__'" in text
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
    assert "grep -qE '^name = \"vibey-(gh|bootstrap)\"' pyproject.toml" in text
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
    checks = re.findall(r"""grep -qE '\^name = "vibey-gh"' automation/pyproject\.toml""", text)
    assert len(checks) == 5  # review, repair, resolve-conflict, escalate, review-fallback
    installs = re.findall(r"python -m pip install --quiet vibey-gh\b", text)
    assert len(installs) == 6  # the five guarded installs above plus the evaluate job's own


def test_promotion_checks_provenance_without_rewriting_or_reauditing_history():
    text = (WORKFLOWS / "provenance.yml").read_text(encoding="utf-8")
    assert 'if [ "$HEAD_REF" = "$INTEGRATION_BRANCH" ]' in text
    assert '[ "$BASE_REF" = "$RELEASE_BRANCH" ]' in text
    assert "Promotion PR: checking repository provenance" in text
    assert "vibey-gh check --ci" in text
    assert 'vibey-gh check --ci --commits "${BASE_SHA}..HEAD"' in text


def test_pin_version_pins_every_managed_templates_tooling_install(tmp_path: Path):
    """`install.pin_version` must reach every managed workflow, not just the ones the
    issue happened to confirm — a config key that only fixes some templates leaves the
    same outage waiting in whichever one it missed.
    """
    from vibey_gh import __version__

    cfg = GhConfig(root=tmp_path, pin_version=True)
    unpinned = re.compile(r"pip install --quiet vibey-gh(?!==)")
    for path in WORKFLOW_TEMPLATES:
        text = render_workflow(path, cfg)
        if "pip install --quiet vibey-gh" not in path.read_text(encoding="utf-8"):
            continue  # this template never installed the floating tooling to begin with
        assert not unpinned.search(text), f"{path.name}: an unpinned install survived pinning"
        assert f'"vibey-gh=={__version__}"' in text


def test_pin_version_unset_leaves_every_managed_template_floating(tmp_path: Path):
    cfg = GhConfig(root=tmp_path)
    for path in WORKFLOW_TEMPLATES:
        text = render_workflow(path, cfg)
        assert "vibey-gh==" not in text


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
    assert "Skipping stale repair: expected $EXPECTED_SHA, found $current" in text
    assert "Discarding stale repair after concurrent update to $current" in text
    assert "Skipping stale conflict resolution: expected $EXPECTED_SHA, found $current" in text
    assert "Discarding stale conflict resolution after concurrent update to $current" in text
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
    assert "needs.evaluate.outputs.evaluated_head_sha == needs.evaluate.outputs.head_sha" in text
    assert "reason=${REASON}" in text
    assert 'select(.state == "open")' in text
    assert "github.event.workflow_run.pull_requests[0].number" in text


def test_draft_evaluation_is_nonterminal_until_ready_draft_promotes_it():
    source = (Path(__file__).resolve().parent.parent / "vibey_gh/pr_automation.py").read_text(
        encoding="utf-8"
    )
    assert 'return result("pending", "pull request is a draft awaiting a stable head")' in source


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
            assert result.returncode == 0, f"{path.name}:{job}:{step.get('name')}: {result.stderr}"


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


def test_the_merge_train_does_not_filter_on_the_triggering_runs_conclusion():
    """Observed in production: every PR held green and unmerged while credits were out.

    "PR automation" concludes `failure` whenever its exact-head review job fails — which
    is precisely the case the local review fallback exists to cover. The fallback then
    succeeds, publishes a green `PR automation / gate`, and the run as a whole still ends
    `failure` because one job in it did. Filtering the merge train on that conclusion
    skipped it on every such pull request and defeated the fallback at the last step.

    Nothing is relaxed by its absence: `judge()` re-reads each pull request and requires a
    completed, successful gate before merging, which is asserted separately.
    """
    spec = yaml.safe_load((WORKFLOWS / "merge-train.yml").read_text(encoding="utf-8"))
    assert "conclusion" not in str(spec["jobs"]["merge"].get("if", ""))


@pytest.mark.parametrize("name", sorted(p.name for p in WORKFLOWS.glob("*.yml")))
def test_no_rendered_workflow_carries_trailing_whitespace(name, tmp_path):
    """Rendered, not just authored — the defect only appears after substitution.

    Every template is clean in source, so checking the templates proves nothing. A
    placeholder that renders empty mid-line leaves the space that separated it from the
    previous argument dangling: `__VIBEY_GH_DOC_SITE_REQUIREMENTS__` did exactly that with
    the default empty `site_requirements`, which is the default path, not an edge case.

    It matters because `installed()` compares byte-for-byte and the near-universal
    `trailing-whitespace` pre-commit hook strips that space on the adopting repository's
    next commit — after which `check` reports the file out of date and the pre-push hook
    refuses the push. A formatting hook silently breaking provenance. Five repositories hit
    it while adopting 1.38.0.
    """
    from vibey_gh.install import render_workflow

    rendered = render_workflow(WORKFLOWS / name, GhConfig(root=tmp_path))
    offenders = [
        (number, line)
        for number, line in enumerate(rendered.split("\n"), 1)
        if line != line.rstrip()
    ]
    assert not offenders, f"{name} renders trailing whitespace at {[n for n, _ in offenders]}"


def test_the_issue_triage_fallback_renders_only_when_enabled(tmp_path):
    """The issue path's counterpart to the review fallback, with a smaller contract: it
    posts one deduplicated analysis comment and never writes code — a local model must not
    inherit the write access the paid solver earned. Disabled it renders `false &&`, so
    the job exists but can never run; enabled it targets the shared fallback runner."""
    from vibey_gh.config import GhConfig, IssueAutomationConfig
    from vibey_gh.install import render_workflow

    source = WORKFLOWS / "issue-automation.yml"
    off = render_workflow(source, GhConfig(root=tmp_path))
    assert "Local triage fallback" in off
    assert "false &&" in off.split("solve-fallback:")[1].split("runs-on:")[0]

    on = render_workflow(
        source,
        GhConfig(root=tmp_path, issue_automation=IssueAutomationConfig(fallback_enabled=True)),
    )
    section = on.split("solve-fallback:")[1]
    assert "true &&" in section.split("runs-on:")[0]
    assert "vibey-local" in section.split("permissions:")[0]
    # The comment is deduplicated by marker, and the job never pushes code.
    assert "vibey-gh:local-triage" in section
    assert "issues: write" in section
    assert "contents: write" not in section


def test_seo_metadata_is_rendered_configurably(tmp_path):
    """The site ships complete search and social metadata with zero configuration — the
    defaults derive from the repository (GitHub's generated OpenGraph card, repo-derived
    keywords) — and every field is overridable from [documentation]."""
    from vibey_gh.config import DocumentationConfig, GhConfig
    from vibey_gh.install import _favicon_links, render_workflow

    source = WORKFLOWS / "release-surfaces.yml"
    plain = render_workflow(source, GhConfig(root=tmp_path))
    # Defaults: emoji favicon becomes a data-URI link pair; og:image falls back to
    # GitHub's card at runtime, so the template must carry the fallback expression.
    assert "data:image/svg+xml," in plain
    assert "opengraph.githubassets.com" in plain
    assert "SEO_KEYWORDS=''" in plain

    configured = render_workflow(
        source,
        GhConfig(
            root=tmp_path,
            documentation=DocumentationConfig(
                favicon="https://example.com/icon.png",
                og_image="https://example.com/card.png",
                twitter_site="@vibey",
                keywords=("alpha", "beta"),
                author="A. Person",
                theme_color="#123abc",
                locale="de_DE",
            ),
        ),
    )
    assert 'href="https://example.com/icon.png"' in configured
    assert "SEO_OG_IMAGE='https://example.com/card.png'" in configured
    assert "SEO_TWITTER_SITE='@vibey'" in configured
    assert "SEO_KEYWORDS='alpha,beta'" in configured
    assert "SEO_AUTHOR='A. Person'" in configured
    assert "SEO_THEME_COLOR='#123abc'" in configured
    assert "SEO_LOCALE='de_DE'" in configured

    # The pure helper: emoji in, matching icon+touch-icon pair out; URLs verbatim.
    pair = _favicon_links("⚙️")
    assert pair.count("data:image/svg+xml,") == 2 and "apple-touch-icon" in pair
    assert _favicon_links("") == ""
    assert _favicon_links("/img/fav.ico") == '<link rel="icon" href="/img/fav.ico">'


def test_seo_fields_refuse_html_injection():
    """These strings land verbatim in rendered pages and workflow YAML; the cheap
    injections are refused at load time rather than discovered on a published site."""
    import pytest as _pytest

    from vibey_gh.config import DocumentationConfig

    with _pytest.raises(ValueError, match="must not contain HTML"):
        DocumentationConfig(author='"><script>x</script>')
    with _pytest.raises(ValueError, match="theme_color"):
        DocumentationConfig(theme_color="blue")
    with _pytest.raises(ValueError, match="plain words"):
        DocumentationConfig(keywords=("ok", "<bad>"))


def test_the_fallback_reconstructs_a_diff_the_api_refuses(tmp_path):
    """GitHub's diff API refuses pull requests beyond roughly 300 files — exactly the
    shape of a migration sweep, observed on a 347-file provenance sweep that could
    therefore never be reviewed at all. The fallback must reconstruct the same merge-base
    diff from fetched refs: read-only, no repository code executed, and --max-chars still
    caps what reaches the model."""
    from vibey_gh.install import render_workflow

    text = render_workflow(WORKFLOWS / "pr-automation.yml", GhConfig(root=tmp_path))
    section = text.split("Fetch the exact-head diff")[1].split("Review with the local model")[0]
    assert "gh pr diff" in section
    assert "reconstructing locally" in section
    assert "merge-base" in section
    # Shallow trusted checkouts must deepen until the histories connect, never guess.
    assert "--unshallow" in section
    assert 'git -C automation diff "$merge_base" "$head_sha"' in section


def test_search_console_verification_survives_redeploys(tmp_path):
    """An uploaded verification FILE is wiped every time release-surfaces rebuilds the
    Pages root — observed as a repeatedly un-verifiable property. The HTML-tag token is
    configuration, rendered into every page and the channel index, so verification
    survives every deploy. Unset, nothing renders."""
    from vibey_gh.config import DocumentationConfig, GhConfig
    from vibey_gh.install import render_workflow

    source = WORKFLOWS / "release-surfaces.yml"
    off = render_workflow(source, GhConfig(root=tmp_path))
    assert "SEO_SITE_VERIFICATION=''" in off
    assert 'name="google-site-verification"' in off  # the injector line, gated at runtime
    assert 'content=""' not in off.split("<title>")[0]

    on = render_workflow(
        source,
        GhConfig(
            root=tmp_path,
            documentation=DocumentationConfig(google_site_verification="tok_ABC-123"),
        ),
    )
    assert "SEO_SITE_VERIFICATION='tok_ABC-123'" in on
    # the channel index carries the full static tag
    assert '<meta name="google-site-verification" content="tok_ABC-123">' in on


def test_search_console_token_refuses_a_whole_tag():
    """People paste the whole <meta> tag; the loader demands the bare token so the render
    cannot double-wrap it into broken HTML."""
    import pytest as _pytest

    from vibey_gh.config import DocumentationConfig

    with _pytest.raises(ValueError, match="bare token"):
        DocumentationConfig(google_site_verification='<meta name="google-site-verification">')
