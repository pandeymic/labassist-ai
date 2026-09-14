# LabAssist platform integration

LabAssist now contains two cooperating application surfaces:

```text
Patient experience: FastAPI + synthetic booking assistant (port 8000)
Operations experience: Next.js + NestJS/Express-compatible API (ports 3000/4000)
Shared infrastructure: PostgreSQL, audit events, and a Python reminder worker
```

The patient workflow remains deterministic: approved catalog facts and booking
confirmation are handled by the existing Python workflow. The operations portal
provides provider, patient, appointment, claims, and audit management. The
operations API uses PostgreSQL when `DATABASE_URL` is configured and retains an
in-memory fallback for fast UI preview.

## Local demo

Patient experience:

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

Operations experience:

```bash
npm install
npm run dev:operations
```

Open `http://localhost:8000` for the patient assistant and
`http://localhost:3000` for the operations dashboard.

## Docker demo

```bash
docker compose up --build
```

This starts the patient service, PostgreSQL, operations API, operations web
app, and the dry-run Python reminder worker. All records are synthetic.

## Production boundary

The assistant may explain approved catalog information and collect a booking
request, but it does not directly write protected operational records. The
operations API validates permissions, availability, and database constraints
before creating or changing appointments and claims.
