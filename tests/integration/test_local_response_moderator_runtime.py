"""Installed OpenCode runtime coverage for the local response moderator."""

from __future__ import annotations

import json
import os
import subprocess
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "workspace/scripts/install-opencode-moderator"
AUDIT_TIMEOUT_MESSAGE = "installed moderator did not persist the required audit record"
EXPECTED_PROVIDER_REQUESTS = 2


def installer_env(tmp_path: Path, decision: str) -> dict[str, str]:
    binary = tmp_path / "bin"
    binary.mkdir()
    response = json.dumps(decision)
    (binary / "curl").write_text(
        '#!/bin/bash\nset -euo pipefail\nurl="${!#}"\n'
        "if [[ \"$url\" == */models ]]; then printf '%s\\n' "
        '\'{"data":[{"id":"/zip/MiniCPM5-1B-Q8_0.gguf"}]}\'\n'
        "elif [[ \"$url\" == */input_tokens ]]; then printf '%s\\n' "
        "'{\"input_tokens\":10}'\n"
        f"else printf '%s\\n' "
        f'\'{{"choices":[{{"message":{{"content":{response}}},'
        '"finish_reason":"stop"}]}\'\nfi\n',
        encoding="utf-8",
    )
    (binary / "curl").chmod(0o755)
    return {
        **os.environ,
        "PATH": f"{binary}:{os.environ['PATH']}",
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "LOCAL_RESPONSE_MODERATOR_REPO_ROOT": str(ROOT),
        "HOME": str(tmp_path / "home"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_STATE_HOME": str(tmp_path / "state"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "OPENCODE_DB": str(tmp_path / "data" / "opencode.db"),
    }


@contextmanager
def provider(tool_call: bool = False) -> object:
    requests: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            requests.append(
                json.loads(
                    self.rfile.read(int(self.headers.get("content-length", "0")))
                )
            )
            tool = tool_call and len(requests) == 1
            delta = (
                {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call-moderator",
                            "type": "function",
                            "function": {
                                "name": "bash",
                                "arguments": '{"command":"true"}',
                            },
                        }
                    ]
                }
                if tool
                else {"content": "completed response"}
            )
            payload = {
                "id": "moderator-test",
                "object": "chat.completion.chunk",
                "choices": [
                    {
                        "index": 0,
                        "delta": delta,
                        "finish_reason": "tool_calls" if tool else "stop",
                    }
                ],
            }
            body = f"data: {json.dumps(payload)}\n\ndata: [DONE]\n\n".encode()
            self.send_response(200)
            self.send_header("content-type", "text/event-stream")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, requests
    finally:
        server.shutdown()
        thread.join(timeout=10)


def wait_for_audit(
    root: Path, decision_type: str, effect: str, ignored: set[Path] | None = None
) -> Path:
    for _ in range(200):
        for record in root.glob("*/*.yaml"):
            if ignored is not None and record in ignored:
                continue
            content = json.loads(record.read_text(encoding="utf-8"))
            if content["decisionType"] == decision_type and any(
                item["effect"] == effect and item["status"] == "ok"
                for item in content["effectResults"]
            ):
                return record
        time.sleep(0.05)
    raise AssertionError(AUDIT_TIMEOUT_MESSAGE)


def run_runtime(
    tmp_path: Path, decision: str, tool_call: bool = False
) -> tuple[dict[str, object], list[dict[str, object]]]:
    env = installer_env(tmp_path, decision)
    install = subprocess.run(
        [str(INSTALLER), "install"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert install.returncode == 0, install.stderr
    runtime, wrapper = (
        ROOT / ".boot-linux/bin/opencode",
        ROOT / "workspace/scripts/bin/oc",
    )
    env["OPENCODE_BINARY"] = str(runtime)
    with provider(tool_call) as (api, requests):
        config = Path(env["XDG_CONFIG_HOME"]) / "opencode"
        config.mkdir(parents=True, exist_ok=True)
        (config / "opencode.jsonc").write_text(
            json.dumps(
                {
                    "model": "moderator/moderator-test",
                    "provider": {
                        "moderator": {
                            "npm": "@ai-sdk/openai-compatible",
                            "options": {
                                "apiKey": "test",
                                "baseURL": f"http://127.0.0.1:{api.server_address[1]}/v1",
                            },
                            "models": {
                                "moderator-test": {
                                    "name": "Moderator test",
                                    "limit": {"context": 4096, "output": 128},
                                    "cost": {"input": 0, "output": 0},
                                }
                            },
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        server = subprocess.Popen(
            [str(runtime), "serve", "--port", "4096"],
            cwd=tmp_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        try:
            time.sleep(1)
            assert server.poll() is None
            result = subprocess.run(
                [
                    str(wrapper),
                    "--db",
                    env["OPENCODE_DB"],
                    "--",
                    "run",
                    "--attach",
                    "http://127.0.0.1:4096",
                    "--auto",
                    "--model",
                    "moderator/moderator-test",
                    "finish this task",
                ],
                cwd=tmp_path,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
                check=False,
            )
            assert result.returncode == 0, result.stderr
            record = wait_for_audit(
                Path(env["XDG_STATE_HOME"]) / "opencode" / "local-response-moderator",
                "moderation-fail" if "CONTINUE" in decision else "moderation-pass",
                "SEND_CONTINUATION" if "CONTINUE" in decision else "WRITE_TRACE",
            )
        finally:
            server.kill()
            server.communicate(timeout=10)
    return json.loads(record.read_text(encoding="utf-8")), requests


def test_installed_release_records_idle_trace_and_continuation(tmp_path: Path) -> None:
    record, _ = run_runtime(
        tmp_path, "decision: CONTINUE_PROGRESS\nreason: WORK_REMAINS"
    )
    assert record["event"]["type"] == "CLASSIFIER_RESULT"
    assert {item["effect"] for item in record["effectResults"]} >= {
        "WRITE_TRACE",
        "SEND_CONTINUATION",
    }


def test_installed_release_ignores_tool_calls_update_until_terminal_response(
    tmp_path: Path,
) -> None:
    record, requests = run_runtime(
        tmp_path, "decision: PASS\nreason: COMPLETE", tool_call=True
    )
    assert len(requests) == EXPECTED_PROVIDER_REQUESTS
    assert record["selectedFacts"]["assistant"]["text"] == "completed response"


def test_installed_release_restores_moderator_state_after_restart(
    tmp_path: Path,
) -> None:
    env = installer_env(tmp_path, "decision: PASS\nreason: COMPLETE")
    install = subprocess.run(
        [str(INSTALLER), "install"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert install.returncode == 0, install.stderr
    runtime, wrapper = (
        ROOT / ".boot-linux/bin/opencode",
        ROOT / "workspace/scripts/bin/oc",
    )
    env["OPENCODE_BINARY"] = str(runtime)
    with provider() as (api, _):
        config = Path(env["XDG_CONFIG_HOME"]) / "opencode"
        config.mkdir(parents=True, exist_ok=True)
        (config / "opencode.jsonc").write_text(
            json.dumps(
                {
                    "model": "moderator/moderator-test",
                    "provider": {
                        "moderator": {
                            "npm": "@ai-sdk/openai-compatible",
                            "options": {
                                "apiKey": "test",
                                "baseURL": f"http://127.0.0.1:{api.server_address[1]}/v1",
                            },
                            "models": {
                                "moderator-test": {
                                    "name": "Moderator test",
                                    "limit": {"context": 4096, "output": 128},
                                    "cost": {"input": 0, "output": 0},
                                }
                            },
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        root = Path(env["XDG_STATE_HOME"]) / "opencode" / "local-response-moderator"
        server = subprocess.Popen(
            [str(runtime), "serve", "--port", "4096"],
            cwd=tmp_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        try:
            time.sleep(1)
            assert server.poll() is None
            first = subprocess.run(
                [
                    str(wrapper),
                    "--db",
                    env["OPENCODE_DB"],
                    "--",
                    "run",
                    "--attach",
                    "http://127.0.0.1:4096",
                    "--auto",
                    "--model",
                    "moderator/moderator-test",
                    "first task",
                ],
                cwd=tmp_path,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
                check=False,
            )
            assert first.returncode == 0, first.stderr
            initial = wait_for_audit(root, "moderation-pass", "WRITE_TRACE")
            first_record = json.loads(initial.read_text(encoding="utf-8"))
        finally:
            server.kill()
            server.communicate(timeout=10)
        session_id = first_record["event"]["sessionID"]
        server = subprocess.Popen(
            [str(runtime), "serve", "--port", "4096"],
            cwd=tmp_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        try:
            time.sleep(1)
            assert server.poll() is None
            second = subprocess.run(
                [
                    str(wrapper),
                    "--db",
                    env["OPENCODE_DB"],
                    "--",
                    "run",
                    "--attach",
                    "http://127.0.0.1:4096",
                    "--session",
                    session_id,
                    "--auto",
                    "--model",
                    "moderator/moderator-test",
                    "second task",
                ],
                cwd=tmp_path,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
                check=False,
            )
            assert second.returncode == 0, second.stderr
            restored = json.loads(
                wait_for_audit(
                    root, "moderation-pass", "WRITE_TRACE", {initial}
                ).read_text(encoding="utf-8")
            )
        finally:
            server.kill()
            server.communicate(timeout=10)
    assert set(first_record["nextState"]["moderatorMessageIDs"]) <= set(
        restored["previousState"]["moderatorMessageIDs"]
    )
