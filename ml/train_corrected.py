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

DATA_FILE = "data/ml/patient_interaction_features.csv"

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
print("SAFEMED CORRECTED ML MODEL TRAINING")
print("=" * 70)

print("\nDataset shape:", df.shape)


# ============================================================
# FEATURES
# ============================================================

feature_columns = [
    "drug_1_length",
    "drug_2_length",
    "drug_1_word_count",
    "drug_2_word_count",
    "same_first_letter"
]

X = df[feature_columns]

y = df["interaction_label"]


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
# MODELS
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
        max_depth=10,
        random_state=RANDOM_STATE
    ),

    "Random Forest": RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=RANDOM_STATE,
        n_jobs=-1
    )
}


# ============================================================
# TRAIN AND EVALUATE
# ============================================================

results = {}

for name, model in models.items():

    print("\n" + "=" * 70)
    print(name)
    print("=" * 70)

    # Train
    model.fit(
        X_train,
        y_train
    )

    # Predict
    y_pred = model.predict(
        X_test
    )

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
# SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("MODEL COMPARISON")
print("=" * 70)

for name, result in results.items():

    print(
        f"\n{name}"
    )

    print(
        f"Accuracy : {result['accuracy']:.4f}"
    )

    print(
        f"Precision: {result['precision']:.4f}"
    )

    print(
        f"Recall   : {result['recall']:.4f}"
    )

    print(
        f"F1 Score : {result['f1']:.4f}"
    )


# ============================================================
# SELECT MODEL BY F1 SCORE
# ============================================================

best_name = max(
    results,
    key=lambda name: results[name]["f1"]
)

best_model = results[
    best_name
]["model"]


print("\n" + "=" * 70)
print("SELECTED MODEL")
print("=" * 70)

print(
    "Model selected using F1-score:",
    best_name
)

print(
    "F1 Score:",
    round(
        results[best_name]["f1"],
        4
    )
)


# ============================================================
# SAVE MODEL
# ============================================================

model_path = (
    f"{MODEL_DIR}/"
    "safemed_corrected_model.pkl"
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
# SAVE FEATURES
# ============================================================

feature_path = (
    f"{MODEL_DIR}/"
    "corrected_feature_columns.txt"
)

with open(
    feature_path,
    "w"
) as file:

    for feature in feature_columns:
        file.write(
            feature + "\n"
        )

print(
    "Features saved to:",
    feature_path
)