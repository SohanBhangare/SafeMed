import pytest
from fastapi.testclient import TestClient
from api import app

client = TestClient(app)

def test_type2_diabetes_hypertension_patient_consistency():
    """
    Verify complete clinical consistency for a patient with:
    - Conditions: Type 2 Diabetes, Hypertension
    - Medications: Metformin, Lisinopril, Ibuprofen
    """
    payload = {
        "medications": ["Metformin", "Lisinopril", "Ibuprofen"],
        "conditions": ["Type 2 Diabetes", "Hypertension"],
        "age": "58",
        "gender": "Male",
        "patient_name": "John Doe",
        "patient_mrn": "SM-2026-T2D",
        "save_to_history": False
    }

    response = client.post("/analyze", json=payload)
    assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}"

    res = response.json()
    assert res.get("success") is True, "Expected success to be True"
    assert "data" in res, "Response must contain 'data'"

    data = res["data"]
    summary = data["summary"]
    clinical_risk = data["clinical_risk"]
    multimorbidity = data["multimorbidity"]
    contraindications = multimorbidity["contraindications"]
    ml_predictions = data["ml_predictions"]
    compounded_toxicities = data["compounded_toxicities"]
    interactions = data["medication_analysis"]["interactions"]

    # 1. Medication & Condition Recognition
    assert summary["medications_entered"] == 3
    assert summary["medications_matched"] == 3
    assert summary["conditions_entered"] == 2
    assert summary["conditions_matched"] == 2

    # 2. Executive Clinical Risk Scores
    assert clinical_risk["risk_level"] == "MODERATE"
    assert clinical_risk["overall_risk_score"] == 45
    assert clinical_risk["overall_risk_level"] == "MODERATE RISK - MONITORING ADVISED"
    assert clinical_risk["requires_clinical_review"] is False

    # 3. Multimorbidity Complexity Scores
    assert multimorbidity["complexity_score"] == 66
    assert multimorbidity["complexity_tier"] == "Moderate Multimorbidity Complexity"
    assert multimorbidity["clashes_count"] == 1
    assert multimorbidity["is_multimorbid"] is True

    # 4. Disease-Drug Contraindication
    assert len(contraindications) == 1
    contra = contraindications[0]
    assert contra["condition"].lower() == "hypertension"
    assert contra["contraindicated_drug"].lower() == "ibuprofen"
    assert contra["severity"] in ["Moderate", "High", "Critical"]
    assert "vasoconstriction" in contra["mechanism"].lower() or "nsaids" in contra["mechanism"].lower()
    assert "nsaids" in contra["recommendation"].lower()

    # 5. Documented Drug Interactions
    assert len(interactions) == 1
    interaction = interactions[0]
    pair = {interaction["drug_1"].lower(), interaction["drug_2"].lower()}
    assert pair == {"lisinopril", "ibuprofen"}
    assert interaction["severity"] == "Moderate"

    # 6. Compounded Organ Toxicities
    assert len(compounded_toxicities) == 5
    systems = {t["system"] for t in compounded_toxicities}
    assert "Cardiovascular" in systems
    assert "Renal & Electrolyte" in systems
    assert "Gastrointestinal" in systems
    assert "Central Nervous System" in systems
    assert "Hepatic" in systems

    # 7. Machine Learning Model Consensus
    assert len(ml_predictions) == 3
    for pred in ml_predictions:
        assert pred["consensus"] is True
        assert pred["consensus_agreed"] is True
        assert "High Model Agreement" in pred["consensus_label"]
        assert "logistic_regression" in pred
        assert "decision_tree" in pred
        assert pred["logistic_regression"]["prediction"] in [0, 1]
        assert pred["decision_tree"]["prediction"] in [0, 1]
        assert 0.0 <= pred["logistic_regression"]["probability"] <= 1.0
        assert 0.0 <= pred["decision_tree"]["probability"] <= 1.0

if __name__ == "__main__":
    pytest.main(["-v", __file__])
