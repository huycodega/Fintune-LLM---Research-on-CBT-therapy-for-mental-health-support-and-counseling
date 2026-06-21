#!/usr/bin/env python3
"""
Fallback Codex conversation logger.

Some Codex surfaces do not run repository lifecycle hooks. This script reads
Codex's local SQLite event log and backfills user prompts into .ai-log/session.jsonl.
Run once to sync, or run with --watch to keep syncing while you chat.
"""
import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

VN_TZ = timezone(timedelta(hours=7))
REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = REPO_ROOT / ".ai-log" / ".codex-sync-state.json"
SESSION_FILE = REPO_ROOT / ".ai-log" / "session.jsonl"
CODEX_LOGS = Path.home() / ".codex" / "logs_2.sqlite"
CODEX_SESSIONS = Path.home() / ".codex" / "sessions"
SESSION_SCAN_WINDOW_SECONDS = 7 * 24 * 60 * 60
MAX_SESSION_LINE_CHARS = 250_000


def load_env_file() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:
        pass


def submit_pending_logs() -> None:
    script = REPO_ROOT / "scripts" / "submit_log.py"
    if not script.exists():
        return
    subprocess.run(
        [sys.executable, str(script)],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def repair_mojibake(text):
    """Repair UTF-8 text that was accidentally decoded as Windows-1252."""
    if not text:
        return text
    markers = ("Ã", "Â", "Ä", "áº", "á»", "Æ")
    if not any(marker in text for marker in markers):
        return text
    try:
        fixed = text.encode("cp1252").decode("utf-8")
    except UnicodeError:
        return text
    return fixed if fixed else text

def git(cmd):
    try:
        return subprocess.check_output(
            cmd, shell=True, cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return ""


def load_state():
    if not STATE_FILE.exists():
        return {"last_id": 0}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"last_id": 0}


def save_state(last_id, last_session_ts=None):
    state = {"last_id": last_id}
    if last_session_ts is not None:
        state["last_session_ts"] = last_session_ts
    else:
        previous = load_state()
        if "last_session_ts" in previous:
            state["last_session_ts"] = previous["last_session_ts"]
    STATE_FILE.parent.mkdir(exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    os.replace(tmp, STATE_FILE)


def extract_request(body):
    normalized = body.replace("\\n", "\n").replace('\\"', '"')
    match = re.search(
        r"## My request for Codex:\n(?P<request>.*?)(?:\", text_elements:|\r?\n\", text_elements:)",
        normalized,
        re.DOTALL,
    )
    if match:
        return match.group("request").strip()

    matches = list(re.finditer(r"User prompt:\n(?P<request>.*?)(?:\", text_elements:)", normalized, re.DOTALL))
    for match in reversed(matches):
        prompt = match.group("request").strip()
        if (
            prompt
            and not prompt.startswith(("You are a helpful assistant", "Generate a clear"))
            and not prompt.startswith("(?P<")
        ):
            return prompt
    return ""


def existing_session_ids():
    if not SESSION_FILE.exists():
        return set()
    ids = set()
    try:
        with SESSION_FILE.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    session_id = json.loads(line).get("session_id")
                except json.JSONDecodeError:
                    continue
                if session_id:
                    ids.add(session_id)
    except OSError:
        return set()
    return ids


def existing_prompts():
    if not SESSION_FILE.exists():
        return set()
    prompts = set()
    try:
        with SESSION_FILE.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    prompt = json.loads(line).get("prompt")
                except json.JSONDecodeError:
                    continue
                if prompt:
                    prompts.add(prompt)
    except OSError:
        return set()
    return prompts


def extract_request_from_user_message(text):
    if not text:
        return ""
    marker = "## My request for Codex:"
    if marker in text:
        return clean_prompt(text.rsplit(marker, 1)[1].strip())
    return clean_prompt(text.strip())


def clean_prompt(prompt):
    if not prompt:
        return ""
    stripped = prompt.strip()
    if stripped.startswith('{"ts":') and '"prompt"' in stripped:
        parts = stripped.splitlines()
        tail = [line.strip() for line in parts[1:] if line.strip()]
        if tail:
            return "\n".join(tail)
    return stripped


def is_project_message(text):
    lower = text.lower()
    return "c2-app-109" in lower or "g:\\github\\c2-app-109" in lower


def iter_session_prompts(since_ts):
    if not CODEX_SESSIONS.exists():
        return []

    now = time.time()
    prompts = []
    for session_file in CODEX_SESSIONS.rglob("*.jsonl"):
        try:
            if now - session_file.stat().st_mtime > SESSION_SCAN_WINDOW_SECONDS:
                continue
        except OSError:
            continue
        try:
            with session_file.open(encoding="utf-8", errors="replace") as f:
                for line_no, line in enumerate(f, start=1):
                    if len(line) > MAX_SESSION_LINE_CHARS:
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    payload = item.get("payload") or {}
                    if payload.get("type") != "user_message":
                        continue
                    message = payload.get("message", "")
                    if not is_project_message(message):
                        continue
                    prompt = extract_request_from_user_message(message)
                    if not prompt:
                        continue
                    ts_raw = item.get("timestamp", "")
                    try:
                        ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).astimezone(VN_TZ)
                    except ValueError:
                        ts = datetime.now(VN_TZ)
                    epoch = ts.timestamp()
                    if epoch <= since_ts:
                        continue
                    prompts.append({
                        "key": f"codex-log-sync-{int(epoch * 1000)}-{line_no}",
                        "ts": ts.isoformat(),
                        "epoch": epoch,
                        "prompt": repair_mojibake(prompt)[:1000],
                        "transcript_path": str(CODEX_LOGS),
                    })
        except OSError:
            continue

    prompts.sort(key=lambda item: item["ts"])
    return prompts


def iter_new_prompts(last_id):
    if not CODEX_LOGS.exists():
        return []

    con = sqlite3.connect(f"file:{CODEX_LOGS}?mode=ro", uri=True)
    rows = con.execute(
        """
        select id, ts, feedback_log_body
        from logs
        where id > ?
          and feedback_log_body like '%Submission sub=Submission%'
          and feedback_log_body like '%UserInput%'
          and feedback_log_body like '%C2-App-109%'
        order by id asc
        """,
        (last_id,),
    ).fetchall()
    con.close()

    prompts = []
    for row_id, ts, body in rows:
        prompt = repair_mojibake(extract_request(body or ""))
        if prompt:
            prompts.append((row_id, ts, prompt))
    return prompts


def append_prompt(row_id, ts, prompt):
    SESSION_FILE.parent.mkdir(exist_ok=True)
    entry = {
        "ts": datetime.fromtimestamp(ts, VN_TZ).isoformat(),
        "tool": "codex",
        "event": "UserPromptSubmit",
        "session_id": f"codex-log-sync-{row_id}",
        "model": "",
        "repo": "C2-App-109",
        "branch": git("git rev-parse --abbrev-ref HEAD"),
        "commit": git("git rev-parse --short HEAD"),
        "student": git("git config user.email"),
        "prompt": prompt[:1000],
        "turn_id": "",
        "transcript_path": str(CODEX_LOGS),
    }
    with SESSION_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def append_session_prompt(item):
    SESSION_FILE.parent.mkdir(exist_ok=True)
    entry = {
        "ts": item["ts"],
        "tool": "codex",
        "event": "UserPromptSubmit",
        "session_id": item["key"],
        "model": "",
        "repo": "C2-App-109",
        "branch": git("git rev-parse --abbrev-ref HEAD"),
        "commit": git("git rev-parse --short HEAD"),
        "student": git("git config user.email"),
        "prompt": item["prompt"],
        "turn_id": "",
        "transcript_path": item["transcript_path"],
    }
    with SESSION_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def sync_once():
    state = load_state()
    last_id = int(state.get("last_id", 0))
    last_session_ts = float(state.get("last_session_ts") or time.time())
    prompts = iter_new_prompts(last_id)
    seen = existing_session_ids()
    seen_prompts = existing_prompts()
    written = 0
    for row_id, ts, prompt in prompts:
        session_id = f"codex-log-sync-{row_id}"
        if session_id not in seen and prompt not in seen_prompts:
            append_prompt(row_id, ts, prompt)
            seen.add(session_id)
            seen_prompts.add(prompt)
            written += 1
        last_id = max(last_id, row_id)

    for item in iter_session_prompts(last_session_ts):
        if item["key"] in seen or item["prompt"] in seen_prompts:
            last_session_ts = max(last_session_ts, item["epoch"])
            continue
        append_session_prompt(item)
        seen.add(item["key"])
        seen_prompts.add(item["prompt"])
        last_session_ts = max(last_session_ts, item["epoch"])
        written += 1

    save_state(last_id, last_session_ts)

    return written


def main():
    load_env_file()

    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true", help="Keep syncing until stopped")
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()

    if args.watch:
        while True:
            count = sync_once()
            submit_pending_logs()
            if count:
                print(json.dumps({"status": "synced", "count": count}), flush=True)
            time.sleep(args.interval)
    else:
        count = sync_once()
        submit_pending_logs()
        print(json.dumps({"status": "synced", "count": count}))


if __name__ == "__main__":
    main()


