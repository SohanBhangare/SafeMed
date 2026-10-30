from analysis.safemed_analyzer import analyze_medications
from analysis.condition_checker import analyze_conditions
from analysis.side_effect_checker import analyze_side_effects
from analysis.ml_predictor import predict_interaction

def get_matched_drug_name(item):
    """
    Extract the actual matched drug name from the
    medication matcher result.
    """

    if isinstance(item, str):
        return item

    if isinstance(item, dict):

        # The matcher should normally use "matched"
        if isinstance(item.get("matched"), str):
            return item["matched"]

        if isinstance(item.get("matched_drug"), str):
            return item["matched_drug"]

        if isinstance(item.get("drug_name"), str):
            return item["drug_name"]

        if isinstance(item.get("drug"), str):
            return item["drug"]

        if isinstance(item.get("name"), str):
            return item["name"]

    return None


def analyze_patient(medications, conditions):

    # ============================================================
    # MEDICATION ANALYSIS
    # ============================================================

    medication_result = analyze_medications(medications)

    matched_medications_raw = medication_result.get(
        "matched_medications",
        []
    )

    # Extract ONLY actual string drug names
    matched_medications = []

    for item in matched_medications_raw:

        drug_name = get_matched_drug_name(item)

        if isinstance(drug_name, str):
            matched_medications.append(drug_name)

    # ============================================================
    # ML PREDICTIONS
    # ============================================================

    ml_predictions = []

    for i in range(len(matched_medications)):

        for j in range(i + 1, len(matched_medications)):

            drug1 = matched_medications[i]
            drug2 = matched_medications[j]

            prediction = predict_interaction(
                drug1,
                drug2
            )

            ml_predictions.append({
                "drug_1":              drug1,
                "drug_2":              drug2,
                "prediction":          prediction["prediction"],
                "probability":         prediction["probability"],
                "class_overlap":       prediction.get("class_overlap", False),
                "decision_tree":       prediction.get("decision_tree", {}),
                "logistic_regression": prediction.get("logistic_regression", {}),
                "consensus":           prediction.get("consensus", True),
                "consensus_label":     prediction.get("consensus_label", ""),
                "consensus_agreed":    prediction.get("consensus", True),
                "consensus_note":      prediction.get("consensus_label", ""),
            })

    # ============================================================
    # CONDITION ANALYSIS
    # ============================================================

    condition_result = analyze_conditions(
        conditions
    )

    # ============================================================
    # SIDE EFFECT ANALYSIS
    # ============================================================

    side_effect_result = analyze_side_effects(
        matched_medications
    )

    # ============================================================
    # FINAL RESULT
    # ============================================================

    result = {
        "medication_analysis": medication_result,
        "condition_analysis": condition_result,
        "side_effect_analysis": side_effect_result,
        "ml_predictions": ml_predictions,

        "summary": {
            "number_of_medications":
                len(matched_medications),

            "number_of_interactions":
                len(
                    medication_result.get(
                        "interactions",
                        []
                    )
                ),

            "number_of_conditions":
                len(conditions),

            "number_of_ml_predictions":
                len(ml_predictions)
        }
    }

    return result


# ================================================================
# TEST
# ================================================================

if __name__ == "__main__":

    print("=" * 70)
    print("SAFEMED COMPLETE PATIENT ANALYZER")
    print("=" * 70)

    medications = [
        "trioxsaln",
        "verteporfin"
    ]

    conditions = [
        "Acne"
    ]

    result = analyze_patient(
        medications,
        conditions
    )

    # ============================================================
    # MEDICATION RESULTS
    # ============================================================

    print("\n" + "=" * 70)
    print("MEDICATION ANALYSIS")
    print("=" * 70)

    print(
        "\nNumber of medications:",
        result["summary"]["number_of_medications"]
    )

    print(
        "Number of documented interactions:",
        result["summary"]["number_of_interactions"]
    )

    print("\nMatched medications:")

    for medication in result["medication_analysis"].get(
        "matched_medications",
        []
    ):
        print("-", medication)

    # ============================================================
    # DOCUMENTED INTERACTIONS
    # ============================================================

    interactions = result["medication_analysis"].get(
        "interactions",
        []
    )

    if interactions:

        print("\nDocumented interactions:")

        for interaction in interactions:

            print(
                f"\n{interaction['drug_1']} + "
                f"{interaction['drug_2']}"
            )

            print(
                "Description:",
                interaction["description"]
            )

    else:

        print(
            "\nNo matching interaction was identified "
            "in the application's reference dataset."
        )

    # ============================================================
    # ML RESULTS
    # ============================================================

    print("\n" + "=" * 70)
    print("ML INTERACTION PREDICTIONS")
    print("=" * 70)

    if result["ml_predictions"]:

        for prediction in result["ml_predictions"]:

            print(
                f"\n{prediction['drug_1']} + "
                f"{prediction['drug_2']}"
            )

            print(
                "Prediction:",
                prediction["prediction"]
            )

            if prediction["probability"] is not None:

                print(
                    "Interaction-like probability:",
                    f"{prediction['probability'] * 100:.2f}%"
                )

    else:

        print(
            "\nNo medication pairs available for ML analysis."
        )

    print(
        "\nNOTE: ML predictions are academic classification "
        "results and do not establish clinical safety or risk."
    )

    # ============================================================
    # CONDITION RESULTS
    # ============================================================

    print("\n" + "=" * 70)
    print("CONDITION ANALYSIS")
    print("=" * 70)

    print(
        "Number of conditions:",
        result["summary"]["number_of_conditions"]
    )

    print("\nCondition results:")

    print(result["condition_analysis"])

    # ============================================================
    # SIDE EFFECT RESULTS
    # ============================================================

    print("\n" + "=" * 70)
    print("SIDE EFFECT ANALYSIS")
    print("=" * 70)

    print(result["side_effect_analysis"])

    # ============================================================
    # FINAL SUMMARY
    # ============================================================

    print("\n" + "=" * 70)
    print("SAFEMED SUMMARY")
    print("=" * 70)

    print(
        "Medications:",
        result["summary"]["number_of_medications"]
    )

    print(
        "Documented interactions:",
        result["summary"]["number_of_interactions"]
    )

    print(
        "Conditions:",
        result["summary"]["number_of_conditions"]
    )

    print(
        "ML predictions:",
        result["summary"]["number_of_ml_predictions"]
    )

    print("\nAnalysis completed successfully.")