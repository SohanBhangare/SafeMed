import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix
)

# ============================================================
# LOAD DATA
# ============================================================

DATA_PATH = "data/ml/improved_interaction_features.csv"

df = pd.read_csv(DATA_PATH)

print("=" * 70)
print("SAFEMED IMPROVED ML TRAINING")
print("=" * 70)

print(f"\nTotal records: {len(df)}")

# ============================================================
# FEATURES
# ============================================================

feature_columns = [
    "drug_1_length",
    "drug_2_length",
    "drug_1_word_count",
    "drug_2_word_count",
    "drug_class_overlap"
]

X = df[feature_columns]
y = df["interaction_label"]

print("\nFeatures:")
for feature in feature_columns:
    print(f"- {feature}")

# ============================================================
# TRAIN / TEST SPLIT
# ============================================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)

print(f"\nTraining records: {len(X_train)}")
print(f"Testing records: {len(X_test)}")

# ============================================================
# MODELS
# ============================================================

models = {
    "Logistic Regression": Pipeline([
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(
            max_iter=1000,
            random_state=42
        ))
    ]),

    "Decision Tree": DecisionTreeClassifier(
        max_depth=8,
        random_state=42
    ),

    "Random Forest": RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        n_jobs=-1
    )
}

results = {}

# ============================================================
# TRAIN AND EVALUATE
# ============================================================

for name, model in models.items():

    print("\n" + "=" * 70)
    print(name)
    print("=" * 70)

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    accuracy = accuracy_score(y_test, predictions)
    precision = precision_score(y_test, predictions, zero_division=0)
    recall = recall_score(y_test, predictions, zero_division=0)
    f1 = f1_score(y_test, predictions, zero_division=0)

    cm = confusion_matrix(y_test, predictions)

    results[name] = {
        "model": model,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1
    }

    print(f"Accuracy : {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall   : {recall:.4f}")
    print(f"F1 Score : {f1:.4f}")

    print("\nConfusion Matrix:")
    print(cm)

# ============================================================
# SELECT MODEL BY F1 SCORE
# ============================================================

best_name = max(
    results,
    key=lambda name: results[name]["f1"]
)

best_model = results[best_name]["model"]

print("\n" + "=" * 70)
print("MODEL COMPARISON")
print("=" * 70)

for name, result in results.items():
    print(
        f"{name:<22} "
        f"Accuracy={result['accuracy']:.4f} | "
        f"Precision={result['precision']:.4f} | "
        f"Recall={result['recall']:.4f} | "
        f"F1={result['f1']:.4f}"
    )

print("\nSelected model based on F1 score:")
print(best_name)

# ============================================================
# SAVE MODEL
# ============================================================

MODEL_PATH = "ml/models/safemed_improved_model.pkl"

joblib.dump(
    {
        "model": best_model,
        "features": feature_columns
    },
    MODEL_PATH
)

print(f"\nModel saved to:")
print(MODEL_PATH)

print("\nTraining completed successfully.")