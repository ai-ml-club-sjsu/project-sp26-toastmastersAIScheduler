from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple

from models import MeetingRequest, SchedulerOutput, Role

@dataclass
class ValidationIssue:
    meeting_date: str
    message: str

def _dt(d: str) -> datetime:
    return datetime.strptime(d, "%Y-%m-%d")

def validate(
    req: MeetingRequest,
    out: SchedulerOutput,
    required_roles: List[Role],
    speakers_n: int,
    evaluators_n: int,
    avoid_same_role_within_days: int,
    max_assignments_per_person: int,
    history_rows: List[Tuple[str, str, str, str]],
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    members_by_id = {m.id: m for m in req.members}

    last_role_date: Dict[Tuple[str, str], datetime] = {}
    for meeting_date, member_id, _, role in history_rows:
        key = (member_id, role)
        dt = _dt(meeting_date)
        if key not in last_role_date or dt > last_role_date[key]:
            last_role_date[key] = dt

    for sched in out.schedules:
        assigned_roles = [a.role for a in sched.assignments]

        # completeness
        for r in required_roles:
            if r not in assigned_roles:
                issues.append(ValidationIssue(sched.meeting_date, f"Missing required role: {r}"))

        if assigned_roles.count("Speaker") != speakers_n:
            issues.append(ValidationIssue(sched.meeting_date, f"Expected {speakers_n} Speaker(s)"))

        if assigned_roles.count("Evaluator") != evaluators_n:
            issues.append(ValidationIssue(sched.meeting_date, f"Expected {evaluators_n} Evaluator(s)"))

        # caps + constraints
        counts: Dict[str, int] = {}
        speakers = {a.member_id for a in sched.assignments if a.role == "Speaker"}
        evaluators = {a.member_id for a in sched.assignments if a.role == "Evaluator"}
        overlap = speakers.intersection(evaluators)
        if overlap:
            issues.append(ValidationIssue(sched.meeting_date, "Member assigned both Speaker and Evaluator"))

        dt = _dt(sched.meeting_date)
        for a in sched.assignments:
            counts[a.member_id] = counts.get(a.member_id, 0) + 1

            m = members_by_id.get(a.member_id)
            if not m:
                issues.append(ValidationIssue(sched.meeting_date, f"Unknown member_id: {a.member_id}"))
                continue

            # availability
            status = m.availability.get(sched.meeting_date, "maybe")
            if status == "no":
                issues.append(ValidationIssue(sched.meeting_date, f"{m.name} assigned but unavailable"))

            # blacklist
            if a.role in m.role_blacklist:
                issues.append(ValidationIssue(sched.meeting_date, f"{m.name} assigned blacklisted role {a.role}"))

            # repeated role window
            key = (a.member_id, a.role)
            if key in last_role_date:
                days = (dt - last_role_date[key]).days
                if days < avoid_same_role_within_days:
                    issues.append(ValidationIssue(sched.meeting_date, f"{m.name} repeated {a.role} within {days}d"))

        for member_id, c in counts.items():
            if c > max_assignments_per_person:
                issues.append(ValidationIssue(sched.meeting_date, f"{members_by_id[member_id].name} has {c} roles"))

    return issues