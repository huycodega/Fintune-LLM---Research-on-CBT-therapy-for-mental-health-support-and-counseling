"""
Claude API transport — the `LLM_PROVIDER=claude` backend for every LLM role
(responder, safety triage, orchestrator, vent-check, rewrite, emphasis,
scope classify, summarizer, copilot). Deliberately dependency-free: raw
HTTPS against api.anthropic.com, same urllib pattern as the Modal clients.

Design constraints honoured:
  - default provider stays "local" — deploying this file changes NOTHING
    until ANTHROPIC_API_KEY + LLM_PROVIDER=claude are set;
  - PII is already scrubbed upstream (same choke as the Modal path);
  - callers keep their existing contracts/fallbacks: any failure here maps
    to the same degraded paths (mock drafts, heuristic triage, fixed
    pipeline) — Claude being down can never behave worse than Modal down;
  - embeddings / rerank / NLI are NOT LLM roles and stay on the brain
    (Anthropic has no embeddings API; the Qdrant index is bge-m3 1024-dim).
"""
import json
import logging
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

from app.core.config import settings

log = logging.getLogger(__name__)

_API = "https://api.anthropic.com/v1/messages"
_VERSION = "2023-06-01"


def enabled() -> bool:
    return (getattr(settings, "llm_provider", "local") == "claude"
            and bool(getattr(settings, "anthropic_api_key", None)))


def _post(payload: dict, timeout: int = 120, retries: int = 4) -> dict:
    """POST with backoff on 429/529 — fresh keys sit in tier 1 (50 req/min)
    and the 147-example crisis gate would trip the limiter without this."""
    last = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            _API, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json",
                     "x-api-key": settings.anthropic_api_key,
                     "anthropic-version": _VERSION},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 529) and attempt < retries:
                wait = min(2 ** attempt * 2, 30)
                retry_after = e.headers.get("retry-after")
                if retry_after:
                    try:
                        wait = max(wait, float(retry_after))
                    except ValueError:
                        pass
                log.warning("Claude %s — retry in %.0fs (%d/%d)",
                            e.code, wait, attempt + 1, retries)
                time.sleep(wait)
                last = e
                continue
            raise
    raise last


def _split(messages: List[Dict]):
    """Anthropic separates system from the turn list; roles must alternate
    user/assistant. Our pipelines only ever send system+user (+history in
    the user block), so a light conversion suffices."""
    system_parts, turns = [], []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            system_parts.append(content)
        elif role in ("user", "assistant"):
            turns.append({"role": role, "content": content})
        else:                      # tool results etc. → user-visible context
            turns.append({"role": "user", "content": str(content)})
    if not turns:
        turns = [{"role": "user", "content": ""}]
    if turns[0]["role"] != "user":
        turns.insert(0, {"role": "user", "content": "(continue)"})
    return "\n\n".join(p for p in system_parts if p), turns


def _text_of(resp: dict) -> str:
    return "".join(b.get("text", "") for b in resp.get("content", [])
                   if b.get("type") == "text").strip()


def generate(messages: List[Dict], n: int = 3,
             temperature: float = 0.7,
             max_tokens: Optional[int] = None) -> Dict:
    """llm_client.generate contract: {"responses": [str...], "mode", ...}.
    Anthropic has no n-sampling param, so n independent calls run in
    parallel. Raises on TOTAL failure (caller degrades like a Modal
    failure); partial success returns what came back."""
    system, turns = _split(messages)
    # Claude 5 family: `temperature` is deprecated (API rejects it) and
    # extended thinking is on by default — disable it: we want fast, cheap,
    # text-only completions with natural sampling variety across n calls.
    payload = {
        "model": settings.claude_model,
        "max_tokens": max_tokens or settings.claude_max_tokens,
        "thinking": {"type": "disabled"},
        "messages": turns,
    }
    if system:
        payload["system"] = system

    t0 = time.time()
    outs: List[str] = []

    def _one(_):
        return _text_of(_post(payload))

    with ThreadPoolExecutor(max_workers=min(n, 4)) as ex:
        for fut in [ex.submit(_one, i) for i in range(n)]:
            try:
                txt = fut.result()
                if txt:
                    outs.append(txt)
            except Exception as e:            # partial failures tolerated
                log.warning("Claude draft call failed: %s", e)
    if not outs:
        raise RuntimeError("all Claude draft calls failed")
    return {"responses": outs, "mode": "claude",
            "model": settings.claude_model,
            "wall_time": time.time() - t0,
            "timing": {"total_seconds": round(time.time() - t0, 2)}}


def triage(messages: List[Dict]) -> Optional[str]:
    """Single near-deterministic call for the safety gate. Returns raw text
    (the gate parses {"level": ...}) or None on failure → heuristic path."""
    system, turns = _split(messages)
    payload = {
        "model": settings.claude_model,
        "max_tokens": 200,
        "thinking": {"type": "disabled"},
        "messages": turns,
    }
    if system:
        payload["system"] = system
    try:
        return _text_of(_post(payload, timeout=60))
    except Exception as e:
        log.warning("Claude triage call failed: %s", e)
        return None


def _tools_to_anthropic(tools: List[Dict]) -> List[Dict]:
    """OpenAI-style {"type":"function","function":{name,description,
    parameters}} → Anthropic {name, description, input_schema}."""
    out = []
    for t in tools or []:
        fn = t.get("function", t)
        out.append({
            "name": fn.get("name", ""),
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters",
                                   {"type": "object", "properties": {}}),
        })
    return out


def chat(messages: List[Dict], tools: Optional[List[Dict]] = None,
         temperature: float = 0.3, max_tokens: int = 512,
         force_tool_call: bool = False) -> Optional[Dict]:
    """agent_client.chat contract: {"content", "tool_calls", "raw"} or None
    on failure (agent falls back to the fixed pipeline)."""
    system, turns = _split(messages)
    payload = {
        "model": settings.claude_model,
        "max_tokens": max_tokens,
        "thinking": {"type": "disabled"},
        "messages": turns,
    }
    if system:
        payload["system"] = system
    a_tools = _tools_to_anthropic(tools)
    if a_tools:
        payload["tools"] = a_tools
        payload["tool_choice"] = ({"type": "any"} if force_tool_call
                                  else {"type": "auto"})
    try:
        resp = _post(payload)
    except Exception as e:
        log.warning("Claude chat call failed: %s", e)
        return None
    tool_calls = [{"name": b.get("name", ""),
                   "arguments": b.get("input", {}) or {}}
                  for b in resp.get("content", [])
                  if b.get("type") == "tool_use"]
    return {"content": _text_of(resp), "tool_calls": tool_calls,
            "raw": json.dumps(resp)[:2000], "mode": "claude",
            "model": settings.claude_model}


def health() -> Dict:
    if not enabled():
        return {"reachable": False, "mode": "claude",
                "error": "LLM_PROVIDER/ANTHROPIC_API_KEY not set"}
    return {"reachable": True, "mode": "claude",
            "model": settings.claude_model}
