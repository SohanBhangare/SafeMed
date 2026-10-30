import { useState } from "react";

export default function AuthModal({ isOpen, onClose, currentUser, onLoginSuccess, onLogout }) {
  const [tab, setTab] = useState("login"); // "login" | "register"
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("clinician");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleLogin = async (e, customUser, customPass) => {
    if (e) e.preventDefault();
    setError("");
    setLoading(true);

    const u = customUser || username;
    const p = customPass || password;

    try {
      const res = await fetch("http://localhost:8000/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: u, password: p }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Authentication failed.");
      }
      localStorage.setItem("safemed_token", data.token);
      localStorage.setItem("safemed_user", JSON.stringify(data.user));
      onLoginSuccess(data.user, data.token);
      onClose();
    } catch (err) {
      setError(err.message || "Failed to log in.");
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch("http://localhost:8000/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          password,
          email,
          full_name: fullName,
          role,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Registration failed.");
      }
      localStorage.setItem("safemed_token", data.token);
      localStorage.setItem("safemed_user", JSON.stringify(data.user));
      onLoginSuccess(data.user, data.token);
      onClose();
    } catch (err) {
      setError(err.message || "Failed to register.");
    } finally {
      setLoading(false);
    }
  };

  const quickLogin = (u, p) => {
    setUsername(u);
    setPassword(p);
    handleLogin(null, u, p);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card auth-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-group">
            <span className="modal-badge-icon">🛡️</span>
            <div>
              <h3>User Authentication</h3>
              <p className="modal-subtitle">Secure clinical access & profile management</p>
            </div>
          </div>
          <button className="btn-modal-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        {currentUser ? (
          <div className="auth-logged-in-box">
            <div className="user-avatar-large">
              {currentUser.full_name ? currentUser.full_name.charAt(0).toUpperCase() : "U"}
            </div>
            <h4>{currentUser.full_name || currentUser.username}</h4>
            <span className="user-role-tag">{currentUser.role || "Clinical Pharmacologist"}</span>
            <p className="user-email-text">{currentUser.email}</p>

            <div className="auth-actions">
              <button
                className="btn-primary"
                onClick={onClose}
              >
                Continue Working
              </button>
              <button
                className="btn-secondary"
                onClick={() => {
                  onLogout();
                  onClose();
                }}
              >
                Sign Out
              </button>
            </div>
          </div>
        ) : (
          <div className="auth-body">
            <div className="auth-tabs">
              <button
                type="button"
                className={`auth-tab ${tab === "login" ? "active" : ""}`}
                onClick={() => { setTab("login"); setError(""); }}
              >
                Clinician Sign In
              </button>
              <button
                type="button"
                className={`auth-tab ${tab === "register" ? "active" : ""}`}
                onClick={() => { setTab("register"); setError(""); }}
              >
                Register New Account
              </button>
            </div>

            {error && <div className="auth-error-alert">{error}</div>}

            {tab === "login" ? (
              <form onSubmit={handleLogin} className="auth-form">
                <div className="form-group">
                  <label htmlFor="login-username">Username or Email</label>
                  <input
                    id="login-username"
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="e.g. doctor or dr.hayes@safemed-clinical.org"
                    required
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="login-password">Password</label>
                  <input
                    id="login-password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter password"
                    required
                  />
                </div>

                <button type="submit" className="btn-primary auth-submit-btn" disabled={loading}>
                  {loading ? "Authenticating…" : "Sign In"}
                </button>

                <div className="demo-accounts-section">
                  <span className="demo-accounts-label">Demo Quick Sign-In:</span>
                  <div className="demo-buttons">
                    <button
                      type="button"
                      className="btn-demo-pill"
                      onClick={() => quickLogin("doctor", "doctor123")}
                    >
                      🩺 Dr. Hayes (Physician)
                    </button>
                    <button
                      type="button"
                      className="btn-demo-pill"
                      onClick={() => quickLogin("pharmacist", "rx123")}
                    >
                      💊 Dr. Rostova (Pharmacist)
                    </button>
                    <button
                      type="button"
                      className="btn-demo-pill"
                      onClick={() => quickLogin("demo", "demo123")}
                    >
                      🔬 Demo Researcher
                    </button>
                  </div>
                </div>
              </form>
            ) : (
              <form onSubmit={handleRegister} className="auth-form">
                <div className="form-row-2">
                  <div className="form-group">
                    <label htmlFor="reg-name">Full Name & Title</label>
                    <input
                      id="reg-name"
                      type="text"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      placeholder="e.g. Dr. Jane Smith, MD"
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="reg-role">Clinical Role</label>
                    <select
                      id="reg-role"
                      value={role}
                      onChange={(e) => setRole(e.target.value)}
                    >
                      <option value="clinician">Attending Physician / Clinician</option>
                      <option value="pharmacist">Clinical Pharmacist / PharmD</option>
                      <option value="researcher">Clinical Researcher / Fellow</option>
                    </select>
                  </div>
                </div>

                <div className="form-group">
                  <label htmlFor="reg-email">Professional Email</label>
                  <input
                    id="reg-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@hospital.org"
                    required
                  />
                </div>

                <div className="form-row-2">
                  <div className="form-group">
                    <label htmlFor="reg-username">Username</label>
                    <input
                      id="reg-username"
                      type="text"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder="e.g. jsmith"
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="reg-password">Password</label>
                    <input
                      id="reg-password"
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Min 4 characters"
                      required
                    />
                  </div>
                </div>

                <button type="submit" className="btn-primary auth-submit-btn" disabled={loading}>
                  {loading ? "Registering…" : "Create Clinical Account"}
                </button>
              </form>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
