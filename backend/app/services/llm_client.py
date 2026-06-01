"""
LLM client — wraps the Modal endpoint for `Huysun29/cbt-llama-3.1-8b`
(Llama-3.1-8B Instruct + CBT LoRA adapter). Guarded by the Redis circuit
breaker so the API does not keep slamming a dead endpoint.

When `MOCK_LLM=true` (default for the local thesis demo), returns
deterministic English drafts that exercise the full HITL flow without
needing a GPU.
"""
import json
import logging
import re
import time
import urllib.request
from typing import Dict, List

from app.core.config import settings
from app.services import redis_client as rc


log = logging.getLogger(__name__)


def health() -> Dict:
    if settings.mock_llm:
        return {"reachable": True, "mode": "mock",
                "model": settings.hf_model_repo}
    url = settings.modal_health_endpoint
    if not url:
        return {"reachable": False, "mode": "modal",
                "error": "MODAL_HEALTH_ENDPOINT not set"}
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return {"reachable": True, "mode": "modal",
                    **json.loads(r.read().decode())}
    except Exception as e:
        return {"reachable": False, "mode": "modal", "error": str(e)}


def generate(messages: List[Dict], n: int = None,
             temperature: float = None) -> Dict:
    n = n or settings.n_responses
    temperature = temperature or settings.temperature

    if settings.mock_llm:
        return _mock(messages, n)

    if not rc.circuit_should_call():
        log.warning("Circuit breaker OPEN — using degraded mock response")
        out = _mock(messages, n)
        out["degraded"] = True
        return out

    body = json.dumps({
        "messages": messages,
        "n_responses": n,
        "temperature": temperature,
        "top_p": settings.top_p,
        "max_new_tokens": settings.max_new_tokens,
    }).encode()

    req = urllib.request.Request(
        settings.modal_llm_endpoint, data=body,
        headers={"Content-Type": "application/json"}, method="POST")

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read().decode())
        rc.circuit_record_success()
        data["wall_time"] = time.time() - t0
        return data
    except Exception as e:
        rc.circuit_record_failure()
        log.exception("Modal LLM call failed: %s", e)
        # Degrade gracefully so the user still gets *something*
        out = _mock(messages, n)
        out["degraded"] = True
        out["error"] = str(e)
        return out


# ============================================================
# Mock generator (English) — varied, distinguishable drafts
# ============================================================
def _mock(messages: List[Dict], n: int) -> Dict:
    user = messages[-1]["content"]
    m = re.search(r"\[CURRENT CLIENT MESSAGE\]\n(.+?)(?:\n\n\[|\Z)",
                  user, re.S)
    thought = (m.group(1).strip()[:120] if m else "")

    templates = [
        ("decatastrophizing",
         "The client is forecasting an extreme worst-case outcome and "
         "evaluating it as already true.",
         "1. Name the feared outcome explicitly. "
         "2. Estimate its realistic probability. "
         "3. Build a coping plan even if the worst case happened.",
         "That sounds genuinely heavy, and it makes sense you'd feel "
         "that way given what you're imagining. Let's slow this down "
         "together: what would it mean, concretely, if that feared "
         "outcome did happen — and what could you do to cope with it?"),
        ("reality testing",
         "The belief is stated as a fact without examined evidence.",
         "1. List evidence for and against the thought. "
         "2. Weigh both sides openly. "
         "3. Try a more balanced version of the belief out loud.",
         "I hear how strongly that belief is sitting with you right now. "
         "Sometimes feelings hit so hard they look like facts. What's "
         "the actual evidence for it — and what evidence might point "
         "the other way?"),
        ("alternative perspective",
         "An all-or-nothing or rigid frame is narrowing the client's "
         "options.",
         "1. Surface the implicit rule the client is operating under. "
         "2. Generate 2-3 other possible viewpoints. "
         "3. Pick one to try this week.",
         "Notice how 'either/or' that thought is framed. If a close "
         "friend told you the same thing, what other ways might you "
         "see their situation? Let's try holding two viewpoints at "
         "once for a moment."),
    ]
    out = []
    for i in range(n):
        tech, rat, plan, resp = templates[i % len(templates)]
        client_quote = f' ("{thought}")' if thought else ""
        full_response = resp.replace(
            "given what you're imagining", f"given what you described{client_quote}"
        )
        out.append(
            f"Technique: {tech}\n"
            f"Rationale: {rat}\n"
            f"Plan: {plan}\n"
            f"Response: {full_response}"
        )
    return {"responses": out, "mode": "mock", "wall_time": 0.0,
            "timing": {"total_seconds": 0.0, "per_response_seconds": 0.0}}
