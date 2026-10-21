import { useCallback, useEffect, useMemo, useState } from "react";
import "./App.css";

const API = (
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

const STAGES = [
  {
    name: "Opening",
    purpose: "Introduce yourself and earn a few seconds of attention.",
    examples: [
      "Hello, who is this?",
      "What is this regarding?",
    ],
  },
  {
    name: "Permission",
    purpose: "Ask whether this is a suitable time for a brief conversation.",
    examples: [
      "I have a minute.",
      "I'm a little busy right now.",
    ],
  },
  {
    name: "Reason for calling",
    purpose: "Explain why you are calling this particular prospect.",
    examples: [
      "Why are you calling me?",
      "How did you get my details?",
    ],
  },
  {
    name: "Problem",
    purpose: "Explore a relevant business problem without making assumptions.",
    examples: [
      "We already have a process for that.",
      "That is something we struggle with.",
    ],
  },
  {
    name: "Value proposition",
    purpose: "Connect the problem to a relevant potential benefit.",
    examples: [
      "How would that help us?",
      "Can you explain that briefly?",
    ],
  },
  {
    name: "Objection handling",
    purpose: "Understand concerns and respond honestly and respectfully.",
    examples: [
      "We don't have the budget.",
      "Send me some information.",
    ],
  },
  {
    name: "Next step",
    purpose: "Agree on a useful next step if the prospect is interested.",
    examples: [
      "Can we talk next week?",
      "Please send me a calendar invite.",
    ],
  },
  {
    name: "Close",
    purpose: "Confirm the outcome and end the conversation professionally.",
    examples: [
      "Thanks, goodbye.",
      "I'm not interested at the moment.",
    ],
  },
];

const EMPTY_FORM = {
  prospect: "",
  company: "",
  caller: "",
};

const EMPTY_DRAFT = {
  outcome: "",
  exactWords: "",
  notes: "",
};

function getCall(data) {
  return data?.call ?? data?.data?.call ?? data?.data ?? data;
}

function getProspect(call) {
  return (
    call?.prospect_name ??
    call?.prospect ??
    call?.contact_name ??
    ""
  );
}

function getCompany(call) {
  return call?.company_name ?? call?.company ?? "";
}

function getCalls(data) {
  if (Array.isArray(data)) return data;

  const calls =
    data?.calls ??
    data?.data?.calls ??
    data?.results ??
    [];

  return Array.isArray(calls) ? calls : [];
}

function isOpenCall(call) {
  return [
    "in_progress",
    "active",
    "open",
    "started",
  ].includes(String(call?.status ?? "").toLowerCase());
}

function mapSavedStages(call) {
  const result = {};
  const rows = call?.stage_results ?? call?.stageResults ?? [];

  if (!Array.isArray(rows)) return result;

  rows.forEach((row) => {
    const number = Number(row?.stage_number);

    if (number < 1 || number > STAGES.length) return;

    result[number] = {
      outcome: row?.what_happened ?? row?.response ?? row?.outcome ?? "",
      exactWords:
        row?.prospect_words ??
        row?.prospect_exact_words ??
        "",
      notes: row?.notes ?? "",
    };
  });

  return result;
}

async function apiRequest(path, options = {}) {
  let response;

  try {
    response = await fetch(`${API}${path}`, {
      ...options,
      headers: {
        ...(options.body
          ? { "Content-Type": "application/json" }
          : {}),
        ...(options.headers || {}),
      },
    });
  } catch {
    throw new Error(
      `Cannot connect to ${API}. Start FastAPI and check frontend/.env.`
    );
  }

  const raw = await response.text();
  let data = {};

  if (raw) {
    try {
      data = JSON.parse(raw);
    } catch {
      data = { detail: raw };
    }
  }

  if (!response.ok) {
    const detail = data?.detail;

    const message = Array.isArray(detail)
      ? detail
          .map((item) => {
            const field = item.loc?.join(".");
            return field
              ? `${field}: ${item.msg}`
              : item.msg || JSON.stringify(item);
          })
          .join("; ")
      : typeof detail === "string"
        ? detail
        : `Request failed with status ${response.status}`;

    throw new Error(message);
  }

  return data;
}

export default function App() {
  const [form, setForm] = useState(EMPTY_FORM);
  const [activeCall, setActiveCall] = useState(null);
  const [stage, setStage] = useState(1);
  const [drafts, setDrafts] = useState({});
  const [history, setHistory] = useState([]);
  const [coach, setCoach] = useState("");
  const [notice, setNotice] = useState("");
  const [noticeType, setNoticeType] = useState("success");
  const [loading, setLoading] = useState(false);

  const callId = activeCall?.id ?? activeCall?.call_id ?? "";
  const callIsOpen = isOpenCall(activeCall);

  const currentStage = STAGES[stage - 1] ?? STAGES[0];
  const currentDraft = drafts[stage] ?? EMPTY_DRAFT;

  const displayedProspect =
    getProspect(activeCall) ||
    form.prospect ||
    "New prospect";

  const displayedCompany =
    getCompany(activeCall) ||
    form.company ||
    "Company not specified";

  const completion = useMemo(
    () => Math.round((stage / STAGES.length) * 100),
    [stage]
  );

  const notify = useCallback((text, type = "success") => {
    setNotice(text);
    setNoticeType(type);
  }, []);

  const loadHistory = useCallback(async () => {
    try {
      const data = await apiRequest("/api/calls");
      setHistory(getCalls(data));
    } catch (error) {
      notify(
        `Could not load call history: ${error.message}`,
        "error"
      );
    }
  }, [notify]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  function updateDraft(field, value) {
    setDrafts((previous) => ({
      ...previous,
      [stage]: {
        ...EMPTY_DRAFT,
        ...(previous[stage] ?? {}),
        [field]: value,
      },
    }));
  }

  function selectStage(value) {
    const next = Math.min(
      STAGES.length,
      Math.max(1, Number(value) || 1)
    );

    setStage(next);
    setCoach("");
  }

  async function startCall(event) {
    event.preventDefault();

    if (!form.prospect.trim()) {
      notify("Please enter the prospect's name.", "error");
      return;
    }

    setLoading(true);
    setNotice("");

    try {
      const data = await apiRequest("/api/calls", {
        method: "POST",
        body: JSON.stringify({
          prospect_name: form.prospect.trim(),
          company: form.company.trim(),
          caller_name: form.caller.trim(),
        }),
      });

      const call = getCall(data);
      const id = call?.id ?? call?.call_id;

      if (!id) {
        throw new Error(
          "The API did not return a call ID. Check POST /api/calls."
        );
      }

      const savedCall = {
        ...call,
        id,
        prospect_name:
          getProspect(call) || form.prospect.trim(),
        company_name:
          getCompany(call) || form.company.trim(),
        caller_name: call?.caller_name ?? form.caller.trim(),
        status: call?.status ?? "in_progress",
        current_stage: Number(call?.current_stage) || 1,
      };

      setActiveCall(savedCall);

      setForm({
        prospect: savedCall.prospect_name,
        company: savedCall.company_name,
        caller: savedCall.caller_name,
      });

      setStage(savedCall.current_stage);
      setDrafts(mapSavedStages(savedCall));
      setCoach("");

      notify(`Call started for ${savedCall.prospect_name}.`);
      await loadHistory();
    } catch (error) {
      notify(`Could not start call: ${error.message}`, "error");
    } finally {
      setLoading(false);
    }
  }

  async function saveStage() {
    if (!callId || !callIsOpen) {
      notify(
        "Start or select an open call before saving a stage.",
        "error"
      );
      return;
    }

    setLoading(true);
    setNotice("");

    // Read the current stage form values.
    const outcome = currentDraft.outcome;
    const exactWords = currentDraft.exactWords;
    const notes = currentDraft.notes;

    try {
      // Save a stage using the required backend fields.
      const data = await apiRequest(
        `/api/calls/${callId}/stages`,
        {
          method: "POST",
          body: JSON.stringify({
            stage_number: stage,
            stage_name: currentStage.name,
            what_happened: outcome,
            prospect_words: exactWords,
            notes: notes,
          }),
        }
      );

      setActiveCall((previous) => ({
        ...previous,
        current_stage:
          Number(data?.current_stage) ||
          Math.min(stage + 1, STAGES.length),
      }));

      notify(`Stage ${stage} — ${currentStage.name} — saved.`);
      await loadHistory();
    } catch (error) {
      notify(`Could not save stage: ${error.message}`, "error");
    } finally {
      setLoading(false);
    }
  }

  async function requestCoaching() {
    if (!callId || !callIsOpen) {
      notify(
        "Start or select an open call before requesting coaching.",
        "error"
      );
      return;
    }

    setLoading(true);
    setCoach("");
    setNotice("");

    try {
      const data = await apiRequest("/api/coach", {
        method: "POST",
        body: JSON.stringify({
          call_id: String(callId),
          stage_number: stage,
          stage_name: currentStage.name,
          what_happened: currentDraft.outcome,
          prospect_words: currentDraft.exactWords,
          notes: currentDraft.notes,
          prospect_name: getProspect(activeCall) || form.prospect,
          company: getCompany(activeCall) || form.company,
        }),
      });

      const result =
        data?.coaching ??
        data?.feedback ??
        data?.suggestion ??
        data?.message ??
        data;

      setCoach(
        typeof result === "string"
          ? result
          : JSON.stringify(result, null, 2)
      );
    } catch (error) {
      notify(`AI coach failed: ${error.message}`, "error");
    } finally {
      setLoading(false);
    }
  }

  async function closeCall() {
    if (!callId || !callIsOpen) {
      notify("There is no open call to close.", "error");
      return;
    }

    const confirmed = window.confirm(
      `Close the call with ${displayedProspect}? Make sure important stages are saved first.`
    );

    if (!confirmed) return;

    setLoading(true);
    setNotice("");

    try {
      await apiRequest(`/api/calls/${callId}/close`, {
        method: "POST",
        body: JSON.stringify({
          outcome: currentDraft.outcome || "completed",
          summary: currentDraft.notes || "",
        }),
      });

      setActiveCall((previous) => ({
        ...previous,
        status: "closed",
      }));

      notify("Call closed successfully.");
      await loadHistory();
    } catch (error) {
      notify(`Could not close call: ${error.message}`, "error");
    } finally {
      setLoading(false);
    }
  }

  function selectCall(call) {
    const id = call?.id ?? call?.call_id;

    if (!id) {
      notify("This history item has no valid call ID.", "error");
      return;
    }

    setActiveCall(call);

    setForm({
      prospect: getProspect(call),
      company: getCompany(call),
      caller: call?.caller_name ?? "",
    });

    setStage(
      Math.min(
        STAGES.length,
        Math.max(1, Number(call?.current_stage) || 1)
      )
    );

    setDrafts(mapSavedStages(call));
    setCoach("");

    notify(
      isOpenCall(call)
        ? "Active call selected."
        : "This call is closed and read-only.",
      isOpenCall(call) ? "success" : "info"
    );
  }

  function newCall() {
    setActiveCall(null);
    setForm(EMPTY_FORM);
    setStage(1);
    setDrafts({});
    setCoach("");
    notify("Ready to start a new call.");
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">CC</span>
          <span>
            <strong>ColdCall</strong>
            <small>CALL ASSISTANT</small>
          </span>
        </div>

        <span className={`connection ${callIsOpen ? "online" : ""}`}>
          {callIsOpen
            ? "Call in progress"
            : activeCall
              ? "Call history"
              : "Sales workspace"}
        </span>
      </header>

      <main className="container">
        <section className="hero">
          <div>
            <p className="eyebrow">CALL WORKSPACE</p>
            <h1>Make every conversation count.</h1>
            <p>
              Guide the call, capture the prospect's exact words,
              and agree on a clear next step.
            </p>
          </div>

          <div className="hero-stat">
            <strong>08</strong>
            <span>CALL STAGES</span>
          </div>
        </section>

        {notice && (
          <div
            className={`notice ${noticeType === "error" ? "error" : ""}`}
            role="status"
            aria-live="polite"
          >
            <span>{notice}</span>
            <button
              type="button"
              onClick={() => setNotice("")}
              aria-label="Dismiss message"
            >
              ×
            </button>
          </div>
        )}

        <div className="layout">
          <aside className="sidebar">
            <section className="panel">
              <p className="eyebrow">NEW CONVERSATION</p>
              <h2>Start a call</h2>

              <form onSubmit={startCall} className="call-form">
                <label htmlFor="prospect">Prospect name *</label>
                <input
                  id="prospect"
                  value={form.prospect}
                  onChange={(event) =>
                    setForm((previous) => ({
                      ...previous,
                      prospect: event.target.value,
                    }))
                  }
                  placeholder="e.g. Alex Morgan"
                  required
                  disabled={loading || Boolean(callId)}
                />

                <label htmlFor="company">Company</label>
                <input
                  id="company"
                  value={form.company}
                  onChange={(event) =>
                    setForm((previous) => ({
                      ...previous,
                      company: event.target.value,
                    }))
                  }
                  placeholder="e.g. Acme Technologies"
                  disabled={loading || Boolean(callId)}
                />

                <label htmlFor="caller">Your name (optional)</label>
                <input
                  id="caller"
                  value={form.caller}
                  onChange={(event) =>
                    setForm((previous) => ({
                      ...previous,
                      caller: event.target.value,
                    }))
                  }
                  placeholder="Your name"
                  disabled={loading || Boolean(callId)}
                />

                <button
                  className="button primary full"
                  type="submit"
                  disabled={loading || Boolean(callId)}
                >
                  {loading ? "Please wait…" : "Start new call"}
                </button>
              </form>

              {activeCall && (
                <button
                  className="button secondary full"
                  type="button"
                  onClick={newCall}
                  disabled={loading}
                >
                  Switch to a new call
                </button>
              )}
            </section>

            <section className="panel history-panel">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">YOUR ACTIVITY</p>
                  <h2>Call history</h2>
                </div>
                <span className="count">{history.length}</span>
              </div>

              {history.length === 0 ? (
                <p className="muted">
                  Your saved calls will appear here.
                </p>
              ) : (
                <ul className="history-list">
                  {history.map((call, index) => {
                    const name =
                      getProspect(call) || "Unnamed prospect";
                    const id = call?.id ?? call?.call_id ?? index;

                    return (
                      <li key={id}>
                        <button
                          type="button"
                          className={`history-item ${
                            String(id) === String(callId)
                              ? "selected"
                              : ""
                          }`}
                          onClick={() => selectCall(call)}
                          disabled={loading}
                        >
                          <span className="avatar">
                            {name.slice(0, 1).toUpperCase()}
                          </span>

                          <span className="history-copy">
                            <strong>{name}</strong>
                            <span>
                              {getCompany(call) ||
                                "Company not specified"}
                            </span>
                            <small>
                              Stage {Number(call?.current_stage) || 1} of 8
                              {" · "}
                              {call?.status || "unknown"}
                            </small>
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}

              <button
                className="button secondary full"
                type="button"
                onClick={loadHistory}
                disabled={loading}
              >
                Refresh history
              </button>
            </section>
          </aside>

          <section className="panel workspace">
            <div className="current-call">
              <span className="avatar large">
                {displayedProspect.slice(0, 1).toUpperCase()}
              </span>

              <div className="current-copy">
                <p className="eyebrow">CURRENT CONVERSATION</p>
                <h2>{displayedProspect}</h2>
                <p className="muted">{displayedCompany}</p>
              </div>

              <span className={`pill ${callIsOpen ? "active" : ""}`}>
                {callIsOpen
                  ? "In progress"
                  : activeCall
                    ? "Closed"
                    : "Not started"}
              </span>
            </div>

            <div className="stage-header">
              <div>
                <p className="eyebrow">
                  STAGE {stage} OF {STAGES.length}
                </p>
                <h2>{currentStage.name}</h2>
                <p className="muted">{currentStage.purpose}</p>
              </div>
              <span className="progress-label">{completion}%</span>
            </div>

            <div className="progress-track">
              <span style={{ width: `${completion}%` }} />
            </div>

            <nav className="stage-nav" aria-label="Call stages">
              {STAGES.map((item, index) => (
                <button
                  type="button"
                  key={item.name}
                  onClick={() => selectStage(index + 1)}
                  className={stage === index + 1 ? "chosen" : ""}
                  title={item.name}
                  aria-label={`Stage ${index + 1}: ${item.name}`}
                  disabled={loading}
                >
                  {index + 1}
                </button>
              ))}
            </nav>

            <div className="examples-box helper">
              <p className="eyebrow">CONVERSATION PROMPTS</p>
              <ul>
                {currentStage.examples.map((example) => (
                  <li key={example}>{example}</li>
                ))}
              </ul>
            </div>

            <div className="stage-form">
              <label htmlFor="outcome">What happened?</label>
              <select
                id="outcome"
                value={currentDraft.outcome}
                onChange={(event) =>
                  updateDraft("outcome", event.target.value)
                }
                disabled={!callIsOpen || loading}
              >
                <option value="">Select an outcome</option>
                <option value="Agreed to receive report">
                  Agreed to receive report
                </option>
                <option value="Next step agreed">Next step agreed</option>
                <option value="Interested">Interested</option>
                <option value="Follow-up required">
                  Follow-up required
                </option>
                <option value="Call again">Call again</option>
                <option value="Not interested">Not interested</option>
                <option value="Do not call">Do not call</option>
                <option value="Wrong person">Wrong person</option>
                <option value="Moved company">Moved company</option>
                <option value="No answer or disconnected">
                  No answer or disconnected
                </option>
                <option value="Other">Other</option>
              </select>

              <label htmlFor="exactWords">
                Prospect's exact words
              </label>
              <textarea
                id="exactWords"
                rows="4"
                value={currentDraft.exactWords}
                onChange={(event) =>
                  updateDraft("exactWords", event.target.value)
                }
                placeholder="Capture what the prospect actually said."
                disabled={!callIsOpen || loading}
              />

              <label htmlFor="notes">Call notes and follow-up</label>
              <textarea
                id="notes"
                rows="3"
                value={currentDraft.notes}
                onChange={(event) =>
                  updateDraft("notes", event.target.value)
                }
                placeholder="Context, follow-up action, or callback time."
                disabled={!callIsOpen || loading}
              />

              {!callId && (
                <p className="helper">
                  Start a call to enable stage saving and AI coaching.
                </p>
              )}

              {callId && !callIsOpen && (
                <p className="helper">
                  This call is closed. Its saved notes are read-only.
                </p>
              )}

              <div className="button-row">
                <button
                  className="button secondary"
                  type="button"
                  onClick={() => selectStage(stage - 1)}
                  disabled={stage === 1 || loading}
                >
                  Previous
                </button>

                <button
                  className="button primary"
                  type="button"
                  onClick={saveStage}
                  disabled={!callIsOpen || loading}
                >
                  {loading ? "Saving…" : "Save stage"}
                </button>

                <button
                  className="button secondary"
                  type="button"
                  onClick={() => selectStage(stage + 1)}
                  disabled={stage === STAGES.length || loading}
                >
                  Next
                </button>
              </div>
            </div>

            <section className="coach-card">
              <div>
                <p className="eyebrow">CONVERSATION SUPPORT</p>
                <h2>AI Sales Coach</h2>
                <p className="muted">
                  Get guidance based on the current stage and the
                  prospect's words.
                </p>
              </div>

              <button
                className="button primary"
                type="button"
                onClick={requestCoaching}
                disabled={!callIsOpen || loading}
              >
                {loading ? "Working…" : "Get coaching"}
              </button>

              {coach && (
                <div className="coach-result">
                  <strong>Suggested coaching</strong>
                  <p>{coach}</p>
                </div>
              )}
            </section>

            <div className="close-row">
              <button
                className="button danger"
                type="button"
                onClick={closeCall}
                disabled={!callIsOpen || loading}
              >
                Close call
              </button>
            </div>
          </section>
        </div>
      </main>

      <footer className="footer">
        ColdCall · Structured conversations, accurate notes, clear next steps.
      </footer>
    </div>
  );
}