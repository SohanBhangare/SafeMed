import pandas as pd
import random
import os


# ============================================================
# SETTINGS
# ============================================================

DDI_FILE = "data/cleaned/drug_interactions_cleaned.csv"

OUTPUT_DIR = "data/ml"

RANDOM_STATE = 42


# ============================================================
# CREATE OUTPUT DIRECTORY
# ============================================================

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
# LOAD DDI DATA
# ============================================================

ddi = pd.read_csv(DDI_FILE)

print("=" * 70)
print("SAFEMED ML DATASET CREATION")
print("=" * 70)

print("\nOriginal interaction records:", len(ddi))


# ============================================================
# POSITIVE EXAMPLES
# ============================================================

positive = ddi[
    [
        "drug_1_normalized",
        "drug_2_normalized",
        "interaction_description"
    ]
].copy()

positive["interaction_label"] = 1


# ============================================================
# GET ALL UNIQUE DRUGS
# ============================================================

drug_list = sorted(
    set(
        ddi["drug_1_normalized"]
    ).union(
        set(ddi["drug_2_normalized"])
    )
)


print("Unique drugs:", len(drug_list))


# ============================================================
# EXISTING PAIRS
# ============================================================

existing_pairs = set(
    ddi["drug_pair"]
)


# ============================================================
# GENERATE NEGATIVE PAIRS
# ============================================================

random.seed(RANDOM_STATE)

negative_pairs = set()

target_negative_count = len(positive)


while len(negative_pairs) < target_negative_count:

    drug1, drug2 = random.sample(
        drug_list,
        2
    )

    pair = "||".join(
        sorted([drug1, drug2])
    )

    # Make sure this pair does NOT exist
    if pair not in existing_pairs:

        negative_pairs.add(pair)


# ============================================================
# CREATE NEGATIVE DATAFRAME
# ============================================================

negative_data = []

for pair in negative_pairs:

    drug1, drug2 = pair.split("||")

    negative_data.append({
        "drug_1_normalized": drug1,
        "drug_2_normalized": drug2,
        "interaction_description": "",
        "interaction_label": 0
    })


negative = pd.DataFrame(
    negative_data
)


# ============================================================
# COMBINE DATA
# ============================================================

ml_data = pd.concat(
    [
        positive,
        negative
    ],
    ignore_index=True
)


# ============================================================
# SHUFFLE
# ============================================================

ml_data = ml_data.sample(
    frac=1,
    random_state=RANDOM_STATE
).reset_index(drop=True)


# ============================================================
# FEATURE ENGINEERING
# ============================================================

ml_data["drug_1_length"] = (
    ml_data["drug_1_normalized"]
    .str.len()
)

ml_data["drug_2_length"] = (
    ml_data["drug_2_normalized"]
    .str.len()
)


# Description length
ml_data["description_length"] = (
    ml_data["interaction_description"]
    .fillna("")
    .str.len()
)


# ============================================================
# TEXT-BASED FEATURES
# ============================================================

description = (
    ml_data["interaction_description"]
    .fillna("")
    .str.lower()
)


keywords = [
    "increase",
    "decrease",
    "risk",
    "concentration",
    "effect",
    "reduce"
]


for keyword in keywords:

    ml_data[
        f"contains_{keyword}"
    ] = description.str.contains(
        keyword,
        regex=False
    ).astype(int)


# ============================================================
# SAVE DATASET
# ============================================================

output_file = (
    f"{OUTPUT_DIR}/"
    "medication_interaction_ml.csv"
)

ml_data.to_csv(
    output_file,
    index=False
)


# ============================================================
# SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("ML DATASET CREATED")
print("=" * 70)

print("\nTotal records:", len(ml_data))

print(
    "\nPositive examples:",
    (ml_data["interaction_label"] == 1).sum()
)

print(
    "Negative examples:",
    (ml_data["interaction_label"] == 0).sum()
)

print("\nClass distribution:")

print(
    ml_data["interaction_label"]
    .value_counts()
)

print("\nFeatures:")

print(
    ml_data.columns.tolist()
)

print(
    "\nSaved to:",
    output_file
)