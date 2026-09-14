INSERT INTO providers (id, name, specialty, location, active) VALUES
  ('pr-101', 'Dr. Maya Chen', 'Primary Care', 'Downtown clinic', TRUE),
  ('pr-102', 'Dr. Elias Brooks', 'Cardiology', 'Riverside clinic', TRUE),
  ('pr-103', 'Dr. Sofia Patel', 'Dermatology', 'Northstar virtual', TRUE)
ON CONFLICT (id) DO NOTHING;

INSERT INTO patients (id, display_name, birth_year, coverage) VALUES
  ('pt-201', 'Jordan R.', 1988, 'Northstar Select'),
  ('pt-202', 'Taylor K.', 1976, 'Summit PPO'),
  ('pt-203', 'Morgan S.', 1994, 'Northstar Select'),
  ('pt-204', 'Casey L.', 1969, 'Harbor Medicare Advantage')
ON CONFLICT (id) DO NOTHING;

INSERT INTO appointments (id, provider_id, patient_id, starts_at, ends_at, status, reason, created_by) VALUES
  ('apt-301', 'pr-101', 'pt-201', NOW() + INTERVAL '2 hours', NOW() + INTERVAL '2 hours 30 minutes', 'scheduled', 'Annual wellness review', 'demo@northstar.test'),
  ('apt-302', 'pr-102', 'pt-202', NOW() + INTERVAL '3 hours', NOW() + INTERVAL '3 hours 45 minutes', 'checked-in', 'Follow-up consultation', 'demo@northstar.test'),
  ('apt-303', 'pr-103', 'pt-203', NOW() + INTERVAL '1 day', NOW() + INTERVAL '1 day 30 minutes', 'scheduled', 'Skin health consult', 'demo@northstar.test'),
  ('apt-304', 'pr-101', 'pt-204', NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day 30 minutes', 'completed', 'Medication review', 'demo@northstar.test')
ON CONFLICT (id) DO NOTHING;

INSERT INTO claims (id, patient_id, provider_id, appointment_id, amount_cents, status, submitted_at, updated_at) VALUES
  ('cl-401', 'pt-201', 'pr-101', 'apt-301', 18500, 'in-review', NOW(), NOW()),
  ('cl-402', 'pt-202', 'pr-102', 'apt-302', 24000, 'submitted', NOW(), NOW()),
  ('cl-403', 'pt-203', 'pr-103', 'apt-303', 12500, 'paid', NOW(), NOW()),
  ('cl-404', 'pt-204', 'pr-101', 'apt-304', 9000, 'denied', NOW(), NOW())
ON CONFLICT (id) DO NOTHING;
