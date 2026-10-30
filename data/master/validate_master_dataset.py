"""
SafeMed Master Dataset Validator
==================================
Validates data/master/safemed_drug_master.csv and produces
data/master/master_dataset_validation_report.txt

Run:
    python data/master/validate_master_dataset.py
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
MASTER_DIR = os.path.join(ROOT, "data", "master")

MASTER_CSV     = os.path.join(MASTER_DIR, "safemed_drug_master.csv")
SOURCES_CSV    = os.path.join(MASTER_DIR, "safemed_drug_sources.csv")
REPORT_TXT     = os.path.join(MASTER_DIR, "master_dataset_validation_report.txt")

# ============================================================
# LOAD
# ============================================================

def run_validation():

    report_lines = []
    issues = []
    warnings_list = []

    def log(msg=""):
        report_lines.append(msg)

    def issue(msg):
        issues.append(msg)
        report_lines.append(f"  [ERROR] {msg}")

    def warn(msg):
        warnings_list.append(msg)
        report_lines.append(f"  [WARN]  {msg}")

    def ok(msg):
        report_lines.append(f"  [OK]    {msg}")

    ts = datetime.now(timezone.utc).isoformat()
    log("=" * 65)
    log("SafeMed Master Dataset Validation Report")
    log(f"Generated: {ts}")
    log("=" * 65)

    # ── Load ──
    if not os.path.exists(MASTER_CSV):
        log()
        log("[FATAL] Master CSV not found. Run enrich_master_dataset.py first.")
        _write_report(report_lines, REPORT_TXT)
        return

    df = pd.read_csv(MASTER_CSV, dtype=str, keep_default_na=False)
    log()
    log(f"File : {MASTER_CSV}")
    log(f"Rows : {len(df):,}")
    log(f"Cols : {len(df.columns)}")

    # ── 1. Row count ──
    log()
    log("── 1. BASIC CHECKS ──────────────────────────────────")

    if len(df) == 0:
        issue("Dataset is empty.")
    else:
        ok(f"Dataset has {len(df):,} records.")

    # ── 2. Required columns ──
    REQUIRED = ["drug_name", "drug_name_normalized", "information_available"]
    for col in REQUIRED:
        if col not in df.columns:
            issue(f"Required column '{col}' is missing.")
        else:
            ok(f"Column '{col}' present.")

    # ── 3. Empty drug names ──
    log()
    log("── 2. DRUG NAME CHECKS ──────────────────────────────")

    empty_names = df[df["drug_name"].str.strip() == ""]
    if len(empty_names):
        issue(f"{len(empty_names)} records have empty drug_name.")
    else:
        ok("No empty drug_name values.")

    # ── 4. Duplicate drug names ──
    dupes = df[df["drug_name_normalized"].str.strip().duplicated(keep=False)]
    if len(dupes):
        dupe_names = dupes["drug_name"].unique().tolist()[:10]
        issue(f"{len(dupes)} rows share a duplicate drug_name_normalized. Examples: {dupe_names}")
    else:
        ok("No duplicate drug_name_normalized values.")

    # ── 5. Empty generic name ──
    log()
    log("── 3. GENERIC NAME CHECKS ───────────────────────────")

    empty_generic = df[df["generic_name"].str.strip() == ""]
    pct = len(empty_generic) / len(df) * 100
    if pct > 10:
        warn(f"{len(empty_generic)} drugs ({pct:.1f}%) have no generic_name.")
    else:
        ok(f"{len(empty_generic)} drugs ({pct:.1f}%) have no generic_name (within expected range).")

    # ── 6. Side effects checks ──
    log()
    log("── 4. SIDE EFFECTS CHECKS ───────────────────────────")

    no_se = df[df["side_effects"].str.strip() == ""]
    pct_no_se = len(no_se) / len(df) * 100
    ok(f"{len(df) - len(no_se)} drugs have side-effect data ({100 - pct_no_se:.1f}%).")
    ok(f"{len(no_se)} drugs have no side-effect data ({pct_no_se:.1f}%).")

    # Check for suspiciously short side effect strings
    se_df = df[df["side_effects"].str.strip() != ""].copy()
    se_df["se_len"] = se_df["side_effects"].str.len()
    very_short = se_df[se_df["se_len"] < 10]
    if len(very_short):
        warn(f"{len(very_short)} drugs have suspiciously short side_effects text (<10 chars).")
        for _, r in very_short.head(5).iterrows():
            warn(f"  {r['drug_name']}: '{r['side_effects']}'")

    # ── 7. Drug classes ──
    log()
    log("── 5. DRUG CLASS CHECKS ─────────────────────────────")

    no_class = df[df["drug_classes"].str.strip() == ""]
    ok(f"{len(no_class)} drugs have no drug_classes entry ({len(no_class)/len(df)*100:.1f}%).")

    # ── 8. Medical conditions ──
    log()
    log("── 6. MEDICAL CONDITION CHECKS ──────────────────────")

    no_cond = df[df["medical_conditions"].str.strip() == ""]
    if len(no_cond):
        warn(f"{len(no_cond)} drugs have no associated medical_conditions.")
    else:
        ok("All drugs have at least one medical condition.")

    # Duplicate conditions within a record
    dup_cond_count = 0
    for _, row in df.iterrows():
        conds = [c.strip().lower() for c in row["medical_conditions"].split("|") if c.strip()]
        if len(conds) != len(set(conds)):
            dup_cond_count += 1
    if dup_cond_count:
        warn(f"{dup_cond_count} drugs have duplicate conditions within their record.")
    else:
        ok("No duplicate conditions within individual drug records.")

    # ── 9. Completeness scores ──
    log()
    log("── 7. COMPLETENESS SCORE CHECKS ─────────────────────")

    if "data_completeness_score" in df.columns:
        scores = pd.to_numeric(df["data_completeness_score"], errors="coerce")
        invalid_scores = scores.isna() | (scores < 0) | (scores > 100)
        if invalid_scores.sum():
            issue(f"{invalid_scores.sum()} drugs have invalid completeness scores.")
        else:
            ok(f"All completeness scores are in valid range [0–100].")
        ok(f"Average completeness: {scores.mean():.1f}%")
        ok(f"Min: {scores.min():.1f}%, Max: {scores.max():.1f}%")

    # ── 10. Regulatory fields ──
    log()
    log("── 8. REGULATORY FIELD CHECKS ───────────────────────")

    if "rx_otc" in df.columns:
        vals = df["rx_otc"].str.strip().value_counts().to_dict()
        ok(f"rx_otc distribution: {vals}")

    if "pregnancy_category" in df.columns:
        vals = df["pregnancy_category"].str.strip().value_counts().to_dict()
        ok(f"pregnancy_category distribution: {vals}")

    # ── 11. information_available ──
    log()
    log("── 9. INFORMATION AVAILABLE FLAG ────────────────────")

    if "information_available" in df.columns:
        ia_counts = df["information_available"].value_counts().to_dict()
        ok(f"information_available values: {ia_counts}")

    # ── 12. Fields that should never be populated (fabricated) ──
    log()
    log("── 10. FABRICATION GUARD CHECKS ─────────────────────")

    SHOULD_BE_EMPTY = [
        "mechanism_of_action", "pharmacological_effect",
        "dosage_forms", "routes_of_administration",
        "contraindications", "warnings", "precautions",
        "pregnancy_information", "breastfeeding_information",
        "pediatric_information", "geriatric_information",
        "renal_information", "hepatic_information",
        "storage_information", "missed_dose_information",
        "drug_food_interactions", "drug_condition_interactions",
        "serious_side_effects", "common_side_effects", "rare_side_effects",
    ]

    for col in SHOULD_BE_EMPTY:
        if col not in df.columns:
            continue
        filled = df[df[col].str.strip() != ""]
        if len(filled):
            issue(
                f"[FABRICATION GUARD] Column '{col}' has {len(filled)} non-empty values. "
                f"This field should only be populated from a verified external source."
            )
        else:
            ok(f"'{col}' correctly empty — not fabricated.")

    # ── 13. Sources table ──
    log()
    log("── 11. SOURCES TABLE CHECKS ─────────────────────────")

    if os.path.exists(SOURCES_CSV):
        src_df = pd.read_csv(SOURCES_CSV, dtype=str, keep_default_na=False)
        ok(f"Sources table: {len(src_df):,} records, {src_df['drug_name'].nunique():,} unique drugs covered.")
        no_source = src_df[src_df["source"].str.strip() == ""]
        if len(no_source):
            warn(f"{len(no_source)} source records have empty source field.")
    else:
        warn("Sources table not found.")

    # ── 12. URL / SOURCE QUALITY ──
    log()
    log("── 12. URL AND SOURCE QUALITY ───────────────────────")

    url_re = re.compile(r"^https?://", re.I)
    malformed_urls = 0
    if "source_urls" in df.columns:
        for _, row in df.iterrows():
            url = str(row.get("source_urls", "")).strip()
            if url and not url_re.match(url):
                malformed_urls += 1
        if malformed_urls:
            issue(f"{malformed_urls} records have malformed source_urls values.")
        else:
            ok("No malformed source_urls values.")

    # Duplicate generic names (informational — not always an error)
    if "generic_name_normalized" in df.columns:
        filled_g = df[df["generic_name_normalized"].str.strip() != ""]
        dup_g = filled_g[filled_g["generic_name_normalized"].duplicated(keep=False)]
        if len(dup_g):
            warn(
                f"{dup_g['generic_name_normalized'].nunique()} generic names appear on more than one drug record "
                f"(may be legitimate brand/alias overlap)."
            )
        else:
            ok("No duplicate generic_name_normalized values among filled records.")

    # Duplicate side effects within a record
    dup_se = 0
    for _, row in df.iterrows():
        parts = [p.strip().lower() for p in str(row.get("side_effects", "")).split("|") if p.strip()]
        if len(parts) != len(set(parts)):
            dup_se += 1
    if dup_se:
        warn(f"{dup_se} drugs have duplicate side-effect fragments within the record.")
    else:
        ok("No duplicate side-effect fragments within individual drug records.")

    # Suspiciously long text
    if "side_effects" in df.columns:
        long_se = df[df["side_effects"].str.len() > 20000]
        if len(long_se):
            warn(f"{len(long_se)} drugs have unusually long side_effects text (>20,000 chars).")
        else:
            ok("No abnormally long side_effects values.")

    if "medical_condition_description" in df.columns:
        long_desc = df[df["medical_condition_description"].str.len() > 30000]
        if len(long_desc):
            warn(f"{len(long_desc)} drugs have unusually long condition descriptions (>30,000 chars).")
        else:
            ok("No abnormally long condition descriptions.")

    # ── 14. SUMMARY ──
    log()
    log("=" * 65)
    log("VALIDATION SUMMARY")
    log("=" * 65)
    log(f"  Total records   : {len(df):,}")
    log(f"  Total columns   : {len(df.columns)}")
    log(f"  Errors found    : {len(issues)}")
    log(f"  Warnings found  : {len(warnings_list)}")
    log()

    if len(issues) == 0:
        log("  VALIDATION STATUS: PASSED")
    else:
        log("  VALIDATION STATUS: FAILED — see errors above")

    log()
    log("  Errors:")
    if issues:
        for e in issues:
            log(f"    • {e}")
    else:
        log("    None")

    log()
    log("  Warnings:")
    if warnings_list:
        for w in warnings_list:
            log(f"    • {w}")
    else:
        log("    None")

    log()
    log("  Field completeness (informational fields):")
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
    for col in INFORMATIONAL_FIELDS:
        if col in df.columns:
            filled = (df[col].str.strip() != "").sum()
            pct = filled / len(df) * 100
            log(f"    {col:<38}: {filled:>5}/{len(df):>5}  ({pct:5.1f}%)")

    _write_report(report_lines, REPORT_TXT)

    # Print to console too
    for line in report_lines:
        print(line)

    return len(issues) == 0


def _write_report(lines, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nReport saved → {path}")


if __name__ == "__main__":
    success = run_validation()
    exit(0 if success else 1)
