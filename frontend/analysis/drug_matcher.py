import os
import pandas as pd
from rapidfuzz import process, fuzz


# ============================================================
# LOAD MASTER DRUG LIST (primary name reference)
# ============================================================

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER_FILE = os.path.join(ROOT, "data", "master", "safemed_drug_master.csv")
DDI_FILE = os.path.join(ROOT, "data", "cleaned", "drug_interactions_cleaned.csv")
DRUG_FILE = os.path.join(ROOT, "data", "cleaned", "drugs_cleaned.csv")

MATCH_NOTE = (
    "This percentage represents text-matching similarity, "
    "not medical confidence."
)

# canonical display name by normalized key
_display_by_norm = {}
# extra aliases: generic / brand -> normalized drug name
_alias_to_norm = {}


def _normalize(text):
    return str(text).strip().lower() if text is not None else ""


def _load_name_maps():
    display = {}
    aliases = {}

    if os.path.exists(MASTER_FILE):
        master = pd.read_csv(MASTER_FILE, dtype=str, keep_default_na=False)
        for _, row in master.iterrows():
            name = str(row.get("drug_name", "")).strip()
            norm = str(row.get("drug_name_normalized", "")).strip().lower() or _normalize(name)
            if not norm:
                continue
            display[norm] = name or norm
            aliases[norm] = norm

            generic = _normalize(row.get("generic_name", ""))
            if generic:
                aliases.setdefault(generic, norm)

            brands = str(row.get("normalized_brand_names", "") or row.get("brand_names", ""))
            for part in brands.replace(",", "|").split("|"):
                b = _normalize(part)
                if b:
                    aliases.setdefault(b, norm)
        return display, aliases

    # Fallback if master dataset is not yet generated
    names = set()
    if os.path.exists(DDI_FILE):
        ddi = pd.read_csv(DDI_FILE)
        for col in ("drug_1_normalized", "drug_2_normalized"):
            if col in ddi.columns:
                names.update(ddi[col].dropna().astype(str).str.lower().str.strip())
        for col in ("drug_1", "drug_2"):
            if col in ddi.columns:
                for val in ddi[col].dropna().astype(str):
                    n = _normalize(val)
                    if n:
                        display.setdefault(n, val.strip())
    if os.path.exists(DRUG_FILE):
        drugs = pd.read_csv(DRUG_FILE)
        if "drug_name_normalized" in drugs.columns:
            names.update(drugs["drug_name_normalized"].dropna().astype(str).str.lower().str.strip())
        if "drug_name" in drugs.columns:
            for val in drugs["drug_name"].dropna().astype(str):
                n = _normalize(val)
                if n:
                    display.setdefault(n, val.strip())
    for n in names:
        if n and n != "nan":
            display.setdefault(n, n)
            aliases[n] = n
    return display, aliases


_display_by_norm, _alias_to_norm = _load_name_maps()
_search_keys = sorted(_alias_to_norm.keys())


def display_name(normalized):
    """Return original spelling for a normalized drug name."""
    n = _normalize(normalized)
    return _display_by_norm.get(n, normalized)


def find_drug_match(user_input, threshold=80):
    """
    Match a user-entered medication name against the SafeMed master list.

    Similarity is string-matching only — not medical confidence.
    """
    raw_input = str(user_input).strip()
    user_norm = _normalize(raw_input)

    empty_miss = {
        "input": raw_input,
        "matched": False,
        "drug_name": None,
        "drug_name_normalized": None,
        "score": 0,
        "match_note": MATCH_NOTE,
    }

    if not user_norm or not _search_keys:
        return empty_miss

    # Exact alias / name match
    if user_norm in _alias_to_norm:
        canonical_norm = _alias_to_norm[user_norm]
        return {
            "input": raw_input,
            "matched": True,
            "drug_name": display_name(canonical_norm),
            "drug_name_normalized": canonical_norm,
            "score": 100,
            "match_note": MATCH_NOTE,
        }

    result = process.extractOne(
        user_norm,
        _search_keys,
        scorer=fuzz.ratio,
    )

    if result is None:
        return empty_miss

    matched_key, score, _ = result
    canonical_norm = _alias_to_norm.get(matched_key, matched_key)
    rounded = round(float(score), 2)

    if rounded >= threshold:
        return {
            "input": raw_input,
            "matched": True,
            "drug_name": display_name(canonical_norm),
            "drug_name_normalized": canonical_norm,
            "score": rounded,
            "match_note": MATCH_NOTE,
        }

    return {
        "input": raw_input,
        "matched": False,
        "drug_name": None,
        "drug_name_normalized": None,
        "score": rounded,
        "match_note": MATCH_NOTE,
    }


if __name__ == "__main__":
    test_drugs = [
        "citrizine",
        "trioxsaln",
        "verteporfin",
        "doxycyclin",
        "metformn",
    ]

    print("=" * 70)
    print("SAFEMED MASTER DRUG MATCHER")
    print("=" * 70)

    for drug in test_drugs:
        result = find_drug_match(drug)
        print("\nEntered:", result["input"])
        if result["matched"]:
            print("Recognized as:", result["drug_name"])
            print("Similarity:", f"{result['score']}%")
            print(result["match_note"])
        else:
            print("No reliable match found.")
            print("Best similarity:", f"{result['score']}%")
            print(result["match_note"])
