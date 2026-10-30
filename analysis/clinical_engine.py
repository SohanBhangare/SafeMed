"""
SafeMed Clinical Engine
- Multimorbidity Disease-Drug Interaction Analysis
- Clinical Severity Classification (Major, Moderate, Minor)
- Clinical Review Flags & Comprehensive Risk Assessment
- Compounded Side Effects & Organ Toxicity Burden
"""

from typing import List, Dict, Any, Optional

# ============================================================
# CLINICAL SEVERITY RULES & TAXONOMY
# ============================================================

# High-risk pharmacological keywords indicating MAJOR severity
MAJOR_KEYWORDS = [
    "fatal", "death", "life-threatening", "hemorrhage", "bleeding", "cardiac arrest",
    "torsade", "qt prolongation", "arrhythmia", "ventricular", "lactic acidosis",
    "serotonin syndrome", "respiratory depression", "rhabdomyolysis", "nephrotoxicity",
    "hepatotoxicity", "hypoglycemia", "hyperkalemia", "anaphylaxis", "toxicity",
    "contraindicated", "avoid concomitant", "severe hypotens", "convulsion", "seizure"
]

MODERATE_KEYWORDS = [
    "increase concentration", "decrease concentration", "decrease clearance",
    "increase bioavailability", "decrease metabolism", "potentiate", "inhibit",
    "monitor", "dosage adjustment", "blood pressure", "therapeutic effect",
    "decreased excretion", "bioavailability", "drowsiness", "hypotension",
    "bradycardia", "efficacy"
]

# Established high-risk medication classes for severity tagging
ANTICOAGULANTS_ANTIPLATELETS = {
    "warfarin", "aspirin", "clopidogrel", "apixaban", "rivaroxaban", "dabigatran",
    "edoxaban", "heparin", "enoxaparin", "ticagrelor", "prasugrel"
}

NSAIDS = {
    "ibuprofen", "naproxen", "diclofenac", "indomethacin", "meloxicam", "celecoxib",
    "ketorolac", "etodolac", "piroxicam", "aspirin"
}

QT_PROLONGING_DRUGS = {
    "amiodarone", "sotalol", "citalopram", "escitalopram", "levofloxacin", "ciprofloxacin",
    "azithromycin", "haloperidol", "ondansetron", "methadone", "quinidine", "erythromycin"
}

CNS_DEPRESSANTS = {
    "diazepam", "lorazepam", "alprazolam", "clonazepam", "morphine", "oxycodone",
    "fentanyl", "tramadol", "codeine", "zolpidem", "gabapentin", "pregabalin"
}

RENAL_RAAS_DRUGS = {
    "lisinopril", "enalapril", "ramipril", "losartan", "valsartan", "candesartan",
    "spironolactone", "eplerenone", "triamterene"
}


def classify_interaction_severity(drug1: str, drug2: str, description: Optional[str] = None) -> Dict[str, Any]:
    """
    Classify the clinical severity of a drug-drug interaction
    into Major (High), Moderate, or Minor based on established
    clinical pharmacology evidence and text analysis.
    """
    d1 = drug1.strip().lower()
    d2 = drug2.strip().lower()
    desc_lower = (description or "").lower()

    # Rule 1: Anticoagulant + NSAID / Antiplatelet -> MAJOR (Bleeding Risk)
    if (d1 in ANTICOAGULANTS_ANTIPLATELETS and d2 in NSAIDS) or (d2 in ANTICOAGULANTS_ANTIPLATELETS and d1 in NSAIDS):
        return {
            "severity": "Major",
            "severity_level": 3,
            "color": "#dc2626", # Red
            "clinical_rationale": "High risk of severe gastrointestinal hemorrhage and bleeding events due to combined platelet inhibition and mucosal injury.",
            "requires_review": True,
            "action": "Avoid combination if possible; if necessary, prescribe co-gastroprotection (PPI) and monitor INR/hemoglobin closely."
        }

    # Rule 2: Dual QT Prolonging Drugs -> MAJOR (Torsades de Pointes)
    if d1 in QT_PROLONGING_DRUGS and d2 in QT_PROLONGING_DRUGS:
        return {
            "severity": "Major",
            "severity_level": 3,
            "color": "#dc2626",
            "clinical_rationale": "Additive QT interval prolongation significantly elevates risk of lethal ventricular arrhythmia (Torsades de Pointes).",
            "requires_review": True,
            "action": "Avoid concurrent use. Obtain baseline and serial ECG; monitor serum potassium and magnesium."
        }

    # Rule 3: Dual CNS / Opioid + Benzodiazepine -> MAJOR (Respiratory Depression)
    if d1 in CNS_DEPRESSANTS and d2 in CNS_DEPRESSANTS:
        return {
            "severity": "Major",
            "severity_level": 3,
            "color": "#dc2626",
            "clinical_rationale": "Synergistic central nervous system depression leading to profound sedation, respiratory arrest, and coma.",
            "requires_review": True,
            "action": "Limit dosages and duration. Prescribe naloxone and monitor respiratory status closely."
        }

    # Rule 4: RAAS Inhibitor + Potassium-Sparing Diuretic -> MODERATE / MAJOR (Hyperkalemia)
    if d1 in RENAL_RAAS_DRUGS and d2 in RENAL_RAAS_DRUGS and ("spironolactone" in [d1, d2] or "eplerenone" in [d1, d2]):
        return {
            "severity": "Major",
            "severity_level": 3,
            "color": "#dc2626",
            "clinical_rationale": "High risk of severe life-threatening hyperkalemia and acute kidney impairment.",
            "requires_review": True,
            "action": "Regularly check serum potassium and renal function (eGFR/creatinine) within 1-2 weeks of initiation."
        }

    # Rule 5: Keyword-based clinical classification
    if any(kw in desc_lower for kw in MAJOR_KEYWORDS):
        return {
            "severity": "Major",
            "severity_level": 3,
            "color": "#dc2626",
            "clinical_rationale": "Interaction description highlights serious clinical risks such as toxicity, hemorrhage, severe arrhythmias, or organ damage.",
            "requires_review": True,
            "action": "Requires prompt clinical review and medication reconciliation prior to administration."
        }

    if any(kw in desc_lower for kw in MODERATE_KEYWORDS) or desc_lower:
        return {
            "severity": "Moderate",
            "severity_level": 2,
            "color": "#d97706", # Amber / Orange
            "clinical_rationale": "May alter therapeutic serum concentration or therapeutic efficacy requiring dose titration or clinical monitoring.",
            "requires_review": False,
            "action": "Monitor clinical response and consider therapeutic drug monitoring or dose optimization."
        }

    # Minor / Reference
    return {
        "severity": "Minor",
        "severity_level": 1,
        "color": "#2563eb", # Blue
        "clinical_rationale": "Interaction documented with mild or minimal clinical significance under standard clinical monitoring.",
        "requires_review": False,
        "action": "Inform patient and continue standard observation."
    }


# ============================================================
# MULTIMORBIDITY & DISEASE-DRUG CONTRAINDICATIONS
# ============================================================

DISEASE_CONTRAINDICATION_RULES = [
    {
        "disease_keywords": ["asthma", "copd", "bronchospasm", "reactive airway"],
        "drug_keywords": ["propranolol", "carvedilol", "nadolol", "timolol", "labetalol", "sotalol", "aspirin", "ibuprofen"],
        "condition_name": "Asthma / COPD",
        "risk_level": "High",
        "mechanism": "Non-selective beta-blockade can trigger severe, potentially fatal bronchospasm. NSAIDs may induce aspirin-exacerbated respiratory disease (AERD).",
        "recommendation": "Use cardioselective beta-1 blockers (e.g. Metoprolol, Bisoprolol) with caution if essential; avoid non-selective agents and NSAIDs if aspirin-sensitive."
    },
    {
        "disease_keywords": ["chronic kidney disease", "ckd", "renal failure", "nephropathy", "renal impairment", "kidney failure"],
        "drug_keywords": ["ibuprofen", "naproxen", "diclofenac", "ketorolac", "meloxicam", "metformin", "gentamicin", "spironolactone"],
        "condition_name": "Chronic Kidney Disease",
        "risk_level": "Critical",
        "mechanism": "NSAIDs inhibit renal prostaglandins causing acute hemodynamically-mediated kidney injury and fluid retention. Metformin accumulates in eGFR < 30 ml/min causing fatal lactic acidosis.",
        "recommendation": "Avoid NSAIDs; substitute paracetamol for pain. Review eGFR before Metformin dosing (contraindicated if eGFR < 30 mL/min). Monitor potassium."
    },
    {
        "disease_keywords": ["heart failure", "chf", "congestive heart failure", "cardiomyopathy"],
        "drug_keywords": ["ibuprofen", "naproxen", "diclofenac", "pioglitazone", "rosiglitazone", "diltiazem", "verapamil"],
        "condition_name": "Heart Failure",
        "risk_level": "High",
        "mechanism": "NSAIDs promote sodium and water retention and blunt diuretics/ACE inhibitors. Non-dihydropyridine CCBs exert negative inotropic effects worsening systolic heart failure.",
        "recommendation": "Avoid NSAIDs and thiazolidinediones. Prefer dihydropyridine CCBs (Amlodipine) if calcium blockade is indicated."
    },
    {
        "disease_keywords": ["hypertension", "high blood pressure"],
        "drug_keywords": ["pseudoephedrine", "phenylephrine", "ibuprofen", "naproxen", "prednisone", "methylprednisolone", "dexamethasone"],
        "condition_name": "Hypertension",
        "risk_level": "Moderate",
        "mechanism": "Sympathomimetics cause peripheral vasoconstriction. NSAIDs cause salt/water retention and counteract ACE-inhibitors and ARBs.",
        "recommendation": "Avoid oral decongestants and chronic NSAIDs. Monitor blood pressure frequently during steroid therapy."
    },
    {
        "disease_keywords": ["diabetes", "type 2 diabetes", "type 1 diabetes", "hyperglycemia"],
        "drug_keywords": ["prednisone", "methylprednisolone", "dexamethasone", "hydrochlorothiazide", "propranolol"],
        "condition_name": "Diabetes Mellitus",
        "risk_level": "Moderate",
        "mechanism": "Corticosteroids induce significant hepatic gluconeogenesis and peripheral insulin resistance. Beta-blockers can mask symptoms of hypoglycemia (except sweating).",
        "recommendation": "Intensify blood glucose monitoring during systemic steroid use. Educate patient on hypoglycemia recognition."
    },
    {
        "disease_keywords": ["peptic ulcer", "gerd", "gastritis", "gi bleed", "gastrointestinal hemorrhage"],
        "drug_keywords": ["ibuprofen", "naproxen", "aspirin", "prednisone", "meloxicam", "citalopram", "sertraline"],
        "condition_name": "Peptic Ulcer / GI Bleed History",
        "risk_level": "High",
        "mechanism": "NSAIDs and corticosteroids degrade protective gastric mucosa. Concurrent SSRIs impair platelet aggregation, compounding gastrointestinal bleeding risk.",
        "recommendation": "Avoid NSAIDs. If antithrombotic therapy is strictly required, co-prescribe a proton pump inhibitor (e.g. Pantoprazole)."
    },
    {
        "disease_keywords": ["liver disease", "cirrhosis", "hepatitis", "hepatic impairment"],
        "drug_keywords": ["paracetamol", "acetaminophen", "methotrexate", "valproate", "amiodarone", "diazepam"],
        "condition_name": "Liver Disease / Cirrhosis",
        "risk_level": "High",
        "mechanism": "Reduced hepatic metabolic clearance increases drug accumulation. High doses of paracetamol or sedatives can precipitate hepatic encephalopathy or fulminant hepatotoxicity.",
        "recommendation": "Cap paracetamol at <= 2g/day in liver disease; avoid sedatives and monitor baseline liver function tests (ALT, AST, Bilirubin)."
    },
    {
        "disease_keywords": ["glaucoma"],
        "drug_keywords": ["amitriptyline", "diphenhydramine", "atropine", "oxybutynin", "prednisone"],
        "condition_name": "Glaucoma",
        "risk_level": "High",
        "mechanism": "Anticholinergic mydriasis can precipitate acute angle-closure glaucoma. Ophthalmic and systemic steroids can increase intraocular pressure.",
        "recommendation": "Avoid potent systemic anticholinergics and monitor intraocular pressure during corticosteroid administration."
    },
    {
        "disease_keywords": ["gout", "hyperuricemia"],
        "drug_keywords": ["hydrochlorothiazide", "furosemide", "aspirin"],
        "condition_name": "Gout",
        "risk_level": "Moderate",
        "mechanism": "Thiazide and loop diuretics competitively inhibit renal tubular uric acid excretion, precipitating acute gout flares.",
        "recommendation": "Monitor serum urate levels; adjust allopurinol/febuxostat or consider losartan as an antihypertensive with mild uricosuric properties."
    }
]


def analyze_multimorbidity(medications: List[str], conditions: List[str], medical_history: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Perform deep multimorbidity cross-analysis evaluating interactions
    between prescribed medications and patient's multiple diagnosed medical conditions.
    """
    meds_clean = [str(m).strip().lower() for m in medications if str(m).strip()]
    conds_clean = [str(c).strip().lower() for c in conditions if str(c).strip()]
    
    # Merge medical history flags into conditions
    history = medical_history or {}
    if history.get("kidney_disease") and not any("kidney" in c for c in conds_clean):
        conds_clean.append("chronic kidney disease")
    if history.get("liver_disease") and not any("liver" in c for c in conds_clean):
        conds_clean.append("liver disease")

    clashes = []
    
    for rule in DISEASE_CONTRAINDICATION_RULES:
        # Check if patient has matching condition
        matched_disease = None
        for disease_kw in rule["disease_keywords"]:
            for patient_cond in conds_clean:
                if disease_kw in patient_cond:
                    matched_disease = patient_cond
                    break
            if matched_disease:
                break
                
        if not matched_disease:
            continue
            
        # Check if patient is taking conflicting medication
        for drug in meds_clean:
            for drug_kw in rule["drug_keywords"]:
                if drug_kw in drug:
                    clashes.append({
                        "condition": rule["condition_name"],
                        "matched_condition_input": matched_disease,
                        "medication": drug,
                        "risk_level": rule["risk_level"],
                        "mechanism": rule["mechanism"],
                        "recommendation": rule["recommendation"]
                    })
                    break

    # Calculate Multimorbidity Burden Index
    # Based on condition count, polypharmacy count, and disease-drug clashes
    polypharmacy_count = len(meds_clean)
    condition_count = len(conds_clean)
    
    complexity_score = min(100, (condition_count * 12) + (polypharmacy_count * 8) + (len(clashes) * 18))
    
    if complexity_score >= 70:
        complexity_tier = "Severe Multimorbidity Complexity"
        complexity_color = "#dc2626"
    elif complexity_score >= 40:
        complexity_tier = "Moderate Multimorbidity Complexity"
        complexity_color = "#d97706"
    else:
        complexity_tier = "Manageable Complexity"
        complexity_color = "#16a34a"

    return {
        "disease_drug_contraindications": clashes,
        "clashes_count": len(clashes),
        "condition_count": condition_count,
        "medication_count": polypharmacy_count,
        "complexity_score": complexity_score,
        "complexity_tier": complexity_tier,
        "complexity_color": complexity_color,
        "is_polypharmacy": polypharmacy_count >= 5,
        "is_multimorbid": condition_count >= 2
    }


# ============================================================
# CLINICAL RISK ASSESSMENT & ACTIONABLE FLAGS
# ============================================================

def perform_clinical_risk_assessment(
    medications: List[str],
    interactions: List[Dict[str, Any]],
    multimorbidity_data: Dict[str, Any],
    patient_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Synthesize all clinical findings into an overarching Clinical Risk Assessment
    flagging combinations that require urgent clinical review before dispensing.
    """
    patient_info = patient_info or {}
    age_str = str(patient_info.get("age") or "")
    try:
        age = int(age_str)
    except Exception:
        age = None
        
    medical_history = patient_info.get("medical_history") or {}
    pregnant = bool(medical_history.get("pregnant"))
    breastfeeding = bool(medical_history.get("breastfeeding"))
    kidney_disease = bool(medical_history.get("kidney_disease"))
    liver_disease = bool(medical_history.get("liver_disease"))

    review_flags = []
    
    # 1. Major Interaction Check
    major_interactions = [i for i in interactions if i.get("severity") == "Major"]
    if major_interactions:
        for mi in major_interactions:
            review_flags.append({
                "type": "Major Drug-Drug Interaction",
                "priority": "Critical",
                "title": f"Major Interaction: {mi.get('drug_1', '').title()} + {mi.get('drug_2', '').title()}",
                "detail": mi.get("clinical_rationale") or mi.get("description", "High risk of adverse clinical outcome."),
                "action": mi.get("action", "Clinical consultation recommended before co-administration.")
            })

    # 2. Disease-Drug Contraindication Check
    contraindications = multimorbidity_data.get("disease_drug_contraindications") or []
    for c in contraindications:
        if c.get("risk_level") in ["Critical", "High"]:
            review_flags.append({
                "type": "Disease-Drug Contraindication",
                "priority": "Critical" if c.get("risk_level") == "Critical" else "High",
                "title": f"Contraindication: {c.get('medication', '').title()} in {c.get('condition')}",
                "detail": c.get("mechanism"),
                "action": c.get("recommendation")
            })

    # 3. Geriatric / Polypharmacy Vulnerability (Age >= 65)
    if age and age >= 65:
        if len(medications) >= 5:
            review_flags.append({
                "type": "Geriatric Polypharmacy Alert",
                "priority": "High",
                "title": f"Senior Polypharmacy Alert (Age {age}, {len(medications)} Medications)",
                "detail": "Patient is elderly taking >= 5 concurrent medications. High susceptibility to adverse drug reactions, fall risk, and metabolic changes.",
                "action": "Conduct a formal medication deprescribing audit using Beers Criteria guidelines."
            })

    # 4. Pregnancy / Breastfeeding
    if pregnant:
        review_flags.append({
            "type": "Special Population Alert: Pregnancy",
            "priority": "Critical",
            "title": "Pregnancy Status Confirmed",
            "detail": "Prescribed regimens require rigorous teratogenicity screening across trimesters.",
            "action": "Verify FDA Pregnancy risk category for each prescribed drug before dispensing."
        })
    if breastfeeding:
        review_flags.append({
            "type": "Special Population Alert: Lactation",
            "priority": "High",
            "title": "Lactation Status Confirmed",
            "detail": "Maternal medications may excrete into breast milk and affect infant development.",
            "action": "Cross-reference infant safety profile and relative infant dose."
        })

    # 5. Organ Toxicity Warning
    if kidney_disease and any(m in ["ibuprofen", "naproxen", "diclofenac", "gentamicin"] for m in medications):
        review_flags.append({
            "type": "Nephrotoxic Risk Alert",
            "priority": "Critical",
            "title": "Nephrotoxic Agent in Documented Kidney Disease",
            "detail": "Patient with established renal disease prescribed potentially nephrotoxic medication.",
            "action": "Order baseline creatinine / BUN and substitute renal-sparing alternative."
        })

    # Overall Risk Level Calculation
    critical_count = sum(1 for f in review_flags if f["priority"] == "Critical")
    high_count = sum(1 for f in review_flags if f["priority"] == "High")
    
    if critical_count > 0:
        overall_risk_level = "CRITICAL - CLINICAL REVIEW REQUIRED"
        overall_risk_color = "#dc2626"
        badge = "Critical Risk"
    elif high_count > 0 or len(interactions) >= 3:
        overall_risk_level = "HIGH RISK - CLINICAL REVIEW RECOMMENDED"
        overall_risk_color = "#ea580c"
        badge = "High Risk"
    elif len(interactions) > 0 or len(contraindications) > 0:
        overall_risk_level = "MODERATE RISK - MONITORING ADVISED"
        overall_risk_color = "#d97706"
        badge = "Moderate Risk"
    else:
        overall_risk_level = "LOW RISK - STANDARD CARE"
        overall_risk_color = "#16a34a"
        badge = "Low Risk"

    return {
        "overall_risk_level": overall_risk_level,
        "overall_risk_color": overall_risk_color,
        "risk_badge": badge,
        "requires_clinical_review": len(review_flags) > 0,
        "review_flags_count": len(review_flags),
        "review_flags": review_flags,
        "patient_demographics_summary": {
            "age": age_str or "Not specified",
            "gender": patient_info.get("gender") or "Not specified",
            "special_conditions": [
                k.replace("_", " ").title()
                for k, v in medical_history.items() if v
            ]
        }
    }


# ============================================================
# COMPOUNDED SIDE EFFECTS & ORGAN TOXICITY ANALYSIS
# ============================================================

ORGAN_SYSTEM_MAPPING = {
    "Cardiovascular": ["arrhythmia", "tachycardia", "bradycardia", "chest pain", "hypertension", "hypotension", "palpitation", "edema", "qtc"],
    "Renal & Electrolyte": ["kidney", "nephro", "creatinine", "hyperkalemia", "hypokalemia", "urinary", "renal failure"],
    "Gastrointestinal": ["nausea", "vomiting", "diarrhea", "constipation", "abdominal pain", "ulcer", "gi bleed", "dyspepsia", "gastritis"],
    "Central Nervous System": ["dizziness", "headache", "somnolence", "insomnia", "seizure", "confusion", "tremor", "sedation", "depression"],
    "Hepatic": ["jaundice", "hepatitis", "elevated liver enzymes", "alt", "ast", "liver injury", "hepatic"],
    "Hematologic / Bleeding": ["bleeding", "bruising", "anemia", "thrombocytopenia", "hemorrhage", "leukopenia"]
}


def analyze_compounded_side_effects(side_effect_analysis: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Examine side effects across all prescribed medications and detect
    cumulative/overlapping toxicities affecting common organ systems.
    """
    organ_impacts: Dict[str, List[str]] = {system: [] for system in ORGAN_SYSTEM_MAPPING}
    
    for item in side_effect_analysis:
        drug_name = item.get("matched_drug") or item.get("input") or "Medication"
        side_effects_text = str(item.get("side_effects") or "").lower()
        
        for system, keywords in ORGAN_SYSTEM_MAPPING.items():
            if any(kw in side_effects_text for kw in keywords):
                if drug_name not in organ_impacts[system]:
                    organ_impacts[system].append(drug_name)

    # Filter organ systems with 2 or more overlapping medications
    compounded_risks = []
    for system, drugs in organ_impacts.items():
        if len(drugs) >= 2:
            compounded_risks.append({
                "organ_system": system,
                "affecting_drugs": drugs,
                "drug_count": len(drugs),
                "severity": "High" if len(drugs) >= 3 or system in ["Cardiovascular", "Renal & Electrolyte"] else "Moderate",
                "alert": f"Additive {system.lower()} toxicity risk: {len(drugs)} medications ({', '.join(drugs)}) may compound adverse effects on this system."
            })

    return {
        "organ_impacts": {k: v for k, v in organ_impacts.items() if v},
        "compounded_risks": compounded_risks,
        "compounded_risks_count": len(compounded_risks)
    }
