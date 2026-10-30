import pandas as pd
import sys
import os

sys.path.append(
    os.path.dirname(os.path.abspath(__file__))
)

from drug_matcher import find_drug_match
# ============================================================
# LOAD DATASET
# ============================================================

DRUG_FILE = "data/cleaned/drugs_cleaned.csv"

drugs = pd.read_csv(DRUG_FILE)


# ============================================================
# NORMALIZE DRUG NAMES
# ============================================================

drugs["drug_name_normalized"] = (
    drugs["drug_name"]
    .fillna("")
    .astype(str)
    .str.lower()
    .str.strip()
)


# ============================================================
# CREATE DRUG LIST
# ============================================================

drug_names = sorted(
    drugs["drug_name_normalized"].unique()
)



# ============================================================
# GET SIDE EFFECTS
# ============================================================

def get_side_effects(drug_name):

    drug_name = drug_name.lower().strip()

    result = drugs[
        drugs["drug_name_normalized"] == drug_name
    ]

    if result.empty:
        return None

    # A drug can appear for multiple conditions,
    # so collect all available side-effect information.

    side_effects = []

    for _, row in result.iterrows():

        value = row["side_effects"]

        if pd.notna(value):

            value = str(value).strip()

            if value and value not in side_effects:

                side_effects.append(value)

    return side_effects


# ============================================================
# ANALYZE MEDICATION SIDE EFFECTS
# ============================================================

def analyze_side_effects(medications):

    results = []

    for medication in medications:

        match = find_drug_match(medication)

        if match["matched"]:

            side_effects = get_side_effects(
                match["drug_name"]
            )

            results.append({
                "input": medication,
                "matched_drug": match["drug_name"],
                "match_score": match["score"],
                "side_effects": side_effects
            })

        else:

            results.append({
                "input": medication,
                "matched_drug": None,
                "match_score": match["score"],
                "side_effects": None
            })

    return results

# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    medications = [
        "doxycycline",
        "spironolactone",
        "trioxsaln"
    ]

    results = analyze_side_effects(medications)

    print("=" * 70)
    print("SAFEMED SIDE-EFFECT ANALYZER")
    print("=" * 70)

    for result in results:

        print("\n----------------------------------------")

        print("Input:", result["input"])

        if result["matched_drug"]:

            print(
                "Matched drug:",
                result["matched_drug"]
            )

            print(
                "Match score:",
                result["match_score"]
            )

            if result["side_effects"]:

                print("Side-effect information:")

                # Show first available record
                print(
                    result["side_effects"][0]
                )

            else:

                print(
                    "No side-effect information "
                    "available in the dataset."
                )

        else:

            print("No reliable drug match found.")
