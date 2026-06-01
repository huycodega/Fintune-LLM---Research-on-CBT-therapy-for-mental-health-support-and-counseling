"""
Unit + service-level tests for v4 — covers the parts that don't need
Postgres / Redis / MinIO / Qdrant running. Full HTTP integration test
(test_pipeline.py) requires the Docker stack — run that with:

    docker compose exec backend pytest -q
"""
import os
import sys
import pytest

os.environ["PHI_AES_KEY_B64"] = "MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDE="
os.environ["MOCK_LLM"] = "true"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_intake_parser_brooke():
    from app.services.intake_parser import parse_intake
    text = (
        "Name: Brooke Davis Age: 41 Gender: female Occupation: Veterinary "
        "Assistant Education: CVT Marital Status: Single Family Details: "
        "Lives alone with multiple pets  2. Presenting Problem I feel "
        "anxious about returning to the shelter.  3. Reason for Seeking "
        "Counseling Affects my daily life.  4. Past History No prior. "
        "5. Academic/occupational functioning level: Job unchanged. "
        "Interpersonal relationships: Strained. Daily life: Sleep poor. "
        "6. Social Support System A few friends."
    )
    p = parse_intake(text)
    assert p["parse_confidence"] >= 0.83
    assert p["demographics"]["name"] == "Brooke Davis"
    assert p["demographics"]["age"] == 41
    assert "shelter" in p["presenting"]
    assert "daily life" in p["reason"]


def test_pii_scrubber():
    from app.services.pii_scrubber import scrub
    # The scrubber targets structured PII (SSN, phone, email, address,
    # 'Name: <X>' patterns) — it deliberately does NOT match free-form
    # names because false positives are too risky.
    text = ("Hi, my SSN is 123-45-6789, phone +1 555-123-4567, "
            "email john@example.com, address 1234 Main Street. "
            "Name: John Smith")
    out = scrub(text)
    assert "[SSN]" in out
    assert "[PHONE]" in out
    assert "[EMAIL]" in out
    assert "[ADDRESS]" in out
    assert "Name: [NAME]" in out
    assert "123-45-6789" not in out
    assert "john@example.com" not in out


def test_safety_heuristic():
    from app.services.safety_gate import _heuristic
    assert _heuristic("I want to disappear forever")["triage_level"] == "L0"
    assert _heuristic("I sometimes cut myself")["triage_level"] == "L1"
    assert _heuristic("I feel anxious lately")["triage_level"] == "L2"
    assert _heuristic("I want to learn time management")["triage_level"] == "L3"


def test_analyzer():
    from app.services.analyzer import analyze
    a = analyze("I always fail at everything", "moderate")
    assert "all-or-nothing" in a["cognitive_distortions"]
    assert a["technique_hint"]


def test_aes_round_trip():
    from app.core.crypto import encrypt_phi, decrypt_str
    s = "She lives alone with multiple pets"
    assert decrypt_str(encrypt_phi(s)) == s


def test_preflight_critical_rejects_dangerous_technique():
    from app.services.preflight import check_draft
    bad = check_draft(
        {"technique": "behavior experiment", "response": "just try it"},
        "critical")
    assert bad[0] is False
    assert any("contraindicated" in r for r in bad[1])

    good = check_draft(
        {"technique": "CRISIS_REFERRAL",
         "response": "Please call 988 hotline and talk to a trusted person."},
        "critical")
    assert good[0] is True


def test_post_process_parse():
    from app.services.post_process import parse_all, grounding_score
    raw = ("Technique: reality testing\nRationale: r\nPlan: p\n"
           "Response: hello world anxious feeling")
    parsed = parse_all([raw])
    assert parsed[0]["technique"] == "reality testing"
    assert "anxious" in parsed[0]["response"]
    g = grounding_score(parsed[0]["response"],
                         [{"text": "anxious feeling about shelter"}])
    assert 0 <= g <= 1


def test_nli_grounding_falls_back_when_model_unavailable():
    """When sentence_transformers is stubbed, NLI module must
    transparently fall back to lexical overlap."""
    from app.services import hallucination_nli
    # Force "model unavailable" path
    hallucination_nli._model = (None, -1)
    score = hallucination_nli.grounding_nli(
        "I feel anxious about the shelter visit tomorrow.",
        [{"text": "anxious feelings about shelter visit are normal"}])
    assert 0 <= score <= 1
    # Lexical should at least register overlap on "anxious" / "shelter"
    assert score > 0


def test_nli_empty_inputs():
    from app.services import hallucination_nli
    assert hallucination_nli.grounding_nli("", [{"text": "x"}]) == 0.0
    assert hallucination_nli.grounding_nli("y", []) == 0.0


def test_grafana_dashboard_json_valid():
    """The provisioned Grafana dashboard must parse and reference our
    real metric names — otherwise the dashboard breaks silently."""
    import json
    from pathlib import Path
    p = (Path(__file__).parent.parent.parent / "infra" / "grafana"
         / "dashboards" / "cbt-overview.json")
    dash = json.loads(p.read_text())
    assert dash["uid"] == "cbt-overview"
    assert len(dash["panels"]) >= 8
    # All PromQL exprs must reference real metric names we actually emit
    emitted = {
        "cbt_triage_level_total", "cbt_stage_latency_seconds_bucket",
        "cbt_hallucination_flag_total", "cbt_preflight_fail_total",
        "cbt_review_decision_total", "cbt_retrieval_count_bucket",
        "cbt_triage_cache_total",
    }
    for panel in dash["panels"]:
        for tgt in panel.get("targets", []):
            expr = tgt.get("expr", "")
            assert any(m in expr for m in emitted), (
                f"Panel '{panel['title']}' references no known metric: "
                f"{expr}")


def test_cron_jobs_runnable():
    """Smoke-check the cron job functions import + name-resolve.
    We don't actually run them (would need Postgres) — but a typo here
    would fail at runtime in the cron container, far away from CI."""
    from app import cron
    assert callable(cron.job_dpo_export)
    assert callable(cron.job_daily_summary)
    s = cron.Schedule()
    s.every(60, lambda: None)
    assert len(s._jobs) == 1


def test_prompt_builder_hash_deterministic():
    from app.services.prompt_builder import build_messages, prompt_hash
    intake = {"demographics": {"age": 30},
              "presenting": "anxiety",
              "reason": "daily impact",
              "past_history": {}, "functioning": {}, "social_support": "few"}
    m1 = build_messages("hi", intake=intake)
    m2 = build_messages("hi", intake=intake)
    assert prompt_hash(m1) == prompt_hash(m2)
    assert len(prompt_hash(m1)) == 64


def test_calibration_default_T():
    # When the calibration JSON is missing it falls back to T=1.0
    # (i.e. raw confidence unchanged).
    import sys, types
    # stub huggingface_hub so import doesn't pull network
    if "huggingface_hub" not in sys.modules:
        m = types.ModuleType("huggingface_hub")
        m.hf_hub_download = lambda **k: (_ for _ in ()).throw(Exception("stub"))
        sys.modules["huggingface_hub"] = m
    from app.services import calibration
    # Force reload of state
    calibration._state["loaded"] = False
    calibration.load_calibration()
    s = calibration.status()
    assert s["loaded"] is True
    assert s["global_temperature"] == 1.0
    assert calibration.calibrate_confidence(0.99) == pytest.approx(0.99)


def test_calibration_with_scalar_T(tmp_path, monkeypatch):
    """When temperature_calibration.json contains T=2.0, confidence shrinks."""
    import json
    import sys, types
    from app.services import calibration

    # Drop a calibration file at the local-mount path the loader checks first
    cal_dir = tmp_path / "models"
    cal_dir.mkdir()
    (cal_dir / "temperature_calibration.json").write_text(
        json.dumps({"temperature": 2.0, "ece_before": 0.73, "ece_after": 0.08}))

    monkeypatch.setattr(
        calibration, "_download_or_local",
        lambda: cal_dir / "temperature_calibration.json")
    calibration._state["loaded"] = False
    calibration.load_calibration()
    s = calibration.status()
    assert s["loaded"]
    assert s["global_temperature"] == 2.0
    # Higher T → flatter (lower) confidence
    raw = 0.99
    cal = calibration.calibrate_confidence(raw)
    assert cal < raw          # softened
    assert cal > 0.5          # but still > 0.5 (still confident)


def test_metrics_render():
    from app.services import metrics
    metrics.inc("test_counter", level="L0")
    metrics.observe("test_latency_seconds", 0.42)
    metrics.gauge("test_gauge", 0.99, channel="x")
    out = metrics.render()
    assert "test_counter" in out
    assert "test_latency_seconds_bucket" in out
    assert "test_gauge" in out


def test_fhir_document_reference_shape():
    """FHIR R4 DocumentReference must have required fields."""
    import uuid
    from datetime import datetime
    from types import SimpleNamespace

    from app.core.crypto import encrypt_phi
    from app.services import fhir_export

    # SimpleNamespace stand-ins (avoid SQLAlchemy ORM machinery)
    sess = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        reviewed_by=uuid.uuid4(),
        final_reply_enc=encrypt_phi("hello"),
    )
    soap = SimpleNamespace(
        id=uuid.uuid4(),
        subjective_enc=encrypt_phi("S text"),
        objective="O text",
        assessment="A text",
        plan="P text",
        created_at=datetime.utcnow(),
    )
    doc = fhir_export.build_document_reference(sess, soap)
    assert doc["resourceType"] == "DocumentReference"
    assert doc["status"] == "current"
    assert doc["docStatus"] == "final"
    assert doc["type"]["coding"][0]["code"] == "11488-4"
    assert doc["subject"]["reference"].startswith("Patient/")
    assert doc["content"][0]["attachment"]["contentType"].startswith("text/plain")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
