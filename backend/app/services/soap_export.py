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
import uuid

from app.core.crypto import encrypt_phi, decrypt_str
from app.db import models
from app.services import minio_client


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
           intake: Optional[models.IntakeForm]) -> models.SoapNote:
    """Synthesize, store row, upload artifact to MinIO."""
    soap = synthesize(session, intake)
    body = render_text(soap)
    key = f"{session.user_id}/{session.id}.txt"
    minio_client.put_bytes("cbt-soap-notes", key, body.encode("utf-8"),
                            content_type="text/plain")

    row = models.SoapNote(
        session_id=session.id,
        subjective_enc=encrypt_phi(soap["subjective"]),
        objective=soap["objective"],
        assessment=soap["assessment"],
        plan=soap["plan"],
        exported_to_ehr=False,
        pdf_s3_key=key,
    )
    db.add(row)
    return row
