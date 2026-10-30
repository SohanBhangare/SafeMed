import { useState, useEffect } from "react";

export default function MIMICExplorer({ onExtractAndAnalyze }) {
  const [activeTab, setActiveTab] = useState("cohort"); // "cohort" | "raw"
  const [cohort, setCohort] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCase, setSelectedCase] = useState(null);

  // Raw text extraction state
  const [rawText, setRawText] = useState("");
  const [extracting, setExtracting] = useState(false);
  const [extractedResult, setExtractedResult] = useState(null);

  const fetchCohort = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/mimic/cohort");
      const json = await res.json();
      if (json.success) {
        setCohort(json.cohort || []);
        if (json.cohort && json.cohort.length > 0) {
          setSelectedCase(json.cohort[0]);
        }
      }
    } catch (e) {
      console.error("Error fetching MIMIC cohort:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCohort();
  }, []);

  const handleExtractFromCohort = (mimicCase) => {
    const meds = (mimicCase.prescriptions || []).map((p) => p.drug_name).filter(Boolean);
    const conds = (mimicCase.diagnoses || []).map((d) => d.description).filter(Boolean);
    const medDetails = (mimicCase.prescriptions || []).map((p) => ({
      name: p.drug_name,
      dosage: p.dose || "",
      frequency: p.freq || "",
    }));

    onExtractAndAnalyze({
      patient_name: mimicCase.patient_name,
      mrn: `MIMIC-${mimicCase.subject_id}`,
      age: String(mimicCase.age || ""),
      gender: mimicCase.gender === "M" ? "Male" : "Female",
      conditions: conds,
      medications: meds,
      medication_details: medDetails,
      medical_history: {
        kidney_disease: conds.some((c) => c.toLowerCase().includes("kidney") || c.toLowerCase().includes("renal")),
        liver_disease: conds.some((c) => c.toLowerCase().includes("liver") || c.toLowerCase().includes("cirrhosis")),
        pregnant: false,
        breastfeeding: false,
      },
      allergies: "Extracted from MIMIC-IV Clinical Record",
    });
  };

  const handleRunRawExtraction = async () => {
    if (!rawText.trim()) return;
    setExtracting(true);
    setExtractedResult(null);

    try {
      const res = await fetch("http://localhost:8000/mimic/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_text: rawText }),
      });
      const data = await res.json();
      if (data.success) {
        setExtractedResult(data);
      }
    } catch (err) {
      alert("Extraction failed. Please check network connection.");
    } finally {
      setExtracting(false);
    }
  };

  const loadSampleDischargeSummary = () => {
    setRawText(`MIMIC-IV INPATIENT DISCHARGE SUMMARY
SUBJECT_ID: 10004291 | HADM_ID: 24901823 | AGE: 69 | GENDER: F
ADMISSION SERVICE: MEDICAL INTENSIVE CARE UNIT (MICU)

PRINCIPAL DISCHARGE DIAGNOSES:
1. Acute decompensated congestive heart failure with reduced ejection fraction (ICD-10 I50.23)
2. Essential hypertension (ICD-10 I10)
3. Chronic kidney disease, stage 3 (ICD-10 N18.3)
4. Type 2 diabetes mellitus with diabetic neuropathy (ICD-10 E11.40)
5. Osteoarthritis of knee (ICD-10 M17.9)

DISCHARGE MEDICATIONS:
1. Furosemide 40 mg PO DAILY
2. Lisinopril 10 mg PO DAILY
3. Metformin 500 mg PO BID with meals
4. Spironolactone 25 mg PO DAILY
5. Ibuprofen 400 mg PO PRN for joint pain
6. Atorvastatin 40 mg PO QPM

HOSPITAL COURSE:
Patient presented with progressive orthopnea, paroxysmal nocturnal dyspnea, and peripheral edema. Initial serum creatinine 1.8 mg/dL. Diuresed with IV loop diuretics.`);
  };

  return (
    <div className="mimic-explorer-container">
      <div className="section-header-row">
        <div>
          <div className="mimic-badge-title">
            <span className="mimic-logo-tag">MIMIC-IV</span>
            <h2>Clinical ICU Integration & Record Extraction</h2>
          </div>
          <p className="section-subtitle">
            Extract patient diagnoses (ICD-9/10) and inpatient medication records directly from the Beth Israel Deaconess / MIT MIMIC-IV database.
          </p>
        </div>

        <div className="tab-pill-group">
          <button
            className={`tab-pill ${activeTab === "cohort" ? "active" : ""}`}
            onClick={() => setActiveTab("cohort")}
          >
            🏥 Real Inpatient Cohort Cases
          </button>
          <button
            className={`tab-pill ${activeTab === "raw" ? "active" : ""}`}
            onClick={() => setActiveTab("raw")}
          >
            📋 Raw EHR & Notes Extractor
          </button>
        </div>
      </div>

      {activeTab === "cohort" && (
        <div className="mimic-cohort-layout">
          {/* Cohort Sidebar */}
          <div className="mimic-sidebar">
            <h4 className="sidebar-heading">MIMIC-IV Cohort Admissions ({cohort.length})</h4>
            <div className="cohort-list">
              {cohort.map((c) => {
                const isSelected = selectedCase?.subject_id === c.subject_id;
                return (
                  <div
                    key={c.subject_id}
                    className={`cohort-item-card ${isSelected ? "active" : ""}`}
                    onClick={() => setSelectedCase(c)}
                  >
                    <div className="cohort-card-top">
                      <span className="mimic-id">#{c.subject_id}</span>
                      <span className="unit-badge">{c.admission_type}</span>
                    </div>
                    <h5 className="cohort-primary-diag">{c.primary_diagnosis}</h5>
                    <div className="cohort-stats">
                      <span>{c.age}yo {c.gender === "M" ? "Male" : "Female"}</span>
                      <span>•</span>
                      <span>{(c.prescriptions || []).length} Meds</span>
                      <span>•</span>
                      <span>{(c.diagnoses || []).length} ICDs</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Selected Case Detail */}
          <div className="mimic-case-detail">
            {selectedCase ? (
              <div className="case-content-card">
                <div className="case-header">
                  <div>
                    <span className="case-subject-tag">MIMIC-IV Case #{selectedCase.subject_id} (HADM #{selectedCase.hadm_id})</span>
                    <h3>{selectedCase.primary_diagnosis}</h3>
                    <div className="patient-demographics-row">
                      <span><strong>Age:</strong> {selectedCase.age} years</span>
                      <span>•</span>
                      <span><strong>Sex:</strong> {selectedCase.gender === "M" ? "Male" : "Female"}</span>
                      <span>•</span>
                      <span><strong>Unit:</strong> {selectedCase.admission_type}</span>
                    </div>
                  </div>

                  <button
                    className="btn-primary btn-extract-action"
                    onClick={() => handleExtractFromCohort(selectedCase)}
                  >
                    ⚡ Extract & Load into SafeMed Analysis
                  </button>
                </div>

                <div className="case-notes-banner">
                  <strong>Clinical Case Summary:</strong> {selectedCase.clinical_notes}
                </div>

                <div className="case-split-grid">
                  {/* Diagnoses Section */}
                  <div className="data-table-card">
                    <div className="table-card-header">
                      <h4>📋 Extracted ICD-10 Diagnoses ({(selectedCase.diagnoses || []).length})</h4>
                    </div>
                    <div className="table-wrapper">
                      <table className="clinical-data-table">
                        <thead>
                          <tr>
                            <th>ICD Code</th>
                            <th>Clinical Description</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(selectedCase.diagnoses || []).map((d, i) => (
                            <tr key={i}>
                              <td className="icd-code-cell">{d.code}</td>
                              <td className="icd-desc-cell">{d.description}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Prescriptions Section */}
                  <div className="data-table-card">
                    <div className="table-card-header">
                      <h4>💊 Prescribed Medications ({(selectedCase.prescriptions || []).length})</h4>
                    </div>
                    <div className="table-wrapper">
                      <table className="clinical-data-table">
                        <thead>
                          <tr>
                            <th>Medication</th>
                            <th>Dose</th>
                            <th>Route</th>
                            <th>Frequency</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(selectedCase.prescriptions || []).map((p, i) => (
                            <tr key={i}>
                              <td className="med-name-cell"><strong>{p.drug_name}</strong></td>
                              <td>{p.dose}</td>
                              <td>{p.route}</td>
                              <td><span className="freq-badge">{p.freq}</span></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="empty-state-box">
                <p>Select a MIMIC-IV cohort case to view records.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === "raw" && (
        <div className="mimic-raw-extractor-card">
          <div className="raw-header">
            <div>
              <h3>Natural Language EHR & MIMIC Record Extractor</h3>
              <p className="text-muted">
                Paste raw clinical discharge summaries, nursing progress notes, or pharmacy order text.
              </p>
            </div>
            <button
              type="button"
              className="btn-secondary btn-sm"
              onClick={loadSampleDischargeSummary}
            >
              📄 Load Sample MIMIC Discharge Note
            </button>
          </div>

          <div className="form-group">
            <textarea
              rows="10"
              className="raw-textarea"
              placeholder="Paste raw MIMIC-IV text or discharge summary here..."
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
            />
          </div>

          <div className="extractor-actions-row">
            <button
              className="btn-primary"
              disabled={extracting || !rawText.trim()}
              onClick={handleRunRawExtraction}
            >
              {extracting ? "Extracting Clinical Records…" : "🔍 Extract Medications & Diagnoses"}
            </button>
            {rawText && (
              <button className="btn-secondary" onClick={() => { setRawText(""); setExtractedResult(null); }}>
                Clear Text
              </button>
            )}
          </div>

          {extractedResult && (
            <div className="extracted-results-box">
              <div className="extracted-header">
                <span className="success-icon">✓</span>
                <h4>Extraction Complete</h4>
              </div>

              <div className="extracted-grid">
                <div className="extracted-col">
                  <h5>Extracted Medications ({extractedResult.extracted_medications.length})</h5>
                  <div className="extracted-chips">
                    {extractedResult.extracted_medications.map((m, i) => (
                      <span key={i} className="chip-med">💊 {m}</span>
                    ))}
                  </div>
                </div>

                <div className="extracted-col">
                  <h5>Extracted Diagnoses & Conditions ({extractedResult.extracted_conditions.length})</h5>
                  <div className="extracted-chips">
                    {extractedResult.extracted_conditions.map((c, i) => (
                      <span key={i} className="chip-cond">📋 {c}</span>
                    ))}
                  </div>
                </div>
              </div>

              <div className="extracted-footer">
                <button
                  className="btn-primary"
                  onClick={() => {
                    onExtractAndAnalyze({
                      patient_name: "MIMIC-IV Natural Language Extraction",
                      mrn: "MIMIC-NLP",
                      age: "69",
                      gender: "Female",
                      conditions: extractedResult.extracted_conditions,
                      medications: extractedResult.extracted_medications,
                      medication_details: extractedResult.medication_details || [],
                      medical_history: {
                        kidney_disease: extractedResult.extracted_conditions.some((c) => c.toLowerCase().includes("kidney")),
                        liver_disease: false,
                        pregnant: false,
                        breastfeeding: false,
                      },
                      allergies: "",
                    });
                  }}
                >
                  🚀 Run SafeMed Analysis with Extracted Data
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
