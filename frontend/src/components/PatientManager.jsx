import { useState, useEffect } from "react";

export default function PatientManager({ onSelectPatient, onNewAnalysisWithPatient, onClose }) {
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedPatient, setSelectedPatient] = useState(null);

  // Form state for creating a new patient
  const [fullName, setFullName] = useState("");
  const [mrn, setMrn] = useState("");
  const [age, setAge] = useState("");
  const [gender, setGender] = useState("Female");
  const [conditionsText, setConditionsText] = useState("");
  const [allergies, setAllergies] = useState("");
  const [kidneyDisease, setKidneyDisease] = useState(false);
  const [liverDisease, setLiverDisease] = useState(false);
  const [pregnant, setPregnant] = useState(false);
  const [breastfeeding, setBreastfeeding] = useState(false);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);

  const fetchPatients = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/patients");
      const json = await res.json();
      if (json.success) {
        setPatients(json.data || []);
      }
    } catch (e) {
      console.error("Error fetching patients:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPatients();
  }, []);

  const handleCreatePatient = async (e) => {
    e.preventDefault();
    setSaving(true);
    const conds = conditionsText
      .split(/[,;\n]/)
      .map((c) => c.trim())
      .filter(Boolean);

    try {
      const res = await fetch("http://localhost:8000/patients", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: fullName,
          mrn: mrn || undefined,
          age,
          gender,
          conditions: conds,
          allergies,
          medical_history: {
            kidney_disease: kidneyDisease,
            liver_disease: liverDisease,
            pregnant,
            breastfeeding,
          },
          notes,
        }),
      });
      const data = await res.json();
      if (data.success) {
        setShowCreateModal(false);
        // Reset form
        setFullName("");
        setMrn("");
        setAge("");
        setConditionsText("");
        setAllergies("");
        setKidneyDisease(false);
        setLiverDisease(false);
        setPregnant(false);
        setBreastfeeding(false);
        setNotes("");
        fetchPatients();
      }
    } catch (err) {
      alert("Failed to save patient profile.");
    } finally {
      setSaving(false);
    }
  };

  const handleDeletePatient = async (id, e) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this patient profile?")) return;
    try {
      await fetch(`http://localhost:8000/patients/${id}`, { method: "DELETE" });
      fetchPatients();
      if (selectedPatient?.id === id) setSelectedPatient(null);
    } catch (err) {
      console.error(err);
    }
  };

  const filteredPatients = patients.filter((p) => {
    const q = searchTerm.toLowerCase();
    return (
      p.full_name?.toLowerCase().includes(q) ||
      p.mrn?.toLowerCase().includes(q) ||
      p.conditions?.some((c) => c.toLowerCase().includes(q))
    );
  });

  return (
    <div className="patient-manager-container">
      <div className="section-header-row">
        <div>
          <h2>Patient Profiles Database</h2>
          <p className="section-subtitle">
            Secure clinical patient records, multimorbidity profiles, and history
          </p>
        </div>
        <button
          className="btn-primary"
          onClick={() => setShowCreateModal(true)}
        >
          + Add New Patient Profile
        </button>
      </div>

      <div className="search-bar-wrapper">
        <input
          type="text"
          className="search-input"
          placeholder="Search by patient name, MRN, or diagnosed condition…"
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
          <p>Loading patient database…</p>
        </div>
      ) : filteredPatients.length === 0 ? (
        <div className="empty-state-box">
          <div className="empty-icon">📁</div>
          <h3>No Patient Profiles Found</h3>
          <p>Create a new profile or import an admission record from MIMIC-IV.</p>
        </div>
      ) : (
        <div className="patient-cards-grid">
          {filteredPatients.map((p) => {
            const isSelected = selectedPatient?.id === p.id;
            return (
              <div
                key={p.id}
                className={`patient-card ${isSelected ? "selected" : ""}`}
                onClick={() => setSelectedPatient(isSelected ? null : p)}
              >
                <div className="patient-card-header">
                  <div>
                    <span className="patient-mrn-badge">{p.mrn}</span>
                    <h3 className="patient-name">{p.full_name}</h3>
                  </div>
                  <div className="patient-demographics-pill">
                    {p.age ? `${p.age} yrs` : "Age N/A"} • {p.gender || "Gender N/A"}
                  </div>
                </div>

                <div className="patient-card-body">
                  <div className="patient-meta-row">
                    <span className="meta-label">Diagnosed Conditions:</span>
                    <div className="conditions-tags-row">
                      {p.conditions && p.conditions.length > 0 ? (
                        p.conditions.map((c, i) => (
                          <span key={i} className="condition-pill">
                            {c}
                          </span>
                        ))
                      ) : (
                        <span className="text-muted">None specified</span>
                      )}
                    </div>
                  </div>

                  {p.allergies && (
                    <div className="patient-meta-row">
                      <span className="meta-label">Allergies:</span>
                      <span className="allergy-alert-text">⚠️ {p.allergies}</span>
                    </div>
                  )}

                  <div className="patient-meta-row">
                    <span className="meta-label">Clinical History:</span>
                    <div className="history-badges-row">
                      {p.medical_history?.kidney_disease && (
                        <span className="history-badge renal">Kidney Disease</span>
                      )}
                      {p.medical_history?.liver_disease && (
                        <span className="history-badge hepatic">Liver Disease</span>
                      )}
                      {p.medical_history?.pregnant && (
                        <span className="history-badge pregnancy">Pregnant</span>
                      )}
                      {p.medical_history?.breastfeeding && (
                        <span className="history-badge lactation">Lactating</span>
                      )}
                      {!p.medical_history?.kidney_disease &&
                        !p.medical_history?.liver_disease &&
                        !p.medical_history?.pregnant &&
                        !p.medical_history?.breastfeeding && (
                          <span className="history-badge standard">No Special Flags</span>
                        )}
                    </div>
                  </div>

                  {p.prescribed_medications && p.prescribed_medications.length > 0 && (
                    <div className="patient-meta-row">
                      <span className="meta-label">Active Prescriptions ({p.prescribed_medications.length}):</span>
                      <p className="prescriptions-summary-text">
                        {p.prescribed_medications.map((m) => m.name || m).join(", ")}
                      </p>
                    </div>
                  )}

                  {p.notes && (
                    <div className="patient-notes-snippet">
                      <em>"{p.notes}"</em>
                    </div>
                  )}
                </div>

                <div className="patient-card-actions">
                  <button
                    className="btn-primary btn-sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      onNewAnalysisWithPatient(p);
                    }}
                  >
                    🚀 Load into SafeMed Analysis
                  </button>
                  <button
                    className="btn-danger-outline btn-sm"
                    onClick={(e) => handleDeletePatient(p.id, e)}
                    title="Delete profile"
                  >
                    🗑️
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* CREATE PATIENT MODAL */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-group">
                <span className="modal-badge-icon">👤</span>
                <div>
                  <h3>New Patient Profile</h3>
                  <p className="modal-subtitle">Register demographic, medical history & condition records</p>
                </div>
              </div>
              <button
                className="btn-modal-close"
                onClick={() => setShowCreateModal(false)}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreatePatient} className="patient-form">
              <div className="form-row-2">
                <div className="form-group">
                  <label>Full Patient Name *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Margaret H. Thornton"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label>MRN (Medical Record Number)</label>
                  <input
                    type="text"
                    placeholder="Auto-generated if blank (e.g. SM-2026-004)"
                    value={mrn}
                    onChange={(e) => setMrn(e.target.value)}
                  />
                </div>
              </div>

              <div className="form-row-2">
                <div className="form-group">
                  <label>Age (Years)</label>
                  <input
                    type="number"
                    placeholder="e.g. 68"
                    min="1"
                    max="125"
                    value={age}
                    onChange={(e) => setAge(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label>Gender</label>
                  <select
                    value={gender}
                    onChange={(e) => setGender(e.target.value)}
                  >
                    <option value="Female">Female</option>
                    <option value="Male">Male</option>
                    <option value="Other">Other / Non-Binary</option>
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label>Diagnosed Medical Conditions (Separate with commas)</label>
                <textarea
                  rows="2"
                  placeholder="e.g. Hypertension, Type 2 Diabetes, Chronic Kidney Disease, Atrial Fibrillation"
                  value={conditionsText}
                  onChange={(e) => setConditionsText(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label>Known Drug Allergies</label>
                <input
                  type="text"
                  placeholder="e.g. Penicillin, Sulfa drugs, Aspirin (GI reaction)"
                  value={allergies}
                  onChange={(e) => setAllergies(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label>Medical History & Special Populations Flags</label>
                <div className="checkbox-grid">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={kidneyDisease}
                      onChange={(e) => setKidneyDisease(e.target.checked)}
                    />
                    <span>Kidney Disease / Renal Impairment</span>
                  </label>
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={liverDisease}
                      onChange={(e) => setLiverDisease(e.target.checked)}
                    />
                    <span>Liver Disease / Hepatic Impairment</span>
                  </label>
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={pregnant}
                      onChange={(e) => setPregnant(e.target.checked)}
                    />
                    <span>Pregnant</span>
                  </label>
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={breastfeeding}
                      onChange={(e) => setBreastfeeding(e.target.checked)}
                    />
                    <span>Breastfeeding</span>
                  </label>
                </div>
              </div>

              <div className="form-group">
                <label>Clinical Notes</label>
                <textarea
                  rows="2"
                  placeholder="Clinical history notes, medication adherence remarks, organ panels..."
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </div>

              <div className="modal-actions-right">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShowCreateModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={saving}
                >
                  {saving ? "Saving…" : "Save Patient Profile"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
