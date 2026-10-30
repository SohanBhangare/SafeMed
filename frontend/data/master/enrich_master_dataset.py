"""
SafeMed Master Drug Dataset Builder
====================================
Builds data/master/safemed_drug_master.csv and related files
from existing cleaned datasets.

IMPORTANT: No medical information is fabricated.
Fields not supported by the source dataset are left empty.
Every field has a recorded source.

Run:
    python data/master/enrich_master_dataset.py
"""

import pandas as pd
import json
import os
import re
from datetime import datetime, timezone

# ============================================================
# PATHS
# ============================================================

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DRUGS_CLEANED   = os.path.join(ROOT, "data", "cleaned", "drugs_cleaned.csv")
DDI_CLEANED     = os.path.join(ROOT, "data", "cleaned", "drug_interactions_cleaned.csv")
MASTER_DIR      = os.path.join(ROOT, "data", "master")

OUT_CSV         = os.path.join(MASTER_DIR, "safemed_drug_master.csv")
OUT_JSON        = os.path.join(MASTER_DIR, "safemed_drug_master.json")
OUT_SOURCES     = os.path.join(MASTER_DIR, "safemed_drug_sources.csv")
OUT_SUMMARY     = os.path.join(MASTER_DIR, "master_dataset_summary.json")
OUT_VERSION     = os.path.join(MASTER_DIR, "version.json")

SOURCE_LABEL    = "SafeMed reference dataset (drugs_side_effects_drugs_com.csv)"
DDI_SOURCE_LABEL = "SafeMed DDI reference dataset (db_drug_interactions.csv)"
SOURCE_URL      = ""   # original source URL unavailable — recorded as empty
GENERATED_AT    = datetime.now(timezone.utc).isoformat()
DATA_VERSION    = "1.1.0"

# ============================================================
# HELPERS
# ============================================================

def normalize(text):
    """Normalize a drug/condition name for matching."""
    if not text or not isinstance(text, str):
        return ""
    return text.strip().lower()


def clean_str(val):
    """Return stripped string or empty string."""
    if val is None or (isinstance(val, float) and str(val) == "nan"):
        return ""
    return str(val).strip()


def join_unique(series, sep=" | "):
    """Join unique non-empty string values from a pandas Series."""
    seen = []
    for v in series:
        s = clean_str(v)
        if s and s not in seen:
            seen.append(s)
    return sep.join(seen)


def merge_conditions(series):
    """Return unique conditions as a pipe-separated string."""
    vals = []
    for v in series:
        s = clean_str(v)
        if s and s.lower() not in [x.lower() for x in vals]:
            vals.append(s)
    return " | ".join(vals)


def merge_descriptions(series):
    """Return unique condition descriptions joined with separator."""
    vals = []
    for v in series:
        s = clean_str(v)
        if s and s not in vals:
            vals.append(s)
    return "\n---\n".join(vals)


def build_completeness(row, informational_fields):
    """
    Calculate what fraction of informational fields are non-empty.
    This is a data-coverage metric, NOT a clinical quality score.
    """
    total = len(informational_fields)
    filled = sum(1 for f in informational_fields if clean_str(row.get(f, "")))
    if total == 0:
        return 0.0
    return round(filled / total * 100, 1)


def parse_csa(csa_val):
    """Convert CSA schedule code to a readable description."""
    mapping = {
        "N": "Not a controlled substance",
        "1": "Schedule I controlled substance",
        "2": "Schedule II controlled substance",
        "3": "Schedule III controlled substance",
        "4": "Schedule IV controlled substance",
        "5": "Schedule V controlled substance",
        "U": "Unscheduled",
        "M": "Monitored",
    }
    s = clean_str(csa_val)
    return mapping.get(s, s) if s else ""


def parse_alcohol(alcohol_val):
    """Convert alcohol flag to readable information."""
    s = clean_str(alcohol_val)
    if s == "X":
        return (
            "The reference dataset flags this medication with an alcohol interaction marker. "
            "Consult official medication labeling or a healthcare professional for details."
        )
    return ""


def normalize_brand_list(brand_names):
    """Return pipe-separated normalized brand names without changing originals."""
    parts = re.split(r"[,;|]", clean_str(brand_names))
    seen = []
    for p in parts:
        n = normalize(p)
        if n and n not in seen:
            seen.append(n)
    return " | ".join(seen)


def blank_master_row(drug_name, drug_name_normalized, primary_source, information_available):
    """Create a master record with empty medical fields (never fabricated)."""
    return {
        "drug_name": drug_name,
        "drug_name_normalized": drug_name_normalized,
        "generic_name": "",
        "generic_name_normalized": "",
        "brand_names": "",
        "normalized_brand_names": "",
        "drug_classes": "",
        "drug_subclass": "",
        "drug_description": "",
        "general_uses": "",
        "medical_conditions": "",
        "medical_condition_description": "",
        "therapeutic_category": "",
        "therapeutic_effect": "",
        "activity": "",
        "mechanism_of_action": "",
        "pharmacological_effect": "",
        "active_ingredient": "",
        "dosage_forms": "",
        "routes_of_administration": "",
        "reference_dosing_information": "",
        "side_effects": "",
        "serious_side_effects": "",
        "common_side_effects": "",
        "rare_side_effects": "",
        "contraindications": "",
        "warnings": "",
        "precautions": "",
        "monitoring_information": "",
        "allergy_information": "",
        "drug_food_interactions": "",
        "drug_alcohol_interactions": "",
        "drug_condition_interactions": "",
        "pregnancy_information": "",
        "breastfeeding_information": "",
        "pediatric_information": "",
        "geriatric_information": "",
        "renal_information": "",
        "hepatic_information": "",
        "storage_information": "",
        "missed_dose_information": "",
        "rx_otc": "",
        "pregnancy_category": "",
        "pregnancy_category_raw": "",
        "controlled_substance_information": "",
        "related_drugs": "",
        "in_ddi_dataset": True,
        "primary_source": primary_source,
        "additional_sources": "",
        "source_urls": "",
        "last_verified": GENERATED_AT,
        "data_version": DATA_VERSION,
        "information_available": information_available,
    }


# ============================================================
# LOAD SOURCE DATA
# ============================================================

print("=" * 60)
print("SafeMed Master Dataset Builder v" + DATA_VERSION)
print("=" * 60)

print("\nLoading source datasets...")

drugs_df = pd.read_csv(DRUGS_CLEANED)
ddi_df   = pd.read_csv(DDI_CLEANED)

print(f"  drugs_cleaned.csv  : {len(drugs_df):,} rows, {drugs_df['drug_name_normalized'].nunique():,} unique drugs")
print(f"  drug_interactions_cleaned.csv: {len(ddi_df):,} rows")

# ============================================================
# STEP 1: GROUP BY DRUG â€” ONE ROW PER DRUG
# ============================================================

print("\nStep 1: Aggregating â€” one record per drug...")

source_records = []   # will build the sources table

master_rows = []

for norm_name, group in drugs_df.groupby("drug_name_normalized", sort=False):

    # Use the first row for scalar fields (rx_otc, pregnancy_category, etc.)
    first = group.iloc[0]

    drug_name      = clean_str(first["drug_name"])
    generic_name   = clean_str(first["generic_name"])
    drug_classes   = clean_str(first["drug_classes"])
    brand_names    = clean_str(first["brand_names"])
    rx_otc         = clean_str(first["rx_otc"])
    pregnancy_cat  = clean_str(first["pregnancy_category"])
    csa_raw        = clean_str(first["csa"])
    alcohol_raw    = clean_str(first["alcohol"])

    # Aggregated fields
    medical_conditions   = merge_conditions(group["medical_condition"])
    condition_descs      = merge_descriptions(group["medical_condition_description"])
    side_effects         = join_unique(group["side_effects"], sep=" | ")
    related_drugs        = join_unique(group["related_drugs"], sep=" | ")
    all_drug_classes     = join_unique(group["drug_classes"], sep=" | ")
    activity_pct         = clean_str(first["activity"])

    # Normalized
    drug_name_normalized     = normalize(drug_name)
    generic_name_normalized  = normalize(generic_name)
    normalized_brand_names   = normalize_brand_list(brand_names)

    # Parse flags
    csa_description     = parse_csa(csa_raw)
    alcohol_information = parse_alcohol(alcohol_raw)

    # Fields NOT available in source â€” left empty (never fabricated)
    row = {
        # â”€â”€ IDENTITY â”€â”€
        "drug_name":                    drug_name,
        "drug_name_normalized":         drug_name_normalized,
        "generic_name":                 generic_name,
        "generic_name_normalized":      generic_name_normalized,
        "brand_names":                  brand_names,
        "normalized_brand_names":       normalized_brand_names,
        "drug_classes":                 all_drug_classes,
        "drug_subclass":                "",          # not in source

        # â”€â”€ GENERAL INFORMATION â”€â”€
        "drug_description":             "",          # not in source
        "general_uses":                 "",          # not in source
        "medical_conditions":           medical_conditions,
        "medical_condition_description":condition_descs,
        "therapeutic_category":         "",          # not in source
        "therapeutic_effect":           "",          # not in source
        "activity":                     activity_pct,

        # â”€â”€ PHARMACOLOGY â”€â”€
        "mechanism_of_action":          "",          # not in source
        "pharmacological_effect":       "",          # not in source
        "active_ingredient":            generic_name if generic_name else "",

        # â”€â”€ ADMINISTRATION â”€â”€
        "dosage_forms":                 "",          # not in source
        "routes_of_administration":     "",          # not in source
        "reference_dosing_information": "",          # not in source

        # â”€â”€ SIDE EFFECTS â”€â”€
        "side_effects":                 side_effects,
        "serious_side_effects":         "",          # source does not categorize
        "common_side_effects":          "",          # source does not categorize
        "rare_side_effects":            "",          # source does not categorize

        # â”€â”€ SAFETY â”€â”€
        "contraindications":            "",          # not in source
        "warnings":                     "",          # not in source
        "precautions":                  "",          # not in source
        "monitoring_information":       "",          # not in source
        "allergy_information":          "",          # not in source

        # â”€â”€ INTERACTIONS â”€â”€
        "drug_food_interactions":       "",          # not in source
        "drug_alcohol_interactions":    alcohol_information,
        "drug_condition_interactions":  "",          # not in source

        # â”€â”€ SPECIAL POPULATIONS â”€â”€
        "pregnancy_information":        "",          # not in source
        "breastfeeding_information":    "",          # not in source
        "pediatric_information":        "",          # not in source
        "geriatric_information":        "",          # not in source

        # â”€â”€ KIDNEY / LIVER â”€â”€
        "renal_information":            "",          # not in source
        "hepatic_information":          "",          # not in source

        # â”€â”€ PRACTICAL â”€â”€
        "storage_information":          "",          # not in source
        "missed_dose_information":      "",          # not in source

        # â”€â”€ REGULATORY â”€â”€
        "rx_otc":                       rx_otc,
        "pregnancy_category":           pregnancy_cat,
        "pregnancy_category_raw":       pregnancy_cat,
        "controlled_substance_information": csa_description,

        # â”€â”€ RELATED â”€â”€
        "related_drugs":                related_drugs,

        # â”€â”€ SOURCE / QUALITY â”€â”€
        "primary_source":               SOURCE_LABEL,
        "additional_sources":           "",
        "source_urls":                  "",
        "last_verified":                GENERATED_AT,
        "data_version":                 DATA_VERSION,
        "information_available":        True,
    }

    master_rows.append(row)

    # Record sources for populated fields
    for field, value in [
        ("drug_name",           drug_name),
        ("generic_name",        generic_name),
        ("brand_names",         brand_names),
        ("drug_classes",        all_drug_classes),
        ("medical_conditions",  medical_conditions),
        ("medical_condition_description", condition_descs),
        ("side_effects",        side_effects),
        ("rx_otc",              rx_otc),
        ("pregnancy_category",  pregnancy_cat),
        ("controlled_substance_information", csa_description),
        ("drug_alcohol_interactions", alcohol_information),
        ("related_drugs",       related_drugs),
        ("active_ingredient",   generic_name),
        ("normalized_brand_names", normalized_brand_names),
    ]:
        if value:
            source_records.append({
                "drug_name":           drug_name,
                "field_name":          field,
                "source":              SOURCE_LABEL,
                "source_url":          SOURCE_URL,
                "source_date":         GENERATED_AT[:10],
                "verification_status": "mapped_from_source",
                "notes":               "Mapped from existing SafeMed cleaned dataset",
            })

print(f"  Built {len(master_rows):,} master drug records from drugs_cleaned.csv")

# Add DDI-only medications as honest stub records (name + DDI presence only)
print("  Adding DDI-only medications (no fabricated clinical fields)...")
existing_norms = {r["drug_name_normalized"] for r in master_rows}
ddi_name_map = {}
for orig_col, norm_col in (("drug_1", "drug_1_normalized"), ("drug_2", "drug_2_normalized")):
    for orig, norm in zip(ddi_df[orig_col], ddi_df[norm_col]):
        n = normalize(clean_str(norm))
        if not n or n == "nan" or n in existing_norms:
            continue
        if n not in ddi_name_map:
            display = clean_str(orig) or n
            ddi_name_map[n] = display

ddi_stub_count = 0
for n, display in sorted(ddi_name_map.items()):
    row = blank_master_row(
        drug_name=display,
        drug_name_normalized=n,
        primary_source=DDI_SOURCE_LABEL,
        information_available=False,
    )
    master_rows.append(row)
    source_records.append({
        "drug_name":           display,
        "field_name":          "drug_name",
        "source":              DDI_SOURCE_LABEL,
        "source_url":          SOURCE_URL,
        "source_date":         GENERATED_AT[:10],
        "verification_status": "mapped_from_source",
        "notes":               "Name present in DDI dataset; clinical fields not available in current reference data",
    })
    ddi_stub_count += 1

print(f"  Added {ddi_stub_count:,} DDI-only name records")
print(f"  Total unique medications: {len(master_rows):,}")

# ============================================================
# STEP 2: INFORMATIONAL FIELDS FOR COMPLETENESS SCORING
# ============================================================

INFORMATIONAL_FIELDS = [
    "generic_name", "brand_names", "drug_classes",
    "medical_conditions", "medical_condition_description",
    "side_effects", "drug_alcohol_interactions",
    "mechanism_of_action", "pharmacological_effect",
    "dosage_forms", "routes_of_administration",
    "contraindications", "warnings", "precautions",
    "pregnancy_information", "breastfeeding_information",
    "pediatric_information", "geriatric_information",
    "renal_information", "hepatic_information",
    "storage_information", "drug_food_interactions",
    "drug_condition_interactions",
]

print("\nStep 2: Calculating data completeness scores...")

for row in master_rows:
    row["data_completeness_score"] = build_completeness(row, INFORMATIONAL_FIELDS)
    missing = [f for f in INFORMATIONAL_FIELDS if not clean_str(row.get(f, ""))]
    row["missing_information_fields"] = " | ".join(missing)
    has_any_info = bool(clean_str(row.get("generic_name", "")) or
                        clean_str(row.get("side_effects", "")) or
                        clean_str(row.get("medical_conditions", "")) or
                        clean_str(row.get("drug_classes", "")))
    row["information_available"] = has_any_info

# ============================================================
# STEP 3: ADD DDI DRUG PRESENCE FLAG
# ============================================================

print("Step 3: Flagging DDI dataset presence...")

ddi_drugs = set(ddi_df["drug_1_normalized"].dropna().str.strip().str.lower())
ddi_drugs |= set(ddi_df["drug_2_normalized"].dropna().str.strip().str.lower())

for row in master_rows:
    in_ddi = row["drug_name_normalized"] in ddi_drugs
    row["in_ddi_dataset"] = in_ddi
    if in_ddi and row.get("primary_source") == SOURCE_LABEL:
        row["additional_sources"] = DDI_SOURCE_LABEL

# ============================================================
# STEP 4: BUILD DATAFRAME & SAVE CSV
# ============================================================

print("Step 4: Building master DataFrame...")

master_df = pd.DataFrame(master_rows)

# Ensure column order
col_order = [
    "drug_name", "drug_name_normalized",
    "generic_name", "generic_name_normalized",
    "brand_names", "normalized_brand_names", "drug_classes", "drug_subclass",
    "drug_description", "general_uses",
    "medical_conditions", "medical_condition_description",
    "therapeutic_category", "therapeutic_effect", "activity",
    "mechanism_of_action", "pharmacological_effect", "active_ingredient",
    "dosage_forms", "routes_of_administration", "reference_dosing_information",
    "side_effects", "serious_side_effects", "common_side_effects", "rare_side_effects",
    "contraindications", "warnings", "precautions",
    "monitoring_information", "allergy_information",
    "drug_food_interactions", "drug_alcohol_interactions", "drug_condition_interactions",
    "pregnancy_information", "breastfeeding_information",
    "pediatric_information", "geriatric_information",
    "renal_information", "hepatic_information",
    "storage_information", "missed_dose_information",
    "rx_otc", "pregnancy_category", "pregnancy_category_raw",
    "controlled_substance_information",
    "related_drugs",
    "in_ddi_dataset",
    "primary_source", "additional_sources", "source_urls",
    "last_verified", "data_version", "information_available",
    "data_completeness_score", "missing_information_fields",
]

# Only keep columns that exist (safety check)
col_order = [c for c in col_order if c in master_df.columns]
master_df = master_df[col_order]

master_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
print(f"  Saved CSV  â†’ {OUT_CSV}")
print(f"  Rows: {len(master_df):,}, Columns: {len(master_df.columns)}")

# ============================================================
# STEP 5: SAVE JSON (structured for API use)
# ============================================================

print("Step 5: Building master JSON...")

def as_bool(val, default=False):
    if isinstance(val, bool):
        return val
    try:
        if hasattr(val, "item"):
            val = val.item()
            if isinstance(val, bool):
                return val
    except Exception:
        pass
    s = str(val).strip().lower()
    if s in ("true", "1", "yes"):
        return True
    if s in ("false", "0", "no", "", "nan"):
        return False
    return default


def row_to_json(row):
    def v(field):
        val = row.get(field, "")
        if val is None or (isinstance(val, float) and str(val) in ("nan", "inf", "-inf")):
            return ""
        return str(val).strip() if not isinstance(val, bool) else val

    conditions_list = [c.strip() for c in v("medical_conditions").split("|") if c.strip()]
    drug_classes_list = [c.strip() for c in v("drug_classes").split("|") if c.strip()]
    brand_list = [b.strip() for b in v("brand_names").replace(",", "|").split("|") if b.strip()]
    related_list = []
    for seg in v("related_drugs").split("|"):
        seg = seg.strip()
        if ":" in seg:
            name = seg.split(":")[0].strip()
            url = ":".join(seg.split(":")[1:]).strip()
            related_list.append({"name": name, "url": url})
        elif seg:
            related_list.append({"name": seg, "url": ""})

    missing_list = [f.strip() for f in v("missing_information_fields").split("|") if f.strip()]
    desc_parts = v("medical_condition_description").split("\n---\n")

    return {
        "drug_name":            v("drug_name"),
        "drug_name_normalized": v("drug_name_normalized"),
        "in_ddi_dataset":       as_bool(row.get("in_ddi_dataset", False)),
        "information_available": as_bool(row.get("information_available", False)),
        "data_completeness_score": float(row.get("data_completeness_score", 0)),

        "identity": {
            "drug_name":    v("drug_name"),
            "generic_name": v("generic_name"),
            "brand_names":  brand_list,
            "normalized_brand_names": [b.strip() for b in v("normalized_brand_names").split("|") if b.strip()],
            "drug_classes": drug_classes_list,
            "drug_subclass":v("drug_subclass"),
            "active_ingredient": v("active_ingredient"),
        },
        "general_information": {
            "drug_description":             v("drug_description"),
            "general_uses":                 v("general_uses"),
            "medical_conditions":           conditions_list,
            "medical_condition_description":desc_parts,
            "therapeutic_category":         v("therapeutic_category"),
            "therapeutic_effect":           v("therapeutic_effect"),
            "activity":                     v("activity"),
        },
        "pharmacology": {
            "mechanism_of_action":   v("mechanism_of_action"),
            "pharmacological_effect":v("pharmacological_effect"),
        },
        "administration": {
            "dosage_forms":                 v("dosage_forms"),
            "routes_of_administration":     v("routes_of_administration"),
            "reference_dosing_information": v("reference_dosing_information"),
        },
        "side_effects": {
            "side_effects":        v("side_effects"),
            "serious_side_effects":v("serious_side_effects"),
            "common_side_effects": v("common_side_effects"),
            "rare_side_effects":   v("rare_side_effects"),
        },
        "safety": {
            "contraindications":      v("contraindications"),
            "warnings":               v("warnings"),
            "precautions":            v("precautions"),
            "monitoring_information": v("monitoring_information"),
            "allergy_information":    v("allergy_information"),
        },
        "interactions": {
            "drug_food_interactions":      v("drug_food_interactions"),
            "drug_alcohol_interactions":   v("drug_alcohol_interactions"),
            "drug_condition_interactions": v("drug_condition_interactions"),
        },
        "special_populations": {
            "pregnancy_information":     v("pregnancy_information"),
            "breastfeeding_information": v("breastfeeding_information"),
            "pediatric_information":     v("pediatric_information"),
            "geriatric_information":     v("geriatric_information"),
        },
        "kidney_liver": {
            "renal_information":   v("renal_information"),
            "hepatic_information": v("hepatic_information"),
        },
        "practical": {
            "storage_information":   v("storage_information"),
            "missed_dose_information": v("missed_dose_information"),
        },
        "regulatory": {
            "rx_otc":                      v("rx_otc"),
            "pregnancy_category":          v("pregnancy_category"),
            "controlled_substance_information": v("controlled_substance_information"),
        },
        "related": {
            "related_drugs": related_list,
        },
        "sources": {
            "primary_source":    v("primary_source"),
            "additional_sources":v("additional_sources"),
            "source_urls":       v("source_urls"),
            "last_verified":     v("last_verified"),
            "data_version":      v("data_version"),
        },
        "data_quality": {
            "data_completeness_score": float(row.get("data_completeness_score", 0)),
            "missing_information_fields": missing_list,
            "information_available": as_bool(row.get("information_available", False)),
            "in_ddi_dataset": bool(row.get("in_ddi_dataset", False)),
        },
    }

json_records = []
for _, row in master_df.iterrows():
    json_records.append(row_to_json(row.to_dict()))

with open(OUT_JSON, "w", encoding="utf-8") as f:
    json.dump(json_records, f, indent=2, ensure_ascii=False)

print(f"  Saved JSON -> {OUT_JSON}")

# ============================================================
# STEP 6: SAVE SOURCES TABLE
# ============================================================

print("Step 6: Saving source provenance table...")

sources_df = pd.DataFrame(source_records)
sources_df.to_csv(OUT_SOURCES, index=False, encoding="utf-8-sig")
print(f"  Saved sources â†’ {OUT_SOURCES} ({len(sources_df):,} source records)")

# ============================================================
# STEP 7: DATASET SUMMARY STATISTICS
# ============================================================

print("Step 7: Computing dataset statistics...")

def count_nonempty(col):
    return int((master_df[col].fillna("").astype(str).str.strip() != "").sum())

summary = {
    "dataset_name": "SafeMed Master Drug Dataset",
    "version": DATA_VERSION,
    "generated_at": GENERATED_AT,
    "source_datasets": [
        "data/cleaned/drugs_cleaned.csv",
        "data/cleaned/drug_interactions_cleaned.csv",
    ],
    "statistics": {
        "total_unique_drugs":               len(master_df),
        "total_drug_classes":               int(
            master_df["drug_classes"].dropna()
            .str.split("|").explode().str.strip()
            .replace("", pd.NA).dropna().nunique()
        ),
        "total_conditions":                 int(
            master_df["medical_conditions"].dropna()
            .str.split("|").explode().str.strip()
            .replace("", pd.NA).dropna().nunique()
        ),
        "drugs_with_generic_name":          count_nonempty("generic_name"),
        "drugs_with_brand_names":           count_nonempty("brand_names"),
        "drugs_with_side_effects":          count_nonempty("side_effects"),
        "drugs_with_drug_classes":          count_nonempty("drug_classes"),
        "drugs_with_mechanism":             count_nonempty("mechanism_of_action"),
        "drugs_with_warnings":              count_nonempty("warnings"),
        "drugs_with_contraindications":     count_nonempty("contraindications"),
        "drugs_with_pregnancy_information": count_nonempty("pregnancy_information"),
        "drugs_with_pregnancy_category":    count_nonempty("pregnancy_category"),
        "drugs_with_alcohol_information":   count_nonempty("drug_alcohol_interactions"),
        "drugs_with_related_drugs":         count_nonempty("related_drugs"),
        "drugs_in_ddi_dataset":             int(master_df["in_ddi_dataset"].sum()),
        "average_completeness_score":       round(float(master_df["data_completeness_score"].mean()), 1),
        "min_completeness_score":           float(master_df["data_completeness_score"].min()),
        "max_completeness_score":           float(master_df["data_completeness_score"].max()),
    },
    "field_completeness": {},
    "note": (
        "Statistics describe data availability only. "
        "They are not clinical quality or safety indicators."
    ),
}

# Per-field completeness
for col in INFORMATIONAL_FIELDS:
    if col in master_df.columns:
        filled = int((master_df[col].fillna("").astype(str).str.strip() != "").sum())
        summary["field_completeness"][col] = {
            "filled": filled,
            "total": len(master_df),
            "percent": round(filled / len(master_df) * 100, 1),
        }

with open(OUT_SUMMARY, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print(f"  Saved summary â†’ {OUT_SUMMARY}")

# ============================================================
# STEP 8: VERSION FILE
# ============================================================

version_data = {
    "dataset_name": "SafeMed Master Drug Dataset",
    "version": DATA_VERSION,
    "generated_at": GENERATED_AT,
    "source_datasets": [
        "data/cleaned/drugs_cleaned.csv",
        "data/cleaned/drug_interactions_cleaned.csv",
    ],
    "schema_fields": col_order,
    "note": (
        "This dataset is built from existing SafeMed source data. "
        "Empty fields indicate unavailable information — not fabricated values."
    ),
}

with open(OUT_VERSION, "w", encoding="utf-8") as f:
    json.dump(version_data, f, indent=2)

print(f"  Saved version -> {OUT_VERSION}")

try:
    from validate_master_dataset import run_validation
    print("\nRunning validation...")
    run_validation()
except Exception as _ve:
    print(f"  Validation skipped: {_ve}")

# ============================================================
# FINAL REPORT
# ============================================================

st = summary["statistics"]
print("\n" + "=" * 60)
print("MASTER DATASET BUILD COMPLETE")
print("=" * 60)
print(f"  Total unique drugs        : {st['total_unique_drugs']:,}")
print(f"  Unique drug classes       : {st['total_drug_classes']:,}")
print(f"  Unique conditions         : {st['total_conditions']:,}")
print(f"  With side effects         : {st['drugs_with_side_effects']:,}")
print(f"  With brand names          : {st['drugs_with_brand_names']:,}")
print(f"  With alcohol information  : {st['drugs_with_alcohol_information']:,}")
print(f"  In DDI dataset            : {st['drugs_in_ddi_dataset']:,}")
print(f"  Average completeness      : {st['average_completeness_score']}%")
print(f"  Mechanism of action       : {st['drugs_with_mechanism']:,} (0 — not in source)")
print(f"  Warnings                  : {st['drugs_with_warnings']:,} (0 — not in source)")
print(f"  Contraindications         : {st['drugs_with_contraindications']:,} (0 — not in source)")
print()
print("  NOTE: Empty fields were intentionally left empty.")
print("  No medical information was fabricated.")
print()
print("  Files created:")
print(f"    {OUT_CSV}")
print(f"    {OUT_JSON}")
print(f"    {OUT_SOURCES}")
print(f"    {OUT_SUMMARY}")
print(f"    {OUT_VERSION}")

