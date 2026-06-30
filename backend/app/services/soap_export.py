"""
SOAP-note auto-export (pipeline v4 layer "SOAP note auto-export").

After a clinician approves/edits a response, we synthesize a SOAP
note (Subjective / Objective / Assessment / Plan) from the session
data and persist it:
  - row in `soap_notes` (Postgres)
  - text file in MinIO bucket `cbt-soap-notes/{user_id}/{session_id}.txt`

We write a text file (not real PDF) to keep dependencies minimal —
swap in reportlab here if you want a true PDF. The schema and S3 key
are already PDF-ready.
"""
from datetime import datetime
from typing import Optional
import logging
import uuid

from app.core.crypto import encrypt_phi, decrypt_str
from app.db import models
from app.services import minio_client

log = logging.getLogger("cbt")


def synthesize(session: models.Session,
               intake: Optional[models.IntakeForm]) -> dict:
    """Build SOAP fields from session + intake. Pure function — no I/O."""
    user_text = decrypt_str(session.user_input_enc)
    reply_text = decrypt_str(session.final_reply_enc) if session.final_reply_enc else ""
    intake_presenting = (decrypt_str(intake.presenting)
                          if (intake and intake.presenting) else "")
    triage = session.triage_level or "L?"
    sev = session.severity or "?"
    conf = session.confidence or 0.0
    tech = session.final_technique or "—"
    analysis = session.analysis or {}

    subjective = (
        f"Client stated message:\n{user_text}\n\n"
        + (f"Intake presenting problem:\n{intake_presenting}\n"
           if intake_presenting else "")
    )

    objective = (
        f"Triage: {triage} (severity={sev}, confidence={conf:.2f})\n"
        f"Detected emotion: {analysis.get('emotion','—')}\n"
        f"Cognitive distortions: {analysis.get('cognitive_distortions','—')}\n"
        f"Session created: {session.created_at.isoformat()}"
    )

    assessment = (
        f"Working assessment based on safety-gate + analysis layers. "
        f"CBT technique selected by clinician: {tech}. "
        f"Reviewed by clinician at: "
        f"{session.reviewed_at.isoformat() if session.reviewed_at else '—'}"
    )

    plan_text = (
        f"Delivered response to client:\n{reply_text}\n\n"
        f"Follow-up: monitor adherence to plan; reassess at next session."
    )

    return {
        "subjective": subjective,
        "objective": objective,
        "assessment": assessment,
        "plan": plan_text,
    }


def render_text(soap: dict) -> str:
    return (
        "SOAP NOTE\n"
        f"Generated: {datetime.utcnow().isoformat()}Z\n"
        "=" * 60 + "\n\n"
        "S — SUBJECTIVE\n" + soap["subjective"] + "\n\n"
        "O — OBJECTIVE\n" + soap["objective"] + "\n\n"
        "A — ASSESSMENT\n" + soap["assessment"] + "\n\n"
        "P — PLAN\n" + soap["plan"] + "\n"
    )


def export(db, session: models.Session,
           intake: Optional[models.IntakeForm],
           soap: Optional[dict] = None) -> models.SoapNote:
    """Store/refresh the SOAP note for a session and archive it to MinIO.

    `soap` lets the caller pass a model-generated SOAP (clinician_copilot.
    draft_soap); when None we synthesize the template version. Upserts by
    session so re-approving or upgrading template→AI doesn't duplicate rows.
    """
    if soap is None:
        soap = synthesize(session, intake)
    body = render_text(soap)
    key = f"{session.user_id}/{session.id}.txt"
    # Archiving the SOAP artifact to object storage is best-effort: when MinIO
    # isn't deployed (e.g. on the managed host) we still keep the full SOAP in
    # the DB so the review/approve never fails over an optional archive step.
    uploaded = False
    try:
        minio_client.put_bytes("cbt-soap-notes", key, body.encode("utf-8"),
                               content_type="text/plain")
        uploaded = True
    except Exception as e:
        log.warning("SOAP artifact upload skipped (object store unavailable): %s", e)

    row = (db.query(models.SoapNote)
           .filter_by(session_id=session.id).first())
    if row is None:
        row = models.SoapNote(session_id=session.id, exported_to_ehr=False)
        db.add(row)
    row.subjective_enc = encrypt_phi(soap["subjective"])
    row.objective = soap["objective"]
    row.assessment = soap["assessment"]
    row.plan = soap["plan"]
    if uploaded:
        row.pdf_s3_key = key
    db.flush()
    return row
