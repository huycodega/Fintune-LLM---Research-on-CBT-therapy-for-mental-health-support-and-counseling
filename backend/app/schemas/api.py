"""Pydantic schemas — request / response bodies for the API."""
from typing import Optional, List
from datetime import date as _date
from pydantic import BaseModel, Field


# ---- Gmail self-registration + OTP ----
# Email kept as plain str (validated in the endpoint against the allowed
# domain list) so we don't hard-depend on the optional email-validator pkg.
class RegisterIn(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=6, max_length=128)


class VerifyOtpIn(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    otp: str = Field(min_length=4, max_length=8)


class ResendOtpIn(BaseModel):
    email: str = Field(min_length=5, max_length=254)


class LoginIn(BaseModel):
    # `username` accepts either the chosen handle or the Gmail address.
    username: str
    password: str
    expected_role: Optional[str] = None       # "user" or "admin"


class GoogleAuthIn(BaseModel):
    # The Google Identity Services ID token (JWT) issued in the browser.
    credential: str = Field(min_length=20)
    expected_role: Optional[str] = None       # "user" or "admin"
    intent: str = "login"                     # "login" (no auto-create) | "register"


class LoginOut(BaseModel):
    token: str
    username: str
    role: str
    consent_required: bool = False
    intake_required: bool = False


class ConsentIn(BaseModel):
    accepted: bool


class IntakeIn(BaseModel):
    raw_text: str = Field(min_length=20)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[str] = None      # None → start a new thread
    n_responses: Optional[int] = None
    temperature: Optional[float] = None
    # UI "just listen" toggle: True → hold advice this thread, False → resume
    # normal support, None → leave as-is (regex/stored preference still applies).
    listen_only: Optional[bool] = None


class ConversationRenameIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class ReviewIn(BaseModel):
    decision: str                              # approve / edit / reject
    chosen_idx: int = 0
    edited_response: str = ""
    edited_technique: str = ""
    rating: Optional[int] = None                # 1-5 for feedback


# ---- admin user management ----
class UserStatusIn(BaseModel):
    status: str = Field(pattern="^(active|suspended)$")
    reason: str = ""                            # audit note


class UserRoleIn(BaseModel):
    role: str = Field(pattern="^(user|clinician|admin)$")


# ---- learning content: lessons ----
class LessonIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    category: str = ""
    level: str = Field(default="basic",
                       pattern="^(basic|intermediate|advanced)$")
    duration: str = ""
    content: str = ""
    objectives: List[str] = []
    tags: List[str] = []
    status: str = Field(default="draft", pattern="^(draft|published)$")
    author: str = ""


class LessonUpdateIn(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    level: Optional[str] = Field(default=None,
                                 pattern="^(basic|intermediate|advanced)$")
    duration: Optional[str] = None
    content: Optional[str] = None
    objectives: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = Field(default=None,
                                  pattern="^(draft|published)$")
    author: Optional[str] = None


# ---- learning content: support resources ----
class ResourceIn(BaseModel):
    type: str = Field(default="Article",
                      pattern="^(Audio|Article|Video|CBT Tool)$")
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    category: str = ""
    duration: str = ""
    url: str = ""
    content: str = ""
    status: str = Field(default="published",
                        pattern="^(published|urgent|update|draft)$")
    urgent: bool = False
    owner: str = ""
    tags: List[str] = []


class ResourceUpdateIn(BaseModel):
    type: Optional[str] = Field(default=None,
                                pattern="^(Audio|Article|Video|CBT Tool)$")
    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    duration: Optional[str] = None
    url: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = Field(default=None,
                                  pattern="^(published|urgent|update|draft)$")
    urgent: Optional[bool] = None
    owner: Optional[str] = None
    tags: Optional[List[str]] = None


class LessonProgressIn(BaseModel):
    progress_pct: int = Field(ge=0, le=100)
    completed_steps: List[int] = []


# ---- Expert consultation booking ----
class PsychologistIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = ""
    experience: str = ""
    specialty: str = ""
    bio: str = ""
    slots: List[str] = []        # ["09:00","10:00",...]
    active: bool = True


class PsychologistUpdateIn(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    phone: Optional[str] = None
    experience: Optional[str] = None
    specialty: Optional[str] = None
    bio: Optional[str] = None
    slots: Optional[List[str]] = None
    active: Optional[bool] = None


class AppointmentIn(BaseModel):
    psychologist_id: str
    date: _date
    slot: str = Field(min_length=1, max_length=10)
    note: str = ""


class AppointmentUpdateIn(BaseModel):
    date: Optional[_date] = None
    slot: Optional[str] = Field(default=None, max_length=10)


class AppointmentStatusIn(BaseModel):
    status: str = Field(pattern="^(pending|accepted|cancelled|declined)$")
