from __future__ import annotations
import json
from datetime import datetime, timedelta
from typing import List, Tuple

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from models import (
    CancellationEvent,
    MeetingRequest,
    SchedulerOutput,
)
from rules import ValidationIssue

SCHEDULER_SYSTEM = """You are an expert Toastmasters VP Education scheduling agent.

Hard constraints:
- Prefer availability yes, then maybe. Avoid no.
- One assignment per person per meeting.
- Fill required roles and exact N speakers/evaluators.
- No one can be both Speaker and Evaluator.

Fairness:
- Use past participation history to rotate roles.
- Avoid repeating the same role for the same person within a configured window.

Output ONLY valid JSON that matches the schema.
"""

REMINDER_SYSTEM = """You write short, friendly Toastmasters role reminder messages.
You must include: meeting date, assigned role, and a simple confirmation request (YES/NO).
Keep it under 80 words.
"""

REASSIGN_SYSTEM = """You are a Toastmasters reassignment agent.
Given an existing schedule and a cancellation, produce an updated schedule that:
- replaces only what is necessary,
- respects all hard constraints,
- maintains fairness as much as possible.
Return ONLY valid JSON matching schema.
"""

def _build_llm(model: str) -> ChatOpenAI:
    return ChatOpenAI(model=model, temperature=0.2)

class SchedulingAgent:
    def __init__(self, model: str):
        self.llm = _build_llm(model).with_structured_output(SchedulerOutput)

    def propose(self, payload: dict) -> SchedulerOutput:
        return self.llm.invoke(
            [SystemMessage(content=SCHEDULER_SYSTEM), HumanMessage(content=json.dumps(payload))]
        )

class RepairAgent:
    def __init__(self, model: str):
        self.llm = _build_llm(model).with_structured_output(SchedulerOutput)

    def repair(self, payload: dict) -> SchedulerOutput:
        return self.llm.invoke(
            [SystemMessage(content=SCHEDULER_SYSTEM), HumanMessage(content=json.dumps(payload))]
        )

class ReminderAgent:
    def __init__(self, model: str):
        self.llm = _build_llm(model)

    def draft_reminders(self, schedule_json: dict) -> List[dict]:
        """
        Returns: [{meeting_date, member_id, role, message}]
        """
        reminders = []
        for sched in schedule_json["schedules"]:
            for a in sched["assignments"]:
                prompt = {
                    "meeting_date": sched["meeting_date"],
                    "member_id": a["member_id"],
                    "member_name": a["member_name"],
                    "role": a["role"],
                }
                msg = self.llm.invoke(
                    [SystemMessage(content=REMINDER_SYSTEM), HumanMessage(content=json.dumps(prompt))]
                ).content
                reminders.append(
                    {
                        "meeting_date": sched["meeting_date"],
                        "member_id": a["member_id"],
                        "role": a["role"],
                        "message": msg,
                    }
                )
        return reminders

class ReassignmentAgent:
    def __init__(self, model: str):
        self.llm = _build_llm(model).with_structured_output(SchedulerOutput)

    def reassign(self, payload: dict) -> SchedulerOutput:
        return self.llm.invoke(
            [SystemMessage(content=REASSIGN_SYSTEM), HumanMessage(content=json.dumps(payload))]
        )


    