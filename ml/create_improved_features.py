import pandas as pd
import random
import os


# ============================================================
# SETTINGS
# ============================================================

DDI_FILE = "data/cleaned/drug_interactions_cleaned.csv"
DRUG_FILE = "data/cleaned/drugs_cleaned.csv"

OUTPUT_DIR = "data/ml"

RANDOM_STATE = 42

random.seed(RANDOM_STATE)


# ============================================================
# CREATE DIRECTORY
# ============================================================

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
# LOAD DATA
# ============================================================

ddi = pd.read_csv(DDI_FILE)
drugs = pd.read_csv(DRUG_FILE)


# ============================================================
# PREPARE DRUG INFORMATION
# ============================================================

drug_info = drugs[
    [
        "drug_name_normalized",
        "drug_classes",
        "activity",
        "rx_otc",
        "csa"
    ]
].copy()


# Some drugs occur multiple times because they are associated
# with different medical conditions.
# Keep the first available metadata record for now.

drug_info = drug_info.drop_duplicates(
    subset=["drug_name_normalized"]
)

drug_info = drug_info.set_index(
    "drug_name_normalized"
)


# ============================================================
# CREATE EXISTING PAIR SET
# ============================================================

existing_pairs = set(
    ddi["drug_pair"]
)


# ============================================================
# UNIQUE DRUG LIST
# ============================================================

drug_list = sorted(
    set(ddi["drug_1_normalized"])
    |
    set(ddi["drug_2_normalized"])
)


# ============================================================
# POSITIVE EXAMPLES
# ============================================================

positive = ddi.sample(
    n=min(50000, len(ddi)),
    random_state=RANDOM_STATE
)[
    [
        "drug_1_normalized",
        "drug_2_normalized"
    ]
].copy()

positive["interaction_label"] = 1


# ============================================================
# NEGATIVE EXAMPLES
# ============================================================

negative_pairs = set()

while len(negative_pairs) < len(positive):

    drug1, drug2 = random.sample(
        drug_list,
        2
    )

    pair = "||".join(
        sorted([drug1, drug2])
    )

    if pair not in existing_pairs:
        negative_pairs.add(pair)


negative = []

for pair in negative_pairs:

    drug1, drug2 = pair.split("||")

    negative.append({
        "drug_1_normalized": drug1,
        "drug_2_normalized": drug2,
        "interaction_label": 0
    })


negative = pd.DataFrame(negative)


# ============================================================
# COMBINE
# ============================================================

data = pd.concat(
    [
        positive,
        negative
    ],
    ignore_index=True
)


# ============================================================
# HELPER FUNCTION
# ============================================================

def get_drug_metadata(drug):

    if drug not in drug_info.index:

        return {
            "drug_classes": "",
            "activity": "",
            "rx_otc": "",
            "csa": ""
        }

    row = drug_info.loc[drug]

    return {
        "drug_classes": str(
            row["drug_classes"]
        ),

        "activity": str(
            row["activity"]
        ),

        "rx_otc": str(
            row["rx_otc"]
        ),

        "csa": str(
            row["csa"]
        )
    }


# ============================================================
# ADD METADATA
# ============================================================

data["drug_1_class"] = data[
    "drug_1_normalized"
].apply(
    lambda x: get_drug_metadata(x)["drug_classes"]
)

data["drug_2_class"] = data[
    "drug_2_normalized"
].apply(
    lambda x: get_drug_metadata(x)["drug_classes"]
)


# ============================================================
# CLASS OVERLAP
# ============================================================

def calculate_class_overlap(row):

    class1 = set(
        x.strip().lower()
        for x in str(row["drug_1_class"]).split(",")
        if x.strip()
    )

    class2 = set(
        x.strip().lower()
        for x in str(row["drug_2_class"]).split(",")
        if x.strip()
    )

    if not class1 or not class2:
        return 0

    return int(
        len(class1.intersection(class2)) > 0
    )


data["drug_class_overlap"] = data.apply(
    calculate_class_overlap,
    axis=1
)


# ============================================================
# BASIC NAME FEATURES
# ============================================================

data["drug_1_length"] = (
    data["drug_1_normalized"].str.len()
)

data["drug_2_length"] = (
    data["drug_2_normalized"].str.len()
)

data["drug_1_word_count"] = (
    data["drug_1_normalized"]
    .str.split()
    .str.len()
)

data["drug_2_word_count"] = (
    data["drug_2_normalized"]
    .str.split()
    .str.len()
)


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
    "improved_interaction_features.csv"
)

data.to_csv(
    output_file,
    index=False
)


# ============================================================
# SUMMARY
# ============================================================

print("=" * 70)
print("SAFEMED IMPROVED ML DATASET")
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

print("\nDrug class overlap:")
print(
    data["drug_class_overlap"].value_counts()
)

print("\nSaved to:")
print(output_file)