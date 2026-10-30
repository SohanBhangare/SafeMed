import os
import joblib
import json
import re
import numpy as np
import pandas as pd

# ============================================================
# MODEL & METRICS PATHS
# ============================================================

BUNDLE_PATH = "ml/models/safemed_models_bundle.pkl"
FALLBACK_PATH = "ml/models/safemed_improved_model.pkl"
METRICS_PATH = "ml/models/model_evaluation_metrics.json"

lr_model = None
dt_model = None
features = [
    "log_deg_1",
    "log_deg_2",
    "deg_product",
    "deg_diff",
    "side_effect_jaccard",
    "shared_classes_count",
    "both_rx",
    "csa_controlled_substance",
    "high_risk_pair"
]
evaluation_data = {}
_metadata = {}

if os.path.exists(BUNDLE_PATH):
    try:
        bundle = joblib.load(BUNDLE_PATH)
        lr_model = bundle.get("logistic_regression")
        dt_model = bundle.get("decision_tree")
        features = bundle.get("features", features)
        evaluation_data = bundle.get("evaluation", {})
        _metadata = bundle.get("metadata", {})
    except Exception as e:
        print(f"[SafeMed ML] Error loading bundle: {e}")

if not evaluation_data and os.path.exists(METRICS_PATH):
    try:
        with open(METRICS_PATH, "r", encoding="utf-8") as f:
            evaluation_data = json.load(f)
    except Exception:
        pass

# Backward compatibility alias
model = dt_model or lr_model

# ============================================================
# PHARMACOLOGICAL CACHES & GRAPH INDICES
# ============================================================

_total_deg: dict[str, float] = _metadata.get("total_deg", {})
_class_cache: dict[str, set] = {k: set(v) for k, v in _metadata.get("class_cache", {}).items()}
_rx_cache: dict[str, bool] = _metadata.get("rx_cache", {})
_csa_cache: dict[str, bool] = _metadata.get("csa_cache", {})
_se_cache: dict[str, set] = {k: set(v) for k, v in _metadata.get("se_cache", {}).items()}

HIGH_RISK_CLASSES = {
    "nsaid": {"ibuprofen", "naproxen", "diclofenac", "meloxicam", "celecoxib", "indomethacin", "ketorolac", "aspirin"},
    "anticoag": {"warfarin", "heparin", "enoxaparin", "apixaban", "rivaroxaban", "clopidogrel", "aspirin", "acetylsalicylic acid"},
    "raas": {"lisinopril", "enalapril", "ramipril", "losartan", "valsartan", "candesartan", "spironolactone"},
    "cns": {"diazepam", "lorazepam", "alprazolam", "clonazepam", "morphine", "oxycodone", "fentanyl", "tramadol", "codeine", "zolpidem", "gabapentin"},
    "qt": {"amiodarone", "sotalol", "citalopram", "escitalopram", "levofloxacin", "ciprofloxacin", "azithromycin", "haloperidol", "ondansetron"}
}

# If metadata was not bundled, populate dynamically from datasets
if not _total_deg and os.path.exists("data/cleaned/drug_interactions_cleaned.csv"):
    try:
        _ddi_df = pd.read_csv("data/cleaned/drug_interactions_cleaned.csv", usecols=["drug_1_normalized", "drug_2_normalized"])
        _deg1 = _ddi_df["drug_1_normalized"].value_counts()
        _deg2 = _ddi_df["drug_2_normalized"].value_counts()
        _total_deg = _deg1.add(_deg2, fill_value=0).to_dict()
    except Exception:
        pass

if not _class_cache and os.path.exists("data/cleaned/drugs_cleaned.csv"):
    try:
        _drugs_df = pd.read_csv("data/cleaned/drugs_cleaned.csv").drop_duplicates(subset=["drug_name_normalized"]).set_index("drug_name_normalized")
        for d, row in _drugs_df.iterrows():
            name = str(d).strip().lower()
            raw_c = str(row.get("drug_classes", "")).lower().split(",")
            _class_cache[name] = {x.strip() for x in raw_c if x.strip() and x.strip() != "nan"}
            _rx_cache[name] = str(row.get("rx_otc", "")).strip() == "Rx"
            csa_val = str(row.get("csa", "")).strip()
            _csa_cache[name] = bool(csa_val and csa_val != "nan" and csa_val != "M")
            raw_se = str(row.get("side_effects", ""))
            _se_cache[name] = set(re.findall(r"\b[a-z]{3,}\b", raw_se.lower())) if raw_se and raw_se != "nan" else set()
    except Exception:
        pass


def _is_high_risk_pair(d1: str, d2: str) -> float:
    s1, s2 = d1.lower().strip(), d2.lower().strip()
    if (s1 in HIGH_RISK_CLASSES["nsaid"] and s2 in HIGH_RISK_CLASSES["anticoag"]) or (s2 in HIGH_RISK_CLASSES["nsaid"] and s1 in HIGH_RISK_CLASSES["anticoag"]):
        return 1.0
    if (s1 in HIGH_RISK_CLASSES["nsaid"] and s2 in HIGH_RISK_CLASSES["raas"]) or (s2 in HIGH_RISK_CLASSES["nsaid"] and s1 in HIGH_RISK_CLASSES["raas"]):
        return 1.0
    if s1 in HIGH_RISK_CLASSES["cns"] and s2 in HIGH_RISK_CLASSES["cns"]:
        return 1.0
    if s1 in HIGH_RISK_CLASSES["qt"] and s2 in HIGH_RISK_CLASSES["qt"]:
        return 1.0
    return 0.0


# ============================================================
# FEATURE CONSTRUCTION
# ============================================================

def create_features(drug1: str, drug2: str) -> pd.DataFrame:
    """
    Construct standardized 9-dimensional pharmacological feature vector.
    """
    s1 = drug1.strip().lower()
    s2 = drug2.strip().lower()

    deg_1 = float(np.log1p(_total_deg.get(s1, 0)))
    deg_2 = float(np.log1p(_total_deg.get(s2, 0)))

    se1 = _se_cache.get(s1, set())
    se2 = _se_cache.get(s2, set())
    jaccard = float(len(se1 & se2) / len(se1 | se2)) if (se1 | se2) else 0.0

    c1 = _class_cache.get(s1, set())
    c2 = _class_cache.get(s2, set())
    shared_classes = float(len(c1 & c2))

    both_rx = float(int(_rx_cache.get(s1, False) and _rx_cache.get(s2, False)))
    csa_flag = float(int(_csa_cache.get(s1, False) or _csa_cache.get(s2, False)))
    high_risk = float(_is_high_risk_pair(s1, s2))

    return pd.DataFrame([{
        "log_deg_1": deg_1,
        "log_deg_2": deg_2,
        "deg_product": deg_1 * deg_2,
        "deg_diff": abs(deg_1 - deg_2),
        "side_effect_jaccard": jaccard,
        "shared_classes_count": shared_classes,
        "both_rx": both_rx,
        "csa_controlled_substance": csa_flag,
        "high_risk_pair": high_risk
    }])


# ============================================================
# PREDICTION (DUAL MODEL CLASSIFICATION)
# ============================================================

def predict_interaction(drug1: str, drug2: str) -> dict:
    """
    Predict interaction likelihood using dual models:
    Logistic Regression (linear probability) and Decision Tree (partitioning).
    """
    input_data = create_features(drug1, drug2)
    s1 = drug1.strip().lower()
    s2 = drug2.strip().lower()
    shared_classes = len(_class_cache.get(s1, set()) & _class_cache.get(s2, set()))

    # 1. Decision Tree Prediction
    dt_pred = 0
    dt_prob = 0.5
    if dt_model is not None:
        try:
            dt_pred = int(dt_model.predict(input_data)[0])
            if hasattr(dt_model, "predict_proba"):
                dt_prob = float(dt_model.predict_proba(input_data)[0][1])
        except Exception as e:
            print(f"[SafeMed ML] Decision tree predict error: {e}")

    # 2. Logistic Regression Prediction
    lr_pred = 0
    lr_prob = 0.5
    if lr_model is not None:
        try:
            lr_pred = int(lr_model.predict(input_data)[0])
            if hasattr(lr_model, "predict_proba"):
                lr_prob = float(lr_model.predict_proba(input_data)[0][1])
        except Exception as e:
            print(f"[SafeMed ML] Logistic regression predict error: {e}")

    consensus = bool(dt_pred == lr_pred)
    top_pred = dt_pred if dt_model is not None else lr_pred
    top_prob = dt_prob if dt_model is not None else lr_prob

    return {
        "prediction": top_pred,
        "probability": top_prob,
        "class_overlap": shared_classes > 0,
        "decision_tree": {
            "prediction": dt_pred,
            "probability": round(dt_prob, 4),
            "label": "Interaction-Like Pattern" if dt_pred == 1 else "Non-Interacting Pattern"
        },
        "logistic_regression": {
            "prediction": lr_pred,
            "probability": round(lr_prob, 4),
            "label": "Interaction-Like Pattern" if lr_pred == 1 else "Non-Interacting Pattern"
        },
        "consensus": consensus,
        "consensus_label": "High Model Agreement" if consensus else "Model Divergence / Review Needed",
        "consensus_agreed": consensus,
        "consensus_note": "High Model Agreement" if consensus else "Model Divergence / Review Needed"
    }


def get_evaluation_metrics() -> dict:
    """Return model evaluation metrics for both models."""
    global evaluation_data
    if not evaluation_data and os.path.exists(METRICS_PATH):
        try:
            with open(METRICS_PATH, "r", encoding="utf-8") as f:
                evaluation_data = json.load(f)
        except Exception:
            pass
    return evaluation_data