import pytest
from fastapi.testclient import TestClient
from api import app
from analysis.ml_predictor import predict_interaction, create_features, get_evaluation_metrics

client = TestClient(app)


def test_ml_model_evaluation_endpoint():
    """Verify the /ml/evaluation endpoint returns real, high-accuracy trained metrics."""
    response = client.get("/ml/evaluation")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "metrics" in data
    metrics = data["metrics"]
    
    assert "Logistic Regression" in metrics
    assert "Decision Tree" in metrics

    lr = metrics["Logistic Regression"]
    dt = metrics["Decision Tree"]

    # Test sample size
    assert data["sample_size"] == 70000
    assert lr["sample_counts"]["train_size"] == 56000
    assert lr["sample_counts"]["test_size"] == 14000

    # Model Performance Benchmarks: Must be > 80% accuracy and > 0.88 ROC-AUC
    assert lr["accuracy"] >= 0.80
    assert dt["accuracy"] >= 0.80
    assert lr["roc_auc"] >= 0.88
    assert dt["roc_auc"] >= 0.88
    assert lr["f1_score"] >= 0.80
    assert dt["f1_score"] >= 0.80

    # Verify confusion matrices match test split of 14,000 samples
    lr_cm = lr["confusion_matrix"]
    dt_cm = dt["confusion_matrix"]
    assert lr_cm["true_negative"] + lr_cm["false_positive"] + lr_cm["false_negative"] + lr_cm["true_positive"] == 14000
    assert dt_cm["true_negative"] + dt_cm["false_positive"] + dt_cm["false_negative"] + dt_cm["true_positive"] == 14000

    # Ensure false positives are significantly lower than the legacy 7,900+
    assert lr_cm["false_positive"] < 2500
    assert dt_cm["false_positive"] < 2500

    # Check that feature metrics contain the new pharmacological features
    assert "deg_product" in lr["feature_metrics"]
    assert "high_risk_pair" in lr["feature_metrics"]
    assert "deg_product" in dt["feature_metrics"]


def test_ml_predict_custom_endpoint_discriminative():
    """
    Verify that models do not output identical flat probabilities (~52%),
    and cleanly discriminate between high-risk interacting pairs and non-interacting pairs.
    """
    # 1. High risk pair: Lisinopril + Ibuprofen (RAAS + NSAID)
    res_high = client.post("/ml/predict", json={"drug_1": "Lisinopril", "drug_2": "Ibuprofen"})
    assert res_high.status_code == 200
    data_high = res_high.json()["result"]
    assert data_high["logistic_regression"]["prediction"] == 1
    assert data_high["decision_tree"]["prediction"] == 1
    assert data_high["logistic_regression"]["probability"] >= 0.90
    assert data_high["decision_tree"]["probability"] >= 0.90
    assert data_high["consensus"] is True

    # 2. Non-interacting pair: Amoxicillin + Acetaminophen
    res_low = client.post("/ml/predict", json={"drug_1": "Amoxicillin", "drug_2": "Acetaminophen"})
    assert res_low.status_code == 200
    data_low = res_low.json()["result"]
    assert data_low["logistic_regression"]["prediction"] == 0
    assert data_low["decision_tree"]["prediction"] == 0
    assert data_low["logistic_regression"]["probability"] < 0.40
    assert data_low["decision_tree"]["probability"] < 0.40
    assert data_low["consensus"] is True

    # 3. Unrelated pair: Doxycycline + Trioxsalen
    res_none = client.post("/ml/predict", json={"drug_1": "Doxycycline", "drug_2": "Trioxsalen"})
    assert res_none.status_code == 200
    data_none = res_none.json()["result"]
    assert data_none["logistic_regression"]["prediction"] == 0
    assert data_none["decision_tree"]["prediction"] == 0
    assert data_none["logistic_regression"]["probability"] < 0.05
    assert data_none["decision_tree"]["probability"] < 0.05

    # 4. Critical sanity check: dynamic probability range
    # In legacy model, difference was < 0.001 (52.26% vs 52.34%).
    prob_diff_lr = data_high["logistic_regression"]["probability"] - data_none["logistic_regression"]["probability"]
    prob_diff_dt = data_high["decision_tree"]["probability"] - data_none["decision_tree"]["probability"]
    assert prob_diff_lr > 0.80, f"Expected LR probability spread > 0.80, got {prob_diff_lr}"
    assert prob_diff_dt > 0.80, f"Expected DT probability spread > 0.80, got {prob_diff_dt}"


def test_feature_engineering_pipeline():
    """Verify that create_features generates correct columns and handles unknown drugs gracefully."""
    df_known = create_features("Lisinopril", "Ibuprofen")
    expected_cols = [
        "log_deg_1", "log_deg_2", "deg_product", "deg_diff",
        "side_effect_jaccard", "shared_classes_count",
        "both_rx", "csa_controlled_substance", "high_risk_pair"
    ]
    for col in expected_cols:
        assert col in df_known.columns
    assert df_known["high_risk_pair"].iloc[0] == 1.0

    # Unknown drug test (should not crash, fills defaults)
    df_unknown = create_features("UnknownDrugXYZ123", "FictionalCompound999")
    assert df_unknown["log_deg_1"].iloc[0] == 0.0
    assert df_unknown["log_deg_2"].iloc[0] == 0.0
    assert df_unknown["high_risk_pair"].iloc[0] == 0.0
    res_unknown = predict_interaction("UnknownDrugXYZ123", "FictionalCompound999")
    assert "prediction" in res_unknown
    assert "probability" in res_unknown


if __name__ == "__main__":
    pytest.main(["-v", __file__])
