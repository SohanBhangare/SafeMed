import pandas as pd
import os
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
    confusion_matrix,
    classification_report
)


# ============================================================
# SETTINGS
# ============================================================

DATA_FILE = "data/ml/medication_interaction_ml.csv"

MODEL_DIR = "ml/models"

RANDOM_STATE = 42


# ============================================================
# CREATE MODEL DIRECTORY
# ============================================================

os.makedirs(MODEL_DIR, exist_ok=True)


# ============================================================
# LOAD DATA
# ============================================================

df = pd.read_csv(DATA_FILE)

print("=" * 70)
print("SAFEMED ML MODEL TRAINING")
print("=" * 70)

print("\nDataset shape:", df.shape)


# ============================================================
# FEATURES
# ============================================================

feature_columns = [
    "drug_1_length",
    "drug_2_length",
    "description_length",
    "contains_increase",
    "contains_decrease",
    "contains_risk",
    "contains_concentration",
    "contains_effect",
    "contains_reduce"
]


X = df[feature_columns]

y = df["interaction_label"]


print("\nFeatures used:")
for feature in feature_columns:
    print("-", feature)


# ============================================================
# TRAIN / TEST SPLIT
# ============================================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=RANDOM_STATE,
    stratify=y
)


print("\nTraining records:", len(X_train))
print("Testing records :", len(X_test))


# ============================================================
# DEFINE MODELS
# ============================================================

models = {

    "Logistic Regression": Pipeline([
        (
            "scaler",
            StandardScaler()
        ),
        (
            "model",
            LogisticRegression(
                max_iter=1000,
                random_state=RANDOM_STATE
            )
        )
    ]),

    "Decision Tree": DecisionTreeClassifier(
        random_state=RANDOM_STATE,
        max_depth=10
    ),

    "Random Forest": RandomForestClassifier(
        n_estimators=100,
        max_depth=15,
        random_state=RANDOM_STATE,
        n_jobs=-1
    )
}


# ============================================================
# TRAIN + EVALUATE
# ============================================================

results = {}

print("\n" + "=" * 70)
print("MODEL RESULTS")
print("=" * 70)


for name, model in models.items():

    print("\n" + "-" * 70)
    print(name)
    print("-" * 70)

    # Train
    model.fit(X_train, y_train)

    # Predict
    y_pred = model.predict(X_test)

    # Metrics
    accuracy = accuracy_score(
        y_test,
        y_pred
    )

    precision = precision_score(
        y_test,
        y_pred,
        zero_division=0
    )

    recall = recall_score(
        y_test,
        y_pred,
        zero_division=0
    )

    f1 = f1_score(
        y_test,
        y_pred,
        zero_division=0
    )

    cm = confusion_matrix(
        y_test,
        y_pred
    )

    results[name] = {
        "model": model,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "confusion_matrix": cm
    }

    print(
        f"Accuracy : {accuracy:.4f}"
    )

    print(
        f"Precision: {precision:.4f}"
    )

    print(
        f"Recall   : {recall:.4f}"
    )

    print(
        f"F1 Score : {f1:.4f}"
    )

    print("\nConfusion Matrix:")

    print(cm)

    print("\nClassification Report:")

    print(
        classification_report(
            y_test,
            y_pred,
            zero_division=0
        )
    )


# ============================================================
# FIND BEST MODEL BY F1
# ============================================================

best_name = max(
    results,
    key=lambda name: results[name]["f1"]
)

best_model = results[best_name]["model"]


print("\n" + "=" * 70)
print("BEST MODEL")
print("=" * 70)

print(
    "Selected based on highest F1-score:",
    best_name
)

print(
    f"F1 Score: "
    f"{results[best_name]['f1']:.4f}"
)


# ============================================================
# SAVE BEST MODEL
# ============================================================

model_path = (
    f"{MODEL_DIR}/"
    "safemed_interaction_model.pkl"
)

joblib.dump(
    best_model,
    model_path
)

print(
    "\nModel saved to:",
    model_path
)


# ============================================================
# SAVE FEATURE LIST
# ============================================================

feature_path = (
    f"{MODEL_DIR}/"
    "feature_columns.txt"
)

with open(feature_path, "w") as file:

    for feature in feature_columns:
        file.write(
            feature + "\n"
        )

print(
    "Feature list saved to:",
    feature_path
)