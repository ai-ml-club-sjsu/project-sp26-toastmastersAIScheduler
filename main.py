from __future__ import annotations
import json
import os

from dotenv import load_dotenv

from models import MeetingRequest, CancellationEvent
from datastore import HistoryStore
from agents import SchedulingAgent, RepairAgent, ReminderAgent, ReassignmentAgent
from rules import validate

def load_config(path="config.json") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def build_payload(req: MeetingRequest, config: dict, history_rows: list) -> dict:
    return {
        "request": req.model_dump(),
        "config": config,
        "recent_role_history": [
            {"meeting_date": d, "member_id": mid, "member_name": name, "role": role}
            for (d, mid, name, role) in history_rows
        ],
        "today": os.getenv("TODAY_OVERRIDE") or None,
    }

def schedule(req: MeetingRequest, config: dict, store: HistoryStore, model: str) -> dict:
    # lookback for fairness
    meeting_dates = sorted(req.meeting_dates)
    since_date = meeting_dates[0]  # keep it simple; you can subtract config lookback if desired

    history_rows = store.fetch_history_since(since_date=since_date)

    scheduler = SchedulingAgent(model)
    repair = RepairAgent(model)

    out = scheduler.propose(build_payload(req, config, history_rows))

    issues = validate(
        req=req,
        out=out,
        required_roles=config["required_roles"],
        speakers_n=config["speakers"],
        evaluators_n=config["evaluators"],
        avoid_same_role_within_days=config["avoid_same_role_within_days"],
        max_assignments_per_person=config["max_assignments_per_person_per_meeting"],
        history_rows=history_rows,
    )

    if issues:
        repair_payload = {
            **build_payload(req, config, history_rows),
            "proposed_schedule": out.model_dump(),
            "validation_issues": [i.__dict__ for i in issues],
            "instruction": "Fix ALL validation issues while keeping fairness.",
        }
        out = repair.repair(repair_payload)

    store.save_schedule(req.club_name, out.model_dump())
    return out.model_dump()

def reassign_on_cancellation(
    req: MeetingRequest,
    config: dict,
    store: HistoryStore,
    model: str,
    current_schedule: dict,
    cancel: CancellationEvent,
) -> dict:
    reassignment = ReassignmentAgent(model)

    payload = {
        "request": req.model_dump(),
        "config": config,
        "current_schedule": current_schedule,
        "cancellation": cancel.model_dump(),
    }

    out = reassignment.reassign(payload)
    store.save_schedule(req.club_name, out.model_dump())
    return out.model_dump()

def main():
    load_dotenv()
    model = os.getenv("TM_MODEL", "gpt-5.2")
    store = HistoryStore(db_path=os.getenv("TM_DB_PATH", "toastmasters.db"))
    config = load_config()

    # Example stub request: replace by Google Sheets loader or your own UI/API input
    from models import Member
    req = MeetingRequest(
        club_name="Toastmasters Club",
        meeting_dates=["2026-03-03"],
        members=[
            Member(id="m1", name="Ava", experience=4, availability={"2026-03-03": "yes"}, role_preferences=["Toastmaster"]),
            Member(id="m2", name="Ben", experience=3, availability={"2026-03-03": "yes"}, role_preferences=["Speaker"]),
            Member(id="m3", name="Chris", experience=2, availability={"2026-03-03": "maybe"}, role_preferences=["Topicsmaster"]),
            Member(id="m4", name="Dee", experience=5, availability={"2026-03-03": "yes"}, role_preferences=["General Evaluator"]),
            Member(id="m5", name="Evan", experience=3, availability={"2026-03-03": "yes"}, role_preferences=["Evaluator"]),
            Member(id="m6", name="Fran", experience=2, availability={"2026-03-03": "yes"}, role_preferences=["Timer"]),
            Member(id="m7", name="Gus", experience=3, availability={"2026-03-03": "yes"}, role_preferences=["Grammarian"]),
            Member(id="m8", name="Hana", experience=3, availability={"2026-03-03": "maybe"}, role_preferences=["Ah-Counter"]),
        ],
    )

    schedule_json = schedule(req, config, store, model)

    # Draft reminders (intelligent reminders & confirmations) :contentReference[oaicite:13]{index=13}
    reminders = ReminderAgent(model).draft_reminders(schedule_json)
    print(json.dumps({"schedule": schedule_json, "reminders": reminders}, indent=2))

if __name__ == "__main__":
    main()