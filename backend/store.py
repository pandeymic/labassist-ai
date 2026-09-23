"""Small persistent data layer for the LabAssist pilot.

SQLite is deliberate here: a single pilot lab can run without operating a
database server. The repository API keeps the booking workflow independent of
the storage engine so PostgreSQL can replace it when LabAssist becomes
multi-tenant.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class LabStore:
    def __init__(self, database_path: Optional[str] = None) -> None:
        default_path = Path(__file__).resolve().parent.parent / "data" / "labassist.db"
        self.database_path = database_path or os.getenv("LABASSIST_DB_PATH", str(default_path))
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._lock, self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS lab_profile (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    name TEXT NOT NULL,
                    city TEXT NOT NULL,
                    support_phone TEXT NOT NULL,
                    supported_languages TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS appointment_slots (
                    id TEXT PRIMARY KEY,
                    appointment_date TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    capacity INTEGER NOT NULL CHECK (capacity > 0),
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    UNIQUE(appointment_date, start_time, end_time)
                );

                CREATE TABLE IF NOT EXISTS appointments (
                    id TEXT PRIMARY KEY,
                    patient_name TEXT NOT NULL,
                    phone_number TEXT NOT NULL,
                    test_name TEXT NOT NULL,
                    collection_type TEXT NOT NULL,
                    preferred_date TEXT NOT NULL,
                    preferred_time TEXT NOT NULL,
                    collection_address TEXT,
                    pincode TEXT,
                    status TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'chat',
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_appointments_slot
                    ON appointments(preferred_date, preferred_time, status);

                CREATE TABLE IF NOT EXISTS booking_sessions (
                    session_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO lab_profile
                    (id, name, city, support_phone, supported_languages, updated_at)
                VALUES (1, ?, ?, ?, ?, ?)
                """,
                ("LabAssist Demo Lab", "New Delhi", "+91-0000000000", json.dumps(["English", "Hindi"]), _utcnow()),
            )

    def get_profile(self) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM lab_profile WHERE id = 1").fetchone()
        assert row is not None
        profile = dict(row)
        profile["supported_languages"] = json.loads(profile["supported_languages"])
        return profile

    def update_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = self.get_profile()
        merged = {**current, **{key: value for key, value in payload.items() if value is not None}}
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE lab_profile
                SET name = ?, city = ?, support_phone = ?, supported_languages = ?, updated_at = ?
                WHERE id = 1
                """,
                (
                    merged["name"],
                    merged["city"],
                    merged["support_phone"],
                    json.dumps(merged["supported_languages"]),
                    _utcnow(),
                ),
            )
        return self.get_profile()

    def create_slot(self, appointment_date: str, start_time: str, end_time: str, capacity: int) -> dict[str, Any]:
        slot = {
            "id": f"slot_{uuid.uuid4().hex[:12]}",
            "appointment_date": appointment_date,
            "start_time": start_time,
            "end_time": end_time,
            "capacity": capacity,
            "is_active": True,
            "created_at": _utcnow(),
        }
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO appointment_slots
                    (id, appointment_date, start_time, end_time, capacity, is_active, created_at)
                VALUES (:id, :appointment_date, :start_time, :end_time, :capacity, :is_active, :created_at)
                """,
                slot,
            )
        return slot

    def list_available_slots(self, appointment_date: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT s.id, s.appointment_date, s.start_time, s.end_time, s.capacity,
                       s.capacity - COUNT(a.id) AS available_capacity
                FROM appointment_slots s
                LEFT JOIN appointments a
                    ON a.preferred_date = s.appointment_date
                   AND a.preferred_time = s.start_time
                   AND a.status IN ('confirmed', 'pending_staff_review')
                WHERE s.appointment_date = ? AND s.is_active = 1
                GROUP BY s.id
                HAVING available_capacity > 0
                ORDER BY s.start_time
                """,
                (appointment_date,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_available_dates(self, limit: int = 10) -> list[str]:
        """Return dates with at least one remaining active collection slot."""
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT s.appointment_date
                FROM appointment_slots s
                LEFT JOIN appointments a
                    ON a.preferred_date = s.appointment_date
                   AND a.preferred_time = s.start_time
                   AND a.status IN ('confirmed', 'pending_staff_review')
                WHERE s.is_active = 1
                GROUP BY s.id
                HAVING s.capacity - COUNT(a.id) > 0
                ORDER BY s.appointment_date, s.start_time
                """,
            ).fetchall()
        return list(dict.fromkeys(row["appointment_date"] for row in rows))[:limit]

    def save_session(self, session_id: str, state: dict[str, Any]) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO booking_sessions(session_id, state_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at
                """,
                (session_id, json.dumps(state), _utcnow()),
            )

    def load_session(self, session_id: str) -> Optional[dict[str, Any]]:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT state_json FROM booking_sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return json.loads(row["state_json"]) if row else None

    def reserve_appointment(self, booking: dict[str, Any]) -> tuple[Optional[dict[str, Any]], Optional[str]]:
        """Atomically check capacity and create a confirmed booking."""
        with self._lock, self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            slot = connection.execute(
                """
                SELECT * FROM appointment_slots
                WHERE appointment_date = ? AND start_time = ? AND is_active = 1
                """,
                (booking["preferred_date"], booking["preferred_time"]),
            ).fetchone()
            if not slot:
                return None, "No active slot exists for that date and time."

            active_bookings = connection.execute(
                """
                SELECT COUNT(*) AS total FROM appointments
                WHERE preferred_date = ? AND preferred_time = ?
                  AND status IN ('confirmed', 'pending_staff_review')
                """,
                (booking["preferred_date"], booking["preferred_time"]),
            ).fetchone()["total"]
            if active_bookings >= slot["capacity"]:
                return None, "That slot has just filled. Please choose another available time."

            now = _utcnow()
            appointment = {
                "id": f"LAB-{uuid.uuid4().hex[:8].upper()}",
                **booking,
                "status": "confirmed",
                "source": "chat",
                "notes": None,
                "created_at": now,
                "updated_at": now,
            }
            connection.execute(
                """
                INSERT INTO appointments(
                    id, patient_name, phone_number, test_name, collection_type,
                    preferred_date, preferred_time, collection_address, pincode,
                    status, source, notes, created_at, updated_at
                ) VALUES (
                    :id, :patient_name, :phone_number, :test_name, :collection_type,
                    :preferred_date, :preferred_time, :collection_address, :pincode,
                    :status, :source, :notes, :created_at, :updated_at
                )
                """,
                appointment,
            )
        return appointment, None

    def list_appointments(self, status: Optional[str] = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM appointments"
        values: tuple[Any, ...] = ()
        if status:
            query += " WHERE status = ?"
            values = (status,)
        query += " ORDER BY preferred_date, preferred_time, created_at DESC"
        with self.connection() as connection:
            rows = connection.execute(query, values).fetchall()
        return [dict(row) for row in rows]

    def dashboard_summary(self) -> dict[str, int]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) AS total FROM appointments GROUP BY status"
            ).fetchall()
        counts = {row["status"]: row["total"] for row in rows}
        return {
            "confirmed": counts.get("confirmed", 0),
            "cancelled": counts.get("cancelled", 0),
            "total": sum(counts.values()),
        }

    def cancel_appointment(self, appointment_id: str) -> Optional[dict[str, Any]]:
        with self.connection() as connection:
            connection.execute(
                "UPDATE appointments SET status = 'cancelled', updated_at = ? WHERE id = ?",
                (_utcnow(), appointment_id),
            )
            row = connection.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
        return dict(row) if row else None


_store: Optional[LabStore] = None


def get_store() -> LabStore:
    global _store
    if _store is None:
        _store = LabStore()
    return _store
