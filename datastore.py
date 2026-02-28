from __future__ import annotations
import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from models import Assignment

SCHEMA = """
CREATE TABLE IF NOT EXISTS role_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  meeting_date TEXT NOT NULL,
  member_id TEXT NOT NULL,
  member_name TEXT NOT NULL,
  role TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schedules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  club_name TEXT NOT NULL,
  schedule_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS confirmations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  meeting_date TEXT NOT NULL,
  member_id TEXT NOT NULL,
  role TEXT NOT NULL,
  status TEXT NOT NULL, -- pending/confirmed/declined
  updated_at TEXT NOT NULL
);
"""

class HistoryStore:
    def __init__(self, db_path: str = "toastmasters.db"):
        self.db_path = db_path
        self._init()

    def _init(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)

    def fetch_history_since(self, since_date: str) -> List[Tuple[str, str, str, str]]:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(
                "SELECT meeting_date, member_id, member_name, role FROM role_history WHERE meeting_date >= ?",
                (since_date,),
            ).fetchall()

    def write_history(self, meeting_date: str, assignments: List[Assignment]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            for a in assignments:
                conn.execute(
                    "INSERT INTO role_history(meeting_date, member_id, member_name, role) VALUES (?,?,?,?)",
                    (meeting_date, a.member_id, a.member_name, a.role),
                )

    def save_schedule(self, club_name: str, schedule_payload: dict) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO schedules(created_at, club_name, schedule_json) VALUES (?,?,?)",
                (datetime.utcnow().isoformat(), club_name, json.dumps(schedule_payload)),
            )

    def set_confirmation(self, meeting_date: str, member_id: str, role: str, status: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO confirmations(meeting_date, member_id, role, status, updated_at)
                VALUES (?,?,?,?,?)
                """,
                (meeting_date, member_id, role, status, datetime.utcnow().isoformat()),
            )

# -------- Optional: Google Sheets loader (members + availability) --------
# This is intentionally simple for beginner-friendly workflows. :contentReference[oaicite:8]{index=8}
def load_members_from_google_sheet(
    spreadsheet_id: str,
    worksheet_name: str,
    service_account_json_path: str,
):
    """
    Expected columns:
      id, name, experience, role_blacklist (comma), role_preferences (comma),
      availability_YYYY-MM-DD columns like availability_2026-03-03 = yes/maybe/no
    """
    import gspread
    from google.oauth2.service_account import Credentials
    from models import Member

    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_file(service_account_json_path, scopes=scopes)
    gc = gspread.authorize(creds)

    sh = gc.open_by_key(spreadsheet_id)
    ws = sh.worksheet(worksheet_name)
    rows = ws.get_all_records()

    members = []
    for r in rows:
        availability: Dict[str, str] = {}
        for k, v in r.items():
            if k.startswith("availability_") and v:
                date = k.replace("availability_", "").strip()
                availability[date] = str(v).strip().lower()

        members.append(
            Member(
                id=str(r["id"]).strip(),
                name=str(r["name"]).strip(),
                experience=int(r.get("experience", 3) or 3),
                role_blacklist=[x.strip() for x in str(r.get("role_blacklist", "")).split(",") if x.strip()],
                role_preferences=[x.strip() for x in str(r.get("role_preferences", "")).split(",") if x.strip()],
                availability=availability,
            )
        )

    return members