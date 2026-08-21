# Made with love by Vibey, the auto-vibecoding machine by Adam Matthew Steinberger.
"""Configuration for the GitHub automation, read from `.vibey-gh.toml`.

Every project-specific decision lives here so the logic beside it can stay general:

    [fingerprint]
    text     = "Made with love by Vibey, ..."      # the source-header comment
    trailer  = "Made-With: Vibey, ..."             # the commit trailer
    sources  = ["tools/*.py", ".github/workflows/*.yml"]

    [version]
    files         = ["src/pkg/__init__.py", "manifest.json"]
    content_paths = ["plugins/"]     # a change here is a MINOR release
    code_paths    = ["src/"]         # a change here alone is a PATCH

    [branches]
    integration = "develop"
    release     = "main"

Absent keys fall back to the defaults below, so a repository that agrees with them needs
no file at all. `tomllib` is stdlib from 3.11, which this package already requires.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_NAME = ".vibey-gh.toml"

DEFAULT_TEXT = "Made with love by Vibey, the auto-vibecoding machine by Adam Matthew Steinberger."
DEFAULT_TRAILER_KEY = "Made-With"
DEFAULT_TRAILER = (
    f"{DEFAULT_TRAILER_KEY}: Vibey, the auto-vibecoding machine by Adam Matthew Steinberger"
)
DEFAULT_SOURCES = ("tools/*.py", "src/**/*.py", ".github/workflows/*.yml")


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
    return GhConfig(
        root=root,
        text=fp.get("text", DEFAULT_TEXT),
        trailer=fp.get("trailer", DEFAULT_TRAILER),
        sources=tuple(fp.get("sources", DEFAULT_SOURCES)),
        version_files=tuple(ver.get("files", ())),
        content_paths=tuple(ver.get("content_paths", ())),
        code_paths=tuple(ver.get("code_paths", ("src/",))),
        integration_branch=br.get("integration", "develop"),
        release_branch=br.get("release", "main"),
        owner=tr.get("owner", ""),
        trusted_authors=tuple(tr.get("trusted_authors", ())),
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
