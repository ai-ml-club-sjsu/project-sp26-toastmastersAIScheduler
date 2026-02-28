import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from models import MeetingRequest, CancellationEvent
from datastore import HistoryStore
from main import load_config, schedule, reassign_on_cancellation
from agents import ReminderAgent

load_dotenv()
app = FastAPI(title="Toastmasters AI Scheduler (OpenAI)")

store = HistoryStore(db_path=os.getenv("TM_DB_PATH", "toastmasters.db"))
config = load_config()
model = os.getenv("TM_MODEL", "gpt-5.2")

# In-memory cache for demo; in production you’d store by schedule_id
LATEST = {}

@app.post("/schedule")
def create_schedule(req: MeetingRequest):
    try:
        out = schedule(req, config, store, model)
        LATEST["schedule"] = out
        LATEST["request"] = req.model_dump()
        return out
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/reminders")
def reminders():
    if "schedule" not in LATEST:
        raise HTTPException(status_code=400, detail="No schedule available. Call /schedule first.")
    agent = ReminderAgent(model)
    return {"reminders": agent.draft_reminders(LATEST["schedule"])}

@app.post("/cancel")
def cancel(cancel_event: CancellationEvent):
    if "schedule" not in LATEST or "request" not in LATEST:
        raise HTTPException(status_code=400, detail="No schedule available. Call /schedule first.")
    try:
        req = MeetingRequest(**LATEST["request"])
        out = reassign_on_cancellation(req, config, store, model, LATEST["schedule"], cancel_event)
        LATEST["schedule"] = out
        return out
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))