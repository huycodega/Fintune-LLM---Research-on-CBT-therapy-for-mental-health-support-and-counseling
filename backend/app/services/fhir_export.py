"""
FHIR R4 export for SOAP notes.

Wraps the SOAP note as a `DocumentReference` resource (the standard
HL7 FHIR container for clinical narratives). Sent to an EHR receiver
URL when configured; otherwise written as JSON to MinIO so an external
batch job can sync.

This is the minimal viable shape for HL7 FHIR R4 — passes basic
validators. Production deployments should add: identifier UUID, signer
practitioner reference, masterIdentifier per organization policy.
"""
import base64
import json
import logging
import os
import urllib.request
from datetime import datetime
from typing import Dict, Optional

from app.core.crypto import decrypt_str
from app.db import models
from app.services import minio_client


log = logging.getLogger(__name__)


def build_document_reference(session: models.Session,
                              soap: models.SoapNote) -> Dict:
    """
    Build a FHIR R4 DocumentReference for the SOAP note.
    Note narrative is base64-encoded as required by FHIR `attachment.data`.
    """
    final_reply = (decrypt_str(session.final_reply_enc)
                    if session.final_reply_enc else "")
    soap_text = (
        "S — SUBJECTIVE\n" + decrypt_str(soap.subjective_enc) + "\n\n"
        "O — OBJECTIVE\n" + (soap.objective or "") + "\n\n"
        "A — ASSESSMENT\n" + (soap.assessment or "") + "\n\n"
        "P — PLAN\n" + (soap.plan or "")
    )

    return {
        "resourceType": "DocumentReference",
        "id": str(soap.id),
        "status": "current",
        "docStatus": "final",
        "type": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "11488-4",
                "display": "Consult note",
            }],
            "text": "CBT session SOAP note",
        },
        "category": [{
            "coding": [{
                "system": "http://hl7.org/fhir/us/core/ValueSet/"
                          "us-core-documentreference-category",
                "code": "clinical-note",
                "display": "Clinical Note",
            }],
        }],
        "subject": {"reference": f"Patient/{session.user_id}"},
        "date": (soap.created_at.isoformat()
                 if soap.created_at else datetime.utcnow().isoformat()),
        "author": [{"reference": f"Practitioner/{session.reviewed_by}"}
                    if session.reviewed_by else
                    {"reference": "Device/cbt-assistant-v4"}],
        "content": [{
            "attachment": {
                "contentType": "text/plain; charset=utf-8",
                "data": base64.b64encode(soap_text.encode("utf-8")).decode(),
                "title": f"CBT Session {session.id} SOAP Note",
                "creation": (soap.created_at.isoformat()
                             if soap.created_at else None),
            },
        }],
        "context": {
            "encounter": [{"reference": f"Encounter/{session.id}"}],
        },
    }


def push_to_ehr(doc_ref: Dict) -> Optional[str]:
    """POST to EHR_FHIR_ENDPOINT if set; else None."""
    endpoint = os.environ.get("EHR_FHIR_ENDPOINT")
    if not endpoint:
        return None
    try:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(doc_ref).encode("utf-8"),
            headers={"Content-Type": "application/fhir+json"},
            method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.headers.get("Location") or "ok"
    except Exception as e:
        log.warning("EHR push failed: %s", e)
        return None


def export(session: models.Session, soap: models.SoapNote) -> Dict:
    """Build + persist FHIR JSON to MinIO, attempt EHR push."""
    doc = build_document_reference(session, soap)
    key = f"fhir/{session.user_id}/{session.id}.json"
    minio_client.put_bytes("cbt-soap-notes", key,
                            json.dumps(doc, indent=2).encode("utf-8"),
                            content_type="application/fhir+json")
    ehr_loc = push_to_ehr(doc)
    return {
        "fhir_s3_key": key,
        "ehr_location": ehr_loc,
        "synced": ehr_loc is not None,
    }
