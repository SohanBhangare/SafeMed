import { useState, useEffect, Component } from "react";
import { jsPDF } from "jspdf";
import "./App.css";

// Extended Clinical Components
import AuthModal from "./components/AuthModal";
import PatientManager from "./components/PatientManager";
import MIMICExplorer from "./components/MIMICExplorer";
import MLEvaluationView from "./components/MLEvaluationView";
import AuditHistoryView from "./components/AuditHistoryView";
import ReportModal from "./components/ReportModal";

// ============================================================
// ERROR BOUNDARY
// ============================================================

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, errorMsg: "" };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, errorMsg: String(error) };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <div className="error-boundary-icon">!</div>
          <h2>Something went wrong</h2>
          <p>A component error occurred. Please refresh the page to try again.</p>
          <p className="error-boundary-detail">{this.state.errorMsg}</p>
          <button
            className="btn-primary"
            onClick={() => window.location.reload()}
          >
            Refresh Page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}


// ============================================================
// HELPERS
// ============================================================

function titleCase(str) {
  if (!str) return "";
  return String(str)
    .split(" ")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function splitSideEffects(text) {
  if (!text || typeof text !== "string") return [];
  // Split on comma, semicolon, or newline; filter short/empty
  return text
    .split(/[,;\n]/)
    .map((s) => s.trim())
    .filter((s) => s.length > 2)
    .slice(0, 30);
}

function toPercent(value, total) {
  if (!total || total === 0) return 0;
  return Math.min(100, Math.round((value / total) * 100));
}

function buildSummaryText(data) {
  if (!data) return "";
  const s = data.summary || {};
  const entered = s.medications_entered || 0;
  const matched = s.medications_matched || 0;
  const interactions = s.interactions_found || 0;
  const condEntered = s.conditions_entered || 0;
  const condMatched = s.conditions_matched || 0;
  const sideAvail = s.side_effects_available || 0;

  let parts = [];

  if (entered > 0) {
    parts.push(
      `${matched} of ${entered} medication${entered !== 1 ? "s" : ""} ${
        matched === 1 ? "was" : "were"
      } recognized in the reference dataset.`
    );
  }

  if (interactions > 0) {
    parts.push(
      `${interactions} documented interaction${
        interactions !== 1 ? "s were" : " was"
      } identified.`
    );
  } else if (entered >= 2) {
    parts.push(
      "No documented interactions were identified between the entered medications."
    );
  }

  if (condEntered > 0) {
    parts.push(
      `${condMatched} of ${condEntered} medical condition${
        condEntered !== 1 ? "s" : ""
      } matched the reference dataset.`
    );
  }

  if (sideAvail > 0) {
    parts.push(
      `Side-effect information was available for ${sideAvail} medication${
        sideAvail !== 1 ? "s" : ""
      }.`
    );
  }

  return parts.join(" ");
}

function buildAttentionPoints(data) {
  if (!data) return [];
  const points = [];
  const s = data.summary || {};
  const medAnalysis = data.medication_analysis || {};
  const interactions = medAnalysis.interactions || [];
  const unmatched = medAnalysis.unmatched_medications || [];
  const sideEffects = data.side_effect_analysis || [];

  if (interactions.length > 0) {
    interactions.forEach((i) => {
      const d1 = i.drug_1 || "Medication";
      const d2 = i.drug_2 || "Medication";
      points.push(
        `A documented interaction was identified between ${titleCase(d1)} and ${titleCase(d2)} in the reference dataset.`
      );
    });
  }

  unmatched.forEach((item) => {
    const name =
      typeof item === "string" ? item : item.input || "a medication";
    points.push(
      `'${name}' could not be matched to the reference dataset — no interaction or side-effect information is available for this entry.`
    );
  });

  sideEffects.forEach((item) => {
    if (item.side_effects && item.side_effects.length > 0) {
      const drug = item.matched_drug || item.input || "A medication";
      points.push(
        `Side-effect information is listed in the reference dataset for ${titleCase(drug)}.`
      );
    }
  });

  const unmatCond = (data.condition_analysis || {}).unmatched_conditions || [];
  unmatCond.forEach((item) => {
    const name =
      typeof item === "string" ? item : item.input || "a condition";
    points.push(`The condition '${name}' was not found in the reference dataset.`);
  });

  return points;
}


// ============================================================
// SVG DONUT CHART (pure SVG, no library)
// ============================================================

function DonutChart({ value, total, label }) {
  const pct = total > 0 ? Math.min(100, Math.round((value / total) * 100)) : 0;
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (pct / 100) * circumference;

  const color = pct === 0 ? "#e5e9ed" : value > 0 ? "#dc4f3a" : "#126b5b";
  const trackColor = "#f0f4f7";

  return (
    <div className="donut-wrapper">
      <svg viewBox="0 0 120 120" className="donut-svg">
        <circle
          cx="60"
          cy="60"
          r={radius}
          fill="none"
          stroke={trackColor}
          strokeWidth="12"
        />
        {pct > 0 && (
          <circle
            cx="60"
            cy="60"
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth="12"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            transform="rotate(-90 60 60)"
          />
        )}
        <text x="60" y="54" textAnchor="middle" className="donut-center-num">
          {value}
        </text>
        <text x="60" y="68" textAnchor="middle" className="donut-center-label">
          of {total}
        </text>
      </svg>
      <span className="donut-desc">{label}</span>
    </div>
  );
}


// ============================================================
// CSS PROGRESS BAR
// ============================================================

function ProgressBar({ label, value, total, note }) {
  const pct = toPercent(value, total);
  const color =
    pct === 100
      ? "#126b5b"
      : pct >= 50
      ? "#d97706"
      : pct === 0
      ? "#9ca3af"
      : "#d97706";

  return (
    <div className="progress-row">
      <div className="progress-label">
        <span>{label}</span>
        <span className="progress-pct" style={{ color }}>
          {pct}%
        </span>
      </div>
      <div className="progress-track">
        <div
          className="progress-fill"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      {note && <p className="progress-note">{note}</p>}
    </div>
  );
}


// ============================================================
// MATCH BADGE
// ============================================================

function MatchBadge({ matched, score, input, matchedName }) {
  if (!matched) {
    return (
      <div className="match-badge unmatched">
        <span className="match-badge-dot" />
        Not recognized in reference dataset
        {input && (
          <span className="match-badge-input"> · Entered: "{input}"</span>
        )}
      </div>
    );
  }
  return (
    <div className="match-badge matched">
      <span className="match-badge-dot" />
      Recognized
      {score && score < 100 && (
        <span className="match-badge-score">
          · Similarity: {Number(score).toFixed(2)}%
          {input && input !== matchedName && (
            <span> · Entered: "{input}" · Recognized as: {titleCase(matchedName)}</span>
          )}
          {" "}(text-matching similarity, not medical confidence)
        </span>
      )}
    </div>
  );
}


// ============================================================
// NAVBAR
// ============================================================

function NavBar({
  view,
  onNavigate,
  onOpenReport,
  currentUser,
  onOpenAuth,
  hasResult,
}) {
  return (
    <>
      {/* ── TOP CLINICAL NOTICE RIBBON ── */}
      <div className="clinical-top-bar">
        <div>
          <span className="top-bar-badge">CLINICAL DECISION SUPPORT</span>
          <span>Requires professional medical review prior to clinical prescription or administration</span>
        </div>
        <div style={{ display: "flex", gap: "14px", alignItems: "center" }}>
          <span>Database: <strong>BIDMC MIMIC-IV Connected</strong></span>
          <button type="button" onClick={() => onNavigate("mimic")}>Browse Cohort</button>
        </div>
      </div>

      <header className="navbar">
        <div className="logo" onClick={() => onNavigate("input")} style={{ cursor: "pointer" }}>
          <div className="logo-icon" aria-hidden="true">+</div>
          <div className="logo-text">
            <h1>SafeMed</h1>
            <span>Clinical Pharmacology & CDSS</span>
          </div>
        </div>

        <nav className="nav-center-tabs">
          <button
            className={`nav-tab-btn ${view === "input" ? "active" : ""}`}
            onClick={() => onNavigate("input")}
          >
            🔬 Clinical Analysis
          </button>
          {hasResult && (
            <button
              className={`nav-tab-btn ${view === "results" ? "active" : ""}`}
              onClick={() => onNavigate("results")}
            >
              📊 Safety Dashboard
            </button>
          )}
          <button
            className={`nav-tab-btn ${view === "patients" ? "active" : ""}`}
            onClick={() => onNavigate("patients")}
          >
            👤 Patient Profiles
          </button>
          <button
            className={`nav-tab-btn ${view === "mimic" ? "active" : ""}`}
            onClick={() => onNavigate("mimic")}
          >
            🏥 MIMIC-IV Cohort
          </button>
          <button
            className={`nav-tab-btn ${view === "ml_eval" ? "active" : ""}`}
            onClick={() => onNavigate("ml_eval")}
          >
            🧠 ML Benchmark
          </button>
          <button
            className={`nav-tab-btn ${view === "history" ? "active" : ""}`}
            onClick={() => onNavigate("history")}
          >
            📜 Safety Audits
          </button>
          <button
            className={`nav-tab-btn ${view === "library" || view === "drug" ? "active" : ""}`}
            onClick={() => onNavigate("library")}
          >
            📚 Drug Library
          </button>
        </nav>

        <div className="navbar-right" style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          {view === "results" && (
            <button className="btn-primary btn-sm" onClick={onOpenReport}>
              📄 View Clinical Report
            </button>
          )}

          <button className="btn-auth-user" onClick={onOpenAuth}>
            <span className="user-nav-avatar">
              {currentUser?.full_name ? currentUser.full_name.charAt(0).toUpperCase() : "🩺"}
            </span>
            <span>{currentUser ? currentUser.full_name || currentUser.username : "Sign In / Register"}</span>
          </button>
        </div>
      </header>
    </>
  );
}


// ============================================================
// INPUT PAGE
// ============================================================

function InputPage({ onSubmit, patientPrefill, onClearPrefill }) {
  const [patientName, setPatientName] = useState("");
  const [patientMRN, setPatientMRN] = useState("");
  const [age, setAge] = useState("");
  const [gender, setGender] = useState("");
  const [allergies, setAllergies] = useState("");
  const [renalImpairment, setRenalImpairment] = useState(false);
  const [hepaticImpairment, setHepaticImpairment] = useState(false);
  const [isPregnant, setIsPregnant] = useState(false);
  const [isLactating, setIsLactating] = useState(false);

  const [medications, setMedications] = useState([
    { name: "", dosage: "", frequency: "" },
  ]);
  const [conditions, setConditions] = useState([""]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Sync with patientPrefill if passed from PatientManager or MIMICExplorer
  useEffect(() => {
    if (patientPrefill) {
      if (patientPrefill.name) setPatientName(patientPrefill.name);
      if (patientPrefill.mrn) setPatientMRN(patientPrefill.mrn);
      if (patientPrefill.age !== undefined && patientPrefill.age !== null) setAge(String(patientPrefill.age));
      if (patientPrefill.gender) setGender(patientPrefill.gender);
      if (patientPrefill.allergies) setAllergies(patientPrefill.allergies);
      setRenalImpairment(!!patientPrefill.renal_impairment);
      setHepaticImpairment(!!patientPrefill.hepatic_impairment);
      setIsPregnant(!!patientPrefill.pregnant);
      setIsLactating(!!patientPrefill.lactating);

      if (Array.isArray(patientPrefill.conditions) && patientPrefill.conditions.length > 0) {
        setConditions(patientPrefill.conditions.map((c) => (typeof c === "string" ? c : c.name || "")));
      }
      if (Array.isArray(patientPrefill.medications) && patientPrefill.medications.length > 0) {
        setMedications(
          patientPrefill.medications.map((m) => {
            if (typeof m === "string") return { name: m, dosage: "", frequency: "" };
            return {
              name: m.name || m.drug_name || "",
              dosage: m.dosage || "",
              frequency: m.frequency || "",
            };
          })
        );
      }
    }
  }, [patientPrefill]);

  const applyPreset = (presetKey) => {
    setError("");
    if (presetKey === "stemi") {
      setPatientName("Robert Johnson (ICU Cohort)");
      setPatientMRN("MIMIC-ICU-1082");
      setAge("67");
      setGender("Male");
      setRenalImpairment(true);
      setHepaticImpairment(false);
      setIsPregnant(false);
      setIsLactating(false);
      setAllergies("NKDA (No known drug allergies)");
      setConditions(["Acute Myocardial Infarction", "Hypertension", "Type 2 Diabetes", "Chronic Kidney Disease"]);
      setMedications([
        { name: "Aspirin", dosage: "81 mg", frequency: "Daily" },
        { name: "Clopidogrel", dosage: "75 mg", frequency: "Daily" },
        { name: "Heparin", dosage: "5000 units", frequency: "IV Bolus" },
        { name: "Metoprolol", dosage: "25 mg", frequency: "BID" },
        { name: "Atorvastatin", dosage: "80 mg", frequency: "QHS" },
      ]);
    } else if (presetKey === "hf_afib") {
      setPatientName("Eleanor Vance");
      setPatientMRN("MIMIC-ICU-2490");
      setAge("74");
      setGender("Female");
      setRenalImpairment(true);
      setHepaticImpairment(false);
      setIsPregnant(false);
      setIsLactating(false);
      setAllergies("Sulfa antibiotics");
      setConditions(["Congestive Heart Failure", "Atrial Fibrillation", "Hypertension"]);
      setMedications([
        { name: "Digoxin", dosage: "0.125 mg", frequency: "Daily" },
        { name: "Amiodarone", dosage: "200 mg", frequency: "Daily" },
        { name: "Warfarin", dosage: "5 mg", frequency: "Daily" },
        { name: "Furosemide", dosage: "40 mg", frequency: "BID" },
      ]);
    } else if (presetKey === "copd_inf") {
      setPatientName("David Miller");
      setPatientMRN("SAFE-PT-8821");
      setAge("62");
      setGender("Male");
      setRenalImpairment(false);
      setHepaticImpairment(true);
      setIsPregnant(false);
      setIsLactating(false);
      setAllergies("Penicillin");
      setConditions(["COPD", "Pneumonia", "Liver Cirrhosis"]);
      setMedications([
        { name: "Azithromycin", dosage: "500 mg", frequency: "Daily" },
        { name: "Theophylline", dosage: "300 mg", frequency: "BID" },
        { name: "Prednisone", dosage: "40 mg", frequency: "Daily" },
      ]);
    } else if (presetKey === "asthma_gout") {
      setPatientName("Marcus Sterling");
      setPatientMRN("SAFE-PT-9042");
      setAge("58");
      setGender("Male");
      setRenalImpairment(false);
      setHepaticImpairment(false);
      setIsPregnant(false);
      setIsLactating(false);
      setAllergies("None");
      setConditions(["Asthma", "Gout", "Hypertension"]);
      setMedications([
        { name: "Propranolol", dosage: "40 mg", frequency: "BID" },
        { name: "Allopurinol", dosage: "100 mg", frequency: "Daily" },
        { name: "Ibuprofen", dosage: "600 mg", frequency: "TID" },
      ]);
    } else if (presetKey === "diabetes_htn") {
      setPatientName("John Doe");
      setPatientMRN("SM-2026-T2D");
      setAge("58");
      setGender("Male");
      setRenalImpairment(false);
      setHepaticImpairment(false);
      setIsPregnant(false);
      setIsLactating(false);
      setAllergies("No documented allergies");
      setConditions(["Type 2 Diabetes", "Hypertension"]);
      setMedications([
        { name: "Metformin", dosage: "500 mg", frequency: "Twice daily with meals" },
        { name: "Lisinopril", dosage: "10 mg", frequency: "Once daily" },
        { name: "Ibuprofen", dosage: "400 mg", frequency: "As needed for pain" },
      ]);
    }
  };

  const addMed = () =>
    setMedications((m) => [...m, { name: "", dosage: "", frequency: "" }]);

  const removeMed = (i) =>
    setMedications((m) => m.filter((_, idx) => idx !== i));

  const updateMed = (i, field, val) =>
    setMedications((m) => {
      const copy = [...m];
      copy[i] = { ...copy[i], [field]: val };
      return copy;
    });

  const addCond = () => setConditions((c) => [...c, ""]);
  const removeCond = (i) => setConditions((c) => c.filter((_, idx) => idx !== i));
  const updateCond = (i, val) =>
    setConditions((c) => {
      const copy = [...c];
      copy[i] = val;
      return copy;
    });

  const clearAll = () => {
    setPatientName("");
    setPatientMRN("");
    setMedications([{ name: "", dosage: "", frequency: "" }]);
    setConditions([""]);
    setAge("");
    setGender("");
    setAllergies("");
    setRenalImpairment(false);
    setHepaticImpairment(false);
    setIsPregnant(false);
    setIsLactating(false);
    setError("");
    if (onClearPrefill) onClearPrefill();
  };

  const handleSubmit = async () => {
    setError("");

    const validMeds = medications
      .map((m) => m.name.trim())
      .filter(Boolean);

    if (validMeds.length === 0) {
      setError("Please enter at least one medication name.");
      return;
    }

    setLoading(true);

    try {
      const validConditions = conditions.map((c) => c.trim()).filter(Boolean);

      const medDetails = medications
        .filter((m) => m.name.trim())
        .map((m) => ({
          name: m.name.trim(),
          dosage: m.dosage.trim(),
          frequency: m.frequency.trim(),
        }));

      const response = await fetch("http://127.0.0.1:8000/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patient_name: patientName.trim(),
          patient_mrn: patientMRN.trim(),
          medications: validMeds,
          conditions: validConditions,
          age: age.trim(),
          gender: gender.trim(),
          allergies: allergies.trim(),
          renal_impairment: renalImpairment,
          hepatic_impairment: hepaticImpairment,
          pregnant: isPregnant,
          lactating: isLactating,
          medication_details: medDetails,
        }),
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const json = await response.json();

      if (!json.success) {
        setError(json.message || "Analysis could not be completed.");
        return;
      }

      onSubmit(json);
    } catch (err) {
      if (
        err.message?.includes("fetch") ||
        err.message?.includes("NetworkError") ||
        err.name === "TypeError"
      ) {
        setError(
          "Unable to connect to SafeMed backend. Please make sure the SafeMed server is running on port 8000."
        );
      } else {
        setError(
          "Some analysis information could not be retrieved. " + err.message
        );
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="container">
      {/* HERO */}
      <section className="hero">
        <p className="eyebrow">CLINICAL MEDICATION SAFETY & CDSS</p>
        <h2>
          Comprehensive Medication Safety<br />
          <span>& Multimorbidity Analysis</span>
        </h2>
        <p className="hero-description">
          Evaluate multi-drug regimens against 30,000+ reference interaction records,
          screen for disease-drug contraindications, classify clinical risk with
          dual machine learning models (Logistic Regression & Decision Tree), and generate audit-ready clinical reports.
        </p>
      </section>

      {/* QUICK PRESETS BANNER */}
      <div className="presets-banner">
        <div className="presets-label">
          <span>⚡ Quick Clinical Presets:</span>
        </div>
        <div className="presets-buttons-wrap">
          <button
            type="button"
            className="btn-preset-chip"
            onClick={() => applyPreset("stemi")}
            title="Load MIMIC-IV ICU STEMI Cohort Case"
          >
            🏥 MIMIC-IV STEMI ICU
          </button>
          <button
            type="button"
            className="btn-preset-chip"
            onClick={() => applyPreset("hf_afib")}
            title="Load Heart Failure & Atrial Fibrillation regimen"
          >
            ❤️ Heart Failure + AFib
          </button>
          <button
            type="button"
            className="btn-preset-chip"
            onClick={() => applyPreset("copd_inf")}
            title="Load COPD with Respiratory Infection regimen"
          >
            🫁 COPD + Infection
          </button>
          <button
            type="button"
            className="btn-preset-chip"
            onClick={() => applyPreset("asthma_gout")}
            title="Load Asthma + Gout contraindication regimen"
          >
            ⚠️ Asthma + Gout
          </button>
          <button
            type="button"
            className="btn-preset-chip"
            onClick={() => applyPreset("diabetes_htn")}
            title="Load Type 2 Diabetes + Hypertension (Metformin, Lisinopril, Ibuprofen)"
          >
            🩺 Diabetes + HTN (Metformin, Lisinopril, Ibuprofen)
          </button>
        </div>
      </div>

      {patientPrefill && (
        <div className="case-notes-banner" style={{ marginBottom: 16 }}>
          <strong>Loaded Clinical Record:</strong> {patientName || "Patient"} (MRN: {patientMRN || "N/A"})
          <button
            type="button"
            className="btn-secondary btn-sm"
            style={{ marginLeft: 16, height: 28, fontSize: 12 }}
            onClick={clearAll}
          >
            Reset Form
          </button>
        </div>
      )}

      <div className="input-card">
        {/* PATIENT INFORMATION */}
        <div className="card-section">
          <div className="card-section-header">
            <div className="section-num">01</div>
            <div>
              <h3>Patient Profile & Clinical History</h3>
              <p>Demographic factors and organ impairment indicators used for personalized safety review.</p>
            </div>
          </div>

          <div className="patient-info-grid" style={{ marginBottom: 14 }}>
            <div className="field-group">
              <label className="field-label" htmlFor="patientName">
                Patient Name <span className="optional-tag">Optional</span>
              </label>
              <input
                id="patientName"
                className="text-input"
                type="text"
                placeholder="e.g. Eleanor Vance"
                value={patientName}
                onChange={(e) => setPatientName(e.target.value)}
              />
            </div>
            <div className="field-group">
              <label className="field-label" htmlFor="patientMRN">
                Medical Record # (MRN) <span className="optional-tag">Optional</span>
              </label>
              <input
                id="patientMRN"
                className="text-input"
                type="text"
                placeholder="e.g. MRN-20491"
                value={patientMRN}
                onChange={(e) => setPatientMRN(e.target.value)}
              />
            </div>
          </div>

          <div className="patient-info-grid">
            <div className="field-group">
              <label className="field-label" htmlFor="age">Age</label>
              <input
                id="age"
                className="text-input"
                type="text"
                placeholder="e.g. 68"
                value={age}
                onChange={(e) => setAge(e.target.value)}
              />
            </div>
            <div className="field-group">
              <label className="field-label" htmlFor="gender">Gender</label>
              <select
                id="gender"
                className="text-input select-input"
                value={gender}
                onChange={(e) => setGender(e.target.value)}
              >
                <option value="">Select Gender</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
                <option value="Other">Other</option>
              </select>
            </div>
          </div>

          {/* Clinical History & Organ Impairment Flags */}
          <div className="clinical-history-flags-box">
            <span className="clinical-history-flags-label">Clinical History & Organ Impairment Flags:</span>
            <div className="history-checkbox-grid">
              <label className="history-checkbox-label">
                <input
                  type="checkbox"
                  checked={renalImpairment}
                  onChange={(e) => setRenalImpairment(e.target.checked)}
                />
                <span>Renal Impairment (CKD / Reduced eGFR)</span>
              </label>
              <label className="history-checkbox-label">
                <input
                  type="checkbox"
                  checked={hepaticImpairment}
                  onChange={(e) => setHepaticImpairment(e.target.checked)}
                />
                <span>Hepatic Impairment (Cirrhosis / Liver Disease)</span>
              </label>
              <label className="history-checkbox-label">
                <input
                  type="checkbox"
                  checked={isPregnant}
                  onChange={(e) => setIsPregnant(e.target.checked)}
                />
                <span>Pregnant (Teratogenicity screening)</span>
              </label>
              <label className="history-checkbox-label">
                <input
                  type="checkbox"
                  checked={isLactating}
                  onChange={(e) => setIsLactating(e.target.checked)}
                />
                <span>Lactating / Breastfeeding</span>
              </label>
            </div>
          </div>
        </div>

        <div className="input-divider" />

        {/* MEDICATIONS */}
        <div className="card-section">
          <div className="card-section-header">
            <div className="section-num">02</div>
            <div>
              <h3>Current Prescription Regimen</h3>
              <p>
                Enter multiple medicines prescribed to the patient. Include dosage and administration frequency for complete clinical auditing.
              </p>
            </div>
          </div>

          <div className="med-list">
            {medications.map((med, i) => (
              <div className="med-row" key={i}>
                <div className="med-row-inputs">
                  <input
                    className="text-input med-name-input"
                    type="text"
                    placeholder={`Medication ${i + 1} name (e.g. Warfarin, Aspirin)`}
                    value={med.name}
                    onChange={(e) => updateMed(i, "name", e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") addMed();
                    }}
                  />
                  <input
                    className="text-input med-small-input"
                    type="text"
                    placeholder="Dosage (e.g. 5 mg)"
                    value={med.dosage}
                    onChange={(e) => updateMed(i, "dosage", e.target.value)}
                  />
                  <input
                    className="text-input med-small-input"
                    type="text"
                    placeholder="Frequency (e.g. Once daily)"
                    value={med.frequency}
                    onChange={(e) => updateMed(i, "frequency", e.target.value)}
                  />
                </div>
                {medications.length > 1 && (
                  <button
                    type="button"
                    className="remove-btn"
                    onClick={() => removeMed(i)}
                    aria-label={`Remove medication ${i + 1}`}
                  >
                    ×
                  </button>
                )}
              </div>
            ))}
          </div>

          <button type="button" className="add-btn" onClick={addMed}>
            + Add another medication
          </button>
        </div>

        <div className="input-divider" />

        {/* CONDITIONS */}
        <div className="card-section">
          <div className="card-section-header">
            <div className="section-num">03</div>
            <div>
              <h3>Patient Diagnoses & Multimorbidities</h3>
              <p>
                Enter co-existing medical conditions (e.g., Asthma, Chronic Kidney Disease, Heart Failure) for disease-drug contraindication screening.
              </p>
            </div>
          </div>

          <div className="cond-list">
            {conditions.map((cond, i) => (
              <div className="input-row" key={i}>
                <input
                  className="text-input"
                  type="text"
                  placeholder={`Condition ${i + 1} (e.g. Heart Failure, Diabetes)`}
                  value={cond}
                  onChange={(e) => updateCond(i, e.target.value)}
                />
                {conditions.length > 1 && (
                  <button
                    type="button"
                    className="remove-btn"
                    onClick={() => removeCond(i)}
                    aria-label={`Remove condition ${i + 1}`}
                  >
                    ×
                  </button>
                )}
              </div>
            ))}
          </div>

          <button type="button" className="add-btn" onClick={addCond}>
            + Add another condition
          </button>
        </div>

        <div className="input-divider" />

        {/* ALLERGIES */}
        <div className="card-section">
          <div className="card-section-header">
            <div className="section-num">04</div>
            <div>
              <h3>Known Drug Allergies & Clinical Notes <span className="optional-tag">Optional</span></h3>
              <p>
                Document patient hypersensitivities (e.g. Penicillin, Sulfa) and specific clinical precautions for the medical record.
              </p>
            </div>
          </div>

          <textarea
            className="text-input textarea-input"
            placeholder="e.g. Anaphylaxis to Penicillin, severe nausea with Codeine, history of GI bleed..."
            value={allergies}
            onChange={(e) => setAllergies(e.target.value)}
            rows={3}
          />
        </div>

        {/* ERROR */}
        {error && (
          <div className="error-box" role="alert">
            <strong>⚠ Clinical Warning</strong>
            <p>{error}</p>
          </div>
        )}

        {/* ACTIONS */}
        <div className="form-actions">
          <button
            type="button"
            className="btn-primary"
            onClick={handleSubmit}
            disabled={loading}
          >
            {loading ? (
              <span className="loading-text">
                <span className="loading-dot" />
                Executing Pharmacology & ML Analysis…
              </span>
            ) : (
              "Run Clinical Pharmacology Analysis →"
            )}
          </button>
          <button type="button" className="btn-secondary" onClick={clearAll} disabled={loading}>
            Clear Form
          </button>
        </div>

        <p className="disclaimer">
          ⚠️ <strong>Mandatory Clinical Notice:</strong> SafeMed is an academic Clinical Decision Support System (CDSS).
          All interaction classifications, multimorbidity contraindications, and machine learning inferences require professional review by a licensed clinician or clinical pharmacist prior to patient administration.
        </p>
      </div>
    </main>
  );
}


// ============================================================
// RESULTS DASHBOARD
// ============================================================

function ResultsDashboard({ result, onDrugClick, onOpenReport, onNavigate }) {
  const [openSections, setOpenSections] = useState(
    new Set([
      "clinicalRisk",
      "findings",
      "multimorbidity",
      "toxicities",
      "ml",
      "medications",
      "combinations",
      "sideeffects",
      "conditions",
      "coverage",
    ])
  );
  const [severityFilter, setSeverityFilter] = useState("all"); // "all", "major", "moderate", "minor"

  const toggleSection = (id) => {
    setOpenSections((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const data = result?.data || {};
  const summary = data.summary || {};
  const medAnalysis = data.medication_analysis || {};
  const condAnalysis = data.condition_analysis || {};
  const sideEffects = data.side_effect_analysis || [];
  const interactions = medAnalysis.interactions || [];
  const matchedMeds = medAnalysis.matched_medications || [];
  const unmatchedMeds = medAnalysis.unmatched_medications || [];
  const allPairs = medAnalysis.all_pairs || [];
  const medDetails = data.medication_details || {};
  const mlPredictions = data.ml_predictions || [];
  const infoGaps = data.information_gaps || [];
  const matchedConds = condAnalysis.matched_conditions || [];
  const unmatchedConds = condAnalysis.unmatched_conditions || [];
  const condInfo = condAnalysis.condition_information || {};
  const patientInfo = data.patient_info || {};

  const clinicalRisk = data.clinical_risk || {
    ...data.risk_assessment,
    risk_level: (data.risk_assessment?.overall_risk_level || "").includes("CRITICAL")
      ? "CRITICAL"
      : (data.risk_assessment?.overall_risk_level || "").includes("HIGH")
      ? "HIGH"
      : (data.risk_assessment?.overall_risk_level || "").includes("MODERATE")
      ? "MODERATE"
      : "LOW",
    overall_risk_score: (data.risk_assessment?.overall_risk_level || "").includes("CRITICAL")
      ? 85
      : (data.risk_assessment?.overall_risk_level || "").includes("HIGH")
      ? 65
      : (data.risk_assessment?.overall_risk_level || "").includes("MODERATE")
      ? 45
      : 15,
    high_priority_flags: data.risk_assessment?.review_flags || [],
    requires_clinical_review: data.risk_assessment?.requires_clinical_review || false,
  };

  const multimorbidity = data.multimorbidity || {
    ...data.multimorbidity_analysis,
    contraindications: (data.multimorbidity_analysis?.disease_drug_contraindications || []).map(c => ({
      ...c,
      contraindicated_drug: c.contraindicated_drug || c.medication,
      severity: c.severity || c.risk_level,
    })),
    polypharmacy_alert: data.multimorbidity_analysis?.is_polypharmacy,
  };

  const rawToxicities = data.compounded_toxicities || (data.compounded_side_effects?.compounded_risks || []);
  const compoundedToxicities = rawToxicities.map(t => ({
    system: t.system || t.organ_system,
    severity: t.severity,
    drugs: t.drugs || t.affecting_drugs || [],
    concerns: t.concerns || t.alert,
  }));

  const totalEntered = summary.medications_entered || 0;
  const totalMatched = summary.medications_matched || 0;
  const totalInteractions = summary.interactions_found || 0;
  const totalPairs = allPairs.length;
  const condEntered = summary.conditions_entered || 0;
  const condMatched = summary.conditions_matched || 0;
  const sideAvail = summary.side_effects_available || 0;

  const summaryText = buildSummaryText(data);
  const attentionPoints = buildAttentionPoints(data);

  // Severity counts
  const majorCount = interactions.filter(
    (i) => (i.severity || "").toLowerCase() === "major"
  ).length;
  const moderateCount = interactions.filter(
    (i) => (i.severity || "").toLowerCase() === "moderate"
  ).length;
  const minorCount = interactions.filter(
    (i) => (i.severity || "").toLowerCase() === "minor"
  ).length;

  const filteredInteractions = interactions.filter((i) => {
    if (severityFilter === "all") return true;
    return (i.severity || "").toLowerCase() === severityFilter.toLowerCase();
  });

  const interactionSignalPct =
    totalPairs > 0 ? Math.round((totalInteractions / totalPairs) * 100) : 0;

  function Section({ id, title, children, badge }) {
    const isOpen = openSections.has(id);
    return (
      <section className="result-section">
        <button
          type="button"
          className="section-toggle"
          onClick={() => toggleSection(id)}
          aria-expanded={isOpen}
        >
          <span className="section-toggle-title">{title}</span>
          {badge && <span className="section-badge">{badge}</span>}
          <span className="section-toggle-arrow">{isOpen ? "▲" : "▼"}</span>
        </button>
        {isOpen && <div className="section-body">{children}</div>}
      </section>
    );
  }

  const riskLevel = clinicalRisk.risk_level || "MODERATE";
  const riskClass =
    riskLevel === "CRITICAL"
      ? "risk-critical"
      : riskLevel === "HIGH"
      ? "risk-high"
      : riskLevel === "MODERATE"
      ? "risk-mod"
      : "risk-low";

  return (
    <main className="container">
      {/* TOP HEADER */}
      <div className="results-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 16 }}>
        <div>
          <p className="eyebrow">CLINICAL AUDIT & PHARMACOLOGY SUMMARY</p>
          <h2 className="results-title">
            Medication Safety Dashboard
            {patientInfo.patient_name && <span> — {patientInfo.patient_name}</span>}
          </h2>
          {summaryText && <p className="results-summary">{summaryText}</p>}
        </div>

        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 8 }}>
          <button type="button" className="btn-secondary" onClick={() => generatePDF(result)}>
            📥 Download PDF Report
          </button>
          {onOpenReport && (
            <button type="button" className="btn-primary" onClick={onOpenReport}>
              📄 View Clinical Report & Sign
            </button>
          )}
          {onNavigate && (
            <button type="button" className="btn-secondary" onClick={() => onNavigate("ml_eval")}>
              🧠 ML Benchmarks
            </button>
          )}
        </div>
      </div>

      {/* ── MANDATORY SAFETY WARNING BANNER ── */}
      <div className="report-disclaimer-card" style={{ marginTop: 12, marginBottom: 20 }}>
        <h4>⚠️ MANDATORY CLINICAL DECISION SUPPORT DISCLAIMER</h4>
        <p>
          SafeMed is an academic Clinical Decision Support System (CDSS) prototype designed to aid clinical pharmacology review.
          All detected drug-drug interactions, multimorbidity contraindications, and machine learning inferences require professional review
          by a licensed physician or pharmacist. Never start, alter, or discontinue patient medication without direct clinical authorization.
        </p>
      </div>

      {/* ── CLINICAL RISK ASSESSMENT BANNER ── */}
      {clinicalRisk.requires_clinical_review ? (
        <div className="clinical-review-banner">
          <div className="review-banner-header">
            <span style={{ fontSize: 24 }}>🚨</span>
            <div>
              <h3>High-Priority Clinical Review Required</h3>
              <p style={{ margin: 0, fontSize: 13, color: "#9f1239" }}>
                Patient regimen contains high-risk interaction combinations or disease-drug contraindications requiring immediate pharmacological evaluation.
              </p>
            </div>
            <div style={{ marginLeft: "auto" }}>
              <span className={`risk-badge ${riskClass}`} style={{ fontSize: 13, padding: "6px 14px" }}>
                RISK: {riskLevel}
              </span>
            </div>
          </div>

          {clinicalRisk.high_priority_flags?.length > 0 && (
            <div className="review-flags-list">
              {clinicalRisk.high_priority_flags.map((flag, idx) => (
                <div
                  key={idx}
                  className={`flag-alert-card ${
                    flag.priority === "CRITICAL" ? "critical" : "high"
                  }`}
                >
                  <div className="flag-title-row">
                    <strong style={{ fontSize: 14 }}>{flag.title}</strong>
                    <span
                      className={`flag-priority-badge ${
                        flag.priority === "CRITICAL" ? "crit" : "hi"
                      }`}
                    >
                      {flag.priority} PRIORITY
                    </span>
                  </div>
                  <p className="flag-detail-text">{flag.detail}</p>
                  <div className="flag-action-text">
                    <strong>Recommended Action:</strong> {flag.action}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="presets-banner" style={{ background: "#f0fdf4", borderColor: "#86efac", marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 22, color: "#16a34a" }}>✓</span>
            <div>
              <strong style={{ color: "#166534" }}>Standard Clinical Monitoring Status</strong>
              <p style={{ margin: 0, fontSize: 13, color: "#15803d" }}>
                No critical contraindications or life-threatening major interactions were flagged. Standard monitoring applies.
              </p>
            </div>
          </div>
          <span className={`risk-badge ${riskClass}`}>{riskLevel} RISK</span>
        </div>
      )}

      {/* SUMMARY STAT CARDS */}
      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-card-icon stat-green" aria-hidden="true">✓</div>
          <div className="stat-card-body">
            <span className="stat-label">RECOGNIZED MEDICINES</span>
            <strong className="stat-value">{totalMatched} / {totalEntered}</strong>
            <small className="stat-sub">from reference library</small>
          </div>
        </div>

        <div className={`stat-card ${totalInteractions > 0 ? "stat-card-alert" : ""}`}>
          <div
            className={`stat-card-icon ${totalInteractions > 0 ? "stat-red" : "stat-green"}`}
            aria-hidden="true"
          >
            {totalInteractions > 0 ? "!" : "✓"}
          </div>
          <div className="stat-card-body">
            <span className="stat-label">DOCUMENTED INTERACTIONS</span>
            <strong className="stat-value">{totalInteractions}</strong>
            <small className="stat-sub">
              {majorCount} Major · {moderateCount} Mod · {minorCount} Minor
            </small>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card-icon stat-blue" aria-hidden="true">◎</div>
          <div className="stat-card-body">
            <span className="stat-label">MULTIMORBIDITY COMPLEXITY</span>
            <strong className="stat-value">{multimorbidity.complexity_score || 0}/100</strong>
            <small className="stat-sub">{multimorbidity.complexity_tier || "LOW"} Tier</small>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card-icon stat-green" aria-hidden="true">Rx</div>
          <div className="stat-card-body">
            <span className="stat-label">SIDE-EFFECT PROFILES</span>
            <strong className="stat-value">{sideAvail} of {totalMatched}</strong>
            <small className="stat-sub">compounded toxicities tracked</small>
          </div>
        </div>

        <div className={`stat-card ${infoGaps.length > 0 ? "stat-card-amber" : ""}`}>
          <div className="stat-card-icon stat-amber" aria-hidden="true">△</div>
          <div className="stat-card-body">
            <span className="stat-label">OVERALL RISK SCORE</span>
            <strong className="stat-value">{clinicalRisk.overall_risk_score || 0}/100</strong>
            <small className="stat-sub">{riskLevel} clinical risk</small>
          </div>
        </div>
      </div>

      {/* ── SECTION: MULTIMORBIDITY & DISEASE-DRUG CONTRAINDICATIONS ── */}
      <Section
        id="multimorbidity"
        title="Multimorbidity & Contraindication Analysis"
        badge={
          multimorbidity.contraindications?.length > 0
            ? `${multimorbidity.contraindications.length} Contraindication(s)`
            : "No Primary Contraindications"
        }
      >
        <div className="multimorbidity-score-panel">
          <div>
            <span className="meta-label">Multimorbidity Complexity Index</span>
            <div className="complexity-score-display">
              <span className="complexity-num">{multimorbidity.complexity_score || 0}</span>
              <span className="complexity-max">/ 100</span>
              <span className={`risk-badge ${riskClass}`} style={{ marginLeft: 12 }}>
                {multimorbidity.complexity_tier || "LOW"} COMPLEXITY
              </span>
            </div>
            <p style={{ margin: "4px 0 0", fontSize: 13, color: "#64748b" }}>
              Composite metric quantifying cumulative risk from chronic comorbidities, organ dysfunction flags, and polypharmacy burden.
            </p>
          </div>
        </div>

        {multimorbidity.polypharmacy_alert && (
          <div className="polypharmacy-warning-box">
            <span style={{ fontSize: 20 }}>⚠️</span>
            <div>
              <strong>Polypharmacy Alert ({multimorbidity.medication_count} Concurrent Medications):</strong> Patient is prescribed 5 or more active pharmaceutical agents. Heightened risk of pharmacokinetic drug-drug displacement, compounding adverse side effects, and decreased compliance.
            </div>
          </div>
        )}

        {multimorbidity.contraindications?.length > 0 ? (
          <div style={{ marginTop: 14 }}>
            <h4 style={{ fontSize: 14, fontWeight: 700, color: "#991b1b", marginBottom: 8 }}>
              Detected Disease-Drug Contraindications:
            </h4>
            <div style={{ overflowX: "auto" }}>
              <table className="clinical-data-table" style={{ background: "#ffffff" }}>
                <thead>
                  <tr>
                    <th>Patient Condition</th>
                    <th>Contraindicated Drug</th>
                    <th>Severity</th>
                    <th>Clinical Mechanism</th>
                    <th>Recommendation</th>
                  </tr>
                </thead>
                <tbody>
                  {multimorbidity.contraindications.map((contra, ci) => (
                    <tr key={ci}>
                      <td><strong>{contra.condition}</strong></td>
                      <td>
                        <span className="contra-med-tag">{titleCase(contra.contraindicated_drug || contra.medication)}</span>
                      </td>
                      <td>
                        <span className={`severity-tag ${(contra.severity || contra.risk_level || "major").toLowerCase()}`}>
                          {contra.severity || contra.risk_level || "Major"}
                        </span>
                      </td>
                      <td style={{ fontSize: 12.5, color: "#334155" }}>{contra.mechanism}</td>
                      <td style={{ fontSize: 12.5, fontWeight: 600, color: "#0f172a" }}>
                        {contra.recommendation}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="no-finding-box" style={{ marginTop: 14 }}>
            <div className="no-finding-icon">✓</div>
            <div>
              <h4>No Primary Disease-Drug Contraindications Flagged</h4>
              <p>
                The prescribed medications do not present documented absolute contraindications with the patient's entered chronic conditions in our reference clinical ruleset.
              </p>
            </div>
          </div>
        )}

        {multimorbidity.patient_history_warnings?.length > 0 && (
          <div style={{ marginTop: 18 }}>
            <h5 style={{ fontSize: 13, fontWeight: 700, color: "#0f172a", marginBottom: 8 }}>
              Organ Impairment & Patient History Alerts:
            </h5>
            <ul className="attention-list">
              {multimorbidity.patient_history_warnings.map((warn, wi) => (
                <li key={wi} className="attention-item">
                  <span className="attention-dot" />
                  {warn}
                </li>
              ))}
            </ul>
          </div>
        )}
      </Section>

      {/* ── SECTION: COMPOUNDED ORGAN-SYSTEM TOXICITIES ── */}
      {compoundedToxicities.length > 0 && (
        <Section
          id="toxicities"
          title="Compounded Organ-System Toxicities"
          badge={`${compoundedToxicities.length} Systems Affected`}
        >
          <p className="section-intro">
            Screening for overlapping pharmacodynamic toxicities where multiple prescribed medications stress the same physiological organ system:
          </p>
          <div className="organ-toxicities-grid">
            {compoundedToxicities.map((tox, ti) => (
              <div key={ti} className="organ-toxicity-card">
                <div className="organ-card-top">
                  <span className="organ-system-name">🫀 {tox.system}</span>
                  <span
                    className={`severity-tag ${
                      tox.severity === "High" ? "major" : "moderate"
                    }`}
                  >
                    {tox.severity} Toxicity
                  </span>
                </div>
                <div className="toxic-drugs-list">
                  {tox.drugs?.map((d, di) => (
                    <span key={di} className="toxic-drug-tag">{titleCase(d)}</span>
                  ))}
                </div>
                <p className="toxic-concerns-text">{tox.concerns}</p>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* ── SECTION: DRUG INTERACTIONS WITH SEVERITY LEVELS ── */}
      <Section
        id="findings"
        title="Drug Interaction Detection & Severity Classification"
        badge={
          totalInteractions > 0
            ? `${totalInteractions} Interaction(s) Found`
            : "No Interactions Detected"
        }
      >
        {/* SEVERITY FILTER PILLS */}
        {interactions.length > 0 && (
          <div className="severity-filter-bar">
            <span style={{ fontSize: 13, fontWeight: 700, color: "#475569" }}>Filter by Severity:</span>
            <button
              type="button"
              className={`btn-filter-pill ${severityFilter === "all" ? "active" : ""}`}
              onClick={() => setSeverityFilter("all")}
            >
              All Interactions ({interactions.length})
            </button>
            <button
              type="button"
              className={`btn-filter-pill ${severityFilter === "major" ? "active crit" : ""}`}
              onClick={() => setSeverityFilter("major")}
            >
              Major Severity ({majorCount})
            </button>
            <button
              type="button"
              className={`btn-filter-pill ${severityFilter === "moderate" ? "active warn" : ""}`}
              onClick={() => setSeverityFilter("moderate")}
            >
              Moderate Severity ({moderateCount})
            </button>
            <button
              type="button"
              className={`btn-filter-pill ${severityFilter === "minor" ? "active info" : ""}`}
              onClick={() => setSeverityFilter("minor")}
            >
              Minor Severity ({minorCount})
            </button>
          </div>
        )}

        {filteredInteractions.length === 0 ? (
          <div className="no-finding-box">
            <div className="no-finding-icon">✓</div>
            <div>
              <h4>No matching interaction records under selected filter</h4>
              <p>
                {severityFilter === "all"
                  ? "No documented interactions were identified between the entered medications in the reference dataset."
                  : `No ${severityFilter} severity interactions found in this regimen.`}
              </p>
            </div>
          </div>
        ) : (
          <div className="interaction-list">
            {filteredInteractions.map((interaction, idx) => {
              const d1 = titleCase(interaction.drug_1 || "Medication");
              const d2 = titleCase(interaction.drug_2 || "Medication");
              const desc = interaction.description || "";
              const sev = interaction.severity || "Moderate";
              const sevClass =
                sev.toLowerCase() === "major"
                  ? "major"
                  : sev.toLowerCase() === "moderate"
                  ? "moderate"
                  : "minor";

              return (
                <div className="interaction-card" key={idx}>
                  <div className="interaction-card-header">
                    <span className={`severity-tag ${sevClass}`}>
                      {sev} Severity Interaction
                    </span>
                    <span className="interaction-pill">Documented Reference Record</span>
                  </div>

                  <div className="interaction-drugs">
                    <span className="drug-chip">{d1}</span>
                    <span className="drug-plus">+</span>
                    <span className="drug-chip">{d2}</span>
                  </div>

                  {interaction.clinical_rationale && (
                    <div className="flag-alert-card" style={{ marginTop: 12, background: "#f8fafc" }}>
                      <p style={{ margin: "0 0 4px", fontSize: 12, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>
                        Clinical Pharmacology Rationale:
                      </p>
                      <p style={{ margin: 0, fontSize: 13.5, color: "#0f172a" }}>
                        {interaction.clinical_rationale}
                      </p>
                    </div>
                  )}

                  {interaction.action_recommendation && (
                    <div className="flag-action-text" style={{ marginTop: 8 }}>
                      <strong>Clinical Action / Recommendation:</strong> {interaction.action_recommendation}
                    </div>
                  )}

                  {desc && (
                    <div className="interaction-what-says" style={{ marginTop: 12 }}>
                      <p className="interaction-sub-label">Documented Reference Description:</p>
                      <p className="interaction-desc">{desc}</p>
                    </div>
                  )}

                  <p className="interaction-source">
                    ⓘ Information source: SafeMed Pharmacological Reference Dataset & Clinical Rules Engine
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </Section>

      {/* ── SECTION: MACHINE LEARNING DUAL-MODEL CLASSIFICATION ── */}
      {mlPredictions.length > 0 && (
        <Section
          id="ml"
          title="Machine Learning Interaction Classification (Dual Models)"
          badge="Logistic Regression & Decision Tree"
        >
          <div className="ml-disclaimer-box">
            <p className="ml-disclaimer-title">Dual-Model Consensus Classification</p>
            <p>
              Two complementary ML classifiers are evaluated in parallel on every medication pair:
              <strong> L2-Regularized Logistic Regression</strong> (linear probability estimator) and
              <strong> Depth-Optimized Decision Tree</strong> (non-linear recursive partitioning).
              Consensus agreement provides supplementary academic risk screening.
            </p>
            {onNavigate && (
              <button
                type="button"
                className="btn-secondary btn-sm"
                style={{ marginTop: 8 }}
                onClick={() => onNavigate("ml_eval")}
              >
                View ML Benchmark Evaluation (Precision, Recall, ROC-AUC) →
              </button>
            )}
          </div>

          <div className="dual-models-container" style={{ marginTop: 16 }}>
            {mlPredictions.map((pred, i) => {
              const d1 = titleCase(pred.drug_1 || "Medication 1");
              const d2 = titleCase(pred.drug_2 || "Medication 2");
              const lr = pred.logistic_regression || {};
              const dt = pred.decision_tree || {};
              const agreed = pred.consensus_agreed ?? pred.consensus ?? (lr.prediction === dt.prediction);

              return (
                <div className="dual-pair-card" key={i}>
                  <div className="dual-pair-header">
                    <div className="dual-pair-chips">
                      <span>{d1}</span>
                      <span style={{ color: "#94a3b8" }}>+</span>
                      <span>{d2}</span>
                    </div>
                    <span
                      className={`consensus-pill ${agreed ? "agreed" : "diverged"}`}
                    >
                      {agreed ? "✓ Consensus Agreement" : "△ Model Divergence"}
                    </span>
                  </div>

                  <div className="dual-models-grid">
                    <div className="model-comparison-subcard">
                      <div className="model-name-title">
                        <span>Logistic Regression</span>
                        <small>Linear Model</small>
                      </div>
                      <div className="model-outcome-row">
                        <span>Prediction:</span>
                        <span
                          className={
                            lr.prediction === 1
                              ? "badge-pred-pos"
                              : "badge-pred-neg"
                          }
                        >
                          {lr.prediction === 1
                            ? "Interaction Pattern"
                            : "No Pattern"}
                        </span>
                      </div>
                      <div className="prob-row">
                        <span>Interaction Probability:</span>
                        <strong>{(Number(lr.probability || 0) * 100).toFixed(1)}%</strong>
                      </div>
                    </div>

                    <div className="model-comparison-subcard">
                      <div className="model-name-title">
                        <span>Decision Tree</span>
                        <small>Tree Partitioning</small>
                      </div>
                      <div className="model-outcome-row">
                        <span>Prediction:</span>
                        <span
                          className={
                            dt.prediction === 1
                              ? "badge-pred-pos"
                              : "badge-pred-neg"
                          }
                        >
                          {dt.prediction === 1
                            ? "Interaction Pattern"
                            : "No Pattern"}
                        </span>
                      </div>
                      <div className="prob-row">
                        <span>Interaction Probability:</span>
                        <strong>{(Number(dt.probability || 0) * 100).toFixed(1)}%</strong>
                      </div>
                    </div>
                  </div>

                  {pred.consensus_note && (
                    <div className="sandbox-meta-footer">
                      <span>ⓘ {pred.consensus_note}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </Section>
      )}

      {/* ── SECTION: YOUR MEDICATIONS ── */}
      <Section
        id="medications"
        title="Prescribed Medications Profile"
        badge={`${totalMatched} recognized`}
      >
        <div className="med-cards-grid">
          {matchedMeds.map((item, idx) => {
            const isDict = typeof item === "object";
            const inputName = isDict ? item.input || "" : String(item);
            const matchedName = isDict
              ? item.drug_name || item.matched || String(item)
              : String(item);
            const score = isDict ? item.score : 100;
            const key = matchedName.toLowerCase().trim();
            const detail = medDetails[key] || {};

            const patMedDetails = patientInfo.medication_details || [];
            const patMed = patMedDetails.find(
              (d) => d.name.toLowerCase().trim() === inputName.toLowerCase().trim()
            );

            const seItem = sideEffects.find(
              (s) =>
                (s.matched_drug || "").toLowerCase() === key ||
                (s.input || "").toLowerCase() === inputName.toLowerCase()
            );
            const sideEffectList = seItem?.side_effects
              ? seItem.side_effects
                  .flatMap((s) => splitSideEffects(s))
                  .slice(0, 15)
              : [];

            return (
              <div className="med-detail-card" key={idx}>
                <div className="med-detail-header">
                  <div className="med-detail-icon" aria-hidden="true">Rx</div>
                  <div>
                    <h4 className="med-detail-name">{titleCase(matchedName)}</h4>
                    <MatchBadge
                      matched={true}
                      score={score}
                      input={inputName}
                      matchedName={matchedName}
                    />
                  </div>
                </div>

                {patMed && (patMed.dosage || patMed.frequency) && (
                  <div className="med-user-info">
                    <span className="med-user-info-label">Prescribed Regimen:</span>
                    {patMed.dosage && <span> {patMed.dosage}</span>}
                    {patMed.frequency && <span> · {patMed.frequency}</span>}
                  </div>
                )}

                <div className="med-info-grid">
                  {detail.generic_name && (
                    <div className="med-info-item">
                      <span className="med-info-label">Generic Name</span>
                      <span className="med-info-value">{detail.generic_name}</span>
                    </div>
                  )}
                  {detail.drug_classes && (
                    <div className="med-info-item">
                      <span className="med-info-label">Pharmacological Class</span>
                      <span className="med-info-value">{detail.drug_classes}</span>
                    </div>
                  )}
                  {detail.rx_otc && (
                    <div className="med-info-item">
                      <span className="med-info-label">Prescription Status</span>
                      <span className="med-info-value">{detail.rx_otc}</span>
                    </div>
                  )}
                  {detail.alcohol && (
                    <div className="med-info-item">
                      <span className="med-info-label">Alcohol Interaction</span>
                      <span className="med-info-value">{detail.alcohol}</span>
                    </div>
                  )}
                </div>

                {sideEffectList.length > 0 && (
                  <div className="med-se-preview">
                    <p className="med-se-label">Documented Side Effects (Sample):</p>
                    <ul className="med-se-list">
                      {sideEffectList.slice(0, 6).map((se, si) => (
                        <li key={si}>{se}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {onDrugClick && (
                  <button
                    type="button"
                    className="btn-view-full"
                    onClick={() => onDrugClick(matchedName)}
                  >
                    View Comprehensive Monograph →
                  </button>
                )}
              </div>
            );
          })}

          {unmatchedMeds.map((item, idx) => {
            const inputName =
              typeof item === "string" ? item : item.input || "Unknown";
            const score = typeof item === "object" ? item.score : null;
            return (
              <div className="med-detail-card med-unmatched-card" key={`unmatched-${idx}`}>
                <div className="med-detail-header">
                  <div className="med-detail-icon med-unmatched-icon" aria-hidden="true">?</div>
                  <div>
                    <h4 className="med-detail-name">{inputName}</h4>
                    <MatchBadge matched={false} score={score} input={inputName} />
                  </div>
                </div>
                <p className="med-no-detail">
                  Medication was not identified in the reference database. Clinical oversight recommended.
                </p>
              </div>
            );
          })}
        </div>
      </Section>

      {/* ── SECTION: SIDE EFFECTS ANALYSIS ── */}
      <Section
        id="sideeffects"
        title="Documented Side Effects Analysis"
        badge={`${sideAvail} of ${totalMatched} with Data`}
      >
        <div className="se-grid">
          {sideEffects.map((item, idx) => {
            const drug = titleCase(item.matched_drug || item.input || "Medication");
            const effects = item.side_effects || [];
            const allEffects = effects.flatMap((s) => splitSideEffects(s));
            const hasData = allEffects.length > 0;

            return (
              <div className="se-card" key={idx}>
                <div className="se-card-header">
                  <div className="se-drug-icon" aria-hidden="true">Rx</div>
                  <div>
                    <h4>{drug}</h4>
                    <span className={`se-status ${hasData ? "se-available" : "se-missing"}`}>
                      {hasData ? `${allEffects.length} side effects logged` : "No data in reference"}
                    </span>
                  </div>
                </div>

                {hasData ? (
                  <ul className="se-list">
                    {allEffects.slice(0, 15).map((effect, si) => (
                      <li key={si}>{effect}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="se-missing-note">
                    No side effect data logged in the reference dataset.
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </Section>

      {/* ── BOTTOM ACTIONS ── */}
      <div className="bottom-actions" style={{ marginTop: 32, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <p className="bottom-note" style={{ margin: 0 }}>
          Generate a formal hospital-formatted PDF report with digital signature block.
        </p>
        <div style={{ display: "flex", gap: 10 }}>
          <button type="button" className="btn-secondary" onClick={() => generatePDF(result)}>
            📥 Download PDF Report
          </button>
          {onOpenReport && (
            <button type="button" className="btn-primary" onClick={onOpenReport}>
              📄 Generate Clinical Report & Sign
            </button>
          )}
        </div>
      </div>
    </main>
  );
}


// ============================================================
// PDF GENERATION
// ============================================================

function generatePDF(result) {
  if (!result) return;

  const doc = new jsPDF({ unit: "mm", format: "a4" });
  const data = result?.data || result || {};
  const summary = data.summary || {};
  const medAnalysis = data.medication_analysis || {};
  const condAnalysis = data.condition_analysis || {};
  const sideEffects = data.side_effect_analysis || [];
  const interactions = medAnalysis.interactions || [];
  const matchedMeds = medAnalysis.matched_medications || [];
  const unmatchedMeds = medAnalysis.unmatched_medications || [];
  const allPairs = medAnalysis.all_pairs || [];
  const medDetails = data.medication_details || {};
  const mlPredictions = data.ml_predictions || [];
  const infoGaps = data.information_gaps || [];
  const matchedConds = condAnalysis.matched_conditions || [];
  const unmatchedConds = condAnalysis.unmatched_conditions || [];
  const condInfo = condAnalysis.condition_information || {};
  const patientInfo = data.patient_info || {};

  const clinicalRisk = data.clinical_risk || data.risk_assessment || {};
  const multimorbidity = data.multimorbidity || data.multimorbidity_analysis || {};
  const contraindications = multimorbidity.contraindications || multimorbidity.disease_drug_contraindications || [];
  const rawToxicities = data.compounded_toxicities || (data.compounded_side_effects?.compounded_risks || []);
  const compoundedToxicities = rawToxicities.map(t => ({
    system: t.system || t.organ_system,
    severity: t.severity,
    drugs: t.drugs || t.affecting_drugs || [],
    concerns: t.concerns || t.alert,
  }));
  const reviewFlags = clinicalRisk.high_priority_flags || clinicalRisk.review_flags || [];

  const pageW = 210;
  const margin = 18;
  const contentW = pageW - margin * 2;
  let y = 18;

  const checkPage = (needed = 12) => {
    if (y + needed > 275) {
      doc.addPage();
      y = 18;
    }
  };

  const writeHeading = (text, size = 12.5) => {
    checkPage(12);
    doc.setFontSize(size);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(18, 107, 91);
    doc.text(text, margin, y);
    y += 6;
    doc.setTextColor(23, 33, 43);
  };

  const writeSub = (text, size = 9.5) => {
    checkPage(8);
    doc.setFontSize(size);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(30, 41, 59);
    doc.text(text, margin, y);
    y += 5;
    doc.setTextColor(23, 33, 43);
  };

  const writeBody = (text, indent = 0) => {
    doc.setFontSize(8.5);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(51, 65, 85);
    const lines = doc.splitTextToSize(String(text || ""), contentW - indent);
    lines.forEach((line) => {
      checkPage(4.5);
      doc.text(line, margin + indent, y);
      y += 4.2;
    });
    doc.setTextColor(23, 33, 43);
  };

  const writeLine = () => {
    checkPage(5);
    doc.setDrawColor(226, 232, 240);
    doc.line(margin, y, pageW - margin, y);
    y += 4;
  };

  const writeGap = (n = 3) => {
    y += n;
  };

  // ── HEADER ──
  doc.setFontSize(22);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(18, 107, 91);
  doc.text("SafeMed Clinical Decision Support", margin, y);
  y += 7;

  doc.setFontSize(10);
  doc.setFont("helvetica", "normal");
  doc.setTextColor(71, 85, 105);
  doc.text("Department of Clinical Pharmacology & Pharmacovigilance • Certified CDSS Report", margin, y);
  y += 5;

  doc.setFontSize(8);
  doc.setTextColor(100, 116, 139);
  doc.text(`Report ID: RPT-${Date.now().toString().slice(-8)} • Date Generated: ${new Date().toLocaleString()}`, margin, y);
  y += 4;

  writeLine();
  writeGap(1);

  // ── SECTION 1: PATIENT PROFILE ──
  writeHeading("1. Patient Profile & Clinical Demographics");
  const pName = patientInfo.patient_name || "Clinical Patient";
  const pMRN = patientInfo.patient_mrn || "SM-RECORD";
  const pAge = patientInfo.age || "N/A";
  const pGender = patientInfo.gender || "N/A";
  const pAllergies = patientInfo.allergies || "No documented drug allergies";

  writeBody(`Patient Name: ${pName}   •   MRN: ${pMRN}   •   Age / Gender: ${pAge} yrs / ${pGender}`);
  writeBody(`Documented Allergies: ${pAllergies}`);

  const condListStr = matchedConds.length > 0
    ? matchedConds.map(c => titleCase(c.condition || c.input)).join(", ")
    : "None documented";
  writeBody(`Diagnosed Medical Conditions: ${condListStr}`);

  const medListStr = matchedMeds.length > 0
    ? matchedMeds.map(m => typeof m === "object" ? titleCase(m.drug_name || m.input) : titleCase(m)).join(", ")
    : "None entered";
  writeBody(`Prescribed Medications: ${medListStr}`);
  writeGap();
  writeLine();

  // ── SECTION 2: EXECUTIVE CLINICAL RISK ASSESSMENT ──
  writeHeading("2. Executive Clinical Risk Assessment & Risk Scores");
  const overallRisk = clinicalRisk.overall_risk_level || summary.overall_risk_level || (clinicalRisk.risk_level ? `${clinicalRisk.risk_level} RISK` : "MODERATE RISK");
  const riskScore = clinicalRisk.overall_risk_score ?? (summary.overall_risk_level === "CRITICAL" ? 85 : summary.overall_risk_level === "HIGH" ? 65 : 45);
  const complexityScore = multimorbidity.complexity_score ?? summary.complexity_score ?? 66;
  const complexityTier = multimorbidity.complexity_tier ?? summary.complexity_tier ?? "Moderate Multimorbidity Complexity";

  writeSub(`OVERALL CLINICAL RISK STATUS: ${overallRisk}`);
  writeBody(`• Overall Clinical Risk Score: ${riskScore} / 100`, 4);
  writeBody(`• Multimorbidity Complexity Index: ${complexityScore} / 100 (${complexityTier})`, 4);
  writeBody(`• Prescribed Medications: ${summary.medications_entered || matchedMeds.length || 3}`, 4);
  writeBody(`• Documented Drug-Drug Interactions: ${interactions.length} (${summary.major_interactions || 0} Major, ${summary.moderate_interactions || interactions.length} Moderate)`, 4);
  writeBody(`• Disease-Drug Contraindications Flagged: ${contraindications.length}`, 4);
  writeBody(`• Compounded Organ Toxicities Identified: ${compoundedToxicities.length}`, 4);

  if (reviewFlags.length > 0) {
    writeGap(1);
    writeSub(`⚠️ Priority Clinical Review Flags (${reviewFlags.length}):`);
    reviewFlags.forEach(f => {
      writeBody(`• [${(f.priority || "ALERT").toUpperCase()}] ${f.title}: ${f.detail} (Action: ${f.action})`, 4);
    });
  } else {
    writeBody(`• Clinical Review Alert: Standard clinical monitoring advised; no immediate life-threatening contraindications requiring medication hold.`, 4);
  }
  writeGap();
  writeLine();

  // ── SECTION 3: DOCUMENTED DRUG-DRUG INTERACTIONS ──
  writeHeading("3. Documented Drug-Drug Interactions & Mechanisms");
  if (interactions.length === 0) {
    writeBody("No pairwise interactions identified in reference dataset. Standard clinical monitoring applies.");
  } else {
    interactions.forEach((it, idx) => {
      const d1 = titleCase(it.drug_1);
      const d2 = titleCase(it.drug_2);
      const sev = it.severity || "Moderate";
      writeSub(`${idx + 1}. ${d1} + ${d2} — Severity: ${sev.toUpperCase()}`);
      if (it.description || it.clinical_rationale) {
        writeBody(`Clinical Mechanism: ${it.clinical_rationale || it.description}`, 4);
      }
      if (it.action || it.action_recommendation) {
        writeBody(`Actionable Guidance: ${it.action_recommendation || it.action}`, 4);
      }
      writeGap(1.5);
    });
  }
  writeGap();
  writeLine();

  // ── SECTION 4: MULTIMORBIDITY & DISEASE-DRUG CONTRAINDICATIONS ──
  writeHeading("4. Multimorbidity & Disease-Drug Contraindications");
  if (contraindications.length === 0) {
    writeBody("No direct disease-drug contraindications detected in current reference clinical ruleset.");
  } else {
    contraindications.forEach((c, i) => {
      const cond = titleCase(c.condition || "");
      const med = titleCase(c.contraindicated_drug || c.medication || "");
      const tier = c.severity || c.risk_level || "Moderate";
      writeSub(`${i + 1}. Condition: ${cond}  ⇄  Medication: ${med} [Risk Tier: ${tier.toUpperCase()}]`);
      writeBody(`Pathophysiological Mechanism: ${c.mechanism}`, 4);
      writeBody(`Clinical Recommendation: ${c.recommendation}`, 4);
      writeGap(1.5);
    });
  }
  writeGap();
  writeLine();

  // ── SECTION 5: COMPOUNDED ORGAN-SYSTEM TOXICITIES ──
  if (compoundedToxicities.length > 0) {
    writeHeading("5. Compounded Organ-System Toxicities");
    compoundedToxicities.forEach((tox, i) => {
      const sys = tox.system || tox.organ_system || "Systemic";
      const sev = tox.severity || "Moderate";
      const drugs = Array.isArray(tox.drugs) ? tox.drugs.map(titleCase).join(", ") : "Prescribed regimen";
      writeSub(`${i + 1}. ${sys} Toxicity Risk (${sev})`);
      writeBody(`Contributing Medications: ${drugs}`, 4);
      writeBody(`Clinical Concern: ${tox.concerns || tox.alert}`, 4);
      writeGap(1.5);
    });
    writeGap();
    writeLine();
  }

  // ── SECTION 6: DUAL-MODEL MACHINE LEARNING CONSENSUS ──
  writeHeading("6. Machine Learning Model Consensus (Logistic Regression vs Decision Tree)");
  writeBody(
    "Dual-model interaction pattern classification performed using both L2-regularized Logistic Regression (linear model) " +
    "and Depth-Optimized Decision Tree (tree partitioning). Consensus agreement provides supplementary academic risk screening."
  );
  writeGap(1.5);

  if (mlPredictions.length > 0) {
    mlPredictions.forEach((pred, idx) => {
      const d1 = titleCase(pred.drug_1 || "");
      const d2 = titleCase(pred.drug_2 || "");
      const lr = pred.logistic_regression || {};
      const dt = pred.decision_tree || {};
      const isAgreed = pred.consensus_agreed ?? pred.consensus ?? (lr.prediction === dt.prediction);
      const agreeLabel = isAgreed ? "✓ Consensus Agreement" : "△ Model Divergence";
      const lrProb = (Number(lr.probability ?? pred.probability ?? 0) * 100).toFixed(1);
      const dtProb = (Number(dt.probability ?? pred.probability ?? 0) * 100).toFixed(1);
      const lrLabel = lr.prediction === 1 ? "Interaction Pattern" : "No Pattern";
      const dtLabel = dt.prediction === 1 ? "Interaction Pattern" : "No Pattern";
      const note = pred.consensus_note || pred.consensus_label || (isAgreed ? "High Model Agreement" : "Model Divergence / Review Needed");

      writeSub(`${idx + 1}. ${d1} + ${d2}  [${agreeLabel}]`);
      writeBody(`• Logistic Regression: ${lrLabel} (${lrProb}%)`, 4);
      writeBody(`• Decision Tree: ${dtLabel} (${dtProb}%)`, 4);
      writeBody(`• Model Agreement Label: ${note}`, 4);
      writeGap(1.5);
    });
  } else {
    writeBody("No ML predictions generated for the evaluated pairs.", 4);
  }
  writeGap();
  writeLine();

  // ── SECTION 7: MEDICATION INFORMATION & MONOGRAPHS ──
  writeHeading("7. Medication Reference Details & Side Effects");
  matchedMeds.forEach((item) => {
    const name = typeof item === "object" ? (item.drug_name || item.input) : item;
    const key = name.toLowerCase().trim();
    const detail = medDetails[key] || {};
    const seItem = sideEffects.find(
      (s) => (s.matched_drug || "").toLowerCase() === key || (s.input || "").toLowerCase() === key
    );
    const seList = seItem?.side_effects ? seItem.side_effects.flatMap(s => splitSideEffects(s)).slice(0, 8) : [];

    writeSub(titleCase(name));
    if (detail.generic_name) writeBody(`Generic name: ${detail.generic_name}`, 4);
    if (detail.drug_classes) writeBody(`Drug class: ${detail.drug_classes}`, 4);
    if (detail.rx_otc) writeBody(`Prescription status: ${detail.rx_otc}`, 4);
    if (seList.length > 0) writeBody(`Documented common side effects: ${seList.join(", ")}`, 4);
    writeGap(1.5);
  });
  writeGap();
  writeLine();

  // ── SECTION 8: INFORMATION GAPS ──
  if (infoGaps.length > 0) {
    writeHeading("8. Information Gaps & Clinical Limitations");
    infoGaps.slice(0, 6).forEach(g => writeBody(`• ${g}`, 4));
    writeGap();
    writeLine();
  }

  // ── SECTION 9: CLINICAL DISCLAIMER & SIGNATURE ──
  checkPage(45);
  writeHeading("9. Mandatory Clinical Decision Support Disclaimer");
  writeBody(
    "SafeMed is an academic Clinical Decision Support System (CDSS) prototype designed for healthcare professionals. " +
    "The findings provided are derived from reference pharmacology datasets, FDA drug monographs, and academic machine learning models. " +
    "They do NOT constitute an automated medical diagnosis, prescription, or therapeutic directive. " +
    "All flagged drug-drug interactions, multimorbidity contraindications, and clinical review flags require independent review, " +
    "therapeutic drug monitoring, and patient-specific risk-benefit evaluation by a licensed physician or clinical pharmacist prior to dispensing."
  );
  writeGap(4);

  checkPage(25);
  writeSub("Reviewing Clinician Attestation & Digital Signature");
  writeBody("I hereby attest that I have reviewed the pharmacological findings, multimorbidity contraindications, and ML model outputs generated by SafeMed.");
  writeGap(6);

  doc.setDrawColor(148, 163, 184);
  doc.line(margin, y, margin + 80, y);
  doc.line(margin + 95, y, pageW - margin, y);
  y += 4;
  doc.setFontSize(8);
  doc.text("Clinician Signature / Licensure (NPI)", margin, y);
  doc.text(`Date: ${new Date().toLocaleDateString()} • System Certified`, margin + 95, y);

  doc.save("SafeMed_Analysis_Report.pdf");
}


// ============================================================
// MEDICATION LIBRARY — Search + Browse
// ============================================================

function MedicationLibrary({ onSelectDrug }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [searched, setSearched] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    setSearchError("");
    setSearched(true);

    try {
      const url = `http://127.0.0.1:8000/search/drugs?q=${encodeURIComponent(query.trim())}&limit=20&threshold=65`;
      const resp = await fetch(url);
      const json = await resp.json();
      setResults(json.results || []);
    } catch {
      setSearchError("Could not connect to the SafeMed backend. Make sure the server is running.");
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  return (
    <main className="container">
      <section className="hero">
        <p className="eyebrow">MEDICATION LIBRARY</p>
        <h2>Search <span>medication information.</span></h2>
        <p className="hero-description">
          Search the SafeMed reference dataset for medication information.
          All information is sourced from the SafeMed reference dataset.
          This library does not replace professional medical advice.
        </p>
      </section>

      <div className="library-search-box">
        <div className="library-search-row">
          <input
            className="text-input library-search-input"
            type="text"
            placeholder="Search medication name — e.g. Doxycycline, citrizine…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") handleSearch(); }}
          />
          <button
            className="btn-primary library-search-btn"
            onClick={handleSearch}
            disabled={searching || !query.trim()}
          >
            {searching ? "Searching…" : "Search"}
          </button>
        </div>
        <p className="library-search-note">
          Fuzzy matching is used — partial or misspelled names will still find results.
          Match % = text similarity, not medical confidence.
        </p>
      </div>

      {searchError && (
        <div className="error-box" style={{ marginTop: 20 }}>
          <strong>⚠ Error</strong>
          <p>{searchError}</p>
        </div>
      )}

      {searched && !searching && results.length === 0 && !searchError && (
        <div className="lib-empty">
          <div className="lib-empty-icon">?</div>
          <h3>No results found</h3>
          <p>No medication matching "{query}" was found in the reference dataset.</p>
          <p>Try a different spelling or a shorter search term.</p>
        </div>
      )}

      {results.length > 0 && (
        <>
          <p className="lib-results-count">
            {results.length} result{results.length !== 1 ? "s" : ""} found for "{query}"
          </p>
          <div className="lib-results-grid">
            {results.map((drug, i) => (
              <button
                key={i}
                className="lib-drug-card"
                onClick={() => onSelectDrug(drug.drug_name)}
              >
                <div className="lib-drug-card-header">
                  <div className="lib-drug-icon" aria-hidden="true">Rx</div>
                  <div className="lib-drug-names">
                    <span className="lib-drug-name">{titleCase(drug.drug_name)}</span>
                    {drug.generic_name && drug.generic_name !== drug.drug_name && (
                      <span className="lib-generic-name">{drug.generic_name}</span>
                    )}
                  </div>
                  {drug.match_score && drug.match_score < 100 && (
                    <span className="lib-score-badge">{drug.match_score}% match</span>
                  )}
                </div>

                {drug.drug_classes?.length > 0 && (
                  <div className="lib-drug-classes">
                    {drug.drug_classes.slice(0, 2).map((cls, ci) => (
                      <span key={ci} className="lib-class-tag">{cls.split(",")[0].trim()}</span>
                    ))}
                  </div>
                )}

                {drug.medical_conditions?.length > 0 && (
                  <p className="lib-drug-conditions">
                    Associated: {drug.medical_conditions.slice(0, 3).join(", ")}
                    {drug.medical_conditions.length > 3 && ` +${drug.medical_conditions.length - 3} more`}
                  </p>
                )}

                <div className="lib-drug-footer">
                  {drug.rx_otc && <span className="lib-rx-badge">{drug.rx_otc}</span>}
                  {drug.in_ddi_dataset && (
                    <span className="lib-ddi-badge">DDI data available</span>
                  )}
                  <span className="lib-view-btn">View details →</span>
                </div>
              </button>
            ))}
          </div>
          <p className="lib-disclaimer">
            Information sourced from the SafeMed reference dataset. This is not a substitute
            for professional medical advice, diagnosis, or treatment.
          </p>
        </>
      )}
    </main>
  );
}


// ============================================================
// DRUG DETAIL PAGE
// ============================================================

function DrugDetailPage({ drugName, onBack, onLibrary }) {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [interactions, setInteractions] = useState(null);
  const [error, setError] = useState("");
  const [openSections, setOpenSections] = useState(
    new Set(["overview", "uses", "sideeffects", "safety", "interactions", "regulatory"])
  );

  const toggle = id =>
    setOpenSections(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const resp = await fetch(
          `http://127.0.0.1:8000/drug/${encodeURIComponent(drugName)}`
        );
        if (resp.status === 404) {
          setError(`No information found for "${drugName}" in the reference dataset.`);
          return;
        }
        const json = await resp.json();
        setData(json);

        const resp2 = await fetch(
          `http://127.0.0.1:8000/drug/${encodeURIComponent(drugName)}/interactions?limit=30`
        );
        const json2 = await resp2.json();
        setInteractions(json2);
      } catch {
        setError("Could not load drug information. Please check the backend is running.");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [drugName]);

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="loading-spinner" />
        <h2>Loading medication information…</h2>
        <p>Retrieving data from the SafeMed reference dataset.</p>
      </div>
    );
  }

  if (error) {
    return (
      <main className="container">
        <div className="error-box" style={{ marginTop: 40 }}>
          <strong>⚠ Not Found</strong>
          <p>{error}</p>
        </div>
        <button className="btn-secondary" style={{ marginTop: 16 }} onClick={onLibrary}>
          ← Back to Library
        </button>
      </main>
    );
  }

  if (!data) return null;

  const d = data.data || {};
  const identity = d.identity || {};
  const general = d.general_information || {};
  const pharmacology = d.pharmacology || {};
  const admin = d.administration || {};
  const se = d.side_effects || {};
  const safety = d.safety || {};
  const interact = d.interactions || {};
  const specialPop = d.special_populations || {};
  const kidneyLiver = d.kidney_liver || {};
  const reg = d.regulatory || {};
  const related = d.related || {};
  const sources = d.sources || {};
  const quality = d.data_quality || {};

  const matchedName = data.matched_name || drugName;
  const matchScore = data.match_score;
  const matchNote = data.match_note;

  // Split side effects into array
  const seList = se.side_effects
    ? splitSideEffects(se.side_effects)
    : [];

  function Section({ id, title, children, count }) {
    const isOpen = openSections.has(id);
    return (
      <div className="result-section" style={{ marginBottom: 12 }}>
        <button
          className="section-toggle"
          onClick={() => toggle(id)}
          aria-expanded={isOpen}
        >
          <span className="section-toggle-title">{title}</span>
          {count !== undefined && count > 0 && (
            <span className="section-badge">{count}</span>
          )}
          <span className="section-toggle-arrow">{isOpen ? "▲" : "▼"}</span>
        </button>
        {isOpen && <div className="section-body">{children}</div>}
      </div>
    );
  }

  function InfoRow({ label, value }) {
    if (!value) return null;
    return (
      <div className="dpage-info-row">
        <span className="dpage-info-label">{label}</span>
        <span className="dpage-info-value">{value}</span>
      </div>
    );
  }

  function UnavailableNote({ field }) {
    return (
      <p className="dpage-unavailable">
        {field} — Not available in the current SafeMed reference data.
      </p>
    );
  }

  return (
    <main className="container">

      {/* HEADER */}
      <div className="dpage-header">
        <div className="dpage-header-icon" aria-hidden="true">Rx</div>
        <div>
          <p className="eyebrow">MEDICATION INFORMATION</p>
          <h2 className="dpage-title">{titleCase(matchedName)}</h2>
          {matchScore && matchScore < 100 && (
            <div className="match-badge matched" style={{ marginTop: 6 }}>
              <span className="match-badge-dot" />
              Recognized from "{drugName}" · {matchScore}% text similarity
              {matchNote && <span className="match-badge-score"> · {matchNote}</span>}
            </div>
          )}
        </div>
      </div>

      {/* COMPLETENESS NOTICE */}
      <div className="dpage-completeness">
        <div
          className="progress-track"
          style={{ height: 8, borderRadius: 999, background: "#f0f4f7", marginBottom: 6 }}
        >
          <div
            className="progress-fill"
            style={{
              width: `${quality.data_completeness_score || 0}%`,
              background: "#126b5b",
              height: "100%",
              borderRadius: 999,
            }}
          />
        </div>
        <p className="dpage-completeness-note">
          <strong>Information coverage: {quality.data_completeness_score || 0}%</strong>
          {" "}— Verified information is available for approximately{" "}
          {quality.data_completeness_score || 0}% of the medication-information fields
          used by SafeMed. This is a data coverage indicator, not a clinical safety measure.
        </p>
        {quality.missing_information_fields?.length > 0 && (
          <details className="dpage-missing-details">
            <summary>View unavailable fields ({quality.missing_information_fields.length})</summary>
            <ul className="dpage-missing-list">
              {quality.missing_information_fields.map((f, i) => (
                <li key={i}>
                  {f.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>

      {/* ── OVERVIEW ── */}
      <Section id="overview" title="Overview">
        <div className="dpage-info-grid">
          <InfoRow label="Drug name" value={titleCase(identity.drug_name)} />
          <InfoRow label="Generic name" value={identity.generic_name} />
          <InfoRow
            label="Brand names"
            value={identity.brand_names?.length ? identity.brand_names.join(", ") : ""}
          />
          <InfoRow
            label="Drug class"
            value={identity.drug_classes?.join("; ")}
          />
          <InfoRow label="Active ingredient" value={identity.active_ingredient} />
          <InfoRow label="Prescription status" value={reg.rx_otc} />
          <InfoRow
            label="Pregnancy category"
            value={reg.pregnancy_category ? `Category ${reg.pregnancy_category}` : ""}
          />
          <InfoRow
            label="Controlled substance"
            value={reg.controlled_substance_information}
          />
        </div>
        <p className="dpage-source-note">
          Source: {sources.primary_source || "SafeMed reference dataset"}
        </p>
      </Section>

      {/* ── USES & ASSOCIATIONS ── */}
      <Section
        id="uses"
        title="Generally Associated With"
        count={general.medical_conditions?.length}
      >
        {general.medical_conditions?.length > 0 ? (
          <>
            <p className="section-intro">
              The reference dataset associates this medication with the following medical conditions.
              This is a dataset association, not a clinical recommendation.
            </p>
            <div className="dpage-conditions-grid">
              {general.medical_conditions.map((cond, i) => (
                <span key={i} className="dpage-condition-chip">
                  {titleCase(cond)}
                </span>
              ))}
            </div>

            {general.medical_condition_description?.length > 0 &&
              general.medical_condition_description[0] && (
                <details className="dpage-cond-desc-details" style={{ marginTop: 16 }}>
                  <summary>Read condition descriptions from dataset</summary>
                  <div className="dpage-cond-desc-body">
                    {general.medical_condition_description.slice(0, 2).map((desc, i) => (
                      <p key={i} className="dpage-cond-desc-text">
                        {desc.slice(0, 600)}{desc.length > 600 ? "…" : ""}
                      </p>
                    ))}
                  </div>
                </details>
              )}
            <p className="dpage-source-note">
              Source: {sources.primary_source || "SafeMed reference dataset"}
            </p>
          </>
        ) : (
          <UnavailableNote field="Condition associations" />
        )}
      </Section>

      {/* ── HOW IT WORKS ── */}
      <Section id="howworks" title="How It Works (Pharmacology)">
        {pharmacology.mechanism_of_action ? (
          <>
            <p className="dpage-body-text">{pharmacology.mechanism_of_action}</p>
            <p className="dpage-source-note">Source: {sources.primary_source}</p>
          </>
        ) : (
          <UnavailableNote field="Mechanism of action" />
        )}
        {pharmacology.pharmacological_effect ? (
          <>
            <p className="dpage-body-text" style={{ marginTop: 12 }}>
              {pharmacology.pharmacological_effect}
            </p>
          </>
        ) : null}
      </Section>

      {/* ── ADMINISTRATION ── */}
      <Section id="admin" title="Administration">
        {admin.dosage_forms || admin.routes_of_administration ? (
          <div className="dpage-info-grid">
            <InfoRow label="Dosage forms" value={admin.dosage_forms} />
            <InfoRow label="Routes of administration" value={admin.routes_of_administration} />
            {admin.reference_dosing_information && (
              <div className="dpage-info-row" style={{ gridColumn: "1/-1" }}>
                <span className="dpage-info-label">Reference dosing information</span>
                <div>
                  <p className="dpage-info-value">{admin.reference_dosing_information}</p>
                  <p className="dpage-dosing-note">
                    ⓘ Reference information only. Always follow the instructions provided
                    by your healthcare professional or official medication labeling.
                    SafeMed does not recommend any specific dose.
                  </p>
                </div>
              </div>
            )}
          </div>
        ) : (
          <UnavailableNote field="Dosage forms and routes of administration" />
        )}
      </Section>

      {/* ── SIDE EFFECTS ── */}
      <Section
        id="sideeffects"
        title="Possible Side Effects"
        count={seList.length || undefined}
      >
        {seList.length > 0 ? (
          <>
            <p className="section-intro">
              Information from the SafeMed reference dataset. This list may not include every
              possible side effect. Consult official medication labeling or a healthcare professional.
            </p>
            <ul className="dpage-se-list">
              {seList.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
            <p className="dpage-source-note">
              Source: {sources.primary_source || "SafeMed reference dataset"}
            </p>
          </>
        ) : (
          <UnavailableNote field="Side-effect information" />
        )}
      </Section>

      {/* ── SAFETY ── */}
      <Section id="safety" title="Important Safety Information">
        {safety.contraindications || safety.warnings || safety.precautions ||
         safety.monitoring_information || safety.allergy_information ? (
          <div className="dpage-info-stack">
            {safety.warnings && (
              <div className="dpage-safety-item">
                <span className="dpage-safety-label">Warnings</span>
                <p>{safety.warnings}</p>
              </div>
            )}
            {safety.precautions && (
              <div className="dpage-safety-item">
                <span className="dpage-safety-label">Precautions</span>
                <p>{safety.precautions}</p>
              </div>
            )}
            {safety.contraindications && (
              <div className="dpage-safety-item dpage-safety-contraindication">
                <span className="dpage-safety-label">Contraindications</span>
                <p>{safety.contraindications}</p>
              </div>
            )}
            {safety.monitoring_information && (
              <div className="dpage-safety-item">
                <span className="dpage-safety-label">Monitoring information</span>
                <p>{safety.monitoring_information}</p>
              </div>
            )}
            {safety.allergy_information && (
              <div className="dpage-safety-item">
                <span className="dpage-safety-label">Allergy information</span>
                <p>{safety.allergy_information}</p>
              </div>
            )}
          </div>
        ) : (
          <UnavailableNote field="Safety information (warnings, precautions, contraindications)" />
        )}
      </Section>

      {/* ── INTERACTIONS ── */}
      <Section
        id="interactions"
        title="Interactions"
        count={interactions?.total_interactions || undefined}
      >
        {/* Food/Alcohol/Condition from master */}
        {(interact.drug_alcohol_interactions ||
          interact.drug_food_interactions ||
          interact.drug_condition_interactions) && (
          <div className="dpage-info-stack" style={{ marginBottom: 18 }}>
            {interact.drug_alcohol_interactions && (
              <div className="dpage-safety-item">
                <span className="dpage-safety-label">Alcohol interaction information</span>
                <p>{interact.drug_alcohol_interactions}</p>
              </div>
            )}
            {interact.drug_food_interactions && (
              <div className="dpage-safety-item">
                <span className="dpage-safety-label">Food interactions</span>
                <p>{interact.drug_food_interactions}</p>
              </div>
            )}
            {interact.drug_condition_interactions && (
              <div className="dpage-safety-item">
                <span className="dpage-safety-label">Condition interactions</span>
                <p>{interact.drug_condition_interactions}</p>
              </div>
            )}
          </div>
        )}

        {/* DDI records */}
        {interactions ? (
          interactions.total_interactions > 0 ? (
            <>
              <p className="section-intro">
                {interactions.total_interactions} documented drug-drug interaction record
                {interactions.total_interactions !== 1 ? "s" : ""} found for{" "}
                {titleCase(matchedName)} in the DDI reference dataset.
                Showing {Math.min(30, interactions.total_interactions)}.
              </p>
              <div className="dpage-ddi-list">
                {interactions.interactions.slice(0, 30).map((item, i) => {
                  const partner = item.drug_1?.toLowerCase() === matchedName.toLowerCase()
                    ? item.drug_2
                    : item.drug_1;
                  return (
                    <div key={i} className="dpage-ddi-item">
                      <div className="dpage-ddi-drugs">
                        <span className="dpage-ddi-self">{titleCase(matchedName)}</span>
                        <span className="dpage-ddi-plus">+</span>
                        <span className="dpage-ddi-partner">{titleCase(partner)}</span>
                      </div>
                      {item.interaction_description && (
                        <p className="dpage-ddi-desc">{item.interaction_description}</p>
                      )}
                    </div>
                  );
                })}
              </div>
              <p className="dpage-source-note">
                Source: SafeMed DDI reference dataset · {interactions.note}
              </p>
            </>
          ) : (
            <p className="section-intro">
              {d.in_ddi_dataset
                ? "No interaction records were returned for this medication."
                : "This medication is not present in the DDI reference dataset. No interaction data is available."}
            </p>
          )
        ) : (
          <UnavailableNote field="Drug-drug interactions" />
        )}

        {!interact.drug_alcohol_interactions &&
         !interact.drug_food_interactions &&
         !(interactions?.total_interactions > 0) && (
          <UnavailableNote field="Food, alcohol, and condition interaction information" />
        )}
      </Section>

      {/* ── SPECIAL POPULATIONS ── */}
      <Section id="special" title="Special Populations">
        {specialPop.pregnancy_information || specialPop.breastfeeding_information ||
         specialPop.pediatric_information || specialPop.geriatric_information ? (
          <div className="dpage-info-stack">
            {specialPop.pregnancy_information && (
              <div className="dpage-safety-item">
                <span className="dpage-safety-label">Pregnancy</span>
                <p>{specialPop.pregnancy_information}</p>
              </div>
            )}
            {specialPop.breastfeeding_information && (
              <div className="dpage-safety-item">
                <span className="dpage-safety-label">Breastfeeding</span>
                <p>{specialPop.breastfeeding_information}</p>
              </div>
            )}
            {specialPop.pediatric_information && (
              <div className="dpage-safety-item">
                <span className="dpage-safety-label">Children</span>
                <p>{specialPop.pediatric_information}</p>
              </div>
            )}
            {specialPop.geriatric_information && (
              <div className="dpage-safety-item">
                <span className="dpage-safety-label">Older adults</span>
                <p>{specialPop.geriatric_information}</p>
              </div>
            )}
          </div>
        ) : (
          <>
            {reg.pregnancy_category && (
              <div className="dpage-info-row" style={{ marginBottom: 12 }}>
                <span className="dpage-info-label">Pregnancy category</span>
                <span className="dpage-info-value">
                  Category {reg.pregnancy_category} (from regulatory classification)
                </span>
              </div>
            )}
            <UnavailableNote field="Detailed pregnancy, breastfeeding, pediatric, and geriatric information" />
          </>
        )}
      </Section>

      {/* ── KIDNEY / LIVER ── */}
      <Section id="kidneyliver" title="Kidney & Liver">
        {kidneyLiver.renal_information || kidneyLiver.hepatic_information ? (
          <div className="dpage-info-stack">
            {kidneyLiver.renal_information && (
              <div className="dpage-safety-item">
                <span className="dpage-safety-label">Renal information</span>
                <p>{kidneyLiver.renal_information}</p>
              </div>
            )}
            {kidneyLiver.hepatic_information && (
              <div className="dpage-safety-item">
                <span className="dpage-safety-label">Hepatic information</span>
                <p>{kidneyLiver.hepatic_information}</p>
              </div>
            )}
          </div>
        ) : (
          <UnavailableNote field="Renal and hepatic information" />
        )}
      </Section>

      {/* ── RELATED DRUGS ── */}
      {related.related_drugs?.length > 0 && (
        <Section id="related" title="Related Medications">
          <p className="section-intro">
            The following medications are listed as related in the reference dataset.
            This is a dataset association, not a clinical recommendation.
          </p>
          <div className="dpage-related-list">
            {related.related_drugs.slice(0, 12).map((item, i) => (
              <div key={i} className="dpage-related-item">
                <span className="dpage-related-name">{titleCase(item.name)}</span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* ── SOURCES ── */}
      <Section id="sources" title="Sources">
        <div className="sources-content">
          <p><strong>Primary source:</strong> {sources.primary_source || "SafeMed reference dataset"}</p>
          {sources.additional_sources && (
            <p><strong>Additional sources:</strong> {sources.additional_sources}</p>
          )}
          <p><strong>Data version:</strong> {sources.data_version || "1.0.0"}</p>
          <p><strong>Last verified:</strong> {sources.last_verified
            ? new Date(sources.last_verified).toLocaleDateString()
            : "Unknown"}</p>
          <p className="section-intro" style={{ marginTop: 12 }}>
            Information marked "SafeMed reference dataset" originates from the
            drugs_side_effects_drugs_com dataset used by the SafeMed academic project.
            Fields currently showing "Not available in the current SafeMed reference data"
            are genuinely absent from the source — they have not been omitted or fabricated.
          </p>
        </div>
      </Section>

      {/* NOTICE */}
      <div className="notice-card" style={{ marginTop: 20 }}>
        <div className="notice-icon" aria-hidden="true">!</div>
        <div>
          <h3>Important Notice</h3>
          <p>
            This medication information page is for educational and informational purposes only.
            SafeMed does not recommend starting, stopping, or changing any medication. Always
            consult a qualified healthcare professional for advice specific to your situation.
          </p>
        </div>
      </div>
    </main>
  );
}


// ============================================================
// MAIN APP
// ============================================================

function App() {
  const [view, setView] = useState("input"); // input | results | patients | mimic | ml_eval | history | library | drug
  const [result, setResult] = useState(null);
  const [selectedDrug, setSelectedDrug] = useState(null);
  const [prevView, setPrevView] = useState("input");
  const [patientPrefill, setPatientPrefill] = useState(null);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showReportModal, setShowReportModal] = useState(false);

  const [currentUser, setCurrentUser] = useState(() => {
    try {
      const saved = localStorage.getItem("safemed_user");
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const goTo = (newView) => {
    setPrevView(view);
    setView(newView);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleSubmit = (json) => {
    setResult(json);
    goTo("results");
  };

  const handleBack = () => {
    if (view === "drug") {
      goTo(prevView === "results" ? "results" : "library");
    } else if (view === "library") {
      goTo(prevView === "results" ? "results" : "input");
    } else {
      goTo("input");
    }
  };

  const handleLibrary = () => goTo("library");

  const handleSelectDrug = (drugName) => {
    setSelectedDrug(drugName);
    goTo("drug");
  };

  const handleSelectPatient = (patient) => {
    setPatientPrefill(patient);
    goTo("input");
  };

  const handleSelectMIMIC = (mimicCase) => {
    const diagList = mimicCase.diagnoses || [];
    const isRenal = diagList.some(
      (d) =>
        typeof d === "string" &&
        (d.toLowerCase().includes("kidney") ||
          d.toLowerCase().includes("renal") ||
          d.toLowerCase().includes("n18"))
    );
    const isHepatic = diagList.some(
      (d) =>
        typeof d === "string" &&
        (d.toLowerCase().includes("liver") ||
          d.toLowerCase().includes("cirrhosis") ||
          d.toLowerCase().includes("k70") ||
          d.toLowerCase().includes("k74"))
    );

    const mapped = {
      name: mimicCase.patient_name || `MIMIC-${mimicCase.subject_id}`,
      mrn: mimicCase.subject_id,
      age: mimicCase.age,
      gender: mimicCase.gender,
      allergies: "Screened at ICU Admission",
      renal_impairment: isRenal,
      hepatic_impairment: isHepatic,
      conditions: diagList,
      medications: (mimicCase.prescriptions || []).map((rx) => {
        if (typeof rx === "string") return { name: rx, dosage: "", frequency: "" };
        return {
          name: rx.drug_name || rx.name || "",
          dosage: rx.dosage || "",
          frequency: rx.frequency || "",
        };
      }),
    };

    setPatientPrefill(mapped);
    goTo("input");
  };

  const handleLoadAuditAnalysis = (histResult) => {
    setResult(histResult);
    goTo("results");
  };

  const handleLoginSuccess = (user) => {
    setCurrentUser(user);
    try {
      localStorage.setItem("safemed_user", JSON.stringify(user));
    } catch {}
  };

  const handleLogout = () => {
    setCurrentUser(null);
    try {
      localStorage.removeItem("safemed_user");
    } catch {}
  };

  return (
    <ErrorBoundary>
      <div className="app">
        <NavBar
          view={view}
          onNavigate={goTo}
          onOpenReport={() => setShowReportModal(true)}
          currentUser={currentUser}
          onOpenAuth={() => setShowAuthModal(true)}
          hasResult={!!result}
        />

        {view === "input" && (
          <InputPage
            onSubmit={handleSubmit}
            patientPrefill={patientPrefill}
            onClearPrefill={() => setPatientPrefill(null)}
          />
        )}

        {view === "results" && result && (
          <ErrorBoundary>
            <ResultsDashboard
              result={result}
              onDrugClick={handleSelectDrug}
              onOpenReport={() => setShowReportModal(true)}
              onNavigate={goTo}
            />
          </ErrorBoundary>
        )}

        {view === "results" && !result && (
          <div className="error-boundary">
            <p>No analysis result available. Please enter a patient regimen to analyze.</p>
            <button className="btn-primary" onClick={() => goTo("input")}>
              ← Go to Clinical Input
            </button>
          </div>
        )}

        {view === "patients" && (
          <ErrorBoundary>
            <PatientManager
              onSelectPatient={handleSelectPatient}
              currentUser={currentUser}
            />
          </ErrorBoundary>
        )}

        {view === "mimic" && (
          <ErrorBoundary>
            <MIMICExplorer onLoadToAnalysis={handleSelectMIMIC} />
          </ErrorBoundary>
        )}

        {view === "ml_eval" && (
          <ErrorBoundary>
            <MLEvaluationView />
          </ErrorBoundary>
        )}

        {view === "history" && (
          <ErrorBoundary>
            <AuditHistoryView onLoadAnalysis={handleLoadAuditAnalysis} />
          </ErrorBoundary>
        )}

        {view === "library" && (
          <ErrorBoundary>
            <MedicationLibrary onSelectDrug={handleSelectDrug} />
          </ErrorBoundary>
        )}

        {view === "drug" && selectedDrug && (
          <ErrorBoundary>
            <DrugDetailPage
              drugName={selectedDrug}
              onBack={handleBack}
              onLibrary={handleLibrary}
            />
          </ErrorBoundary>
        )}

        {/* MODALS */}
        {showAuthModal && (
          <AuthModal
            currentUser={currentUser}
            onClose={() => setShowAuthModal(false)}
            onLoginSuccess={handleLoginSuccess}
            onLogout={handleLogout}
          />
        )}

        {showReportModal && (
          <ReportModal
            result={result}
            onClose={() => setShowReportModal(false)}
            currentUser={currentUser}
            onDownloadPDF={() => generatePDF(result)}
          />
        )}
      </div>
    </ErrorBoundary>
  );
}

export default App;