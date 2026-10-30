import { useState, useEffect } from "react";

export default function AuditHistoryView({ onReloadAnalysis, onGenerateReport }) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/history");
      const json = await res.json();
      if (json.success) {
        setHistory(json.history || []);
      }
    } catch (e) {
      console.error("Error fetching analysis history:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const handleDeleteHistory = async (id, e) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this historical analysis record?")) return;
    try {
      await fetch(`http://localhost:8000/history/${id}`, { method: "DELETE" });
      fetchHistory();
    } catch (err) {
      console.error(err);
    }
  };

  const handleReload = async (item) => {
    try {
      const res = await fetch(`http://localhost:8000/history/${item.id}`);
      const data = await res.json();
      if (data.success && data.record?.full_result) {
        onReloadAnalysis(data.record.full_result);
      } else {
        alert("Full historical result data not found.");
      }
    } catch (err) {
      alert("Failed to load historical analysis.");
    }
  };

  const filteredHistory = history.filter((h) => {
    const q = searchTerm.toLowerCase();
    return (
      h.patient_name?.toLowerCase().includes(q) ||
      h.patient_mrn?.toLowerCase().includes(q) ||
      h.medications?.some((m) => m.toLowerCase().includes(q))
    );
  });

  return (
    <div className="audit-history-container">
      <div className="section-header-row">
        <div>
          <h2>Clinical Safety Audits & Analysis History</h2>
          <p className="section-subtitle">
            Secure persistent log of patient medication reviews, interaction audits, and clinical risk reports.
          </p>
        </div>
      </div>

      <div className="search-bar-wrapper">
        <input
          type="text"
          className="search-input"
          placeholder="Search audits by patient name, MRN, or medication…"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
        {searchTerm && (
          <button className="search-clear-btn" onClick={() => setSearchTerm("")}>
            ✕
          </button>
        )}
      </div>

      {loading ? (
        <div className="loading-state">
          <div className="loading-spinner" />
          <p>Loading clinical audit history…</p>
        </div>
      ) : filteredHistory.length === 0 ? (
        <div className="empty-state-box">
          <div className="empty-icon">📜</div>
          <h3>No Analysis History Found</h3>
          <p>Run a medication safety analysis to automatically record clinical audits.</p>
        </div>
      ) : (
        <div className="history-list">
          {filteredHistory.map((h) => {
            const isCritical = h.overall_risk_level?.includes("CRITICAL");
            const isHigh = h.overall_risk_level?.includes("HIGH");
            const isModerate = h.overall_risk_level?.includes("MODERATE");

            const riskBadgeClass = isCritical
              ? "risk-critical"
              : isHigh
              ? "risk-high"
              : isModerate
              ? "risk-mod"
              : "risk-low";

            const dateStr = h.created_at
              ? new Date(h.created_at).toLocaleString()
              : "Recent";

            return (
              <div key={h.id} className="history-item-card">
                <div className="history-card-top">
                  <div>
                    <div className="history-patient-row">
                      <span className="history-mrn">{h.patient_mrn || "Anonymous"}</span>
                      <h4 className="history-patient-name">{h.patient_name}</h4>
                    </div>
                    <span className="history-date">🕒 {dateStr}</span>
                  </div>

                  <div className="history-risk-pill-box">
                    <span className={`risk-badge ${riskBadgeClass}`}>
                      {h.overall_risk_level || "Standard Risk"}
                    </span>
                    {h.requires_clinical_review && (
                      <span className="review-req-tag">⚠️ Review Required</span>
                    )}
                  </div>
                </div>

                <div className="history-card-body">
                  <div className="history-stat-pills">
                    <span className="stat-pill">
                      💊 <strong>{(h.medications || []).length}</strong> Medications
                    </span>
                    <span className="stat-pill">
                      ⚡ <strong>{h.interactions_count}</strong> Interactions ({h.major_count} Major)
                    </span>
                    <span className="stat-pill">
                      🏥 <strong>{(h.conditions || []).length}</strong> Conditions ({h.multimorbidity_clashes} Clashes)
                    </span>
                  </div>

                  <div className="history-meds-summary">
                    <span className="meta-label">Regimen:</span>{" "}
                    {(h.medications || []).join(", ")}
                  </div>
                </div>

                <div className="history-card-footer">
                  <button
                    className="btn-primary btn-sm"
                    onClick={() => handleReload(h)}
                  >
                    🔄 Reload Analysis Dashboard
                  </button>
                  <button
                    className="btn-danger-outline btn-sm"
                    onClick={(e) => handleDeleteHistory(h.id, e)}
                    title="Delete record"
                  >
                    🗑️ Delete
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
