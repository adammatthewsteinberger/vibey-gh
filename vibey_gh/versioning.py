# Made with ❤️ by [Vibey](https://adammatthewsteinberger.github.io/vibey/), Developed by [Adam Matthew Steinberger](https://hire.adam.matthewsteinberger.com/) ([@adammatthewsteinberger](https://github.com/adammatthewsteinberger/)).
"""Derive the release version from what actually changed.

This has to be automatic, not remembered. A PyPI upload with `skip-existing` turns an
unbumped release into a green run that publishes nothing, silently, with no warning — so
a human-maintained version is a silent-failure generator.

    content_paths changed  -> MINOR   the product changed; users receive something new
    only code_paths        -> PATCH   an internal fix
    neither                -> NONE    docs, CI, tooling: nothing an installed user gets
    version already ahead  -> NONE    a deliberate bump is in place; never double it

`none` is a legitimate and common answer. The promotion still happens; it simply does not
publish, which is correct rather than a failure.
"""

from __future__ import annotations

import json
import re
import subprocess
import tomllib

from vibey_gh.config import GhConfig

VERSION_RE = re.compile(r'^(__version__\s*=\s*")([^"]+)(")', re.MULTILINE)
JSON_VERSION_KEYS = ("version",)
# A TOML `version = "..."`, matched only inside the [project] table — pyproject has
# other tables with a `version` key and bumping the wrong one is worse than not bumping.
TOML_VERSION_RE = re.compile(r'^(version\s*=\s*")([^"]+)(")', re.MULTILINE)


def _toml_version(text: str) -> str | None:
    """The [project] version, read with the parser rather than a regex."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return None
    version = data.get("project", {}).get("version")
    return str(version) if version is not None else None


def _project_table(text: str) -> tuple[int, int]:
    """(start, end) character offsets of the [project] table's body."""
    match = re.search(r"^\[project\]\s*$", text, re.MULTILINE)
    if match is None:
        raise RuntimeError("no [project] table")
    start = match.end()
    nxt = re.search(r"^\[", text[start:], re.MULTILINE)
    return start, start + (nxt.start() if nxt else len(text) - start)


def _git(cfg: GhConfig, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=cfg.root, capture_output=True, text=True, check=False)
    if r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def read_version(cfg: GhConfig) -> str:
    """The working version, from the first configured version file."""
    for rel in cfg.version_files:
        path = cfg.root / rel
        if not path.is_file():
            continue
        if path.suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            meta = data.get("metadata", data)
            for key in JSON_VERSION_KEYS:
                if key in meta:
                    return str(meta[key])
        elif path.suffix == ".toml":
            version = _toml_version(path.read_text(encoding="utf-8"))
            if version is not None:
                return version
        else:
            match = VERSION_RE.search(path.read_text(encoding="utf-8"))
            if match:
                return match.group(2)
    raise RuntimeError("no version found in any configured version file")


def read_version_at(cfg: GhConfig, ref: str) -> str | None:
    for rel in cfg.version_files:
        r = subprocess.run(
            ["git", "show", f"{ref}:{rel}"],
            cwd=cfg.root,
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode:
            continue
        if rel.endswith(".json"):
            try:
                data = json.loads(r.stdout)
            except json.JSONDecodeError:
                continue
            meta = data.get("metadata", data)
            for key in JSON_VERSION_KEYS:
                if key in meta:
                    return str(meta[key])
        elif rel.endswith(".toml"):
            version = _toml_version(r.stdout)
            if version is not None:
                return version
        else:
            match = VERSION_RE.search(r.stdout)
            if match:
                return match.group(2)
    return None


def bump(version: str, level: str) -> str:
    major, minor, patch = (int(p) for p in version.split(".")[:3])
    return f"{major}.{minor + 1}.0" if level == "minor" else f"{major}.{minor}.{patch + 1}"


def decide(cfg: GhConfig, since: str) -> tuple[str | None, str]:
    released = read_version_at(cfg, since)
    if released is None:
        return None, f"cannot read a version at {since}; refusing to guess"

    working = read_version(cfg)
    if working != released:
        return None, (
            f"already at {working} while {since} is {released} — "
            "a deliberate bump is in place, leaving it alone"
        )

    changed = [
        line for line in _git(cfg, "diff", "--name-only", since, "HEAD").splitlines() if line
    ]
    if not changed:
        return None, f"no changes since {since}"
    if any(f.startswith(p) for f in changed for p in cfg.content_paths):
        return bump(working, "minor"), "packaged content changed"
    if any(f.startswith(p) for f in changed for p in cfg.code_paths):
        return bump(working, "patch"), "only internal code changed"
    return None, (
        f"{len(changed)} file(s) changed but none reach an installed user "
        "(docs, workflows, tooling) — nothing to release"
    )


def apply_version(cfg: GhConfig, new: str) -> list[str]:
    """Write `new` into every configured version file. All of them, or the tree is
    inconsistent and its own validator will reject it."""
    written = []
    for rel in cfg.version_files:
        path = cfg.root / rel
        if not path.is_file():
            continue
        if path.suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            target = data.get("metadata") if isinstance(data.get("metadata"), dict) else data
            target["version"] = new
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        elif path.suffix == ".toml":
            text = path.read_text(encoding="utf-8")
            start, end = _project_table(text)
            patched, n = TOML_VERSION_RE.subn(rf"\g<1>{new}\g<3>", text[start:end], count=1)
            if n != 1:
                raise RuntimeError(f"{rel}: expected one [project] version, found {n}")
            path.write_text(text[:start] + patched + text[end:], encoding="utf-8")
        else:
            text = path.read_text(encoding="utf-8")
            patched, n = VERSION_RE.subn(rf"\g<1>{new}\g<3>", text, count=1)
            if n != 1:
                raise RuntimeError(f"{rel}: expected one __version__ line, found {n}")
            path.write_text(patched, encoding="utf-8")
        written.append(rel)
    return written


def dev_version(cfg: GhConfig, build: str) -> str:
    """`<release>.dev<build>` — distinct per push, PEP 440 valid, and sorting before the
    release it anticipates, which is the correct relationship."""
    digits = re.sub(r"\D", "", str(build)) or "0"
    return f"{read_version(cfg)}.dev{int(digits)}"
