import React, { useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, { method = "GET", token, body } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${API}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const detail = data && data.detail;
    const text =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
        ? detail.map((item) => item.msg).join(", ")
        : "Request failed";
    throw new Error(text);
  }
  return data;
}

function Field({ field, value, onChange }) {
  const id = `field-${field.key}`;
  if (field.type === "checkbox") {
    return (
      <label className="check" htmlFor={id}>
        <input
          id={id}
          type="checkbox"
          checked={Boolean(value)}
          onChange={(event) => onChange(event.target.checked)}
        />
        <span>{field.label}</span>
      </label>
    );
  }
  if (field.type === "select") {
    return (
      <label htmlFor={id}>
        <span>{field.label}</span>
        <select
          id={id}
          value={value ?? ""}
          onChange={(event) => onChange(event.target.value)}
        >
          {field.options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
    );
  }
  return (
    <label htmlFor={id}>
      <span>{field.label}</span>
      <input
        id={id}
        type={field.type === "number" ? "number" : "text"}
        min={field.min}
        max={field.max}
        step={field.step}
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function RoomCard({ room, busy, onJoin, allowJoin, onOpenDetails }) {
  return (
    <article className={`room status-${room.status}`}>
      <header className="room-head">
        <div>
          <h3>{room.room_name}</h3>
          <p className="room-location">
            📍 {room.location}
            {room.location_group && (
              <span className="location-tag"> • {room.location_group}</span>
            )}
          </p>
        </div>
        <span className="badge">{room.status_label}</span>
      </header>

      {room.description && (
        <p className="room-description">{room.description}</p>
      )}

      <dl className="facts">
        {room.facts.map((fact) => (
          <div key={fact.label}>
            <dt>{fact.label}</dt>
            <dd>{fact.value}</dd>
          </div>
        ))}
      </dl>

      {room.scored && (
        <div className="score-block">
          <div className="score-header">
            <span>Roommate Compatibility</span>
            <b>{room.ensemble_score}%</b>
          </div>
          <div className="score-bar">
            <div
              className="score-fill"
              style={{ width: `${Math.min(room.ensemble_score, 100)}%` }}
            />
          </div>
          <small className="muted score-disclaimer">
            Model estimate based on lifestyle preferences, not a guarantee.
          </small>
        </div>
      )}

      {room.compatibility_note && (
        <p className="compatibility-note">ℹ️ {room.compatibility_note}</p>
      )}

      {room.score_breakdown && room.score_breakdown.length > 0 && (
        <div className="breakdown-container">
          <span className="breakdown-title">Model Breakdown:</span>
          <div className="breakdown-chips">
            {room.score_breakdown.map((item) => (
              <span key={item.key} className="breakdown-chip">
                {item.label}: <b>{item.value}%</b>
              </span>
            ))}
          </div>
        </div>
      )}

      {room.occupants && room.occupants.length > 0 && (
        <div className="occupants-block">
          <span className="occupants-title">Current Occupants:</span>
          <ul className="occupants-list">
            {room.occupants.map((occ) => (
              <li key={occ.occupant_id}>
                👤 Occupant {occ.occupant_id}{" "}
                <span className="occupant-info">
                  ({occ.occupation}, {occ.gender})
                </span>
                {!occ.has_profile && (
                  <span className="muted"> [Profile pending]</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {room.reasons && room.reasons.length > 0 && (
        <div className="reasons-block">
          <span className="reasons-title">Ineligibility Reasons:</span>
          <ul className="reasons">
            {room.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      )}

      <footer className="room-foot">
        {room.joined && <span className="tag">✓ You are a member</span>}
        <button
          className="secondary small-btn"
          onClick={() => onOpenDetails(room)}
        >
          View Details
        </button>
        {allowJoin && room.can_join && (
          <button
            className="primary small-btn"
            onClick={() => onJoin(room.room_id)}
            disabled={busy}
          >
            Join Room
          </button>
        )}
      </footer>
    </article>
  );
}

function RoomDetailModal({ room, onClose, onJoin, allowJoin, busy }) {
  if (!room) return null;
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <header className="modal-header">
          <h2>{room.room_name}</h2>
          <button className="close-btn" onClick={onClose}>
            ✕
          </button>
        </header>
        <div className="modal-body">
          <div className="badge-row">
            <span className="badge">{room.status_label}</span>
            <span className="location-badge">📍 {room.location}</span>
            <span className="rent-badge">
              ₹{room.monthly_rent?.toLocaleString()}/month
            </span>
          </div>

          {room.description && (
            <div className="modal-section">
              <h4>Description</h4>
              <p>{room.description}</p>
            </div>
          )}

          <div className="modal-section">
            <h4>Room Facts</h4>
            <dl className="facts modal-facts">
              {room.facts.map((fact) => (
                <div key={fact.label}>
                  <dt>{fact.label}</dt>
                  <dd>{fact.value}</dd>
                </div>
              ))}
            </dl>
          </div>

          {room.amenities && room.amenities.length > 0 && (
            <div className="modal-section">
              <h4>Amenities</h4>
              <div className="amenities-chips">
                {room.amenities.map((item, idx) => (
                  <span key={idx} className="amenity-chip">
                    ✨ {item}
                  </span>
                ))}
              </div>
            </div>
          )}

          {room.scored && (
            <div className="modal-section">
              <h4>Match Analysis</h4>
              <p className="score">
                Estimated Compatibility: <b>{room.ensemble_score}%</b>
              </p>
              {room.score_breakdown && room.score_breakdown.length > 0 && (
                <ul className="breakdown">
                  {room.score_breakdown.map((item) => (
                    <li key={item.key}>
                      {item.label}: <b>{item.value}%</b>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {room.reasons && room.reasons.length > 0 && (
            <div className="modal-section">
              <h4>Constraints &amp; Ineligibility</h4>
              <ul className="reasons">
                {room.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <footer className="modal-footer">
          <button className="secondary" onClick={onClose}>
            Close
          </button>
          {allowJoin && room.can_join && (
            <button
              className="primary"
              onClick={() => {
                onJoin(room.room_id);
                onClose();
              }}
              disabled={busy}
            >
              Confirm &amp; Join Room
            </button>
          )}
        </footer>
      </div>
    </div>
  );
}

function ConfirmLeaveModal({ isOpen, onClose, onConfirm, busy }) {
  if (!isOpen) return null;
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content confirm-modal" onClick={(e) => e.stopPropagation()}>
        <header className="modal-header">
          <h2>Leave Room Confirmation</h2>
          <button className="close-btn" onClick={onClose}>
            ✕
          </button>
        </header>
        <div className="modal-body">
          <p>
            Are you sure you want to leave your current room? Your slot will be
            vacated immediately, and you will be able to search and join another
            room.
          </p>
        </div>
        <footer className="modal-footer">
          <button className="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button
            className="danger-btn"
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? "Leaving..." : "Yes, Leave Room"}
          </button>
        </footer>
      </div>
    </div>
  );
}

export function App() {
  const [token, setToken] = useState(() => localStorage.getItem("roommate_token") || "");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authMode, setAuthMode] = useState("login");
  const [schema, setSchema] = useState(null);
  const [values, setValues] = useState({});
  const [listing, setListing] = useState(null);
  const [recommendations, setRecommendations] = useState(null);
  const [account, setAccount] = useState(null);
  const [view, setView] = useState("dashboard");
  const [expandSearch, setExpandSearch] = useState(false);
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState("info");
  const [busy, setBusy] = useState(false);
  const [activeRoomDetail, setActiveRoomDetail] = useState(null);
  const [showLeaveConfirm, setShowLeaveConfirm] = useState(false);

  const showBanner = (text, type = "info") => {
    setMessage(text);
    setMessageType(type);
    if (type !== "error") {
      setTimeout(() => setMessage(""), 5000);
    }
  };

  const loadRooms = useCallback(
    async (sessionToken = token, page = 1, append = false) => {
      try {
        const next = await request(`/rooms?page=${page}&page_size=20`, {
          token: sessionToken,
        });
        setListing((current) =>
          append && current
            ? { ...next, rooms: [...current.rooms, ...next.rooms] }
            : next
        );
      } catch (error) {
        showBanner(error.message, "error");
      }
    },
    [token]
  );

  const loadAccount = useCallback(
    async (sessionToken = token) => {
      if (!sessionToken) return;
      try {
        const nextAccount = await request("/me", { token: sessionToken });
        setAccount(nextAccount);
        if (nextAccount.current_room) {
          setView("dashboard");
        }
      } catch (error) {
        localStorage.removeItem("roommate_token");
        setToken("");
        showBanner(error.message, "error");
      }
    },
    [token]
  );

  useEffect(() => {
    request("/profile/form")
      .then((next) => {
        setSchema(next);
        setValues((cur) => ({ ...next.defaults, ...cur }));
      })
      .catch((error) => showBanner(error.message, "error"));
    loadRooms("");
  }, [loadRooms]);

  useEffect(() => {
    if (!token) {
      setAccount(null);
      return;
    }
    loadAccount(token);
    loadRooms(token);
    request("/profile", { token })
      .then((saved) => {
        setValues((current) => ({ ...current, ...saved }));
      })
      .catch(() => {});
  }, [token, loadAccount, loadRooms]);

  const update = (key, value) =>
    setValues((current) => ({ ...current, [key]: value }));

  async function authenticate(e) {
    if (e) e.preventDefault();
    if (!email || !password) {
      showBanner("Please fill in both email and password.", "error");
      return;
    }
    setBusy(true);
    const endpoint = authMode === "register" ? "/auth/register" : "/auth/login";
    try {
      const data = await request(endpoint, {
        method: "POST",
        body: { email, password },
      });
      localStorage.setItem("roommate_token", data.token);
      setToken(data.token);
      setRecommendations(null);
      showBanner(
        authMode === "register"
          ? "Account registered successfully!"
          : "Logged in successfully!",
        "success"
      );
      await loadAccount(data.token);
      setView("dashboard");
    } catch (error) {
      showBanner(error.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    try {
      await request("/auth/logout", { method: "POST", token });
    } catch {
      // Session local cleanup
    }
    localStorage.removeItem("roommate_token");
    setToken("");
    setAccount(null);
    setRecommendations(null);
    setView("all");
    showBanner("Signed out.", "info");
    loadRooms("");
  }

  async function saveProfile(showMessage = true) {
    if (!token) return false;
    setBusy(true);
    try {
      await request("/profile", { method: "PUT", token, body: values });
      await loadAccount(token);
      if (showMessage) {
        showBanner("Lifestyle profile saved successfully!", "success");
      }
      return true;
    } catch (error) {
      showBanner(error.message, "error");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function findRooms(nextExpand = expandSearch, page = 1, append = false) {
    if (!token) {
      setView("all");
      return;
    }
    setBusy(true);
    try {
      const saved = await saveProfile(false);
      if (!saved) return;
      const filters = {
        strict_max_rent: values.strict_max_rent || null,
        required_room_type: values.required_room_type || null,
        no_smoking: Boolean(values.no_smoking),
      };
      const next = await request(
        `/recommendations?expand_search=${nextExpand}&page=${page}&page_size=20`,
        { method: "POST", token, body: filters }
      );
      setRecommendations((current) =>
        append && current
          ? {
              ...next,
              rooms: [...current.rooms, ...next.rooms],
              occupied_rooms: [
                ...(current.occupied_rooms || []),
                ...(next.occupied_rooms || []),
              ],
              empty_rooms: [
                ...(current.empty_rooms || []),
                ...(next.empty_rooms || []),
              ],
            }
          : next
      );
      setExpandSearch(nextExpand);
      setView("find");
    } catch (error) {
      showBanner(error.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function showAllRooms(page = 1) {
    setBusy(true);
    try {
      await loadRooms(token, page);
      setView("all");
    } finally {
      setBusy(false);
    }
  }

  async function loadMore() {
    if (view === "find") {
      const pagination = recommendations?.pagination;
      if (!pagination || !pagination.has_more) return;
      await findRooms(expandSearch, pagination.page + 1, true);
    } else {
      const pagination = listing?.pagination;
      if (!pagination || !pagination.has_more) return;
      await loadRooms(token, pagination.page + 1, true);
    }
  }

  async function joinRoom(roomId) {
    setBusy(true);
    try {
      const filters = {
        strict_max_rent: values.strict_max_rent || null,
        required_room_type: values.required_room_type || null,
        no_smoking: Boolean(values.no_smoking),
      };
      await request(`/rooms/${roomId}/join`, {
        method: "POST",
        token,
        body: filters,
      });
      await loadAccount(token);
      await loadRooms(token);
      setRecommendations(null);
      setView("dashboard");
      showBanner("Successfully joined the room!", "success");
    } catch (error) {
      showBanner(error.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirmLeave() {
    setBusy(true);
    try {
      if (account?.current_room) {
        await request(`/rooms/${account.current_room.room_id}/leave`, {
          method: "POST",
          token,
        });
      } else {
        await request("/me/leave", { method: "POST", token });
      }
      setShowLeaveConfirm(false);
      await loadAccount(token);
      await loadRooms(token);
      setView("all");
      showBanner("You have left the room.", "info");
    } catch (error) {
      showBanner(error.message, "error");
    } finally {
      setBusy(false);
    }
  }

  const hasRoom = Boolean(account?.current_room);

  return (
    <main>
      <header className="page-header">
        <div className="brand-bar">
          <div>
            <h1>Intelligent Roommate Matching</h1>
            <p className="muted">
              Filter by compulsory eligibility rules and discover compatible
              roommates using our lifestyle ensemble.
            </p>
          </div>
          {token && (
            <div className="user-nav">
              <span className="user-email-badge">
                👤 {account?.email || "User"}
              </span>
              <button
                className="secondary small-btn"
                onClick={signOut}
                disabled={busy}
              >
                Sign out
              </button>
            </div>
          )}
        </div>

        {token && (
          <nav className="tab-nav">
            <button
              className={`tab-btn ${view === "dashboard" ? "active" : ""}`}
              onClick={() => setView("dashboard")}
            >
              Dashboard {hasRoom && "🏠"}
            </button>
            {!hasRoom && (
              <button
                className={`tab-btn ${view === "find" ? "active" : ""}`}
                onClick={() => {
                  if (!recommendations) {
                    findRooms(false);
                  } else {
                    setView("find");
                  }
                }}
              >
                Find Rooms
              </button>
            )}
            <button
              className={`tab-btn ${view === "all" ? "active" : ""}`}
              onClick={() => showAllRooms()}
            >
              All Rooms Directory
            </button>
            <button
              className={`tab-btn ${view === "profile" ? "active" : ""}`}
              onClick={() => setView("profile")}
            >
              My Profile {!account?.has_profile && "⚠️"}
            </button>
          </nav>
        )}
      </header>

      {message && (
        <div className={`message-banner ${messageType}`}>{message}</div>
      )}

      {/* Auth Screen */}
      {!token && (
        <section className="card auth-card">
          <div className="auth-tabs">
            <button
              className={`auth-tab ${authMode === "login" ? "active" : ""}`}
              onClick={() => setAuthMode("login")}
            >
              Login
            </button>
            <button
              className={`auth-tab ${authMode === "register" ? "active" : ""}`}
              onClick={() => setAuthMode("register")}
            >
              Create Account
            </button>
          </div>
          <form className="auth-form" onSubmit={authenticate}>
            <h2>
              {authMode === "register"
                ? "Create Your Account"
                : "Welcome Back"}
            </h2>
            <div className="stack">
              <label htmlFor="email">
                <span>Email Address</span>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  placeholder="e.g. user@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </label>
              <label htmlFor="password">
                <span>Password (min. 8 characters)</span>
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                />
              </label>
            </div>
            <div className="row auth-actions">
              <button className="primary" type="submit" disabled={busy}>
                {busy
                  ? "Processing..."
                  : authMode === "register"
                  ? "Register"
                  : "Login"}
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => setView("all")}
              >
                Browse Public Directory
              </button>
            </div>
          </form>
        </section>
      )}

      {/* DASHBOARD VIEW */}
      {token && view === "dashboard" && (
        <section className="dashboard-container">
          {hasRoom ? (
            <div className="card current-room-card">
              <div className="card-head">
                <div>
                  <span className="tag">Active Membership</span>
                  <h2>Your Current Accommodation</h2>
                </div>
                <button
                  className="danger-btn"
                  onClick={() => setShowLeaveConfirm(true)}
                  disabled={busy}
                >
                  Leave Room
                </button>
              </div>
              <p className="muted">
                You belong to this room. You cannot join other rooms unless you
                first leave this room.
              </p>
              <RoomCard
                room={account.current_room}
                busy={busy}
                onJoin={joinRoom}
                allowJoin={false}
                onOpenDetails={setActiveRoomDetail}
              />
            </div>
          ) : (
            <div className="card welcome-card">
              <h2>Welcome to Roommate Matching!</h2>
              <p className="muted">
                You haven't joined a room yet. Complete your profile and use our
                matching engine to find suitable roommates.
              </p>

              {!account?.has_profile && (
                <div className="profile-alert">
                  <span>⚠️ You haven't set up your lifestyle profile yet.</span>
                  <button
                    className="primary small-btn"
                    onClick={() => setView("profile")}
                  >
                    Setup Profile
                  </button>
                </div>
              )}

              {account?.has_profile && (
                <div className="profile-summary-box">
                  <h4>Your Preferences Summary</h4>
                  <div className="chips">
                    <span className="chip">
                      📍 Location: <b>{values.location || "Any"}</b>
                    </span>
                    <span className="chip">
                      💰 Budget:{" "}
                      <b>
                        ₹{values.budget_min?.toLocaleString()} - ₹
                        {values.budget_max?.toLocaleString()}
                      </b>
                    </span>
                    <span className="chip">
                      🛏️ Type: <b>{values.room_type_preference || "Any"}</b>
                    </span>
                    <span className="chip">
                      🌙 Sleep: <b>{values.sleep_schedule || "Flexible"}</b>
                    </span>
                  </div>
                </div>
              )}

              <div className="quick-actions">
                <button
                  className="primary"
                  onClick={() => findRooms(false)}
                  disabled={busy || !account?.has_profile}
                >
                  🔍 Find Matching Rooms
                </button>
                <button
                  className="secondary"
                  onClick={() => showAllRooms()}
                  disabled={busy}
                >
                  📂 Browse All Rooms
                </button>
                <button
                  className="secondary"
                  onClick={() => setView("profile")}
                  disabled={busy}
                >
                  ✏️ Edit Profile
                </button>
              </div>
            </div>
          )}
        </section>
      )}

      {/* FIND ROOMS / RECOMMENDATIONS VIEW */}
      {token && view === "find" && (
        <section className="find-view">
          <div className="card filters-card">
            <div className="card-head">
              <div>
                <h2>Find Compatible Rooms</h2>
                <p className="muted">
                  Strict constraints are strictly filtered. Eligible occupied
                  rooms are ranked by our ML compatibility ensemble.
                </p>
              </div>
              <button
                className="primary"
                onClick={() => findRooms(expandSearch)}
                disabled={busy}
              >
                {busy ? "Searching..." : "Apply & Search"}
              </button>
            </div>

            {schema && (
              <fieldset>
                <legend>Optional Hard Constraints (Strict Overrides)</legend>
                <div className="grid">
                  {schema.filter_fields.map((field) => (
                    <Field
                      key={field.key}
                      field={field}
                      value={values[field.key]}
                      onChange={(value) => update(field.key, value)}
                    />
                  ))}
                </div>
              </fieldset>
            )}

            <div className="search-expansion-bar">
              <label className="check">
                <input
                  type="checkbox"
                  checked={expandSearch}
                  onChange={(e) => {
                    const nextVal = e.target.checked;
                    setExpandSearch(nextVal);
                    findRooms(nextVal);
                  }}
                />
                <span>
                  Expand Search: Include nearby &amp; alternative locations if
                  none found in {values.location || "selected location"}
                </span>
              </label>
            </div>
          </div>

          {recommendations && (
            <div className="results-container">
              <div className="results-summary">
                <div className="chips">
                  {recommendations.summary.map((item) => (
                    <span className="chip" key={item.label}>
                      {item.label}: <b>{item.value}</b>
                    </span>
                  ))}
                  {expandSearch && (
                    <span className="chip highlight">
                      Expanded Search Active
                    </span>
                  )}
                </div>
              </div>

              {recommendations.notice && (
                <div className="notice-banner">{recommendations.notice}</div>
              )}

              {/* 1. Occupied Rooms with Compatibility Scores */}
              <div className="section-block">
                <h3>
                  Recommended Matches with Roommates (
                  {recommendations.occupied_rooms?.length || 0})
                </h3>
                <p className="muted">
                  Rooms with existing occupants evaluated with our Random Forest,
                  K-Means, and Cosine similarity ensemble.
                </p>
                {(!recommendations.occupied_rooms ||
                  recommendations.occupied_rooms.length === 0) ? (
                  <p className="muted empty-box">
                    No occupied rooms match all compulsory criteria in this
                    location. Check available empty rooms below or try expanding
                    your search.
                  </p>
                ) : (
                  <div className="rooms">
                    {recommendations.occupied_rooms.map((room) => (
                      <RoomCard
                        key={room.room_id}
                        room={room}
                        busy={busy}
                        onJoin={joinRoom}
                        allowJoin={!hasRoom}
                        onOpenDetails={setActiveRoomDetail}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* 2. Available Empty Rooms */}
              <div className="section-block empty-rooms-section">
                <h3>
                  Available Empty Rooms (
                  {recommendations.empty_rooms?.length || 0})
                </h3>
                <p className="muted">
                  These rooms meet all your budget, location, and type
                  requirements. No roommates currently reside here, so no
                  artificial compatibility score is applied.
                </p>
                {(!recommendations.empty_rooms ||
                  recommendations.empty_rooms.length === 0) ? (
                  <p className="muted empty-box">
                    No empty rooms currently available matching these filters.
                  </p>
                ) : (
                  <div className="rooms">
                    {recommendations.empty_rooms.map((room) => (
                      <RoomCard
                        key={room.room_id}
                        room={room}
                        busy={busy}
                        onJoin={joinRoom}
                        allowJoin={!hasRoom}
                        onOpenDetails={setActiveRoomDetail}
                      />
                    ))}
                  </div>
                )}
              </div>

              {recommendations.pagination?.has_more && (
                <div className="load-more-row">
                  <button
                    className="secondary"
                    onClick={loadMore}
                    disabled={busy}
                  >
                    Load More Rooms
                  </button>
                </div>
              )}
            </div>
          )}
        </section>
      )}

      {/* ALL ROOMS DIRECTORY VIEW */}
      {view === "all" && (
        <section className="directory-view card">
          <div className="card-head">
            <div>
              <h2>Complete Room Directory</h2>
              <p className="muted">
                Browse all accommodation listings. Rooms that do not meet your
                criteria are marked with explicit eligibility reasons.
              </p>
            </div>
            {token && !hasRoom && (
              <button
                className="primary small-btn"
                onClick={() => findRooms(false)}
                disabled={busy}
              >
                🔍 Find My Best Matches
              </button>
            )}
          </div>

          {listing && (
            <>
              <div className="chips">
                {listing.summary.map((item) => (
                  <span className="chip" key={item.label}>
                    {item.label}: <b>{item.value}</b>
                  </span>
                ))}
              </div>

              <div className="rooms">
                {listing.rooms.map((room) => (
                  <RoomCard
                    key={room.room_id}
                    room={room}
                    busy={busy}
                    onJoin={joinRoom}
                    allowJoin={Boolean(token) && !hasRoom}
                    onOpenDetails={setActiveRoomDetail}
                  />
                ))}
              </div>

              {listing.pagination?.has_more && (
                <div className="load-more-row">
                  <button
                    className="secondary"
                    onClick={loadMore}
                    disabled={busy}
                  >
                    Load More Rooms
                  </button>
                </div>
              )}
            </>
          )}
        </section>
      )}

      {/* PROFILE VIEW */}
      {token && view === "profile" && schema && (
        <section className="card profile-card">
          <div className="card-head">
            <div>
              <h2>Your Lifestyle &amp; Preferences Profile</h2>
              <p className="muted">
                Preferences marked with compulsory criteria are used as hard
                filters. Lifestyle habits are fed to the ML compatibility
                models.
              </p>
            </div>
            <button
              className="primary"
              onClick={() => saveProfile(true)}
              disabled={busy}
            >
              {busy ? "Saving..." : "Save Profile"}
            </button>
          </div>

          {schema.profile_groups.map((group) => (
            <fieldset key={group.title}>
              <legend>
                {group.title}{" "}
                {group.title === "Budget" || group.title === "Basics"
                  ? "(Compulsory Constraints)"
                  : "(Lifestyle Preferences)"}
              </legend>
              <div className="grid">
                {group.fields.map((field) => (
                  <Field
                    key={field.key}
                    field={field}
                    value={values[field.key]}
                    onChange={(value) => update(field.key, value)}
                  />
                ))}
              </div>
            </fieldset>
          ))}

          <fieldset>
            <legend>Strict Filtering Overrides</legend>
            <div className="grid">
              {schema.filter_fields.map((field) => (
                <Field
                  key={field.key}
                  field={field}
                  value={values[field.key]}
                  onChange={(value) => update(field.key, value)}
                />
              ))}
            </div>
          </fieldset>

          <div className="row profile-actions">
            <button
              className="primary"
              onClick={() => saveProfile(true)}
              disabled={busy}
            >
              Save Profile
            </button>
            {!hasRoom && (
              <button
                className="secondary"
                onClick={() => findRooms(false)}
                disabled={busy}
              >
                Save &amp; Find Rooms
              </button>
            )}
          </div>
        </section>
      )}

      {/* Room Detail Modal */}
      <RoomDetailModal
        room={activeRoomDetail}
        onClose={() => setActiveRoomDetail(null)}
        onJoin={joinRoom}
        allowJoin={Boolean(token) && !hasRoom}
        busy={busy}
      />

      {/* Leave Confirmation Modal */}
      <ConfirmLeaveModal
        isOpen={showLeaveConfirm}
        onClose={() => setShowLeaveConfirm(false)}
        onConfirm={handleConfirmLeave}
        busy={busy}
      />
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
