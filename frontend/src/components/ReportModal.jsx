export default function ReportModal({ isOpen = true, onClose, result, onDownloadPDF, currentUser }) {
  if (isOpen === false || !result) return null;

  const payload = result?.data || result || {};
  const patientInfo = payload.patient_info || {};
  const summary = payload.summary || {};
  const medAnalysis = payload.medication_analysis || {};
  const interactions = medAnalysis.interactions || [];
  const multimorbidity = payload.multimorbidity || payload.multimorbidity_analysis || {};
  const contraindications = multimorbidity.contraindications || multimorbidity.disease_drug_contraindications || [];
  const clinicalRisk = payload.clinical_risk || payload.risk_assessment || {};
  const reviewFlags = clinicalRisk.high_priority_flags || clinicalRisk.review_flags || [];
  const compoundedToxicities = payload.compounded_toxicities || (payload.compounded_side_effects?.compounded_risks) || [];
  const mlPredictions = payload.ml_predictions || [];

  const handlePrint = () => {
    window.print();
  };

  const handleDownloadPDF = () => {
    if (onDownloadPDF) {
      onDownloadPDF();
    } else {
      window.print();
    }
  };

  return (
    <div className="modal-overlay report-modal-overlay" onClick={onClose}>
      <div className="modal-card report-modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="report-modal-toolbar no-print">
          <div className="toolbar-left">
            <span className="toolbar-icon">📄</span>
            <strong>Clinical Safety & Drug Interaction Report</strong>
          </div>
          <div className="toolbar-right" style={{ display: "flex", gap: "10px", alignItems: "center" }}>
            <button type="button" className="btn-secondary btn-sm" onClick={handlePrint}>
              🖨️ Print Report
            </button>
            <button type="button" className="btn-primary btn-sm" onClick={handleDownloadPDF}>
              📥 Save PDF / Print
            </button>
            <button type="button" className="btn-modal-close" onClick={onClose} aria-label="Close">
              ✕
            </button>
          </div>
        </div>

        <div className="printable-clinical-report" id="clinical-report-content">
          {/* Hospital/System Header */}
          <div className="report-header-block">
            <div className="report-brand">
              <div className="brand-cross">+</div>
              <div>
                <h2>SafeMed Clinical Decision Support</h2>
                <p className="brand-subtitle">Department of Clinical Pharmacology & Pharmacovigilance</p>
              </div>
            </div>
            <div className="report-meta-block">
              <div><strong>Report ID:</strong> RPT-{Date.now().toString().slice(-8)}</div>
              <div><strong>Date Generated:</strong> {new Date().toLocaleDateString()} {new Date().toLocaleTimeString()}</div>
              <div><strong>System Status:</strong> Certified Decision Support</div>
            </div>
          </div>

          <hr className="report-divider" />

          {/* Patient Profile Box */}
          <div className="report-section">
            <h3 className="report-section-title">1. Patient Profile & Clinical Demographics</h3>
            <div className="report-patient-grid">
              <div className="patient-field">
                <span className="field-lbl">Patient Name:</span>
                <span className="field-val">{patientInfo.patient_name || "Clinical Patient"}</span>
              </div>
              <div className="patient-field">
                <span className="field-lbl">MRN:</span>
                <span className="field-val">{patientInfo.patient_mrn || "SM-RECORD"}</span>
              </div>
              <div className="patient-field">
                <span className="field-lbl">Age / Gender:</span>
                <span className="field-val">{patientInfo.age || "N/A"} years • {patientInfo.gender || "N/A"}</span>
              </div>
              <div className="patient-field">
                <span className="field-lbl">Allergies:</span>
                <span className="field-val">{patientInfo.allergies || "No documented drug allergies"}</span>
              </div>
            </div>

            <div className="report-conditions-row">
              <strong>Diagnosed Medical Conditions:</strong>{" "}
              {payload.condition_analysis?.matched_conditions?.length > 0
                ? payload.condition_analysis.matched_conditions.map((c) => c.condition || c.input || c).join(", ")
                : "None documented"}
            </div>
          </div>

          {/* Executive Clinical Risk Assessment */}
          <div className="report-section">
            <h3 className="report-section-title">2. Executive Clinical Risk Assessment</h3>
            <div className="report-risk-summary-box">
              <div
                className="risk-level-banner"
                style={{
                  background:
                    (clinicalRisk.risk_level === "CRITICAL" || summary.overall_risk_level === "CRITICAL")
                      ? "#dc2626"
                      : (clinicalRisk.risk_level === "HIGH" || summary.overall_risk_level === "HIGH")
                      ? "#ea580c"
                      : "#d97706",
                }}
              >
                <span>OVERALL RISK STATUS:</span>
                <h4>{clinicalRisk.risk_level || summary.overall_risk_level || "MODERATE RISK"}</h4>
              </div>

              <div className="report-kpi-row">
                <div className="report-kpi">
                  <span className="kpi-num">{summary.medications_entered || 0}</span>
                  <span className="kpi-lbl">Prescribed Meds</span>
                </div>
                <div className="report-kpi">
                  <span className="kpi-num">{summary.interactions_found || 0}</span>
                  <span className="kpi-lbl">Interactions</span>
                </div>
                <div className="report-kpi">
                  <span className="kpi-num highlight-crit">{summary.major_interactions || 0}</span>
                  <span className="kpi-lbl">Major Severity</span>
                </div>
                <div className="report-kpi">
                  <span className="kpi-num">{multimorbidity.complexity_score || 0}/100</span>
                  <span className="kpi-lbl">Complexity Index</span>
                </div>
              </div>
            </div>

            {reviewFlags.length > 0 && (
              <div className="report-review-flags-box" style={{ marginTop: 14 }}>
                <h4 className="flags-header">⚠️ Priority Clinical Review Flags ({reviewFlags.length})</h4>
                <ul className="flags-list" style={{ listStyle: "none", padding: 0, margin: "8px 0 0" }}>
                  {reviewFlags.map((f, i) => (
                    <li
                      key={i}
                      className="flag-alert-card"
                      style={{
                        marginBottom: 8,
                        background: f.priority === "CRITICAL" ? "#fff1f2" : "#fff7ed",
                        borderLeft: `4px solid ${f.priority === "CRITICAL" ? "#dc2626" : "#f97316"}`,
                      }}
                    >
                      <strong>[{f.priority?.toUpperCase()} PRIORITY] {f.title}:</strong> {f.detail}
                      <div className="flag-action-text" style={{ marginTop: 4 }}>
                        <strong>Action:</strong> {f.action}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Documented Drug Interactions */}
          <div className="report-section">
            <h3 className="report-section-title">3. Documented Drug-Drug Interactions</h3>
            {interactions.length === 0 ? (
              <p className="no-records-text">No documented pairwise interactions were identified in the reference dataset.</p>
            ) : (
              <table className="report-table">
                <thead>
                  <tr>
                    <th>Medication Pair</th>
                    <th>Severity Level</th>
                    <th>Clinical Mechanism & Description</th>
                    <th>Actionable Guidance</th>
                  </tr>
                </thead>
                <tbody>
                  {interactions.map((it, idx) => (
                    <tr key={idx}>
                      <td className="med-pair-cell">
                        <strong>{it.drug_1?.toUpperCase()}</strong> + <strong>{it.drug_2?.toUpperCase()}</strong>
                      </td>
                      <td>
                        <span className={`severity-tag ${it.severity?.toLowerCase() || "moderate"}`}>
                          {it.severity || "Moderate"}
                        </span>
                      </td>
                      <td className="desc-cell">{it.clinical_rationale || it.description}</td>
                      <td className="action-cell">{it.action_recommendation || it.action || "Standard monitoring recommended."}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Multimorbidity Disease-Drug Contraindications */}
          <div className="report-section">
            <h3 className="report-section-title">4. Multimorbidity & Disease-Drug Contraindications</h3>
            {contraindications.length === 0 ? (
              <p className="no-records-text">No direct disease-drug contraindications were detected for the diagnosed conditions.</p>
            ) : (
              <table className="report-table">
                <thead>
                  <tr>
                    <th>Diagnosed Disease</th>
                    <th>Conflicting Medication</th>
                    <th>Risk Tier</th>
                    <th>Pathophysiological Mechanism & Recommendation</th>
                  </tr>
                </thead>
                <tbody>
                  {contraindications.map((c, i) => (
                    <tr key={i}>
                      <td><strong>{c.condition}</strong></td>
                      <td><span className="contra-med-tag">{c.contraindicated_drug || c.medication}</span></td>
                      <td><span className={`severity-tag ${c.severity?.toLowerCase() || "major"}`}>{c.severity || "Major"}</span></td>
                      <td className="desc-cell">
                        {c.mechanism} {c.recommendation && <span>— <em>{c.recommendation}</em></span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Compounded Organ Toxicities */}
          {compoundedToxicities.length > 0 && (
            <div className="report-section">
              <h3 className="report-section-title">5. Compounded Organ-System Toxicities</h3>
              <ul className="compounded-list" style={{ paddingLeft: 20 }}>
                {compoundedToxicities.map((cr, i) => (
                  <li key={i} className="compounded-item" style={{ marginBottom: 6 }}>
                    <strong>{cr.system || cr.organ_system} Toxicity ({cr.severity || "Moderate"}):</strong>{" "}
                    {cr.concerns || cr.alert} (Contributing drugs: {Array.isArray(cr.drugs) ? cr.drugs.join(", ") : "Prescribed regimen"})
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Machine Learning Model Evaluation Consensus */}
          <div className="report-section">
            <h3 className="report-section-title">6. Machine Learning Model Consensus (Logistic Regression vs Decision Tree)</h3>
            <p className="ml-note-text" style={{ fontSize: 13, color: "#64748b", marginBottom: 12 }}>
              Dual-model interaction pattern classification performed using both L2-regularized Logistic Regression and an 8-depth Decision Tree Classifier.
            </p>
            <div className="report-ml-chips" style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
              {mlPredictions.slice(0, 8).map((ml, i) => {
                const lr = ml.logistic_regression || {};
                const dt = ml.decision_tree || {};
                const isAgreed = ml.consensus_agreed ?? ml.consensus ?? (lr.prediction === dt.prediction);
                const lrProb = (Number(lr.probability ?? ml.probability ?? 0) * 100).toFixed(1);
                const dtProb = (Number(dt.probability ?? ml.probability ?? 0) * 100).toFixed(1);
                return (
                  <div key={i} className="report-ml-chip" style={{ background: "#f8fafc", border: "1px solid #e2e8f0", padding: "8px 14px", borderRadius: 8, minWidth: 240 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                      <span className="pair-names" style={{ fontWeight: 700, textTransform: "capitalize" }}>
                        {ml.drug_1} + {ml.drug_2}
                      </span>
                      <span className={`chip-badge ${isAgreed ? "agreed" : "diverged"}`}>
                        {isAgreed ? "✓ Consensus Agreement" : "△ Model Divergence"}
                      </span>
                    </div>
                    <div style={{ fontSize: 11.5, color: "#475569" }}>
                      <span>LR: {lr.prediction === 1 ? "Interaction" : "No Pattern"} ({lrProb}%)</span> • <span>DT: {dt.prediction === 1 ? "Interaction" : "No Pattern"} ({dtProb}%)</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Clinical Disclaimer & Safety Warnings */}
          <div className="report-disclaimer-card">
            <h4>⚠️ MANDATORY CLINICAL SAFETY WARNING & DISCLAIMER</h4>
            <p>
              This report is generated by SafeMed as an assistive clinical decision support tool for healthcare professionals.
              The information herein is derived from reference pharmacology databases, FDA package inserts, and academic machine learning models.
              It does NOT constitute an automated medical diagnosis, clinical prescription, or treatment order.
              All flagged interactions, contraindications, and recommendations require independent professional clinical review,
              therapeutic drug monitoring, and patient-specific risk-benefit assessment by a licensed physician or pharmacist.
            </p>
          </div>

          {/* Clinician Signature Block */}
          <div className="report-signature-grid">
            <div className="sig-block">
              <div className="sig-line" />
              <span>
                {currentUser?.full_name
                  ? `Reviewing Clinician: ${currentUser.full_name} (${currentUser.role || "Clinician"})`
                  : "Reviewing Physician / Pharmacist Signature"}
              </span>
            </div>
            <div className="sig-block">
              <div className="sig-line" />
              <span>Date: {new Date().toLocaleDateString()} • Clinical License / NPI Number</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
