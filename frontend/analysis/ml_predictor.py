import joblib
import pandas as pd


MODEL_PATH = "ml/models/safemed_improved_model.pkl"


# Load model once
saved_model = joblib.load(MODEL_PATH)

model = saved_model["model"]
features = saved_model["features"]


def create_features(drug1, drug2):
    """
    Create the same features used during ML training.
    """

    return pd.DataFrame([{
        "drug_1_length": len(drug1),
        "drug_2_length": len(drug2),
        "drug_1_word_count": len(drug1.split()),
        "drug_2_word_count": len(drug2.split()),
        "drug_class_overlap": 0
    }])


def predict_interaction(drug1, drug2):
    """
    Predict whether the drug pair resembles
    a documented interaction pair in the training dataset.

    This is an academic ML prediction and NOT
    a clinical safety determination.
    """

    input_data = create_features(drug1, drug2)

    prediction = model.predict(input_data)[0]

    probability = None

    if hasattr(model, "predict_proba"):
        probability = model.predict_proba(input_data)[0][1]

    return {
        "prediction": int(prediction),
        "probability": float(probability) if probability is not None else None
    }


if __name__ == "__main__":

    print("=" * 70)
    print("SAFEMED ML PREDICTOR TEST")
    print("=" * 70)

    result = predict_interaction(
        "trioxsalen",
        "verteporfin"
    )

    print("\nDrug 1: trioxsalen")
    print("Drug 2: verteporfin")

    print("\nPrediction:", result["prediction"])

    if result["probability"] is not None:
        print(
            "Interaction-like probability:",
            round(result["probability"] * 100, 2),
            "%"
        )

    print("\nNote:")
    print(
        "This ML prediction is an academic classification result "
        "and does not establish clinical safety or risk."
    )