import pandas as pd


# ============================================================
# LOAD CLEANED DDI DATASET
# ============================================================

FILE = "data/cleaned/drug_interactions_cleaned.csv"

ddi = pd.read_csv(FILE)


# ============================================================
# BASIC ANALYSIS
# ============================================================

print("=" * 70)
print("SAFEMED INTERACTION DATA ANALYSIS")
print("=" * 70)

print("\nTotal interaction records:", len(ddi))

print(
    "Unique drug pairs:",
    ddi["drug_pair"].nunique()
)


# ============================================================
# DESCRIPTION LENGTH
# ============================================================

ddi["description_length"] = (
    ddi["interaction_description"]
    .astype(str)
    .str.len()
)

print("\nDescription statistics:")
print(
    ddi["description_length"].describe()
)


# ============================================================
# COMMON WORDS / PATTERNS
# ============================================================

keywords = [
    "increase",
    "decrease",
    "inhibit",
    "enhance",
    "reduce",
    "toxicity",
    "risk",
    "concentration",
    "effect",
    "activity"
]


print("\n" + "=" * 70)
print("INTERACTION DESCRIPTION KEYWORDS")
print("=" * 70)

description_text = (
    ddi["interaction_description"]
    .astype(str)
    .str.lower()
)

for keyword in keywords:

    count = description_text.str.contains(
        keyword,
        regex=False
    ).sum()

    percentage = (
        count / len(ddi)
    ) * 100

    print(
        f"{keyword:15} : "
        f"{count:7} records "
        f"({percentage:.2f}%)"
    )


# ============================================================
# SAMPLE INTERACTIONS
# ============================================================

print("\n" + "=" * 70)
print("SAMPLE INTERACTION DESCRIPTIONS")
print("=" * 70)

for description in (
    ddi["interaction_description"]
    .head(20)
):

    print("\n-", description)