"""
analysis/openfda_client.py
===========================
OpenFDA Drug Label API client for SafeMed.

Fetches structured drug-label information from the FDA's public API
and maps it to the SafeMed master dataset schema.

API docs : https://open.fda.gov/apis/drug/label/
Rate limit: 40 requests/minute (no API key)
             240 requests/minute (with API key — set OPENFDA_API_KEY env var)

SAFETY RULE: This module NEVER fabricates data.
             If a field is absent in the FDA label, it is left empty.
             All returned data is sourced directly from the FDA.
"""

import json
import os
import time
import requests
from typing import Any, Dict, Optional

# ============================================================
# CONFIG
# ============================================================

OPENFDA_LABEL_URL = "https://api.fda.gov/drug/label.json"

# Disk cache — persists between restarts
CACHE_PATH = "data/master/openfda_cache.json"

# Rate limiting: stay below 40 req/min without key (1.6 s gap)
#                                240 req/min with key (0.26 s gap)
_API_KEY = os.environ.get("OPENFDA_API_KEY", "")
_REQUEST_DELAY = 0.26 if _API_KEY else 1.6

# ============================================================
# DISK CACHE
# ============================================================

_cache: Dict[str, Any] = {}


def _load_cache() -> None:
    global _cache
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                _cache = json.load(f)
        except Exception:
            _cache = {}


def _save_cache() -> None:
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(_cache, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# Load cache when module is imported
_load_cache()


# ============================================================
# HTTP HELPERS
# ============================================================

def _fetch_label(search_query: str) -> Optional[Dict]:
    """
    Make a single OpenFDA request.
    Returns the first result dict, or None if not found / error.
    """
    params: Dict[str, str] = {"search": search_query, "limit": "1"}
    if _API_KEY:
        params["api_key"] = _API_KEY

    try:
        resp = requests.get(OPENFDA_LABEL_URL, params=params, timeout=10)
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            if results:
                return results[0]
        return None
    except Exception:
        return None


def _get_label_for_drug(drug_name: str) -> Optional[Dict]:
    """
    Try multiple search strategies to find the FDA label.
    Tries generic name first, then brand name.
    """
    norm = drug_name.strip().lower()

    # Strategy 1 — exact generic name
    label = _fetch_label(f"openfda.generic_name:{norm}")
    if label:
        return label

    time.sleep(_REQUEST_DELAY)

    # Strategy 2 — exact brand name
    label = _fetch_label(f"openfda.brand_name:{norm}")
    if label:
        return label

    time.sleep(_REQUEST_DELAY)

    # Strategy 3 — substance name (catches salts like "doxycycline hyclate")
    label = _fetch_label(f"openfda.substance_name:{norm}")
    return label


# ============================================================
# TEXT EXTRACTION HELPERS
# ============================================================

def _first_text(label: Dict, *keys: str) -> str:
    """
    Return the first non-empty string value from any of the given
    label keys.  OpenFDA stores most text fields as lists of strings.
    """
    for key in keys:
        val = label.get(key)
        if isinstance(val, list):
            for item in val:
                text = str(item).strip()
                if text:
                    return text
        elif isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _first_list(d: Dict, key: str) -> Optional[str]:
    """Return first item of a list field, or None."""
    vals = d.get(key, [])
    return vals[0] if vals else None


# ============================================================
# FIELD MAPPING  —  FDA label → SafeMed master schema
# ============================================================

def _map_label_to_safemed(label: Dict) -> Dict[str, Any]:
    """
    Map a raw OpenFDA label to SafeMed's nested master schema.

    Rules:
    - Only non-empty values are included in the returned dict.
    - Nothing is invented — all values come verbatim from the FDA label.
    - Long clinical_pharmacology text is used as a fallback for
      mechanism_of_action only when that specific section is absent.
    """
    openfda = label.get("openfda", {})

    # ---- mechanism of action ----
    # Older labels use "clinical_pharmacology" instead of
    # "mechanism_of_action" — extract the first sentence as a proxy.
    moa = _first_text(label, "mechanism_of_action")
    if not moa:
        cp = _first_text(label, "clinical_pharmacology")
        if cp:
            # Use only the first 600 chars so it stays readable
            moa = cp[:600].rsplit(".", 1)[0] + "." if "." in cp[:600] else cp[:600]

    result: Dict[str, Any] = {}

    # ── identity ──────────────────────────────────────────────
    gname = _first_list(openfda, "generic_name")
    if gname:
        result["generic_name_fda"] = gname

    brands = openfda.get("brand_name", [])[:5]
    if brands:
        result["brand_names_fda"] = brands

    drug_classes_fda = openfda.get("pharm_class_epc", [])[:5]
    if drug_classes_fda:
        result["drug_classes_fda"] = drug_classes_fda

    mfr = _first_list(openfda, "manufacturer_name")
    if mfr:
        result["manufacturer"] = mfr

    rxcui = openfda.get("rxcui", [])[:3]
    if rxcui:
        result["rxcui"] = rxcui

    # ── general information ────────────────────────────────────
    desc = _first_text(label, "description")
    if desc:
        result["drug_description"] = desc

    uses = _first_text(label, "indications_and_usage")
    if uses:
        result["general_uses"] = uses

    # ── pharmacology ──────────────────────────────────────────
    if moa:
        result["mechanism_of_action"] = moa

    pd_ = _first_text(label, "pharmacodynamics")
    if pd_:
        result["pharmacological_effect"] = pd_

    # ── administration ────────────────────────────────────────
    dforms = _first_text(label, "dosage_forms_and_strengths", "how_supplied")
    if dforms:
        result["dosage_forms"] = dforms

    routes = openfda.get("route", [])
    if routes:
        result["routes_of_administration"] = routes

    dosing = _first_text(label, "dosage_and_administration")
    if dosing:
        result["reference_dosing_information"] = dosing

    # ── side effects ──────────────────────────────────────────
    adverse = _first_text(label, "adverse_reactions")
    if adverse:
        result["side_effects"] = adverse

    # ── safety ────────────────────────────────────────────────
    contra = _first_text(label, "contraindications")
    if contra:
        result["contraindications"] = contra

    warn = _first_text(
        label,
        "warnings_and_precautions",
        "warnings",
        "boxed_warning",
    )
    if warn:
        result["warnings"] = warn

    prec = _first_text(label, "precautions", "general_precautions")
    if prec:
        result["precautions"] = prec

    # ── interactions ──────────────────────────────────────────
    food = _first_text(label, "food_effect")
    if food:
        result["drug_food_interactions"] = food

    ddi_text = _first_text(label, "drug_interactions")
    if ddi_text:
        result["drug_condition_interactions"] = ddi_text

    # ── special populations ───────────────────────────────────
    preg = _first_text(label, "pregnancy")
    if preg:
        result["pregnancy_information"] = preg

    bf = _first_text(label, "nursing_mothers", "lactation")
    if bf:
        result["breastfeeding_information"] = bf

    ped = _first_text(label, "pediatric_use")
    if ped:
        result["pediatric_information"] = ped

    ger = _first_text(label, "geriatric_use")
    if ger:
        result["geriatric_information"] = ger

    # ── kidney / liver ────────────────────────────────────────
    renal = _first_text(label, "renal_impairment")
    if renal:
        result["renal_information"] = renal

    hep = _first_text(label, "hepatic_impairment")
    if hep:
        result["hepatic_information"] = hep

    # ── practical ─────────────────────────────────────────────
    storage = _first_text(label, "storage_and_handling")
    if storage:
        result["storage_information"] = storage

    missed = _first_text(label, "missed_dose")
    if missed:
        result["missed_dose_information"] = missed

    # ── regulatory ────────────────────────────────────────────
    terato = _first_text(label, "teratogenic_effects")
    if terato:
        result["pregnancy_category_text"] = terato

    csa = _first_text(label, "drug_abuse_and_dependence")
    if csa:
        result["controlled_substance_information"] = csa

    # ── source metadata ───────────────────────────────────────
    app_no = _first_list(openfda, "application_number")
    if app_no:
        result["fda_application_number"] = app_no

    result["fda_source"] = "OpenFDA drug label API (open.fda.gov)"

    return result


# ============================================================
# PUBLIC API
# ============================================================

def get_fda_label_data(drug_name: str, use_cache: bool = True) -> Dict[str, Any]:
    """
    Fetch structured FDA label data for *drug_name*.

    Parameters
    ----------
    drug_name : str
        Generic or brand name of the drug.
    use_cache : bool
        If True (default), return cached result when available
        and cache new results to disk.

    Returns
    -------
    dict
        Mapped SafeMed-schema fields extracted from the FDA label.
        Empty dict if the drug is not found or the API is unavailable.

    Notes
    -----
    - Results are cached to ``data/master/openfda_cache.json``.
    - A sentinel key ``"_not_found"`` is stored for misses so we
      don't re-query the same drug repeatedly.
    - This function NEVER fabricates data.
    """
    norm = drug_name.strip().lower()

    if use_cache and norm in _cache:
        cached = _cache[norm]
        # Sentinel: we previously confirmed the drug is not on FDA
        if cached.get("_not_found"):
            return {}
        return cached

    label = _get_label_for_drug(norm)
    time.sleep(_REQUEST_DELAY)

    if not label:
        result: Dict[str, Any] = {"_not_found": True}
    else:
        result = _map_label_to_safemed(label)
        result["_found"] = True

    _cache[norm] = result
    _save_cache()

    return {} if result.get("_not_found") else result


def get_cached_fda_data(drug_name: str) -> Dict[str, Any]:
    """
    Return cached FDA data only — no live API call.
    Safe to use during web-request handlers.
    """
    norm = drug_name.strip().lower()
    cached = _cache.get(norm, {})
    if cached.get("_not_found"):
        return {}
    return {k: v for k, v in cached.items() if not k.startswith("_")}


def cache_size() -> int:
    """Return how many drugs have been cached (found + not-found)."""
    return len(_cache)


def is_cached(drug_name: str) -> bool:
    """Return True if this drug has already been queried (found or not)."""
    return drug_name.strip().lower() in _cache
