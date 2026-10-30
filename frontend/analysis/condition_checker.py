import pandas as pd
from rapidfuzz import process, fuzz


# ============================================================
# LOAD DATASET 1
# ============================================================

DRUG_FILE = "data/cleaned/drugs_cleaned.csv"

drugs = pd.read_csv(DRUG_FILE)


# ============================================================
# NORMALIZE CONDITIONS
# ============================================================

drugs["medical_condition_normalized"] = (
    drugs["medical_condition"]
    .fillna("")
    .astype(str)
    .str.lower()
    .str.strip()
)


# ============================================================
# CREATE CONDITION LIST
# ============================================================

conditions = sorted(
    drugs["medical_condition_normalized"]
    .dropna()
    .unique()
)


# ============================================================
# FIND CONDITION MATCH
# ============================================================

def find_condition_match(user_input, threshold=80):

    user_input = str(user_input).strip().lower()

    # Exact match
    if user_input in conditions:

        return {
            "input": user_input,
            "matched": True,
            "condition": user_input,
            "score": 100
        }

    # Fuzzy matching
    result = process.extractOne(
        user_input,
        conditions,
        scorer=fuzz.ratio
    )

    if result is None:

        return {
            "input": user_input,
            "matched": False,
            "condition": None,
            "score": 0
        }

    matched_condition, score, _ = result

    if score >= threshold:

        return {
            "input": user_input,
            "matched": True,
            "condition": matched_condition,
            "score": round(score, 2)
        }

    return {
        "input": user_input,
        "matched": False,
        "condition": None,
        "score": round(score, 2)
    }


# ============================================================
# GET DRUG INFORMATION FOR CONDITION
# ============================================================

def get_condition_information(condition):

    condition = condition.lower().strip()

    result = drugs[
        drugs["medical_condition_normalized"] == condition
    ]

    if result.empty:
        return []

    information = []

    for _, row in result.iterrows():

        information.append({
            "drug_name": row["drug_name"],
            "generic_name": row["generic_name"],
            "drug_classes": row["drug_classes"],
            "side_effects": row["side_effects"],
            "activity": row["activity"]
        })

    return information


# ============================================================
# ANALYZE PATIENT CONDITIONS
# ============================================================

def analyze_conditions(patient_conditions):

    matched_conditions = []
    unmatched_conditions = []

    for condition in patient_conditions:

        result = find_condition_match(condition)

        if result["matched"]:
            matched_conditions.append(result)
        else:
            unmatched_conditions.append(result)

    condition_information = {}

    for condition in matched_conditions:

        matched_name = condition["condition"]

        condition_information[matched_name] = (
            get_condition_information(matched_name)
        )

    return {
        "matched_conditions": matched_conditions,
        "unmatched_conditions": unmatched_conditions,
        "condition_information": condition_information
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    patient_conditions = [
        "Acne",
        "Diabete"
    ]

    result = analyze_conditions(patient_conditions)

    print("=" * 70)
    print("SAFEMED DRUG–CONDITION ANALYSIS")
    print("=" * 70)

    print("\nMATCHED CONDITIONS:")

    for condition in result["matched_conditions"]:

        print(
            f"Input: {condition['input']} "
            f"→ Matched: {condition['condition']} "
            f"({condition['score']}%)"
        )

    print("\nUNMATCHED CONDITIONS:")

    if result["unmatched_conditions"]:

        for condition in result["unmatched_conditions"]:

            print(
                condition["input"],
                "→ no reliable match"
            )

    else:

        print("None")

    print("\nCONDITION INFORMATION:")

    for condition, information in (
        result["condition_information"].items()
    ):

        print(
            f"\nCondition: {condition}"
        )

        print(
            "Number of records:",
            len(information)
        )

        # Show first 3 records only
        for item in information[:3]:

            print(
                f"  Drug: {item['drug_name']}"
            )

            print(
                f"  Generic: {item['generic_name']}"
            )

            print(
                f"  Class: {item['drug_classes']}"
            )

            print()