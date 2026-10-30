import pandas as pd
import random
import os
from itertools import combinations


# ============================================================
# SETTINGS
# ============================================================

DDI_FILE = "data/cleaned/drug_interactions_cleaned.csv"

OUTPUT_DIR = "data/ml"

RANDOM_STATE = 42

random.seed(RANDOM_STATE)


# ============================================================
# CREATE DIRECTORY
# ============================================================

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
# LOAD DDI DATA
# ============================================================

ddi = pd.read_csv(DDI_FILE)

existing_pairs = set(
    ddi["drug_pair"]
)


# ============================================================
# UNIQUE DRUGS
# ============================================================

drug_list = sorted(
    set(ddi["drug_1_normalized"])
    |
    set(ddi["drug_2_normalized"])
)


# ============================================================
# CREATE POSITIVE PAIRS
# ============================================================

positive_pairs = []

for _, row in ddi.sample(
    n=min(50000, len(ddi)),
    random_state=RANDOM_STATE
).iterrows():

    positive_pairs.append({
        "drug_1": row["drug_1_normalized"],
        "drug_2": row["drug_2_normalized"],
        "interaction_label": 1
    })


# ============================================================
# CREATE NEGATIVE PAIRS
# ============================================================

negative_pairs = set()

while len(negative_pairs) < len(positive_pairs):

    drug1, drug2 = random.sample(
        drug_list,
        2
    )

    pair = "||".join(
        sorted([drug1, drug2])
    )

    if pair not in existing_pairs:

        negative_pairs.add(pair)


negative_data = []

for pair in negative_pairs:

    drug1, drug2 = pair.split("||")

    negative_data.append({
        "drug_1": drug1,
        "drug_2": drug2,
        "interaction_label": 0
    })


# ============================================================
# COMBINE
# ============================================================

positive_df = pd.DataFrame(
    positive_pairs
)

negative_df = pd.DataFrame(
    negative_data
)

data = pd.concat(
    [
        positive_df,
        negative_df
    ],
    ignore_index=True
)


# ============================================================
# FEATURES
# ============================================================

data["drug_1_length"] = (
    data["drug_1"].str.len()
)

data["drug_2_length"] = (
    data["drug_2"].str.len()
)

data["drug_1_word_count"] = (
    data["drug_1"].str.split().str.len()
)

data["drug_2_word_count"] = (
    data["drug_2"].str.split().str.len()
)

data["same_first_letter"] = (
    data["drug_1"].str[0]
    ==
    data["drug_2"].str[0]
).astype(int)


# ============================================================
# SHUFFLE
# ============================================================

data = data.sample(
    frac=1,
    random_state=RANDOM_STATE
).reset_index(drop=True)


# ============================================================
# SAVE
# ============================================================

output_file = (
    f"{OUTPUT_DIR}/"
    "patient_interaction_features.csv"
)

data.to_csv(
    output_file,
    index=False
)


# ============================================================
# SUMMARY
# ============================================================

print("=" * 70)
print("SAFEMED PATIENT ML DATASET")
print("=" * 70)

print("\nTotal records:", len(data))

print(
    "Positive records:",
    (data["interaction_label"] == 1).sum()
)

print(
    "Negative records:",
    (data["interaction_label"] == 0).sum()
)

print("\nFeatures:")

for column in data.columns:
    print("-", column)

print("\nSaved to:")
print(output_file)