# Made with ❤️ by [Vibey](https://adammatthewsteinberger.github.io/vibey/), Developed by [Adam Matthew Steinberger](https://hire.adam.matthewsteinberger.com/) ([@adammatthewsteinberger](https://github.com/adammatthewsteinberger/)).
# Made with ❤️ by [Vibey](https://adammatthewsteinberger.github.io/vibey/), Developed by [Adam Matthew Steinberger](https://hire.adam.matthewsteinberger.com/) ([@adammatthewsteinberger](https://github.com/adammatthewsteinberger/)).
"""One executable capability contract projected through SDK, CLI, API, MCP, and webhooks."""

from __future__ import annotations

import hashlib
import hmac
import io
import json
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from typing import Any

CAPABILITIES = (
    "check",
    "install",
    "version",
    "trailer",
    "trailer-key",
    "merge-train",
    "pr-automation",
    "github-release",
    "promote",
    "realign",
)
SURFACES = ("mcp", "api", "cli", "sdk", "webhook")


@dataclass(frozen=True)
class Result:
    capability: str
    exit_code: int
    stdout: str
    stderr: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


def _validate(capability: str, arguments: list[str]) -> None:
    if capability not in CAPABILITIES:
        raise ValueError(f"unknown capability: {capability}")
    if not all(isinstance(value, str) for value in arguments):
        raise TypeError("arguments must be strings")


def invoke(capability: str, arguments: list[str] | None = None) -> Result:
    """Python SDK entry point; all remote adapters delegate to this exact behavior."""
    argv = list(arguments or [])
    _validate(capability, argv)
    from vibey_gh.cli import main

    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            code = main([capability, *argv])
        except SystemExit as exc:
            code = int(exc.code or 0)
    return Result(capability, code, stdout.getvalue(), stderr.getvalue())


def api_dispatch(method: str, path: str, body: bytes = b"") -> tuple[int, dict[str, Any]]:
    """Dependency-free JSON API application callable from any WSGI/HTTP adapter."""
    if method == "GET" and path == "/v1/capabilities":
        return 200, {"capabilities": list(CAPABILITIES), "surfaces": list(SURFACES)}
    prefix = "/v1/capabilities/"
    if method != "POST" or not path.startswith(prefix):
        return 404, {"error": "not found"}
    capability = path[len(prefix) :]
    try:
        value = json.loads(body or b"{}")
        arguments = value.get("arguments", [])
        if not isinstance(arguments, list):
            raise TypeError("arguments must be an array")
        _validate(capability, arguments)
        result = invoke(capability, arguments)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return 400, {"error": str(exc)}
    return 200, result.as_dict()


def mcp_dispatch(request: dict[str, Any]) -> dict[str, Any]:
    """Handle MCP initialize, tools/list, and tools/call JSON-RPC requests."""
    request_id = request.get("id")
    method = request.get("method")
    if method == "initialize":
        result: Any = {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "vibey-gh", "version": "1"},
        }
    elif method == "tools/list":
        result = {"tools": [_mcp_tool(name) for name in CAPABILITIES]}
    elif method == "tools/call":
        params = request.get("params", {})
        name = params.get("name", "")
        arguments = params.get("arguments", {}).get("arguments", [])
        try:
            _validate(name, arguments)
            payload = invoke(name, arguments).as_dict()
            result = {"content": [{"type": "text", "text": json.dumps(payload)}]}
        except (TypeError, ValueError) as exc:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": str(exc)},
            }
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": "method not found"},
        }
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _mcp_tool(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "description": f"Invoke vibey-gh {name}",
        "inputSchema": {
            "type": "object",
            "properties": {"arguments": {"type": "array", "items": {"type": "string"}}},
            "additionalProperties": False,
        },
    }


class WebhookDispatcher:
    """Authenticated, replay-safe webhook projection of every capability."""

    def __init__(self, secret: bytes, executor: Callable[[str, list[str]], Result] = invoke):
        if not secret:
            raise ValueError("webhook secret must not be empty")
        self._secret = secret
        self._executor = executor
        self._deliveries: set[str] = set()

    def dispatch(self, delivery: str, signature: str, body: bytes) -> tuple[int, dict[str, Any]]:
        expected = "sha256=" + hmac.new(self._secret, body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return 401, {"error": "invalid signature"}
        if not delivery or delivery in self._deliveries:
            return 409, {"error": "duplicate or missing delivery"}
        try:
            value = json.loads(body)
            capability = value["capability"]
            arguments = value.get("arguments", [])
            _validate(capability, arguments)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            return 400, {"error": str(exc)}
        self._deliveries.add(delivery)
        return 200, self._executor(capability, arguments).as_dict()


def parity() -> dict[str, tuple[str, ...]]:
    """Machine-readable matrix; adapters are shared implementations, not help stubs."""
    return {name: SURFACES for name in CAPABILITIES}
