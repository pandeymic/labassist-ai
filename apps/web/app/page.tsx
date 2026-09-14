"use client";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:4000/api";
type Appointment = {
  id: string;
  providerId: string;
  patientId: string;
  startsAt: string;
  endsAt?: string;
  status: string;
  reason: string;
};
type Claim = {
  id: string;
  patientId: string;
  providerId?: string;
  appointmentId?: string;
  amountCents: number;
  status: string;
};
type Provider = {
  id: string;
  name: string;
  specialty: string;
  location: string;
  active: boolean;
};
type Patient = {
  id: string;
  displayName: string;
  birthYear: number;
  coverage: string;
};
const providers: Record<string, string> = {
  "pr-101": "Dr. Maya Chen",
  "pr-102": "Dr. Elias Brooks",
  "pr-103": "Dr. Sofia Patel",
};
const statusColors: Record<string, string> = {
  scheduled: "blue",
  "checked-in": "green",
  completed: "gray",
  cancelled: "red",
  paid: "green",
  "in-review": "yellow",
  submitted: "blue",
  denied: "red",
};
const toLocalInput = (date: Date) => {
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
};

export default function Home() {
  const [token, setToken] = useState("");
  const [tab, setTab] = useState<
    "overview" | "appointments" | "claims" | "providers" | "patients"
  >("overview");
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [providerList, setProviderList] = useState<Provider[]>([]);
  const [patientList, setPatientList] = useState<Patient[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<"appointment" | "claim" | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const headers = useCallback(
    (authToken = token) => ({
      Authorization: `Bearer ${authToken}`,
      "Content-Type": "application/json",
    }),
    [token],
  );
  const loadData = useCallback(
    async (authToken: string) => {
      const h = headers(authToken);
      const [a, c, p, pt] = await Promise.all([
        fetch(`${API}/appointments`, { headers: h }),
        fetch(`${API}/claims`, { headers: h }),
        fetch(`${API}/providers`, { headers: h }),
        fetch(`${API}/patients`, { headers: h }),
      ]);
      setAppointments((await a.json()).data);
      setClaims((await c.json()).data);
      setProviderList((await p.json()).data);
      setPatientList((await pt.json()).data);
    },
    [headers],
  );
  useEffect(() => {
    (async () => {
      const login = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: "demo@northstar.test",
          password: "demo-password",
        }),
      });
      const auth = await login.json();
      setToken(auth.token);
      await loadData(auth.token);
      setLoading(false);
    })();
  }, [loadData]);
  const openModal = (kind: "appointment" | "claim") => {
    setError("");
    setForm(
      kind === "appointment"
        ? {
            providerId: "pr-101",
            patientId: "pt-201",
            startsAt: toLocalInput(new Date(Date.now() + 3600000)),
            endsAt: toLocalInput(new Date(Date.now() + 5400000)),
            reason: "",
          }
        : {
            providerId: "pr-101",
            patientId: "pt-201",
            appointmentId: "",
            amountCents: "15000",
          },
    );
    setModal(kind);
  };
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!modal) return;
    setSaving(true);
    setError("");
    const body =
      modal === "appointment"
        ? {
            ...form,
            startsAt: new Date(form.startsAt).toISOString(),
            endsAt: new Date(form.endsAt).toISOString(),
          }
        : { ...form, amountCents: Number(form.amountCents) };
    const response = await fetch(
      `${API}/${modal === "appointment" ? "appointments" : "claims"}`,
      { method: "POST", headers: headers(), body: JSON.stringify(body) },
    );
    const payload = await response.json();
    if (!response.ok) {
      setError(payload.message || "Unable to save record");
      setSaving(false);
      return;
    }
    await loadData(token);
    setModal(null);
    setSaving(false);
  };
  const filtered = useMemo(
    () =>
      appointments.filter((a) =>
        JSON.stringify(a).toLowerCase().includes(query.toLowerCase()),
      ),
    [appointments, query],
  );
  const money = (c: number) =>
    `$${(c / 100).toLocaleString("en-US", { minimumFractionDigits: 2 })}`;
  if (loading)
    return (
      <main className="shell loading">
        <div className="mark">✦</div>
        <p>Loading synthetic workspace…</p>
      </main>
    );
  return (
    <main className="shell">
      <aside>
        <div className="brand">
          <span className="mark">✦</span>
          <span>
            northstar
            <br />
            <b>provider ops</b>
          </span>
        </div>
        <div className="workspace">
          <span className="avatar">OP</span>
          <span>
            <strong>Operations</strong>
            <small>Northstar Health</small>
          </span>
          <span className="chev">⌄</span>
        </div>
        <nav>
          <button
            className={tab === "overview" ? "active" : ""}
            onClick={() => setTab("overview")}
          >
            ⌁ <span>Overview</span>
          </button>
          <button
            className={tab === "appointments" ? "active" : ""}
            onClick={() => setTab("appointments")}
          >
            ▦ <span>Appointments</span>
            <em>{appointments.length}</em>
          </button>
          <button
            className={tab === "claims" ? "active" : ""}
            onClick={() => setTab("claims")}
          >
            ◈ <span>Claims</span>
            <em>{claims.length}</em>
          </button>
          <button
            className={tab === "providers" ? "active" : ""}
            onClick={() => setTab("providers")}
          >
            ♧ <span>Providers</span>
            <em>{providerList.length}</em>
          </button>
          <button
            className={tab === "patients" ? "active" : ""}
            onClick={() => setTab("patients")}
          >
            ◎ <span>Patients</span>
            <em>{patientList.length}</em>
          </button>
        </nav>
        <div className="sidebarBottom">
          <button
            type="button"
            disabled
            title="Settings are outside this synthetic demo"
          >
            ⚙ <span>Settings</span>
          </button>
          <button
            type="button"
            disabled
            title="Demo session ends when the browser tab closes"
          >
            ↪ <span>Sign out</span>
          </button>
        </div>
      </aside>
      <section className="content">
        <header>
          <div>
            <p className="eyebrow">MONDAY, SEPTEMBER 14, 2026</p>
            <h1>
              {tab === "overview"
                ? "Good morning, Operations"
                : "Workspace / " + tab}
            </h1>
            <p className="muted">A clear view of today’s care operations.</p>
          </div>
          <div className="headerActions">
            <button
              className="iconBtn"
              type="button"
              disabled
              title="Search is available in each workspace"
            >
              ⌕
            </button>
            <button
              className="iconBtn"
              type="button"
              disabled
              title="Notifications are outside this synthetic demo"
            >
              ♢<i></i>
            </button>
            <span className="user">VP</span>
          </div>
        </header>
        {tab === "overview" ? (
          <Overview
            appointments={appointments}
            claims={claims}
            setTab={setTab}
            money={money}
          />
        ) : (
          <section className="card full">
            <div className="cardHead">
              <div>
                <h2>
                  {tab === "appointments"
                    ? "Appointments"
                    : tab === "claims"
                      ? "Claims"
                      : tab === "providers"
                        ? "Providers"
                        : "Patients"}
                </h2>
                <p>Search and review synthetic records only.</p>
              </div>
              <div className="toolbar">
                <input
                  aria-label="Search records"
                  placeholder="Search records…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
                {(tab === "appointments" || tab === "claims") && (
                  <button
                    className="primary"
                    onClick={() =>
                      openModal(
                        tab === "appointments" ? "appointment" : "claim",
                      )
                    }
                  >
                    + New {tab === "appointments" ? "appointment" : "claim"}
                  </button>
                )}
              </div>
            </div>
            {tab === "appointments" ? (
              <div className="table">
                <div className="tr th">
                  <span>Time</span>
                  <span>Provider</span>
                  <span>Patient</span>
                  <span>Reason</span>
                  <span>Status</span>
                </div>
                {filtered.map((a) => (
                  <div className="tr" key={a.id}>
                    <span>
                      {new Date(a.startsAt).toLocaleTimeString([], {
                        hour: "numeric",
                        minute: "2-digit",
                      })}
                    </span>
                    <span>{providers[a.providerId]}</span>
                    <span>{a.patientId}</span>
                    <span>{a.reason}</span>
                    <span>
                      <b className={`pill ${statusColors[a.status]}`}>
                        {a.status}
                      </b>
                    </span>
                  </div>
                ))}
              </div>
            ) : tab === "claims" ? (
              <div className="table">
                <div className="tr th">
                  <span>Claim</span>
                  <span>Patient</span>
                  <span>Amount</span>
                  <span>Updated</span>
                  <span>Status</span>
                </div>
                {claims
                  .filter((c) =>
                    JSON.stringify(c)
                      .toLowerCase()
                      .includes(query.toLowerCase()),
                  )
                  .map((c) => (
                    <div className="tr" key={c.id}>
                      <span>
                        <strong>{c.id.toUpperCase()}</strong>
                      </span>
                      <span>{c.patientId}</span>
                      <span>{money(c.amountCents)}</span>
                      <span>Today</span>
                      <span>
                        <b className={`pill ${statusColors[c.status]}`}>
                          {c.status.replace("-", " ")}
                        </b>
                      </span>
                    </div>
                  ))}
              </div>
            ) : tab === "providers" ? (
              <Directory
                type="providers"
                records={providerList}
                query={query}
              />
            ) : (
              <Directory type="patients" records={patientList} query={query} />
            )}
          </section>
        )}
        <footer>
          <span>
            <i className="dot"></i> Demo environment · synthetic records only
          </span>
          <span>
            API status <b className="online">● online</b> ·{" "}
            <a href="http://localhost:4000/docs" target="_blank">
              API docs ↗
            </a>
          </span>
        </footer>
      </section>
      {modal && (
        <CreateModal
          kind={modal}
          form={form}
          setForm={setForm}
          error={error}
          saving={saving}
          onClose={() => setModal(null)}
          onSubmit={submit}
        />
      )}
    </main>
  );
}
function Overview({
  appointments,
  claims,
  setTab,
  money,
}: {
  appointments: Appointment[];
  claims: Claim[];
  setTab: (tab: "overview" | "appointments" | "claims") => void;
  money: (c: number) => string;
}) {
  return (
    <>
      <div className="notice">
        <span>✦</span>
        <div>
          <strong>Everything looks calm</strong>
          <p>
            4 appointments are on the board today. One claim needs attention.
          </p>
        </div>
        <button onClick={() => setTab("claims")}>View queue →</button>
      </div>
      <div className="stats">
        <Stat
          label="Today’s appointments"
          value={String(appointments.length)}
          change="+2 from yesterday"
          icon="▦"
        />
        <Stat
          label="Checked in"
          value={String(
            appointments.filter((a) => a.status === "checked-in").length,
          )}
          change="On schedule"
          icon="◷"
        />
        <Stat
          label="Claims in review"
          value={String(claims.filter((c) => c.status === "in-review").length)}
          change="Needs attention"
          icon="◈"
          alert
        />
        <Stat
          label="Clean claim rate"
          value="96.4%"
          change="+1.2% this month"
          icon="↗"
        />
      </div>
      <div className="grid">
        <section className="card appointments">
          <div className="cardHead">
            <div>
              <h2>Today’s appointments</h2>
              <p>Monday, September 14</p>
            </div>
            <button onClick={() => setTab("appointments")}>View all →</button>
          </div>
          <div className="timeline">
            {appointments.slice(0, 3).map((a) => (
              <AppointmentRow key={a.id} a={a} />
            ))}
          </div>
        </section>
        <section className="card claims">
          <div className="cardHead">
            <div>
              <h2>Claims pipeline</h2>
              <p>Latest billing activity</p>
            </div>
            <button onClick={() => setTab("claims")}>View all →</button>
          </div>
          {claims.map((c) => (
            <div className="claimRow" key={c.id}>
              <span className="claimIcon">◈</span>
              <div>
                <strong>{c.id.toUpperCase()}</strong>
                <small>{c.patientId} · Submitted today</small>
              </div>
              <span className={`pill ${statusColors[c.status]}`}>
                {c.status.replace("-", " ")}
              </span>
              <b>{money(c.amountCents)}</b>
            </div>
          ))}
        </section>
      </div>
    </>
  );
}
type DirectoryProps =
  | { type: "providers"; records: Provider[]; query: string }
  | { type: "patients"; records: Patient[]; query: string };

function Directory({ type, records, query }: DirectoryProps) {
  const filtered = records.filter((record) =>
    JSON.stringify(record).toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <div className="table">
      <div className="tr th">
        {type === "providers" ? (
          <>
            <span>Name</span>
            <span>Specialty</span>
            <span>Location</span>
            <span>Status</span>
          </>
        ) : (
          <>
            <span>Display name</span>
            <span>Birth year</span>
            <span>Coverage</span>
            <span>Status</span>
          </>
        )}
      </div>
      {filtered.map((record) =>
        type === "providers" ? (
          <div className="tr" key={record.id}>
            <span>
              <strong>{(record as Provider).name}</strong>
            </span>
            <span>{(record as Provider).specialty}</span>
            <span>{(record as Provider).location}</span>
            <span>
              <b className="pill green">Active</b>
            </span>
          </div>
        ) : (
          <div className="tr" key={record.id}>
            <span>
              <strong>{(record as Patient).displayName}</strong>
            </span>
            <span>{(record as Patient).birthYear}</span>
            <span>{(record as Patient).coverage}</span>
            <span>
              <b className="pill blue">Synthetic</b>
            </span>
          </div>
        ),
      )}
    </div>
  );
}
function CreateModal({
  kind,
  form,
  setForm,
  error,
  saving,
  onClose,
  onSubmit,
}: {
  kind: "appointment" | "claim";
  form: Record<string, string>;
  setForm: (form: Record<string, string>) => void;
  error: string;
  saving: boolean;
  onClose: () => void;
  onSubmit: (e: FormEvent) => void;
}) {
  const update = (key: string, value: string) =>
    setForm({ ...form, [key]: value });
  return (
    <div className="modalBackdrop" role="dialog" aria-modal="true">
      <form className="modal" onSubmit={onSubmit}>
        <div className="modalHead">
          <div>
            <p className="eyebrow">SYNTHETIC RECORD</p>
            <h2>New {kind}</h2>
          </div>
          <button type="button" className="close" onClick={onClose}>
            ×
          </button>
        </div>
        <label>
          Provider
          <select
            value={form.providerId}
            onChange={(e) => update("providerId", e.target.value)}
          >
            <option value="pr-101">Dr. Maya Chen</option>
            <option value="pr-102">Dr. Elias Brooks</option>
            <option value="pr-103">Dr. Sofia Patel</option>
          </select>
        </label>
        <label>
          Patient
          <select
            value={form.patientId}
            onChange={(e) => update("patientId", e.target.value)}
          >
            <option value="pt-201">Jordan R.</option>
            <option value="pt-202">Taylor K.</option>
            <option value="pt-203">Morgan S.</option>
            <option value="pt-204">Casey L.</option>
          </select>
        </label>
        {kind === "appointment" ? (
          <>
            <label>
              Starts
              <input
                required
                type="datetime-local"
                value={form.startsAt}
                onChange={(e) => update("startsAt", e.target.value)}
              />
            </label>
            <label>
              Ends
              <input
                required
                type="datetime-local"
                value={form.endsAt}
                onChange={(e) => update("endsAt", e.target.value)}
              />
            </label>
            <label>
              Reason
              <input
                required
                placeholder="Annual wellness review"
                value={form.reason}
                onChange={(e) => update("reason", e.target.value)}
              />
            </label>
          </>
        ) : (
          <>
            <label>
              Appointment
              <select
                required
                value={form.appointmentId}
                onChange={(e) => update("appointmentId", e.target.value)}
              >
                <option value="">Choose appointment</option>
                {["apt-301", "apt-302", "apt-303"].map((id) => (
                  <option key={id} value={id}>
                    {id.toUpperCase()}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Amount in cents
              <input
                required
                type="number"
                min="1"
                value={form.amountCents}
                onChange={(e) => update("amountCents", e.target.value)}
              />
            </label>
          </>
        )}
        {error && <p className="formError">{error}</p>}
        <div className="modalActions">
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button className="primary" disabled={saving}>
            {saving ? "Saving…" : "Create " + kind}
          </button>
        </div>
      </form>
    </div>
  );
}
function Stat({
  label,
  value,
  change,
  icon,
  alert,
}: {
  label: string;
  value: string;
  change: string;
  icon: string;
  alert?: boolean;
}) {
  return (
    <div className="stat">
      <div className={`statIcon ${alert ? "alert" : ""}`}>{icon}</div>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
        <small className={alert ? "alertText" : ""}>{change}</small>
      </div>
    </div>
  );
}
function AppointmentRow({ a }: { a: Appointment }) {
  return (
    <div className="aptRow">
      <span className="time">
        {new Date(a.startsAt).toLocaleTimeString([], {
          hour: "numeric",
          minute: "2-digit",
        })}
      </span>
      <span className="line"></span>
      <span className="person">
        <span className="personAvatar">{a.patientId.slice(-1)}</span>
        <span>
          <strong>{providers[a.providerId]}</strong>
          <small>{a.reason}</small>
        </span>
      </span>
      <span className={`pill ${statusColors[a.status]}`}>
        {a.status.replace("-", " ")}
      </span>
    </div>
  );
}
