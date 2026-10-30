import pandas as pd

# ==============================
# LOAD DATASETS
# ==============================

file1 = "data/data1/drugs_side_effects_drugs_com.csv"
file2 = "data/data2/db_drug_interactions.csv"

df1 = pd.read_csv(file1)
df2 = pd.read_csv(file2)


# ==============================
# DATASET 1
# ==============================

print("=" * 70)
print("DATASET 1 - DRUGS, CONDITIONS & SIDE EFFECTS")
print("=" * 70)

print("Shape:", df1.shape)

print("\nColumns:")
for column in df1.columns:
    print("-", column)

print("\nMissing values:")
print(df1.isnull().sum())

print("\nDuplicate rows:", df1.duplicated().sum())

print("\nUnique drug names:", df1["drug_name"].nunique())

print("\nUnique medical conditions:", df1["medical_condition"].nunique())


# ==============================
# DATASET 2
# ==============================

print("\n" + "=" * 70)
print("DATASET 2 - DRUG DRUG INTERACTIONS")
print("=" * 70)

print("Shape:", df2.shape)

print("\nColumns:")
for column in df2.columns:
    print("-", column)

print("\nMissing values:")
print(df2.isnull().sum())

print("\nDuplicate rows:", df2.duplicated().sum())


# ==============================
# DATA TYPES
# ==============================

print("\n" + "=" * 70)
print("DATA TYPES")
print("=" * 70)

print("\nDataset 1:")
print(df1.dtypes)

print("\nDataset 2:")
print(df2.dtypes)


# ==============================
# SAMPLE DATASET 2
# ==============================

print("\n" + "=" * 70)
print("DATASET 2 - FIRST 10 ROWS")
print("=" * 70)

print(df2.head(10).to_string(index=False))