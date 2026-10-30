import pandas as pd
from itertools import combinations


# ============================================================
# LOAD DDI DATASET
# ============================================================

DDI_FILE = "data/cleaned/drug_interactions_cleaned.csv"

ddi = pd.read_csv(DDI_FILE)


# ============================================================
# NORMALIZE DRUG NAME
# ============================================================

def normalize_drug_name(drug_name):
    """
    Convert a drug name into a standard format
    for matching.
    """

    return str(drug_name).strip().lower()


# ============================================================
# CREATE DRUG PAIR
# ============================================================

def create_drug_pair(drug1, drug2):
    """
    Creates a consistent pair.

    This means:
    aspirin + warfarin

    and

    warfarin + aspirin

    produce the same pair.
    """

    drugs = sorted([
        normalize_drug_name(drug1),
        normalize_drug_name(drug2)
    ])

    return "||".join(drugs)


# ============================================================
# CHECK ONE DRUG PAIR
# ============================================================

def check_interaction(drug1, drug2):

    pair = create_drug_pair(drug1, drug2)

    result = ddi[ddi["drug_pair"] == pair]

    if not result.empty:

        return {
            "drug_1": drug1,
            "drug_2": drug2,
            "interaction_found": True,
            "description": result.iloc[0]["interaction_description"]
        }

    return {
        "drug_1": drug1,
        "drug_2": drug2,
        "interaction_found": False,
        "description": None
    }


# ============================================================
# CHECK MULTIPLE MEDICATIONS
# ============================================================

def check_multiple_drugs(drug_list):

    # Remove empty values
    drug_list = [
        drug.strip()
        for drug in drug_list
        if drug.strip()
    ]

    # Remove duplicate medicine names
    unique_drugs = []

    for drug in drug_list:

        normalized = normalize_drug_name(drug)

        if normalized not in [
            normalize_drug_name(d)
            for d in unique_drugs
        ]:
            unique_drugs.append(drug)

    results = []

    # Generate every possible combination
    for drug1, drug2 in combinations(unique_drugs, 2):

        result = check_interaction(drug1, drug2)

        results.append(result)

    return results


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    medicines = [
        "Trioxsalen",
        "Verteporfin"
    ]

    results = check_multiple_drugs(medicines)

    print("=" * 70)
    print("SAFEMED DRUG–DRUG INTERACTION CHECKER")
    print("=" * 70)

    for result in results:

        print("\n----------------------------------------")

        print(
            f"{result['drug_1']} + {result['drug_2']}"
        )

        if result["interaction_found"]:

            print("⚠ Interaction found")

            print(
                "Description:",
                result["description"]
            )

        else:

            print(
                "No matching interaction found "
                "in the reference dataset."
            )