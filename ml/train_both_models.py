import pandas as pd
import numpy as np
import random
import re
import os
import joblib
import json
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    roc_auc_score
)

# ============================================================
# CONFIGURATION & REPRODUCIBILITY
# ============================================================

RANDOM_STATE = 42
random.seed(RANDOM_STATE)
np.random.seed(RANDOM_STATE)

DDI_FILE = "data/cleaned/drug_interactions_cleaned.csv"
DRUGS_FILE = "data/cleaned/drugs_cleaned.csv"
DATA_OUTPUT = "data/ml/improved_interaction_features.csv"
MODEL_DIR = "ml/models"

os.makedirs("data/ml", exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

print("=" * 70)
print("SAFEMED MACHINE LEARNING PIPELINE: DUAL MODEL TRAINING")
print("=" * 70)

# ============================================================
# 1. LOAD RAW DATASETS
# ============================================================

print("\n[1/5] Loading reference datasets...")
ddi = pd.read_csv(DDI_FILE)
drugs_df = pd.read_csv(DRUGS_FILE).drop_duplicates(subset=["drug_name_normalized"]).set_index("drug_name_normalized")

print(f"  • Documented interactions: {len(ddi):,}")
print(f"  • Pharmacological drug monographs: {len(drugs_df):,}")

# Interaction graph degree map (interaction propensity)
deg1 = ddi["drug_1_normalized"].value_counts()
deg2 = ddi["drug_2_normalized"].value_counts()
total_deg = deg1.add(deg2, fill_value=0).to_dict()

all_drugs = sorted(set(ddi["drug_1_normalized"]).union(set(ddi["drug_2_normalized"])))
existing_pairs = set(ddi["drug_pair"])
print(f"  • Graph universe size: {len(all_drugs):,} unique drugs")

# ============================================================
# 2. PHARMACOLOGICAL FEATURE EXTRACTION
# ============================================================

print("\n[2/5] Engineering pharmacological and biomedical features...")

HIGH_RISK_CLASSES = {
    "nsaid": {"ibuprofen", "naproxen", "diclofenac", "meloxicam", "celecoxib", "indomethacin", "ketorolac", "aspirin"},
    "anticoag": {"warfarin", "heparin", "enoxaparin", "apixaban", "rivaroxaban", "clopidogrel", "aspirin", "acetylsalicylic acid"},
    "raas": {"lisinopril", "enalapril", "ramipril", "losartan", "valsartan", "candesartan", "spironolactone"},
    "cns": {"diazepam", "lorazepam", "alprazolam", "clonazepam", "morphine", "oxycodone", "fentanyl", "tramadol", "codeine", "zolpidem", "gabapentin"},
    "qt": {"amiodarone", "sotalol", "citalopram", "escitalopram", "levofloxacin", "ciprofloxacin", "azithromycin", "haloperidol", "ondansetron"}
}

def is_high_risk_combo(d1: str, d2: str) -> int:
    s1, s2 = d1.lower().strip(), d2.lower().strip()
    if (s1 in HIGH_RISK_CLASSES["nsaid"] and s2 in HIGH_RISK_CLASSES["anticoag"]) or (s2 in HIGH_RISK_CLASSES["nsaid"] and s1 in HIGH_RISK_CLASSES["anticoag"]):
        return 1
    if (s1 in HIGH_RISK_CLASSES["nsaid"] and s2 in HIGH_RISK_CLASSES["raas"]) or (s2 in HIGH_RISK_CLASSES["nsaid"] and s1 in HIGH_RISK_CLASSES["raas"]):
        return 1
    if s1 in HIGH_RISK_CLASSES["cns"] and s2 in HIGH_RISK_CLASSES["cns"]:
        return 1
    if s1 in HIGH_RISK_CLASSES["qt"] and s2 in HIGH_RISK_CLASSES["qt"]:
        return 1
    return 0

def extract_se_tokens(d: str) -> set:
    if d not in drugs_df.index:
        return set()
    raw = str(drugs_df.loc[d, "side_effects"])
    if not raw or raw == "nan":
        return set()
    return set(re.findall(r"\b[a-z]{3,}\b", raw.lower()))

se_cache = {d: extract_se_tokens(d) for d in all_drugs}

# Pre-extract classes & attributes
class_cache = {}
rx_cache = {}
csa_cache = {}

for d in all_drugs:
    if d in drugs_df.index:
        raw_classes = str(drugs_df.loc[d, "drug_classes"]).lower().split(",")
        class_cache[d] = {x.strip() for x in raw_classes if x.strip() and x.strip() != "nan"}
        rx_cache[d] = str(drugs_df.loc[d, "rx_otc"]).strip() == "Rx"
        csa_val = str(drugs_df.loc[d, "csa"]).strip()
        csa_cache[d] = bool(csa_val and csa_val != "nan" and csa_val != "M")
    else:
        class_cache[d] = set()
        rx_cache[d] = False
        csa_cache[d] = False

feature_columns = [
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

def build_features(d1: str, d2: str) -> list:
    s1, s2 = d1.lower().strip(), d2.lower().strip()
    
    deg_1 = float(np.log1p(total_deg.get(s1, 0)))
    deg_2 = float(np.log1p(total_deg.get(s2, 0)))
    
    se1 = se_cache.get(s1, set())
    se2 = se_cache.get(s2, set())
    jaccard = float(len(se1 & se2) / len(se1 | se2)) if (se1 | se2) else 0.0
    
    c1 = class_cache.get(s1, set())
    c2 = class_cache.get(s2, set())
    shared_classes = float(len(c1 & c2))
    
    both_rx = float(int(rx_cache.get(s1, False) and rx_cache.get(s2, False)))
    csa_flag = float(int(csa_cache.get(s1, False) or csa_cache.get(s2, False)))
    high_risk = float(is_high_risk_combo(s1, s2))
    
    return [
        deg_1,
        deg_2,
        deg_1 * deg_2,
        abs(deg_1 - deg_2),
        jaccard,
        shared_classes,
        both_rx,
        csa_flag,
        high_risk
    ]

# ============================================================
# 3. CONSTRUCT BALANCED DATASET
# ============================================================

print("\n[3/5] Constructing balanced training dataset...")
SAMPLE_SIZE = 35000

pos_sample = ddi.sample(n=min(SAMPLE_SIZE, len(ddi)), random_state=RANDOM_STATE)
pos_pairs = list(zip(pos_sample["drug_1_normalized"], pos_sample["drug_2_normalized"]))

neg_pairs = []
while len(neg_pairs) < len(pos_pairs):
    d1, d2 = random.sample(all_drugs, 2)
    pair = "||".join(sorted([d1, d2]))
    if pair not in existing_pairs:
        neg_pairs.append((d1, d2))

rows = []
for d1, d2 in pos_pairs:
    f = build_features(d1, d2)
    rows.append([d1, d2, 1] + f)

for d1, d2 in neg_pairs:
    f = build_features(d1, d2)
    rows.append([d1, d2, 0] + f)

df_features = pd.DataFrame(rows, columns=["drug_1", "drug_2", "interaction_label"] + feature_columns)
df_features = df_features.sample(frac=1.0, random_state=RANDOM_STATE).reset_index(drop=True)
df_features.to_csv(DATA_OUTPUT, index=False)
print(f"  • Total samples: {len(df_features):,} ({len(pos_pairs):,} positive, {len(neg_pairs):,} negative)")

X = df_features[feature_columns]
y = df_features["interaction_label"]

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=RANDOM_STATE,
    stratify=y
)

print(f"  • Training set : {len(X_train):,} samples")
print(f"  • Testing set  : {len(X_test):,} samples")

# ============================================================
# 4. MODEL TRAINING & HYPERPARAMETER CONFIGURATION
# ============================================================

print("\n[4/5] Training Logistic Regression & Decision Tree...")

lr_pipeline = Pipeline([
    ("scaler", StandardScaler()),
    ("model", LogisticRegression(max_iter=1000, C=1.0, random_state=RANDOM_STATE))
])

dt_model = DecisionTreeClassifier(
    max_depth=6,
    min_samples_split=20,
    min_samples_leaf=10,
    random_state=RANDOM_STATE
)

models = {
    "Logistic Regression": lr_pipeline,
    "Decision Tree": dt_model
}

evaluation_results = {}

for name, model in models.items():
    print(f"\n--- Training {name} ---")
    model.fit(X_train, y_train)
    
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    
    acc = float(accuracy_score(y_test, y_pred))
    prec = float(precision_score(y_test, y_pred, zero_division=0))
    rec = float(recall_score(y_test, y_pred, zero_division=0))
    f1 = float(f1_score(y_test, y_pred, zero_division=0))
    roc_auc = float(roc_auc_score(y_test, y_prob))
    cm = confusion_matrix(y_test, y_pred).tolist()
    
    feature_meta = {}
    if name == "Logistic Regression":
        coefficients = model.named_steps["model"].coef_[0].tolist()
        intercept = float(model.named_steps["model"].intercept_[0])
        for feat, coef in zip(feature_columns, coefficients):
            feature_meta[feat] = {
                "coefficient": round(coef, 4),
                "odds_ratio": round(float(np.exp(coef)), 4)
            }
        feature_meta["_intercept"] = round(intercept, 4)
    elif name == "Decision Tree":
        importances = model.feature_importances_.tolist()
        for feat, imp in zip(feature_columns, importances):
            feature_meta[feat] = {
                "importance": round(imp, 4)
            }

    evaluation_results[name] = {
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1_score": round(f1, 4),
        "roc_auc": round(roc_auc, 4),
        "confusion_matrix": {
            "true_negative": int(cm[0][0]),
            "false_positive": int(cm[0][1]),
            "false_negative": int(cm[1][0]),
            "true_positive": int(cm[1][1]),
            "matrix": cm
        },
        "feature_metrics": feature_meta,
        "sample_counts": {
            "train_size": len(X_train),
            "test_size": len(X_test)
        }
    }
    
    print(f"  • Accuracy : {acc * 100:.2f}%")
    print(f"  • Precision: {prec * 100:.2f}%")
    print(f"  • Recall   : {rec * 100:.2f}%")
    print(f"  • F1-Score : {f1 * 100:.2f}%")
    print(f"  • ROC-AUC  : {roc_auc:.4f}")
    print(f"  • Confusion Matrix: TN={cm[0][0]}, FP={cm[0][1]}, FN={cm[1][0]}, TP={cm[1][1]}")

# ============================================================
# 5. PERSISTENCE & EVALUATION METRICS
# ============================================================

print("\n[5/5] Saving model bundle and evaluation metrics...")

# Save lightweight metadata so runtime predictor does zero slow recomputations
metadata_payload = {
    "total_deg": total_deg,
    "class_cache": {k: list(v) for k, v in class_cache.items()},
    "rx_cache": rx_cache,
    "csa_cache": csa_cache,
    "high_risk_classes": {k: list(v) for k, v in HIGH_RISK_CLASSES.items()},
    "se_cache": {k: list(v) for k, v in se_cache.items()}
}

bundle_path = os.path.join(MODEL_DIR, "safemed_models_bundle.pkl")
joblib.dump({
    "logistic_regression": lr_pipeline,
    "decision_tree": dt_model,
    "features": feature_columns,
    "evaluation": evaluation_results,
    "metadata": metadata_payload
}, bundle_path)
print(f"  • Saved models bundle: {bundle_path}")

metrics_path = os.path.join(MODEL_DIR, "model_evaluation_metrics.json")
with open(metrics_path, "w", encoding="utf-8") as f:
    json.dump(evaluation_results, f, indent=2)
print(f"  • Saved evaluation metrics JSON: {metrics_path}")

print("\nPipeline execution complete.")
