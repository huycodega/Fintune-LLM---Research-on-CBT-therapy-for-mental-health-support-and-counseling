"""
Conversation (tasktab) + memory endpoints — user-facing.

A Conversation is a multi-turn thread. Each turn is a Session carrying the
full triage/safety pipeline outcome, linked via Session.conversation_id.
The frontend sidebar lists conversations; opening one renders its turns as
a back-and-forth (user message → assistant reply / system notice).
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core import auth, audit as audit_mod
from app.core.crypto import decrypt_str
from app.db import models
from app.db.session import get_db
from app.schemas.api import ConversationRenameIn
from app.services import user_memory, safety_plan as safety_plan_svc, roadmap as roadmap_svc

router = APIRouter(prefix="/api")


# system notices shown in place of an AI reply for non-answer outcomes
_NOTICE = {
    "crisis": ("This message raised a safety concern. The AI did not reply "
               "automatically; please use the crisis resources provided."),
    "pending_review": ("A clinician is reviewing this message. You'll be "
                       "notified once it's approved."),
    "rejected": "A clinician reviewed this and chose not to send an AI reply.",
}


def _own_convo(db, cid, uid) -> models.Conversation:
    c = db.query(models.Conversation).filter_by(id=cid).first()
    if not c or str(c.user_id) != uid:
        raise HTTPException(404, "Conversation not found")
    return c


@router.get("/conversations")
def list_conversations(user: dict = Depends(auth.current_user),
                       db: Session = Depends(get_db)):
    rows = (db.query(models.Conversation)
              .filter_by(user_id=user["uid"], archived=False)
              .order_by(models.Conversation.updated_at.desc())
              .limit(100).all())
    return {"conversations": [
        {"id": str(c.id), "title": c.title,
         "created_at": c.created_at.isoformat(),
         "updated_at": c.updated_at.isoformat()} for c in rows]}


@router.post("/conversations")
def create_conversation(user: dict = Depends(auth.current_user),
                        db: Session = Depends(get_db)):
    c = models.Conversation(user_id=user["uid"], title="New conversation")
    db.add(c); db.flush()
    return {"id": str(c.id), "title": c.title,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat()}


@router.get("/conversations/{cid}")
def get_conversation(cid: str, user: dict = Depends(auth.current_user),
                     db: Session = Depends(get_db)):
    c = _own_convo(db, cid, user["uid"])
    sessions = (db.query(models.Session)
                  .filter_by(conversation_id=c.id)
                  .order_by(models.Session.created_at.asc()).all())
    messages = []
    for s in sessions:
        messages.append({
            "role": "user",
            "content": decrypt_str(s.user_input_enc),
            "created_at": s.created_at.isoformat(),
            "session_id": str(s.id),
        })
        if s.status in ("answered", "auto_sent") and s.final_reply_enc:
            msg = {
                "role": "assistant",
                "content": decrypt_str(s.final_reply_enc),
                "technique": s.final_technique,
                "created_at": (s.completed_at or s.created_at).isoformat(),
                "session_id": str(s.id),
            }
            # Re-attach structured cards so a reopened thread looks identical
            # to when it was first sent (otherwise only the text survives).
            an = s.analysis or {}
            if an.get("safety_plan"):
                msg["safety_plan"] = safety_plan_svc.load(db, c.user_id)
            if an.get("roadmap_id"):
                msg["roadmap"] = roadmap_svc.load_one(db, c.user_id,
                                                      an["roadmap_id"])
            messages.append(msg)
        else:
            messages.append({
                "role": "system",
                "content": _NOTICE.get(s.status, ""),
                "status": s.status,
                "triage_level": s.triage_level,
                "created_at": s.created_at.isoformat(),
                "session_id": str(s.id),
            })
    return {"id": str(c.id), "title": c.title,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
            # durable per-thread "just listen" state — the UI restores the 🎧
            # toggle from here, so it survives reloads and backend redeploys
            "listen_active": bool(c.listen_mode),
            "messages": messages}


@router.patch("/conversations/{cid}")
def rename_conversation(cid: str, body: ConversationRenameIn,
                        user: dict = Depends(auth.current_user),
                        db: Session = Depends(get_db)):
    c = _own_convo(db, cid, user["uid"])
    c.title = body.title.strip()[:120]
    c.updated_at = datetime.now(timezone.utc)
    db.flush()
    return {"id": str(c.id), "title": c.title}


@router.delete("/conversations/{cid}")
def delete_conversation(cid: str, request: Request,
                        user: dict = Depends(auth.current_user),
                        db: Session = Depends(get_db)):
    c = _own_convo(db, cid, user["uid"])
    c.archived = True
    c.updated_at = datetime.now(timezone.utc)
    db.flush()
    audit_mod.audit(db, action="conversation_archived", actor=user,
                    ip=auth.client_ip(request),
                    resource_type="conversation", resource_id=c.id)
    return {"ok": True}


@router.get("/memory")
def my_memory(user: dict = Depends(auth.current_user),
              db: Session = Depends(get_db)):
    """The user's own durable memory (transparency — they can see what the
    assistant remembers about them)."""
    return user_memory.load_for_prompt(db, user["uid"])
