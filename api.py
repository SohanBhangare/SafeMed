from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import math
import json
import pandas as pd
from itertools import combinations
from rapidfuzz import fuzz, process as rfprocess

# OpenFDA cache lookup (cache-only — no live calls during requests)
try:
    from analysis.openfda_client import get_cached_fda_data as _get_fda_cache
    _fda_available = True
except Exception:
    _get_fda_cache = lambda _: {}   # type: ignore
    _fda_available = False



# =========================================================
# SAFE MED API
# =========================================================

app = FastAPI(
    title="SafeMed API",
    description="Safe Medical Combination Analysis for Multimorbidity Patients",
    version="2.1.0"
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Extended SafeMed modules: database, clinical engine, and extended routes
from database import init_db, SessionLocal, AnalysisHistory
from analysis.clinical_engine import (
    classify_interaction_severity,
    analyze_multimorbidity,
    perform_clinical_risk_assessment,
    analyze_compounded_side_effects
)
from routes_extended import router as extended_router
from analysis.ml_predictor import predict_interaction, get_evaluation_metrics

app.include_router(extended_router)

@app.on_event("startup")
def startup_event():
    init_db()


# =========================================================
# LOAD DATASETS (once at startup)
# =========================================================

# Existing cleaned drugs CSV (used for analyze endpoint)
try:
    _drugs_df = pd.read_csv("data/cleaned/drugs_cleaned.csv")
    _drugs_df["drug_name_normalized"] = (
        _drugs_df["drug_name"]
        .fillna("")
        .astype(str)
        .str.lower()
        .str.strip()
    )
except Exception:
    _drugs_df = pd.DataFrame()

# Master dataset JSON (structured, one record per drug)
_master_records: List[Dict] = []
_master_index:   Dict[str, Dict] = {}   # normalized_name -> record
_alias_index:    Dict[str, str] = {}    # alias / brand / generic -> normalized_name

try:
    with open("data/master/safemed_drug_master.json", "r", encoding="utf-8") as _f:
        _master_records = json.load(_f)
    _master_index = {
        r["drug_name_normalized"]: r
        for r in _master_records
        if r.get("drug_name_normalized")
    }
    _alias_index: Dict[str, str] = {}
    for r in _master_records:
        norm = r.get("drug_name_normalized")
        if not norm:
            continue
        _alias_index[norm] = norm
        identity = r.get("identity", {})
        gn = str(identity.get("generic_name") or "").strip().lower()
        if gn:
            _alias_index.setdefault(gn, norm)
        for b in (identity.get("normalized_brand_names") or identity.get("brand_names") or []):
            bn = str(b).strip().lower()
            if bn:
                _alias_index.setdefault(bn, norm)
    print(f"[SafeMed] Master dataset loaded: {len(_master_index):,} drugs")
except Exception as _e:
    print(f"[SafeMed] Master dataset not found or failed to load: {_e}")
    _master_records = []
    _master_index = {}
    _alias_index = {}

# Master sources CSV
_sources_df: pd.DataFrame = pd.DataFrame()
try:
    _sources_df = pd.read_csv(
        "data/master/safemed_drug_sources.csv",
        dtype=str,
        keep_default_na=False
    )
except Exception:
    pass

# DDI dataset (for drug-specific interaction lookup)
_ddi_df: pd.DataFrame = pd.DataFrame()
try:
    _ddi_df = pd.read_csv("data/cleaned/drug_interactions_cleaned.csv")
except Exception:
    pass



# =========================================================
# REQUEST MODEL
# =========================================================

class MedicationDetail(BaseModel):
    name: str
    dosage: Optional[str] = ""
    frequency: Optional[str] = ""


class PatientRequest(BaseModel):
    medications: List[str] = Field(...)
    conditions: List[str] = Field(default=[])
    age: Optional[str] = Field(default="")
    gender: Optional[str] = Field(default="")
    allergies: Optional[str] = Field(default="")
    medication_details: Optional[List[MedicationDetail]] = Field(default=[])
    # Medical History flags — optional, used only to surface relevant reference info
    pregnant: Optional[bool] = Field(default=False)
    breastfeeding: Optional[bool] = Field(default=False)
    kidney_disease: Optional[bool] = Field(default=False)
    liver_disease: Optional[bool] = Field(default=False)
    # Database linkage & history tracking
    patient_id: Optional[int] = Field(default=None)
    patient_mrn: Optional[str] = Field(default="")
    patient_name: Optional[str] = Field(default="")
    save_to_history: Optional[bool] = Field(default=True)


# =========================================================
# JSON CLEANER
# =========================================================

def clean_for_json(data):

    if isinstance(data, dict):
        return {
            key: clean_for_json(value)
            for key, value in data.items()
        }

    if isinstance(data, list):
        return [
            clean_for_json(value)
            for value in data
        ]

    if isinstance(data, float):

        if not math.isfinite(data):
            return None

        return data

    # Convert numpy/pandas types to Python native
    try:
        if hasattr(data, 'item'):
            return data.item()
    except Exception:
        pass

    return data


# =========================================================
# GET MEDICATION DETAILS FROM MASTER DATASET
# =========================================================

def get_medication_detail(drug_name: str) -> Dict[str, Any]:
    """
    Look up structured medication information from the master dataset.
    If the OpenFDA cache has been populated (via the batch enrichment
    script), also merges any richer FDA fields into empty master slots
    — cache-only, no live API calls during a user request.
    Returns both a legacy flat view (for existing UI) and the full
    grouped master record.
    """
    if not drug_name:
        return {}

    key = str(drug_name).strip().lower()
    record = _master_index.get(key)

    if not record:
        matched_key, score = _fuzzy_find_drug(key, threshold=90)
        if matched_key:
            record = _master_index.get(matched_key)

    if not record:
        return {}

    # ── Merge OpenFDA cache (if available) into empty master fields ──
    # We work on a shallow copy of the record so we don't mutate
    # the in-memory master index permanently at runtime.
    if _fda_available:
        fda = _get_fda_cache(drug_name)
        if fda:
            import copy
            record = copy.deepcopy(record)
            _fda_field_map = [
                ("pharmacology",        "mechanism_of_action",           "mechanism_of_action"),
                ("pharmacology",        "pharmacological_effect",        "pharmacological_effect"),
                ("general_information", "drug_description",              "drug_description"),
                ("general_information", "general_uses",                  "general_uses"),
                ("administration",      "dosage_forms",                  "dosage_forms"),
                ("administration",      "routes_of_administration",      "routes_of_administration"),
                ("administration",      "reference_dosing_information",  "reference_dosing_information"),
                ("side_effects",        "side_effects",                  "side_effects"),
                ("safety",              "contraindications",             "contraindications"),
                ("safety",             "warnings",                      "warnings"),
                ("safety",             "precautions",                   "precautions"),
                ("interactions",        "drug_food_interactions",        "drug_food_interactions"),
                ("interactions",        "drug_condition_interactions",   "drug_condition_interactions"),
                ("special_populations", "pregnancy_information",         "pregnancy_information"),
                ("special_populations", "breastfeeding_information",     "breastfeeding_information"),
                ("special_populations", "pediatric_information",         "pediatric_information"),
                ("special_populations", "geriatric_information",         "geriatric_information"),
                ("kidney_liver",        "renal_information",             "renal_information"),
                ("kidney_liver",        "hepatic_information",           "hepatic_information"),
                ("practical",           "storage_information",           "storage_information"),
                ("practical",           "missed_dose_information",       "missed_dose_information"),
                ("regulatory",          "controlled_substance_information","controlled_substance_information"),
            ]
            for section, master_field, fda_key in _fda_field_map:
                fda_val = fda.get(fda_key)
                if not fda_val:
                    continue
                if section not in record:
                    record[section] = {}
                existing = record[section].get(master_field)
                if not existing:
                    record[section][master_field] = fda_val
            # Mark that FDA enrichment was applied
            record["fda_enriched"] = bool(fda)

    identity = record.get("identity", {})
    general = record.get("general_information", {})
    se = record.get("side_effects", {})
    interact = record.get("interactions", {})
    reg = record.get("regulatory", {})
    quality = record.get("data_quality", {})
    sources = record.get("sources", {})
    related = record.get("related", {})

    classes = identity.get("drug_classes") or []
    if isinstance(classes, list):
        classes_str = "; ".join(classes)
    else:
        classes_str = str(classes)

    related_names = []
    for item in related.get("related_drugs") or []:
        if isinstance(item, dict) and item.get("name"):
            related_names.append(item["name"])
        elif isinstance(item, str):
            related_names.append(item)

    missing = quality.get("missing_information_fields") or []

    return {
        "generic_name": identity.get("generic_name") or None,
        "drug_classes": classes_str or None,
        "associated_conditions": (general.get("medical_conditions") or [])[:8],
        "condition_descriptions": (general.get("medical_condition_description") or [])[:3],
        "rx_otc": reg.get("rx_otc") or None,
        "alcohol": interact.get("drug_alcohol_interactions") or None,
        "related_drugs": ", ".join(related_names[:10]) if related_names else None,
        "drug_link": None,
        "brand_names": identity.get("brand_names") or [],
        "side_effects": se.get("side_effects") or "",
        "pregnancy_category": reg.get("pregnancy_category") or "",
        "controlled_substance_information": reg.get("controlled_substance_information") or "",
        "data_completeness_score": record.get("data_completeness_score", 0),
        "missing_information_fields": missing,
        "primary_source": sources.get("primary_source") or "SafeMed reference dataset",
        "in_ddi_dataset": record.get("in_ddi_dataset", False),
        "information_available": record.get("information_available", False),
        "fda_enriched": record.get("fda_enriched", False),
        "master": record,
    }



# =========================================================
# BUILD ALL MEDICATION PAIRS
# =========================================================

def build_all_pairs(matched_medications: list, interactions: list) -> list:
    """
    Build a list of all possible medication pairs and indicate
    whether each has a documented interaction in the reference dataset.
    """

    drug_names = []
    for item in matched_medications:
        if isinstance(item, dict):
            name = (
                item.get("drug_name")
                or item.get("matched")
                or item.get("name")
            )
            if name:
                drug_names.append(name)
        elif isinstance(item, str):
            drug_names.append(item)

    # Deduplicate
    unique_drugs = []
    seen = set()
    for d in drug_names:
        key = d.lower().strip()
        if key not in seen:
            seen.add(key)
            unique_drugs.append(d)

    interaction_pairs = set()
    for i in interactions:
        d1 = str(i.get("drug_1", "")).lower().strip()
        d2 = str(i.get("drug_2", "")).lower().strip()
        pair = "||".join(sorted([d1, d2]))
        interaction_pairs.add(pair)

    all_pairs = []

    for d1, d2 in combinations(unique_drugs, 2):
        pair_key = "||".join(sorted([
            d1.lower().strip(),
            d2.lower().strip()
        ]))

        has_interaction = pair_key in interaction_pairs

        # Find description if interaction exists
        description = None
        if has_interaction:
            for i in interactions:
                id1 = str(i.get("drug_1", "")).lower().strip()
                id2 = str(i.get("drug_2", "")).lower().strip()
                if "||".join(sorted([id1, id2])) == pair_key:
                    description = i.get("description")
                    break

        severity_info = {}
        if has_interaction:
            severity_info = classify_interaction_severity(d1, d2, description)

        ml_res = predict_interaction(d1, d2)

        all_pairs.append({
            "drug_1": d1,
            "drug_2": d2,
            "interaction_found": has_interaction,
            "description": description,
            "severity": severity_info.get("severity", "No Documented Interaction" if not has_interaction else "Minor"),
            "severity_level": severity_info.get("severity_level", 0 if not has_interaction else 1),
            "color": severity_info.get("color", "#9ca3af" if not has_interaction else "#2563eb"),
            "clinical_rationale": severity_info.get("clinical_rationale"),
            "action": severity_info.get("action"),
            "ml_prediction": ml_res.get("prediction", 0),
            "ml_probability": ml_res.get("probability", 0.5),
            "ml_consensus": ml_res.get("consensus", True),
            "decision_tree": ml_res.get("decision_tree", {}),
            "logistic_regression": ml_res.get("logistic_regression", {}),
        })

    return all_pairs


# =========================================================
# BUILD INFORMATION GAPS
# =========================================================

def build_information_gaps(
    medications_input: list,
    matched_medications: list,
    unmatched_medications: list,
    side_effect_analysis: list,
    matched_conditions: list,
    unmatched_conditions: list,
    interactions: list,
    medication_details_map: dict,
) -> list:
    """
    Derive an honest list of information gaps from the analysis results.
    """

    gaps = []

    # Unrecognized medications
    for item in unmatched_medications:
        name = item.get("input", item) if isinstance(item, dict) else str(item)
        gaps.append(
            f"'{name}' could not be matched to the reference dataset. "
            f"No interaction, side-effect, or condition information is available for this entry."
        )

    # No side-effect information
    for item in side_effect_analysis:
        drug = item.get("matched_drug") or item.get("input", "")
        effects = item.get("side_effects")
        if not effects:
            gaps.append(
                f"No side-effect information was available for '{drug}' "
                f"in the current reference dataset."
            )

    # Medications with missing master fields
    for item in matched_medications:
        if isinstance(item, dict):
            name = item.get("drug_name") or item.get("name") or ""
        else:
            name = str(item)
        if not name:
            continue
        detail = medication_details_map.get(name.lower().strip(), {})
        missing = detail.get("missing_information_fields") or []
        notable = [
            f for f in missing
            if f in {
                "mechanism_of_action", "warnings", "contraindications",
                "pregnancy_information", "renal_information",
                "hepatic_information", "storage_information",
            }
        ]
        if notable:
            labels = ", ".join(f.replace("_", " ") for f in notable)
            gaps.append(
                f"For '{name}', the following is not available in the current "
                f"SafeMed reference data: {labels}."
            )
        elif name and name.lower() not in medication_details_map:
            gaps.append(
                f"Additional medication information (drug class, generic name, "
                f"condition association) was not available for '{name}' in the "
                f"master reference dataset."
            )

    # Unmatched conditions
    for item in unmatched_conditions:
        name = item.get("input", item) if isinstance(item, dict) else str(item)
        gaps.append(
            f"The condition '{name}' was not found in the current reference dataset."
        )

    # No interactions possible (only 1 medication)
    if len(matched_medications) == 1:
        gaps.append(
            "Only one medication was entered. "
            "Drug-drug interaction analysis requires at least two medications."
        )

    # Dataset does not provide severity labels
    if interactions:
        gaps.append(
            "The reference dataset does not provide validated clinical severity "
            "labels for documented interactions. Severity classification is not available."
        )

    # Always note dataset scope
    gaps.append(
        "The application's reference datasets may not include every medication, "
        "condition, or interaction. A missing result does not confirm clinical safety."
    )

    return gaps


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {
        "message": "SafeMed API is running",
        "version": "2.1.0",
        "status": "active",
        "master_drugs_loaded": len(_master_index),
    }


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():

    return {
        "status": "healthy"
    }


# =========================================================
# ANALYZE PATIENT
# =========================================================

@app.post("/analyze")
def analyze(request: PatientRequest):

    if not request.medications:

        return {
            "success": False,
            "message": "At least one medication is required."
        }

    # -------------------------------------------------------
    # Core analysis
    # -------------------------------------------------------

    from analysis.patient_analyzer import analyze_patient

    result = analyze_patient(
        request.medications,
        request.conditions
    )

    med_analysis = result.get("medication_analysis", {})
    condition_analysis = result.get("condition_analysis", {})
    side_effect_analysis = result.get("side_effect_analysis", [])
    ml_predictions = result.get("ml_predictions", [])

    matched_medications = med_analysis.get("matched_medications", [])
    unmatched_medications = med_analysis.get("unmatched_medications", [])
    interactions = med_analysis.get("interactions", [])
    matched_conditions = condition_analysis.get("matched_conditions", [])
    unmatched_conditions = condition_analysis.get("unmatched_conditions", [])

    # -------------------------------------------------------
    # Enrich: medication details from drugs dataset
    # -------------------------------------------------------

    medication_details_map = {}

    for item in matched_medications:

        if isinstance(item, dict):
            name = item.get("drug_name") or item.get("name") or ""
        else:
            name = str(item)

        if name:
            key = name.lower().strip()
            if key not in medication_details_map:
                detail = get_medication_detail(name)
                if detail:
                    medication_details_map[key] = detail

    # -------------------------------------------------------
    # Enrich: Interaction Clinical Severity Classification
    # -------------------------------------------------------
    enriched_interactions = []
    major_count = 0
    moderate_count = 0
    minor_count = 0

    for i in interactions:
        d1 = i.get("drug_1", "")
        d2 = i.get("drug_2", "")
        desc = i.get("description", "")
        sev = classify_interaction_severity(d1, d2, desc)
        enriched_item = {**i, **sev}
        if sev.get("severity") == "Major":
            major_count += 1
        elif sev.get("severity") == "Moderate":
            moderate_count += 1
        else:
            minor_count += 1
        enriched_interactions.append(enriched_item)

    # -------------------------------------------------------
    # Build all medication pairs (with severity and ML predictions)
    # -------------------------------------------------------

    all_pairs = build_all_pairs(matched_medications, enriched_interactions)

    # -------------------------------------------------------
    # Multimorbidity Cross-Analysis
    # -------------------------------------------------------
    multimorbidity_analysis = analyze_multimorbidity(
        medications=request.medications,
        conditions=request.conditions,
        medical_history={
            "pregnant": bool(request.pregnant),
            "breastfeeding": bool(request.breastfeeding),
            "kidney_disease": bool(request.kidney_disease),
            "liver_disease": bool(request.liver_disease),
        }
    )

    # -------------------------------------------------------
    # Patient info passthrough
    # -------------------------------------------------------

    patient_info = {
        "patient_id": request.patient_id,
        "patient_mrn": request.patient_mrn or "",
        "patient_name": request.patient_name or "Clinical Patient",
        "age": request.age or "",
        "gender": request.gender or "",
        "allergies": request.allergies or "",
        "medication_details": [
            {
                "name": md.name,
                "dosage": md.dosage or "",
                "frequency": md.frequency or "",
            }
            for md in (request.medication_details or [])
        ],
        "medical_history": {
            "pregnant": bool(request.pregnant),
            "breastfeeding": bool(request.breastfeeding),
            "kidney_disease": bool(request.kidney_disease),
            "liver_disease": bool(request.liver_disease),
        },
    }

    # -------------------------------------------------------
    # Clinical Risk Assessment & Clinical Review Flags
    # -------------------------------------------------------
    risk_assessment = perform_clinical_risk_assessment(
        medications=request.medications,
        interactions=enriched_interactions,
        multimorbidity_data=multimorbidity_analysis,
        patient_info=patient_info
    )

    # -------------------------------------------------------
    # Compounded Side Effects & Organ Toxicity Analysis
    # -------------------------------------------------------
    compounded_side_effects = analyze_compounded_side_effects(side_effect_analysis)

    # -------------------------------------------------------
    # Build information gaps
    # -------------------------------------------------------

    information_gaps = build_information_gaps(
        medications_input=request.medications,
        matched_medications=matched_medications,
        unmatched_medications=unmatched_medications,
        side_effect_analysis=side_effect_analysis,
        matched_conditions=matched_conditions,
        unmatched_conditions=unmatched_conditions,
        interactions=enriched_interactions,
        medication_details_map=medication_details_map,
    )

    # -------------------------------------------------------
    # Safety Warnings & Medical Disclaimer
    # -------------------------------------------------------
    safety_warnings = {
        "disclaimer_title": "Professional Clinical Review Required",
        "disclaimer_text": (
            "SafeMed provides assistive pharmacological and machine learning insights "
            "based on reference biomedical datasets. This software does NOT provide medical "
            "diagnosis or replace personalized clinical judgment by a licensed medical "
            "practitioner. All interactions, contraindications, and clinical review flags "
            "must be independently reviewed and verified prior to dispensing or administering medication."
        ),
        "requires_clinical_review": risk_assessment.get("requires_clinical_review", False),
        "regulatory_status": "Non-diagnostic Clinical Decision Support System (CDSS) for Investigational & Educational Use",
        "actionable_guidance": "Consult full drug monographs and patient organ function panels (renal/hepatic) before altering dosage regimens."
    }

    # -------------------------------------------------------
    # Structured summary
    # -------------------------------------------------------

    total_entered = len(request.medications)
    total_matched = len(matched_medications)
    total_interactions = len(enriched_interactions)
    total_conditions_entered = len(request.conditions)
    total_conditions_matched = len(matched_conditions)

    side_with_info = sum(
        1 for s in side_effect_analysis
        if s.get("side_effects")
    )

    summary = {
        "medications_entered": total_entered,
        "medications_matched": total_matched,
        "medications_unmatched": len(unmatched_medications),
        "interactions_found": total_interactions,
        "major_interactions": major_count,
        "moderate_interactions": moderate_count,
        "minor_interactions": minor_count,
        "possible_pairs": len(all_pairs),
        "conditions_entered": total_conditions_entered,
        "conditions_matched": total_conditions_matched,
        "side_effects_available": side_with_info,
        "information_gaps_count": len(information_gaps),
        "number_of_medications": total_matched,
        "number_of_interactions": total_interactions,
        "number_of_conditions": total_conditions_entered,
        "number_of_ml_predictions": len(ml_predictions),
        "overall_risk_level": risk_assessment.get("overall_risk_level", "Low"),
        "risk_badge": risk_assessment.get("risk_badge", "Low Risk"),
        "overall_risk_color": risk_assessment.get("overall_risk_color", "#16a34a"),
        "requires_clinical_review": risk_assessment.get("requires_clinical_review", False),
        "review_flags_count": risk_assessment.get("review_flags_count", 0),
        "multimorbidity_clashes": multimorbidity_analysis.get("clashes_count", 0),
        "complexity_score": multimorbidity_analysis.get("complexity_score", 0),
        "complexity_tier": multimorbidity_analysis.get("complexity_tier", "Manageable Complexity"),
        "compounded_risks_count": compounded_side_effects.get("compounded_risks_count", 0),
    }

    # -------------------------------------------------------
    # Final response
    # -------------------------------------------------------

    response_data = {
        "patient_info": patient_info,
        "summary": summary,
        "medication_analysis": {
            **med_analysis,
            "interactions": enriched_interactions,
            "all_pairs": all_pairs,
        },
        "medication_details": medication_details_map,
        "condition_analysis": condition_analysis,
        "side_effect_analysis": side_effect_analysis,
        "compounded_side_effects": compounded_side_effects,
        "multimorbidity_analysis": multimorbidity_analysis,
        "risk_assessment": risk_assessment,
        "ml_predictions": ml_predictions,
        "information_gaps": information_gaps,
        "safety_warnings": safety_warnings,
        # Extended canonical fields for dashboard & PDF report consistency
        "clinical_risk": {
            **risk_assessment,
            "risk_level": (
                "CRITICAL" if "CRITICAL" in risk_assessment.get("overall_risk_level", "").upper()
                else "HIGH" if "HIGH" in risk_assessment.get("overall_risk_level", "").upper()
                else "MODERATE" if "MODERATE" in risk_assessment.get("overall_risk_level", "").upper()
                else "LOW"
            ),
            "overall_risk_score": (
                85 if "CRITICAL" in risk_assessment.get("overall_risk_level", "").upper()
                else 65 if "HIGH" in risk_assessment.get("overall_risk_level", "").upper()
                else 45 if "MODERATE" in risk_assessment.get("overall_risk_level", "").upper()
                else 15
            ),
            "high_priority_flags": risk_assessment.get("review_flags", []),
        },
        "multimorbidity": {
            **multimorbidity_analysis,
            "contraindications": [
                {
                    **c,
                    "contraindicated_drug": c.get("medication"),
                    "severity": c.get("risk_level"),
                }
                for c in multimorbidity_analysis.get("disease_drug_contraindications", [])
            ],
            "polypharmacy_alert": multimorbidity_analysis.get("is_polypharmacy", False),
        },
        "compounded_toxicities": [
            {
                "system": r.get("organ_system"),
                "severity": r.get("severity"),
                "drugs": r.get("affecting_drugs", []),
                "concerns": r.get("alert"),
            }
            for r in compounded_side_effects.get("compounded_risks", [])
        ],
    }

    # -------------------------------------------------------
    # Save to Database History (if requested)
    # -------------------------------------------------------
    saved_history_id = None
    if request.save_to_history:
        try:
            db_session = SessionLocal()
            hist_record = AnalysisHistory(
                patient_id=request.patient_id,
                patient_name=patient_info.get("patient_name") or "Clinical Patient",
                patient_mrn=patient_info.get("patient_mrn") or "",
                medications=json.dumps(request.medications),
                conditions=json.dumps(request.conditions),
                overall_risk_level=risk_assessment.get("overall_risk_level", "Low"),
                interactions_count=total_interactions,
                major_count=major_count,
                multimorbidity_clashes=multimorbidity_analysis.get("clashes_count", 0),
                requires_clinical_review=bool(risk_assessment.get("requires_clinical_review")),
                summary_data=json.dumps(summary),
                full_result=json.dumps(clean_for_json(response_data)),
            )
            db_session.add(hist_record)
            db_session.commit()
            saved_history_id = hist_record.id
            db_session.close()
        except Exception as _db_err:
            print(f"[SafeMed DB] Failed to auto-save history: {_db_err}")

    response_data["history_id"] = saved_history_id
    response_data = clean_for_json(response_data)

    return {
        "success": True,
        "data": response_data
    }


# =========================================================
# MASTER DATASET — HELPERS
# =========================================================

def _fuzzy_find_drug(query: str, threshold: int = 75):
    """
    Find the best matching drug in the master index using fuzzy matching.
    Returns (normalized_name, score) or (None, 0) if below threshold.
    """
    if not query or not _master_index:
        return None, 0

    norm_q = query.strip().lower()

    if norm_q in _master_index:
        return norm_q, 100

    if "_alias_index" in globals() and norm_q in _alias_index:
        return _alias_index[norm_q], 100

    candidates = list(_alias_index.keys()) if "_alias_index" in globals() and _alias_index else list(_master_index.keys())
    result = rfprocess.extractOne(
        norm_q,
        candidates,
        scorer=fuzz.ratio,
        score_cutoff=threshold,
    )
    if result:
        matched_alias = result[0]
        canonical = _alias_index.get(matched_alias, matched_alias) if "_alias_index" in globals() else matched_alias
        return canonical, result[1]
    return None, 0


def _get_drug_sources(drug_name: str) -> list:
    """Return source records for a given drug name from the sources table."""
    if _sources_df.empty:
        return []
    norm = drug_name.strip().lower()
    rows = _sources_df[
        _sources_df["drug_name"].str.lower().str.strip() == norm
    ]
    return rows.to_dict(orient="records")


def _get_drug_interactions(drug_name: str) -> list:
    """Return all DDI records involving this drug."""
    if _ddi_df.empty:
        return []
    norm = drug_name.strip().lower()
    mask = (
        (_ddi_df["drug_1_normalized"].str.lower().str.strip() == norm) |
        (_ddi_df["drug_2_normalized"].str.lower().str.strip() == norm)
    )
    rows = _ddi_df[mask].copy()
    return [
        {
            "drug_1": str(r.get("drug_1", "")),
            "drug_2": str(r.get("drug_2", "")),
            "interaction_description": str(r.get("interaction_description", "")),
        }
        for _, r in rows.iterrows()
    ]


def _master_summary(record: dict) -> dict:
    """Return a lightweight summary for list views."""
    identity = record.get("identity", {})
    general  = record.get("general_information", {})
    reg      = record.get("regulatory", {})
    quality  = record.get("data_quality", {})
    return {
        "drug_name":              record.get("drug_name", ""),
        "drug_name_normalized":   record.get("drug_name_normalized", ""),
        "generic_name":           identity.get("generic_name", ""),
        "drug_classes":           identity.get("drug_classes", []),
        "medical_conditions":     general.get("medical_conditions", []),
        "rx_otc":                 reg.get("rx_otc", ""),
        "data_completeness_score":record.get("data_completeness_score", 0),
        "in_ddi_dataset":         record.get("in_ddi_dataset", False),
        "information_available":  record.get("information_available", True),
    }


# =========================================================
# GET /drugs  — list all drugs (summary only, paginated)
# =========================================================

@app.get("/drugs")
def list_drugs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    drug_class: Optional[str] = Query(default=None),
    rx_otc: Optional[str] = Query(default=None),
):
    """
    Return a paginated list of all drugs in the master dataset.
    Optionally filter by drug_class or rx_otc.
    """
    if not _master_records:
        return {
            "success": True,
            "total": 0,
            "page": page,
            "page_size": page_size,
            "data": [],
        }

    records = _master_records

    # Filter by drug_class
    if drug_class:
        dc_lower = drug_class.strip().lower()
        records = [
            r for r in records
            if any(
                dc_lower in cls.lower()
                for cls in r.get("identity", {}).get("drug_classes", [])
            )
        ]

    # Filter by rx_otc
    if rx_otc:
        rx_lower = rx_otc.strip().lower()
        records = [
            r for r in records
            if r.get("regulatory", {}).get("rx_otc", "").lower() == rx_lower
        ]

    total = len(records)
    start = (page - 1) * page_size
    end   = start + page_size
    page_records = records[start:end]

    return {
        "success":   True,
        "total":     total,
        "page":      page,
        "page_size": page_size,
        "data":      [_master_summary(r) for r in page_records],
    }


# =========================================================
# GET /search/drugs  — fuzzy search across the master dataset
# =========================================================

@app.get("/search/drugs")
def search_drugs(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    threshold: int = Query(default=70, ge=50, le=100),
):
    """
    Fuzzy search for drugs by name in the master dataset.
    Returns matches with similarity scores.

    NOTE: Similarity % is text-matching similarity, not medical confidence.
    """
    if not _master_index:
        return {"success": True, "query": q, "results": []}

    norm_q = q.strip().lower()
    candidates = list(_alias_index.keys()) if _alias_index else list(_master_index.keys())

    raw_results = rfprocess.extract(
        norm_q,
        candidates,
        scorer=fuzz.ratio,
        limit=limit * 3,
        score_cutoff=threshold,
    )

    results = []
    seen = set()
    for match_name, score, _ in raw_results:
        canonical = _alias_index.get(match_name, match_name)
        if canonical in seen:
            continue
        seen.add(canonical)
        record = _master_index.get(canonical)
        if not record:
            continue
        summary = _master_summary(record)
        summary["match_score"] = round(score, 1)
        summary["match_note"] = (
            "This percentage represents text-matching similarity, "
            "not medical confidence."
        )
        results.append(summary)
        if len(results) >= limit:
            break

    results.sort(key=lambda x: x["match_score"], reverse=True)

    return {
        "success":   True,
        "query":     q,
        "threshold": threshold,
        "results":   results,
    }


# =========================================================
# GET /drug/{drug_name}  — full drug detail from master dataset
# =========================================================

@app.get("/drug/{drug_name}")
def get_drug(drug_name: str, threshold: int = Query(default=75, ge=50, le=100)):
    """
    Return full structured medication information for a given drug.
    Uses fuzzy matching. All fields come from the master dataset only.
    """
    matched_key, score = _fuzzy_find_drug(drug_name, threshold=threshold)

    if not matched_key:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "query": drug_name,
                "message": (
                    f"No drug matching '{drug_name}' was found in the master dataset "
                    f"(threshold: {threshold}%). "
                    "The medication may not be in the current reference data."
                ),
            },
        )

    record = _master_index[matched_key]

    return {
        "success": True,
        "query": drug_name,
        "matched_name": record.get("drug_name", ""),
        "match_score": round(score, 1),
        "match_note": (
            "This percentage represents text-matching similarity, "
            "not medical confidence."
        )
        if score < 100
        else None,
        "data": record,
    }


# =========================================================
# GET /drug/{drug_name}/interactions  — DDI records for a drug
# =========================================================

@app.get("/drug/{drug_name}/interactions")
def get_drug_interactions(
    drug_name: str,
    threshold: int = Query(default=75, ge=50, le=100),
    limit: int = Query(default=50, ge=1, le=500),
):
    """
    Return all documented drug-drug interactions for a given drug
    from the DDI reference dataset.
    """
    matched_key, score = _fuzzy_find_drug(drug_name, threshold=threshold)

    if not matched_key:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "query": drug_name,
                "message": f"No drug matching '{drug_name}' found in master dataset.",
            },
        )

    record = _master_index[matched_key]
    matched_name = record.get("drug_name", matched_key)

    interactions = _get_drug_interactions(matched_key)

    return {
        "success":      True,
        "query":        drug_name,
        "matched_name": matched_name,
        "match_score":  round(score, 1),
        "in_ddi_dataset": record.get("in_ddi_dataset", False),
        "total_interactions": len(interactions),
        "interactions": interactions[:limit],
        "note": (
            "Drug-drug interactions are sourced from the SafeMed DDI reference dataset. "
            "This dataset does not provide clinical severity labels."
        ),
        "disclaimer": (
            "This information is for reference only. Consult a qualified healthcare "
            "professional for any medication-related decisions."
        ),
    }


# =========================================================
# GET /drug/{drug_name}/sources  — source provenance for a drug
# =========================================================

@app.get("/drug/{drug_name}/sources")
def get_drug_sources(
    drug_name: str,
    threshold: int = Query(default=75, ge=50, le=100),
):
    """
    Return source provenance records for a given drug.
    """
    matched_key, score = _fuzzy_find_drug(drug_name, threshold=threshold)

    if not matched_key:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "query": drug_name,
                "message": f"No drug matching '{drug_name}' found in master dataset.",
            },
        )

    record = _master_index[matched_key]
    matched_name = record.get("drug_name", matched_key)
    sources = _get_drug_sources(matched_name)

    return {
        "success":        True,
        "query":          drug_name,
        "matched_name":   matched_name,
        "match_score":    round(score, 1),
        "source_records": sources,
        "primary_source": record.get("sources", {}).get("primary_source", ""),
        "last_verified":  record.get("sources", {}).get("last_verified", ""),
        "data_version":   record.get("sources", {}).get("data_version", ""),
    }