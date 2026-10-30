import pandas as pd
import os


# ============================================================
# FILE PATHS
# ============================================================

file1 = "data/data1/drugs_side_effects_drugs_com.csv"
file2 = "data/data2/db_drug_interactions.csv"


# ============================================================
# CREATE CLEAN DATA FOLDER
# ============================================================

os.makedirs("data/cleaned", exist_ok=True)


# ============================================================
# LOAD DATASETS
# ============================================================

df1 = pd.read_csv(file1)
df2 = pd.read_csv(file2)


# ============================================================
# DATASET 1 CLEANING
# ============================================================

print("=" * 70)
print("CLEANING DATASET 1")
print("=" * 70)

# Keep only useful columns for our project
df1 = df1[
    [
        "drug_name",
        "medical_condition",
        "side_effects",
        "generic_name",
        "drug_classes",
        "brand_names",
        "activity",
        "rx_otc",
        "pregnancy_category",
        "csa",
        "alcohol",
        "related_drugs",
        "medical_condition_description"
    ]
].copy()


# Convert important text columns to strings
text_columns_1 = [
    "drug_name",
    "medical_condition",
    "side_effects",
    "generic_name",
    "drug_classes",
    "brand_names",
    "activity",
    "rx_otc",
    "pregnancy_category",
    "csa",
    "alcohol",
    "related_drugs",
    "medical_condition_description"
]

for column in text_columns_1:
    df1[column] = df1[column].fillna("").astype(str).str.strip()


# Create normalized drug name
df1["drug_name_normalized"] = (
    df1["drug_name"]
    .str.lower()
    .str.strip()
)


# Create normalized medical condition
df1["medical_condition_normalized"] = (
    df1["medical_condition"]
    .str.lower()
    .str.strip()
)


# Remove exact duplicate rows
df1 = df1.drop_duplicates()


# Save cleaned Dataset 1
output1 = "data/cleaned/drugs_cleaned.csv"
df1.to_csv(output1, index=False)


print("Cleaned Dataset 1 shape:", df1.shape)
print("Saved to:", output1)


# ============================================================
# DATASET 2 CLEANING
# ============================================================

print("\n" + "=" * 70)
print("CLEANING DATASET 2")
print("=" * 70)


# Rename columns to easier names
df2 = df2.rename(
    columns={
        "Drug 1": "drug_1",
        "Drug 2": "drug_2",
        "Interaction Description": "interaction_description"
    }
)


# Clean text
df2["drug_1"] = (
    df2["drug_1"]
    .fillna("")
    .astype(str)
    .str.strip()
)

df2["drug_2"] = (
    df2["drug_2"]
    .fillna("")
    .astype(str)
    .str.strip()
)

df2["interaction_description"] = (
    df2["interaction_description"]
    .fillna("")
    .astype(str)
    .str.strip()
)


# Normalized drug names
df2["drug_1_normalized"] = (
    df2["drug_1"]
    .str.lower()
    .str.strip()
)

df2["drug_2_normalized"] = (
    df2["drug_2"]
    .str.lower()
    .str.strip()
)


# ============================================================
# CREATE CANONICAL DRUG PAIR
# ============================================================

df2["drug_pair"] = df2.apply(
    lambda row: "||".join(
        sorted(
            [
                row["drug_1_normalized"],
                row["drug_2_normalized"]
            ]
        )
    ),
    axis=1
)


# Remove exact duplicate rows
df2 = df2.drop_duplicates()


# Remove duplicate drug pairs
# We keep the first interaction description available.
df2 = df2.drop_duplicates(
    subset=["drug_pair"],
    keep="first"
)


# Save cleaned Dataset 2
output2 = "data/cleaned/drug_interactions_cleaned.csv"
df2.to_csv(output2, index=False)


print("Cleaned Dataset 2 shape:", df2.shape)
print("Saved to:", output2)


# ============================================================
# FINAL SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("CLEANING COMPLETE")
print("=" * 70)

print("\nDataset 1:")
print("Original rows: 2931")
print("Cleaned rows :", len(df1))

print("\nDataset 2:")
print("Original rows: 191541")
print("Cleaned rows :", len(df2))

print("\nCleaned files created successfully!")