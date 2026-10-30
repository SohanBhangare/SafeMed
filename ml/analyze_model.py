import joblib
import pandas as pd

MODEL_PATH = "ml/models/safemed_improved_model.pkl"

print("=" * 70)
print("SAFEMED MODEL FEATURE ANALYSIS")
print("=" * 70)

# Load saved model
saved = joblib.load(MODEL_PATH)

model = saved["model"]
features = saved["features"]

print("\nSelected Model:")
print("Decision Tree")

print("\nFeatures:")
for feature in features:
    print("-", feature)

# Get feature importance
importance = model.feature_importances_

feature_importance = pd.DataFrame({
    "Feature": features,
    "Importance": importance
})

feature_importance = feature_importance.sort_values(
    by="Importance",
    ascending=False
)

print("\nFeature Importance:")
print("-" * 50)

for _, row in feature_importance.iterrows():
    print(
        f"{row['Feature']:<25} "
        f"{row['Importance']:.4f}"
    )

print("\nTotal importance:",
      round(feature_importance["Importance"].sum(), 4))

print("\nAnalysis completed.")
