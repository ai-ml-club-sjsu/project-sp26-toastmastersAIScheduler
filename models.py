from __future__ import annotations
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

Role = Literal[
    "Toastmaster",
    "Topicsmaster",
    "General Evaluator",
    "Timer",
    "Grammarian",
    "Ah-Counter",
    "Speaker",
    "Evaluator",
]

Availability = Literal["yes", "maybe", "no"]

class Member(BaseModel):
    id: str
    name: str
    experience: int = 3  # 1-5
    availability: Dict[str, Availability] = Field(default_factory=dict)  # date -> yes/maybe/no
    role_blacklist: List[Role] = Field(default_factory=list)
    role_preferences: List[Role] = Field(default_factory=list)

    @field_validator("experience")
    @classmethod
    def clamp_exp(cls, v: int) -> int:
        return max(1, min(5, v))

class MeetingRequest(BaseModel):
    club_name: str
    meeting_dates: List[str]  # YYYY-MM-DD
    members: List[Member]

class Assignment(BaseModel):
    role: Role
    member_id: str
    member_name: str

class MeetingSchedule(BaseModel):
    meeting_date: str
    assignments: List[Assignment]
    notes: List[str] = Field(default_factory=list)

class SchedulerOutput(BaseModel):
    schedules: List[MeetingSchedule]
    warnings: List[str] = Field(default_factory=list)

class CancellationEvent(BaseModel):
    meeting_date: str
    member_id: str
    reason: Optional[str] = None