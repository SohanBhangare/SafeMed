import pandas as pd
from itertools import combinations

try:
    from analysis.drug_matcher import find_drug_match
except ImportError:
    from drug_matcher import find_drug_match


# ============================================================
# LOAD DDI DATA (kept as a separate interaction database)
# ============================================================

DDI_FILE = "data/cleaned/drug_interactions_cleaned.csv"

ddi = pd.read_csv(DDI_FILE)


# ============================================================
# NORMALIZE NAME
# ============================================================

def normalize_drug_name(drug):
    return str(drug).strip().lower()


# ============================================================
# CREATE DRUG PAIR
# ============================================================

def create_drug_pair(drug1, drug2):

    drugs = sorted([
        normalize_drug_name(drug1),
        normalize_drug_name(drug2)
    ])

    return "||".join(drugs)


# ============================================================
# CHECK INTERACTION
# ============================================================

def check_interaction(drug1, drug2):

    pair = create_drug_pair(drug1, drug2)

    result = ddi[ddi["drug_pair"] == pair]

    if not result.empty:

        return {
            "drug_1": drug1,
            "drug_2": drug2,
            "interaction_found": True,
            "description": result.iloc[0][
                "interaction_description"
            ]
        }

    return {
        "drug_1": drug1,
        "drug_2": drug2,
        "interaction_found": False,
        "description": None
    }


# ============================================================
# COMPLETE SAFEMED ANALYSIS
# ============================================================

def analyze_medications(medications):

    matched_medications = []
    unmatched_medications = []

    # --------------------------------------------------------
    # STEP 1: MATCH DRUG NAMES
    # --------------------------------------------------------

    for medication in medications:

        result = find_drug_match(medication)

        if result["matched"]:

            matched_medications.append(result)

        else:

            unmatched_medications.append(result)

    # --------------------------------------------------------
    # STEP 2: REMOVE DUPLICATE MATCHES
    # --------------------------------------------------------

    unique_drugs = []

    for result in matched_medications:

        drug = result["drug_name"]

        if drug not in unique_drugs:
            unique_drugs.append(drug)

    # --------------------------------------------------------
    # STEP 3: CHECK ALL DRUG COMBINATIONS
    # --------------------------------------------------------

    interactions = []

    for drug1, drug2 in combinations(unique_drugs, 2):

        result = check_interaction(drug1, drug2)

        if result["interaction_found"]:
            interactions.append(result)

    # --------------------------------------------------------
    # STEP 4: RETURN COMPLETE RESULT
    # --------------------------------------------------------

    return {
        "matched_medications": matched_medications,
        "unmatched_medications": unmatched_medications,
        "interactions": interactions,
        "number_of_medications": len(unique_drugs),
        "number_of_interactions": len(interactions)
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    medications = [
        "trioxsaln",
        "verteporfin"
    ]

    result = analyze_medications(medications)

    print("=" * 70)
    print("SAFEMED MEDICATION ANALYSIS")
    print("=" * 70)

    print("\nMATCHED MEDICATIONS:")

    for drug in result["matched_medications"]:

        print(
            f"Input: {drug['input']} "
            f"→ Matched: {drug['drug_name']} "
            f"({drug['score']}%)"
        )

    print("\nUNMATCHED MEDICATIONS:")

    if result["unmatched_medications"]:

        for drug in result["unmatched_medications"]:
            print(drug["input"])

    else:

        print("None")

    print("\nINTERACTIONS:")

    if result["interactions"]:

        for interaction in result["interactions"]:

            print(
                f"\n⚠ {interaction['drug_1']} + "
                f"{interaction['drug_2']}"
            )

            print(
                "Description:",
                interaction["description"]
            )

    else:

        print(
            "No matching interaction was identified "
            "in the reference dataset."
        )

    print("\nSUMMARY")
    print("-" * 40)

    print(
        "Medications:",
        result["number_of_medications"]
    )

    print(
        "Interactions:",
        result["number_of_interactions"]
    )