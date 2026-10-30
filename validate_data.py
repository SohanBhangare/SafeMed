import pandas as pd


# ============================================================
# LOAD CLEANED DATASETS
# ============================================================

drugs_file = "data/cleaned/drugs_cleaned.csv"
ddi_file = "data/cleaned/drug_interactions_cleaned.csv"

drugs = pd.read_csv(drugs_file)
ddi = pd.read_csv(ddi_file)


# ============================================================
# BASIC INFORMATION
# ============================================================

print("=" * 70)
print("SAFEMED DATA VALIDATION")
print("=" * 70)

print("\nDataset 1 rows:", len(drugs))
print("Dataset 2 rows:", len(ddi))


# ============================================================
# UNIQUE DRUGS
# ============================================================

drug_names_dataset1 = set(
    drugs["drug_name_normalized"]
    .dropna()
    .astype(str)
    .str.strip()
)

drug_names_dataset2 = set(
    ddi["drug_1_normalized"]
    .dropna()
    .astype(str)
    .str.strip()
)

drug_names_dataset2.update(
    ddi["drug_2_normalized"]
    .dropna()
    .astype(str)
    .str.strip()
)


print("\n" + "=" * 70)
print("UNIQUE DRUG ANALYSIS")
print("=" * 70)

print("\nUnique drugs in Dataset 1:", len(drug_names_dataset1))
print("Unique drugs in Dataset 2:", len(drug_names_dataset2))


# ============================================================
# OVERLAP
# ============================================================

common_drugs = drug_names_dataset1.intersection(
    drug_names_dataset2
)

only_dataset1 = drug_names_dataset1 - drug_names_dataset2
only_dataset2 = drug_names_dataset2 - drug_names_dataset1


print("\n" + "=" * 70)
print("DATASET OVERLAP")
print("=" * 70)

print("\nDrugs present in BOTH datasets:", len(common_drugs))
print("Drugs only in Dataset 1:", len(only_dataset1))
print("Drugs only in Dataset 2:", len(only_dataset2))


# ============================================================
# OVERLAP PERCENTAGE
# ============================================================

if len(drug_names_dataset1) > 0:
    overlap_percentage = (
        len(common_drugs) / len(drug_names_dataset1)
    ) * 100
else:
    overlap_percentage = 0


print(
    "\nPercentage of Dataset 1 drugs found in Dataset 2:"
    f" {overlap_percentage:.2f}%"
)


# ============================================================
# SHOW COMMON DRUGS
# ============================================================

print("\n" + "=" * 70)
print("SAMPLE COMMON DRUGS")
print("=" * 70)

for drug in sorted(common_drugs)[:30]:
    print("-", drug)


# ============================================================
# DDI STATISTICS
# ============================================================

print("\n" + "=" * 70)
print("INTERACTION DATASET STATISTICS")
print("=" * 70)

print("\nUnique drug pairs:", ddi["drug_pair"].nunique())

print(
    "\nUnique interaction descriptions:",
    ddi["interaction_description"].nunique()
)


# ============================================================
# CHECK EMPTY VALUES
# ============================================================

print("\n" + "=" * 70)
print("EMPTY VALUES AFTER CLEANING")
print("=" * 70)

print("\nDataset 1 empty values:")
print(
    (drugs == "").sum()
)

print("\nDataset 2 empty values:")
print(
    (ddi == "").sum()
)


# ============================================================
# SAMPLE INTERACTIONS
# ============================================================

print("\n" + "=" * 70)
print("SAMPLE CLEANED INTERACTIONS")
print("=" * 70)

print(
    ddi[
        [
            "drug_1",
            "drug_2",
            "interaction_description"
        ]
    ].head(10).to_string(index=False)
)


# ============================================================
# SAMPLE DRUG INFORMATION
# ============================================================

print("\n" + "=" * 70)
print("SAMPLE DRUG INFORMATION")
print("=" * 70)

print(
    drugs[
        [
            "drug_name",
            "medical_condition",
            "side_effects",
            "generic_name"
        ]
    ].head(10).to_string(index=False)
)