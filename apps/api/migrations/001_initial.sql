CREATE TABLE IF NOT EXISTS providers (id TEXT PRIMARY KEY, name TEXT NOT NULL, specialty TEXT NOT NULL, location TEXT NOT NULL, active BOOLEAN DEFAULT TRUE);
CREATE TABLE IF NOT EXISTS patients (id TEXT PRIMARY KEY, display_name TEXT NOT NULL, birth_year INT NOT NULL, coverage TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS appointments (id TEXT PRIMARY KEY, provider_id TEXT REFERENCES providers(id), patient_id TEXT REFERENCES patients(id), starts_at TIMESTAMPTZ NOT NULL, ends_at TIMESTAMPTZ NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL, created_by TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS claims (id TEXT PRIMARY KEY, patient_id TEXT REFERENCES patients(id), provider_id TEXT REFERENCES providers(id), appointment_id TEXT REFERENCES appointments(id), amount_cents INT NOT NULL, status TEXT NOT NULL, submitted_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL);
CREATE TABLE IF NOT EXISTS audit_logs (id TEXT PRIMARY KEY, actor TEXT NOT NULL, action TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, metadata JSONB NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW());
CREATE INDEX IF NOT EXISTS appointments_provider_time_idx ON appointments(provider_id, starts_at, ends_at);
CREATE INDEX IF NOT EXISTS appointments_status_time_idx ON appointments(status, starts_at);
CREATE INDEX IF NOT EXISTS claims_status_updated_idx ON claims(status, updated_at);
CREATE INDEX IF NOT EXISTS audit_created_idx ON audit_logs(created_at DESC);
