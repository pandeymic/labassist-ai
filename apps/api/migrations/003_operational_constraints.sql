CREATE UNIQUE INDEX IF NOT EXISTS claims_appointment_unique_idx ON claims(appointment_id);
CREATE INDEX IF NOT EXISTS providers_name_search_idx ON providers(name);
CREATE INDEX IF NOT EXISTS patients_display_name_search_idx ON patients(display_name);
