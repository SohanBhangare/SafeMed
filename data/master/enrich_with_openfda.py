"""
data/master/enrich_with_openfda.py
====================================
Batch-enriches the SafeMed master dataset with FDA drug label data.

For each drug in safemed_drug_master.json:
  1. Checks which SafeMed fields are currently empty.
  2. Calls the OpenFDA drug label API if any key field is missing.
  3. Merges the FDA data into the master record
     — only fills EMPTY fields, never overwrites existing data.
  4. Saves progress every 50 drugs (resumable if interrupted).
  5. Writes an updated master JSON when done.

Run from the SafeMed project root:
    python data/master/enrich_with_openfda.py

Rate limit (no API key): ~40 requests/minute -> ~1.7 hrs for 4138 drugs.
Set OPENFDA_API_KEY environment variable for 240 req/min -> ~20 minutes.

SAFETY RULE: This script NEVER fabricates data.
             Only FDA-sourced text is written into the master file.
"""

import json
import os
import sys
import time

# ── Absolute project root (works regardless of cwd) ───────
_SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", ".."))

# Change cwd to project root so relative imports inside analysis/ work
os.chdir(_PROJECT_ROOT)
sys.path.insert(0, _PROJECT_ROOT)

from analysis.openfda_client import get_fda_label_data, cache_size

# ============================================================
# PATHS  (all absolute)
# ============================================================

MASTER_JSON   = os.path.join(_PROJECT_ROOT, "data", "master", "safemed_drug_master.json")
OUTPUT_JSON   = MASTER_JSON   # overwrite in-place
BACKUP_JSON   = os.path.join(_PROJECT_ROOT, "data", "master", "safemed_drug_master_pre_fda_backup.json")
PROGRESS_FILE = os.path.join(_PROJECT_ROOT, "data", "master", "openfda_enrich_progress.json")

# ============================================================
# FIELDS THAT BENEFIT FROM FDA ENRICHMENT
# (schema path → FDA result key)
# ============================================================

# Maps  (section, field_in_master)  →  key_in_fda_result
FDA_FIELD_MAP = [
    # pharmacology
    ("pharmacology",       "mechanism_of_action",           "mechanism_of_action"),
    ("pharmacology",       "pharmacological_effect",        "pharmacological_effect"),
    # general
    ("general_information","drug_description",              "drug_description"),
    ("general_information","general_uses",                  "general_uses"),
    # administration
    ("administration",     "dosage_forms",                  "dosage_forms"),
    ("administration",     "routes_of_administration",      "routes_of_administration"),
    ("administration",     "reference_dosing_information",  "reference_dosing_information"),
    # side effects
    ("side_effects",       "side_effects",                  "side_effects"),
    # safety
    ("safety",             "contraindications",             "contraindications"),
    ("safety",             "warnings",                      "warnings"),
    ("safety",             "precautions",                   "precautions"),
    # interactions
    ("interactions",       "drug_food_interactions",        "drug_food_interactions"),
    ("interactions",       "drug_condition_interactions",   "drug_condition_interactions"),
    # special populations
    ("special_populations","pregnancy_information",         "pregnancy_information"),
    ("special_populations","breastfeeding_information",     "breastfeeding_information"),
    ("special_populations","pediatric_information",         "pediatric_information"),
    ("special_populations","geriatric_information",         "geriatric_information"),
    # kidney / liver
    ("kidney_liver",       "renal_information",             "renal_information"),
    ("kidney_liver",       "hepatic_information",           "hepatic_information"),
    # practical
    ("practical",          "storage_information",           "storage_information"),
    ("practical",          "missed_dose_information",       "missed_dose_information"),
    # regulatory
    ("regulatory",         "controlled_substance_information","controlled_substance_information"),
]

# Key fields we check to decide whether to call the API at all.
# If all of these are already populated, we skip the drug.
SKIP_IF_FILLED = [
    ("pharmacology",       "mechanism_of_action"),
    ("safety",             "warnings"),
    ("special_populations","pregnancy_information"),
]


# ============================================================
# HELPERS
# ============================================================

def _is_empty(value) -> bool:
    """True when a master field is considered empty / missing."""
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, list) and not value:
        return True
    return False


def _needs_enrichment(record: dict) -> bool:
    """Return True if ANY of the key fields are empty."""
    for section, field in SKIP_IF_FILLED:
        val = record.get(section, {}).get(field)
        if _is_empty(val):
            return True
    return False


def _merge_fda_into_record(record: dict, fda_data: dict) -> int:
    """
    Merge fda_data into record, filling only empty fields.
    Returns the count of fields that were actually filled.
    """
    filled = 0
    for section, master_field, fda_key in FDA_FIELD_MAP:
        fda_val = fda_data.get(fda_key)
        if _is_empty(fda_val):
            continue
        if section not in record:
            record[section] = {}
        existing = record[section].get(master_field)
        if _is_empty(existing):
            record[section][master_field] = fda_val
            filled += 1

    # Update sources section to note FDA enrichment
    if filled > 0:
        if "sources" not in record:
            record["sources"] = {}
        existing_src = record["sources"].get("primary_source", "")
        if "OpenFDA" not in existing_src:
            fda_src = fda_data.get("fda_source", "OpenFDA drug label API")
            record["sources"]["additional_sources"] = (
                record["sources"].get("additional_sources", [])
            )
            if isinstance(record["sources"]["additional_sources"], list):
                if fda_src not in record["sources"]["additional_sources"]:
                    record["sources"]["additional_sources"].append(fda_src)

    return filled


def _load_progress() -> set:
    """Return set of drug names already processed in a previous run."""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def _save_progress(done: set) -> None:
    try:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(done), f)
    except Exception:
        pass


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 70)
    print("SafeMed — OpenFDA Batch Enrichment")
    print("=" * 70)

    # ── Load master dataset ───────────────────────────────────
    print(f"\nLoading master dataset: {MASTER_JSON}")
    with open(MASTER_JSON, "r", encoding="utf-8") as f:
        drugs = json.load(f)
    print(f"  {len(drugs):,} drug records loaded.")

    # ── Backup original ───────────────────────────────────────
    if not os.path.exists(BACKUP_JSON):
        print(f"\nCreating backup: {BACKUP_JSON}")
        with open(BACKUP_JSON, "w", encoding="utf-8") as f:
            json.dump(drugs, f, indent=2, ensure_ascii=False)
        print("  Backup saved.")
    else:
        print(f"\n  Backup already exists — skipping.")

    # ── Load progress (resumable) ─────────────────────────────
    done_names = _load_progress()
    print(f"  Previously processed: {len(done_names):,} drugs (resuming).")

    # ── Stats ─────────────────────────────────────────────────
    total          = len(drugs)
    skipped_done   = 0
    skipped_full   = 0
    api_calls      = 0
    fields_filled  = 0
    drugs_enriched = 0
    not_found      = 0
    errors         = 0

    save_interval  = 50   # save JSON every N drugs processed

    print(f"\nStarting enrichment (cache has {cache_size():,} entries)...")
    print("-" * 70)

    start_time = time.time()

    for i, record in enumerate(drugs):
        drug_name = record.get("drug_name", "")
        norm_name = drug_name.strip().lower()

        # ── Already processed in a previous run ──────────────
        if norm_name in done_names:
            skipped_done += 1
            continue

        # ── All key fields already filled ────────────────────
        if not _needs_enrichment(record):
            skipped_full += 1
            done_names.add(norm_name)
            continue

        # ── Call OpenFDA ──────────────────────────────────────
        api_calls += 1
        try:
            fda_data = get_fda_label_data(drug_name, use_cache=True)
        except Exception as e:
            print(f"  [ERROR] {drug_name}: {e}")
            errors += 1
            done_names.add(norm_name)
            continue

        if not fda_data:
            not_found += 1
        else:
            n_filled = _merge_fda_into_record(record, fda_data)
            fields_filled  += n_filled
            drugs_enriched += (1 if n_filled > 0 else 0)

        done_names.add(norm_name)

        # ── Progress print ────────────────────────────────────
        elapsed  = time.time() - start_time
        rate     = api_calls / elapsed if elapsed > 0 else 1
        remaining = (total - i - 1) * (1 / rate) if rate > 0 else 0
        eta_min  = remaining / 60

        print(
            f"  [{i+1:>5}/{total}] {drug_name:<30} "
            f"| filled={fields_filled}  ETA={eta_min:.1f}m"
        )

        # ── Periodic save ─────────────────────────────────────
        if api_calls % save_interval == 0:
            _save_progress(done_names)
            with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
                json.dump(drugs, f, indent=2, ensure_ascii=False)
            print(f"  [SAVED] Progress saved at drug #{i+1}")

    # ── Final save ────────────────────────────────────────────
    _save_progress(done_names)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(drugs, f, indent=2, ensure_ascii=False)

    # ── Summary ───────────────────────────────────────────────
    elapsed_total = time.time() - start_time
    print("\n" + "=" * 70)
    print("ENRICHMENT COMPLETE")
    print("=" * 70)
    print(f"  Total drugs         : {total:,}")
    print(f"  Skipped (done)      : {skipped_done:,}")
    print(f"  Skipped (full)      : {skipped_full:,}")
    print(f"  API calls made      : {api_calls:,}")
    print(f"  Drugs enriched      : {drugs_enriched:,}")
    print(f"  Total fields filled : {fields_filled:,}")
    print(f"  Not found on FDA    : {not_found:,}")
    print(f"  Errors              : {errors:,}")
    print(f"  Time taken          : {elapsed_total/60:.1f} minutes")
    print(f"\n  Master JSON saved   : {OUTPUT_JSON}")
    print(f"  Cache size          : {cache_size():,} entries")
    print("\nDone.")


if __name__ == "__main__":
    main()
