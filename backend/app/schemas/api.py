"""Pydantic schemas — request / response bodies for the API."""
from typing import Optional, List
from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str
    password: str
    expected_role: Optional[str] = None       # "user" or "admin"


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
    n_responses: Optional[int] = None
    temperature: Optional[float] = None


class ReviewIn(BaseModel):
    decision: str                              # approve / edit / reject
    chosen_idx: int = 0
    edited_response: str = ""
    edited_technique: str = ""
    rating: Optional[int] = None                # 1-5 for feedback
