"""
Agent orchestrator client — wraps the Modal-hosted Huysun29/cbt-qwen2.5-7b-v2
(function-calling brain) at MODAL_AGENT_ENDPOINT.

This is the transport layer for the agentic loop in `agent.py`. It speaks
the same circuit-breaker protocol as `llm_client.py` so a dead orchestrator
endpoint degrades the system back to the deterministic pipeline rather than
hanging requests.

Endpoint contract (modal/agent_service.py):
    POST /chat   { messages, tools, temperature, max_new_tokens }
                 → { content, tool_calls, raw }
    GET  /health → { status, model, gpu }

`tool_calls` is a list of {"name": str, "arguments": dict}. When the model
chooses to answer in prose instead of calling a tool, `tool_calls` is empty
and `content` carries the text.
"""
import json
import logging
import time
import urllib.request
from typing import Dict, List, Optional

from app.core.config import settings
from app.services import redis_client as rc


log = logging.getLogger(__name__)


def available() -> bool:
    """True only when the agent feature is on AND a backend exists for it
    (the Modal orchestrator endpoint, or the Claude provider)."""
    if not settings.agent_enabled:
        return False
    if settings.llm_provider == "claude" and settings.anthropic_api_key:
        return True
    return bool(settings.modal_agent_endpoint)


def health() -> Dict:
    if not settings.agent_enabled:
        return {"reachable": False, "mode": "disabled",
                "note": "AGENT_ENABLED is false"}
    if settings.llm_provider == "claude":
        from app.services import claude_client
        return {**claude_client.health(), "role": "orchestrator"}
    url = settings.modal_agent_health_endpoint
    if not url:
        return {"reachable": False, "mode": "agent",
                "error": "MODAL_AGENT_HEALTH_ENDPOINT not set"}
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return {"reachable": True, "mode": "agent",
                    **json.loads(r.read().decode())}
    except Exception as e:
        return {"reachable": False, "mode": "agent", "error": str(e)}


def chat(messages: List[Dict],
         tools: Optional[List[Dict]] = None,
         temperature: Optional[float] = None,
         max_new_tokens: int = 512,
         timeout: Optional[int] = None,
         force_tool_call: Optional[bool] = None) -> Optional[Dict]:
    """
    One orchestrator step. Returns {"content", "tool_calls", "raw"} or None
    on failure (caller is expected to fall back to the fixed pipeline).

    Shares the Modal circuit breaker with llm_client so repeated failures
    against either Modal app trip the same breaker.
    """
    if not available():
        return None
    if not rc.circuit_should_call():
        log.warning("Circuit breaker OPEN — agent orchestrator skipped")
        return None

    if timeout is None:
        timeout = settings.modal_call_timeout

    # Force a tool call ONLY when tools are offered (never for plain-text
    # completions like the clinician copilot). Defaults to the global setting.
    if force_tool_call is None:
        force_tool_call = settings.agent_force_tool_call
    force_tool_call = bool(force_tool_call and tools)

    if settings.llm_provider == "claude":
        from app.services import claude_client
        out = claude_client.chat(
            messages, tools=tools,
            temperature=(settings.agent_temperature
                         if temperature is None else temperature),
            max_tokens=max_new_tokens, force_tool_call=force_tool_call)
        if out is not None:
            rc.circuit_record_success()
        else:
            rc.circuit_record_failure()
        return out

    body = json.dumps({
        "messages": messages,
        "tools": tools or [],
        "temperature": (settings.agent_temperature
                        if temperature is None else temperature),
        "max_new_tokens": max_new_tokens,
        "force_tool_call": force_tool_call,
    }).encode()

    req = urllib.request.Request(
        settings.modal_agent_endpoint, data=body,
        headers={"Content-Type": "application/json"}, method="POST")

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
        rc.circuit_record_success()
        data.setdefault("content", "")
        data.setdefault("tool_calls", [])
        data["wall_time"] = time.time() - t0
        return data
    except Exception as e:
        rc.circuit_record_failure()
        log.warning("Agent orchestrator call failed: %s", e)
        return None


def complete(system: str, user: str,
             temperature: float = 0.3, max_new_tokens: int = 600) -> Optional[str]:
    """
    Plain text completion (no tools) — used by clinician_copilot for
    summaries / SOAP drafting / Q&A. Returns the content string or None.
    """
    out = chat(
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        tools=[],
        temperature=temperature,
        max_new_tokens=max_new_tokens,
    )
    if out is None:
        return None
    return (out.get("content") or "").strip() or None
