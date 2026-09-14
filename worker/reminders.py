"""Synthetic appointment reminder worker.

By default this uses the local fixture list. Set API_URL and demo credentials to
read upcoming appointments from the running API. It never sends real messages.
"""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from datetime import datetime, timedelta, timezone

DEMO_APPOINTMENTS = [
    {"id": "apt-301", "patient": "Jordan R.", "provider": "Dr. Maya Chen", "starts_at": datetime.now(timezone.utc) + timedelta(hours=2)},
    {"id": "apt-302", "patient": "Taylor K.", "provider": "Dr. Elias Brooks", "starts_at": datetime.now(timezone.utc) + timedelta(hours=5)},
]

def build_reminder_report(appointments):
    return [{"appointment_id": item["id"], "channel": "dry-run", "message": f"Reminder prepared for synthetic patient {item['patient']} with {item['provider']}."} for item in appointments]

def fetch_api_appointments():
    api_url = os.getenv("API_URL")
    if not api_url:
        return DEMO_APPOINTMENTS
    login = json.dumps({"email": os.getenv("DEMO_EMAIL", "demo@northstar.test"), "password": os.getenv("DEMO_PASSWORD", "demo-password")}).encode()
    login_request = Request(f"{api_url}/auth/login", data=login, headers={"Content-Type": "application/json"})
    with urlopen(login_request, timeout=10) as response:
        token = json.load(response)["token"]
    appointments_request = Request(f"{api_url}/appointments?status=scheduled", headers={"Authorization": f"Bearer {token}"})
    with urlopen(appointments_request, timeout=10) as response:
        records = json.load(response)["data"]
    now = datetime.now(timezone.utc)
    upcoming = []
    for record in records:
        starts_at = datetime.fromisoformat(record["startsAt"].replace("Z", "+00:00"))
        if now <= starts_at <= now + timedelta(hours=24):
            upcoming.append({"id": record["id"], "patient": record["patientId"], "provider": record["providerId"], "starts_at": starts_at})
    return upcoming

if __name__ == "__main__":
    print(f"Reminder worker run at {datetime.now(timezone.utc).isoformat()}")
    try:
        appointments = fetch_api_appointments()
    except (HTTPError, URLError, TimeoutError) as error:
        raise SystemExit(f"Reminder worker could not read API: {error}")
    for reminder in build_reminder_report(appointments):
        print(f"[DRY RUN] {reminder['appointment_id']}: {reminder['message']}")
