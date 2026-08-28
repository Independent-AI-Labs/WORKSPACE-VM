"""End-to-end tests for the local response moderator Bash script."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "workspace/config/opencode/plugins/local-response-moderator.sh"
CONFIG = (
    ROOT / "workspace/config/opencode/plugins/local-response-moderator.template.json"
)
INSTALLER = ROOT / "workspace/scripts/install-opencode-moderator"
MAX_TOKENS = 128


def _installed_script(tmp_path: Path) -> Path:
    """Create the classifier release layout expected by the runtime."""
    script = tmp_path / "local-response-moderator.sh"
    shutil.copy(SCRIPT, script)
    shutil.copy(CONFIG, tmp_path / "config.json")
    return script


def _fake_curl(
    bin_dir: Path, payload_log: Path, response: str = "", finish_reason: str = "stop"
) -> None:
    response_literal = response or "decision: PASS\nreason: COMPLETE"
    (bin_dir / "curl").write_text(
        """#!/bin/bash
set -euo pipefail
url="${!#}"
data=""
while [[ $# -gt 0 ]]; do
  if [[ "$1" == "--data" ]]; then data="$2"; shift 2; continue; fi
  if [[ "$1" == "--data-binary" ]]; then data="$(< "${2#@}")"; shift 2; continue; fi
  shift
done
printf '%s\n' "$data" >> "__PAYLOAD_LOG__"
if [[ "$url" == */input_tokens ]]; then
  printf '{"input_tokens": 10}\n'
else
   response='__RESPONSE__'
    jq -cn --arg content "$response" --arg finish_reason "__FINISH_REASON__" \
      '{choices: [{message: {content: $content}, finish_reason: $finish_reason}]}'
fi
""".replace("__PAYLOAD_LOG__", str(payload_log))
        .replace("__RESPONSE__", response_literal)
        .replace("__FINISH_REASON__", finish_reason),
        encoding="utf-8",
    )
    (bin_dir / "curl").chmod(0o755)


def _installer_env(tmp_path: Path, decision: str | None = None) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    curl = bin_dir / "curl"
    response = json.dumps(decision or "decision: PASS\nreason: COMPLETE")
    curl.write_text(
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
    curl.chmod(0o755)
    return {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "LOCAL_RESPONSE_MODERATOR_REPO_ROOT": str(ROOT),
    }


def test_script_preserves_three_real_users_and_todos(tmp_path: Path) -> None:
    payload_log = tmp_path / "payloads.jsonl"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _fake_curl(fake_bin, payload_log)
    snapshot = {
        "session_id": "ses_test",
        "todos": [{"content": "verify", "status": "in_progress", "priority": "high"}],
        "messages": [
            {
                "info": {"role": "user", "id": "u1"},
                "parts": [{"type": "text", "text": "first request"}],
            },
            {
                "info": {"role": "assistant", "id": "a1"},
                "parts": [{"type": "text", "text": "old answer"}],
            },
            {
                "info": {"role": "user", "id": "u2"},
                "parts": [{"type": "text", "text": "second request"}],
            },
            {
                "info": {"role": "assistant", "id": "a2"},
                "parts": [{"type": "text", "text": "middle answer"}],
            },
            {
                "info": {"role": "user", "id": "u3"},
                "parts": [{"type": "text", "text": "third request"}],
            },
            {
                "info": {"role": "user", "id": "retry"},
                "parts": [
                    {
                        "type": "text",
                        "text": "⚠️ Local Moderator Continuation old failure",
                    }
                ],
            },
            {
                "info": {"role": "assistant", "id": "a3"},
                "parts": [{"type": "text", "text": "latest answer"}],
            },
        ],
    }
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "OPENCODE_MODERATOR_CAPTURE": str(tmp_path / "capture.yaml"),
        "OPENCODE_MODERATOR_CONFIG": str(tmp_path / "config.json"),
    }
    result = subprocess.run(
        ["bash", str(_installed_script(tmp_path))],
        input=json.dumps(snapshot),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "decision: PASS" in result.stdout
    requests = [
        json.loads(line)
        for line in payload_log.read_text().splitlines()
        if line.strip()
    ]
    final_messages = requests[-1]["messages"]
    content = "\n".join(message["content"] for message in final_messages)
    assert "verify" in content
    assert all(
        value in content
        for value in ("first request", "second request", "third request")
    )
    assert "old failure" not in content
    assert requests[-1]["model"] == "/zip/MiniCPM5-1B-Q8_0.gguf"
    assert "decision: PASS\\nreason: COMPLETE" in requests[-1]["grammar"]
    assert requests[-1]["max_tokens"] == MAX_TOKENS
    capture = (tmp_path / "capture.yaml").read_text()
    assert "request: |" in capture


def test_script_excludes_moderator_trace_from_review_context(tmp_path: Path) -> None:
    payload_log = tmp_path / "payloads.jsonl"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _fake_curl(fake_bin, payload_log)
    snapshot = {
        "session_id": "ses_trace",
        "todos": [],
        "messages": [
            {
                "info": {"role": "user", "id": "u1"},
                "parts": [{"type": "text", "text": "complete the task"}],
            },
            {
                "info": {"role": "user", "id": "trace"},
                "parts": [
                    {"type": "text", "text": "🔎 Local Moderator Decision: PASS"}
                ],
            },
            {
                "info": {"role": "assistant", "id": "a1"},
                "parts": [{"type": "text", "text": "[WORK DONE]"}],
            },
        ],
    }
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "OPENCODE_MODERATOR_CAPTURE": str(tmp_path / "capture.yaml"),
        "OPENCODE_MODERATOR_CONFIG": str(tmp_path / "config.json"),
    }
    result = subprocess.run(
        ["bash", str(_installed_script(tmp_path))],
        input=json.dumps(snapshot),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    requests = [
        json.loads(line)
        for line in payload_log.read_text().splitlines()
        if line.strip()
    ]
    content = "\n".join(message["content"] for message in requests[-1]["messages"])
    assert "🔎 Local Moderator Decision" not in content


def test_script_returns_continuation_decision(tmp_path: Path) -> None:
    payload_log = tmp_path / "payloads.jsonl"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _fake_curl(
        fake_bin,
        payload_log,
        "decision: CONTINUE_NO_PROGRESS\nreason: NO_PROGRESS",
    )
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "OPENCODE_MODERATOR_CAPTURE": str(tmp_path / "capture.yaml"),
        "OPENCODE_MODERATOR_CONFIG": str(tmp_path / "config.json"),
    }
    snapshot = {
        "session_id": "ses_continue",
        "todos": [{"content": "finish", "status": "in_progress", "priority": "high"}],
        "messages": [],
    }
    result = subprocess.run(
        ["bash", str(_installed_script(tmp_path))],
        input=json.dumps(snapshot),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "decision: CONTINUE_NO_PROGRESS" in result.stdout
    assert "reason: NO_PROGRESS" in result.stdout


def test_script_accepts_two_field_pass_decision(tmp_path: Path) -> None:
    payload_log = tmp_path / "payloads.jsonl"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _fake_curl(fake_bin, payload_log, "decision: PASS\nreason: COMPLETE")
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "OPENCODE_MODERATOR_CAPTURE": str(tmp_path / "capture.yaml"),
        "OPENCODE_MODERATOR_CONFIG": str(tmp_path / "config.json"),
    }
    result = subprocess.run(
        ["bash", str(_installed_script(tmp_path))],
        input=json.dumps({"session_id": "ses_incomplete", "todos": [], "messages": []}),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "decision: PASS" in result.stdout


def test_script_rejects_extra_yaml_fields(tmp_path: Path) -> None:
    payload_log = tmp_path / "payloads.jsonl"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _fake_curl(
        fake_bin,
        payload_log,
        "decision: CONTINUE_PROGRESS\nreason: implementation advanced\n"
        "task_completion: FAIL - work remains\nreason: work remains\n"
        "prompt_adherence: PASS - followed instructions\nreason: followed instructions",
    )
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "OPENCODE_MODERATOR_CAPTURE": str(tmp_path / "capture.yaml"),
        "OPENCODE_MODERATOR_CONFIG": str(tmp_path / "config.json"),
    }
    result = subprocess.run(
        ["bash", str(_installed_script(tmp_path))],
        input=json.dumps({"session_id": "ses_inline", "todos": [], "messages": []}),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert result.returncode != 0
    assert "invalid moderator YAML line" in result.stderr


def test_script_rejects_title_case_prose_rulings(tmp_path: Path) -> None:
    payload_log = tmp_path / "payloads.jsonl"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _fake_curl(
        fake_bin,
        payload_log,
        "Decision: PASS\nReason: verified completion\nRuling: PASS",
    )
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "OPENCODE_MODERATOR_CAPTURE": str(tmp_path / "capture.yaml"),
        "OPENCODE_MODERATOR_CONFIG": str(tmp_path / "config.json"),
    }
    result = subprocess.run(
        ["bash", str(_installed_script(tmp_path))],
        input=json.dumps({"session_id": "ses_prose", "todos": [], "messages": []}),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert result.returncode != 0
    assert "invalid moderator YAML line" in result.stderr


def test_script_rejects_invalid_decision_reason_pair(tmp_path: Path) -> None:
    payload_log = tmp_path / "payloads.jsonl"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _fake_curl(fake_bin, payload_log, "decision: PASS\nreason: WORK_REMAINS")
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "OPENCODE_MODERATOR_CAPTURE": str(tmp_path / "capture.yaml"),
        "OPENCODE_MODERATOR_CONFIG": str(tmp_path / "config.json"),
    }
    result = subprocess.run(
        ["bash", str(_installed_script(tmp_path))],
        input=json.dumps({"session_id": "ses_pair", "todos": [], "messages": []}),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert result.returncode != 0
    assert "invalid moderator decision and reason combination" in result.stderr


def test_script_rejects_nonterminating_classifier_response(tmp_path: Path) -> None:
    payload_log = tmp_path / "payloads.jsonl"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _fake_curl(
        fake_bin,
        payload_log,
        "decision: PASS\nreason: COMPLETE",
        finish_reason="length",
    )
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "OPENCODE_MODERATOR_CAPTURE": str(tmp_path / "capture.yaml"),
        "OPENCODE_MODERATOR_CONFIG": str(tmp_path / "config.json"),
    }
    result = subprocess.run(
        ["bash", str(_installed_script(tmp_path))],
        input=json.dumps({"session_id": "ses_length", "todos": [], "messages": []}),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert result.returncode != 0
    assert "invalid moderator finish reason: length" in result.stderr


def test_script_preserves_raw_response_on_invalid_yaml(tmp_path: Path) -> None:
    payload_log = tmp_path / "payloads.jsonl"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _fake_curl(fake_bin, payload_log, "prose without a YAML verdict")
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "OPENCODE_MODERATOR_CAPTURE": str(tmp_path / "capture.yaml"),
        "OPENCODE_MODERATOR_CONFIG": str(tmp_path / "config.json"),
    }
    snapshot = {"session_id": "ses_invalid", "todos": [], "messages": []}
    result = subprocess.run(
        ["bash", str(_installed_script(tmp_path))],
        input=json.dumps(snapshot),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert result.returncode != 0
    capture = (tmp_path / "capture.yaml").read_text()
    assert "rawResponse: |" in capture
    assert "prose without a YAML verdict" in capture


def test_installer_rejects_current_link_outside_releases(tmp_path: Path) -> None:
    env = _installer_env(tmp_path)
    state = Path(env["XDG_CONFIG_HOME"]) / "opencode/plugins/.local-response-moderator"
    state.mkdir(parents=True)
    (state / "current").symlink_to(tmp_path)
    for command in ("verify", "status", "install"):
        result = subprocess.run(
            [str(INSTALLER), command],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert result.returncode != 0
        assert "active release escapes releases directory" in result.stderr


def test_installer_verify_rejects_entry_replaced_outside_current_release(
    tmp_path: Path,
) -> None:
    env = _installer_env(tmp_path)
    installed = subprocess.run(
        [str(INSTALLER), "install"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert installed.returncode == 0, installed.stderr
    plugins = Path(env["XDG_CONFIG_HOME"]) / "opencode/plugins"
    entry = plugins / "local-response-moderator.js"
    entry.unlink()
    replacement = tmp_path / "replacement.js"
    replacement.write_text("export default {}\n", encoding="utf-8")
    entry.symlink_to(replacement)
    result = subprocess.run(
        [str(INSTALLER), "verify"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode != 0
    assert "does not resolve to the current release adapter" in result.stderr


def test_installed_release_loads_in_opencode(tmp_path: Path) -> None:
    env = _installer_env(tmp_path)
    env["HOME"] = str(tmp_path / "home")
    env["XDG_DATA_HOME"] = str(tmp_path / "data")
    install = subprocess.run(
        [str(INSTALLER), "install"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert install.returncode == 0, install.stderr
    runtime = ROOT / ".boot-linux/bin/opencode"
    assert runtime.is_file(), f"OpenCode runtime missing: {runtime}"
    process = subprocess.Popen(
        [str(runtime), "serve", "--port", "0", "--print-logs", "--log-level", "DEBUG"],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    time.sleep(1)
    assert process.poll() is None
    process.terminate()
    stdout, stderr = process.communicate(timeout=10)
    assert "failed to load plugin" not in (stdout + stderr).lower()
