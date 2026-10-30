"""
SafeMed Extended Routes
- User Authentication (Register, Login, Me, Logout)
- Patient Profile Management (CRUD)
- MIMIC-IV Integration (Cohort browser, patient extractor, raw parser)
- Analysis History & Report Records (Save, List, Retrieve, Delete)
- ML Model Evaluation (Precision, Recall, F1, Accuracy, Confusion Matrix, ROC-AUC)
- ML Dual-Model Predictor (Logistic Regression vs Decision Tree comparison)
"""

import re
import json
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import (
    get_db, User, Token, Patient, AnalysisHistory, MIMICPatient,
    hash_password, verify_password, create_auth_token, get_user_by_token
)
from analysis.ml_predictor import predict_interaction, get_evaluation_metrics

router = APIRouter()


# ============================================================
# PYDANTIC SCHEMAS
# ============================================================

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(...)
    password: str = Field(..., min_length=4)
    full_name: Optional[str] = ""
    role: Optional[str] = "clinician" # clinician, pharmacist, researcher


class LoginRequest(BaseModel):
    username: str
    password: str


class PatientCreateUpdateRequest(BaseModel):
    mrn: Optional[str] = ""
    full_name: str
    age: Optional[str] = ""
    gender: Optional[str] = ""
    conditions: Optional[List[str]] = []
    allergies: Optional[str] = ""
    medical_history: Optional[Dict[str, Any]] = {}
    prescribed_medications: Optional[List[Dict[str, Any]]] = []
    notes: Optional[str] = ""


class SaveHistoryRequest(BaseModel):
    patient_id: Optional[int] = None
    patient_name: Optional[str] = ""
    patient_mrn: Optional[str] = ""
    medications: List[str] = []
    conditions: List[str] = []
    overall_risk_level: Optional[str] = "Low"
    interactions_count: Optional[int] = 0
    major_count: Optional[int] = 0
    multimorbidity_clashes: Optional[int] = 0
    requires_clinical_review: Optional[bool] = False
    summary_data: Optional[Dict[str, Any]] = {}
    full_result: Optional[Dict[str, Any]] = {}


class MLPredictCustomRequest(BaseModel):
    drug_1: str
    drug_2: str
    model_type: Optional[str] = "both" # both, logistic_regression, decision_tree


class MIMICExtractRequest(BaseModel):
    raw_text: Optional[str] = ""
    subject_id: Optional[int] = None


# ============================================================
# AUTH DEPENDENCY
# ============================================================

def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> Optional[User]:
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "").strip()
    return get_user_by_token(db, token)


# ============================================================
# 1. USER AUTHENTICATION
# ============================================================

@router.post("/auth/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user (clinician, pharmacist, or researcher)."""
    username_clean = req.username.strip().lower()
    email_clean = req.email.strip().lower()

    if db.query(User).filter(User.username == username_clean).first():
        raise HTTPException(status_code=400, detail="Username already registered.")
    if db.query(User).filter(User.email == email_clean).first():
        raise HTTPException(status_code=400, detail="Email already registered.")

    pwd_hash, salt = hash_password(req.password)
    new_user = User(
        username=username_clean,
        email=email_clean,
        password_hash=pwd_hash,
        salt=salt,
        full_name=req.full_name.strip() if req.full_name else req.username,
        role=req.role or "clinician"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_auth_token(db, new_user.id)
    return {
        "success": True,
        "message": "User registration successful.",
        "token": token,
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
            "full_name": new_user.full_name,
            "role": new_user.role
        }
    }


@router.post("/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate with username and password, returning a secure auth token."""
    username_clean = req.username.strip().lower()
    user = db.query(User).filter(
        (User.username == username_clean) | (User.email == username_clean)
    ).first()

    if not user or not verify_password(req.password, user.password_hash, user.salt):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    token = create_auth_token(db, user.id)
    return {
        "success": True,
        "message": "Authentication successful.",
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role
        }
    }


@router.get("/auth/me")
def get_me(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    """Get the currently logged-in user profile."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing.")
    token = authorization.replace("Bearer ", "").strip()
    user = get_user_by_token(db, token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return {
        "success": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "created_at": user.created_at.isoformat() if user.created_at else None
        }
    }


@router.post("/auth/logout")
def logout(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    """Log out and revoke current token."""
    if authorization:
        token = authorization.replace("Bearer ", "").strip()
        db.query(Token).filter(Token.token == token).delete()
        db.commit()
    return {"success": True, "message": "Successfully logged out."}


# ============================================================
# 2. PATIENT PROFILE MANAGEMENT
# ============================================================

@router.get("/patients")
def list_patients(
    q: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List all saved patient profiles with optional search query."""
    query = db.query(Patient)
    if q:
        search = f"%{q.strip()}%"
        query = query.filter((Patient.full_name.ilike(search)) | (Patient.mrn.ilike(search)))
    patients = query.order_by(Patient.updated_at.desc()).limit(limit).all()

    results = []
    for p in patients:
        try:
            conds = json.loads(p.conditions or "[]")
        except Exception:
            conds = []
        try:
            meds = json.loads(p.prescribed_medications or "[]")
        except Exception:
            meds = []
        try:
            hist = json.loads(p.medical_history or "{}")
        except Exception:
            hist = {}

        results.append({
            "id": p.id,
            "mrn": p.mrn,
            "full_name": p.full_name,
            "age": p.age,
            "gender": p.gender,
            "conditions": conds,
            "allergies": p.allergies,
            "medical_history": hist,
            "prescribed_medications": meds,
            "notes": p.notes,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None
        })

    return {
        "success": True,
        "total": len(results),
        "data": results
    }


@router.post("/patients")
def create_patient(
    req: PatientCreateUpdateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Create a new patient profile."""
    # Generate MRN if not provided
    mrn = req.mrn.strip() if req.mrn else f"SM-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    # Check MRN uniqueness
    if db.query(Patient).filter(Patient.mrn == mrn).first():
        mrn = f"{mrn}-{secrets.token_hex(2).upper()}"

    patient = Patient(
        user_id=current_user.id if current_user else None,
        mrn=mrn,
        full_name=req.full_name.strip(),
        age=req.age.strip() if req.age else "",
        gender=req.gender.strip() if req.gender else "",
        conditions=json.dumps(req.conditions or []),
        allergies=req.allergies or "",
        medical_history=json.dumps(req.medical_history or {}),
        prescribed_medications=json.dumps(req.prescribed_medications or []),
        notes=req.notes or ""
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)

    return {
        "success": True,
        "message": "Patient profile created successfully.",
        "patient": {
            "id": patient.id,
            "mrn": patient.mrn,
            "full_name": patient.full_name,
            "age": patient.age,
            "gender": patient.gender,
            "conditions": req.conditions or [],
            "allergies": patient.allergies,
            "medical_history": req.medical_history or {},
            "prescribed_medications": req.prescribed_medications or [],
            "notes": patient.notes
        }
    }


@router.get("/patients/{patient_id}")
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    """Retrieve full patient profile by ID."""
    p = db.query(Patient).filter(Patient.id == patient_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Patient profile not found.")

    return {
        "success": True,
        "patient": {
            "id": p.id,
            "mrn": p.mrn,
            "full_name": p.full_name,
            "age": p.age,
            "gender": p.gender,
            "conditions": json.loads(p.conditions or "[]"),
            "allergies": p.allergies,
            "medical_history": json.loads(p.medical_history or "{}"),
            "prescribed_medications": json.loads(p.prescribed_medications or "[]"),
            "notes": p.notes,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None
        }
    }


@router.put("/patients/{patient_id}")
def update_patient(patient_id: int, req: PatientCreateUpdateRequest, db: Session = Depends(get_db)):
    """Update an existing patient profile."""
    p = db.query(Patient).filter(Patient.id == patient_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Patient profile not found.")

    p.full_name = req.full_name.strip()
    if req.mrn:
        p.mrn = req.mrn.strip()
    p.age = req.age.strip() if req.age else ""
    p.gender = req.gender.strip() if req.gender else ""
    p.conditions = json.dumps(req.conditions or [])
    p.allergies = req.allergies or ""
    p.medical_history = json.dumps(req.medical_history or {})
    p.prescribed_medications = json.dumps(req.prescribed_medications or [])
    p.notes = req.notes or ""
    p.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(p)
    return {
        "success": True,
        "message": "Patient profile updated successfully.",
        "patient": {
            "id": p.id,
            "mrn": p.mrn,
            "full_name": p.full_name
        }
    }


@router.delete("/patients/{patient_id}")
def delete_patient(patient_id: int, db: Session = Depends(get_db)):
    """Delete a patient profile."""
    p = db.query(Patient).filter(Patient.id == patient_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Patient profile not found.")
    db.delete(p)
    db.commit()
    return {"success": True, "message": "Patient profile removed."}


# ============================================================
# 3. MIMIC-IV INTEGRATION & CLINICAL EXTRACTION
# ============================================================

@router.get("/mimic/cohort")
def get_mimic_cohort(db: Session = Depends(get_db)):
    """
    Retrieve realistic MIMIC-IV clinical inpatient admissions with diagnoses
    and medication prescriptions for clinical testing and benchmarking.
    """
    cases = db.query(MIMICPatient).order_by(MIMICPatient.subject_id).all()
    results = []
    for c in cases:
        results.append({
            "id": c.id,
            "subject_id": c.subject_id,
            "hadm_id": c.hadm_id,
            "patient_name": c.patient_name,
            "age": c.age,
            "gender": c.gender,
            "admission_type": c.admission_type,
            "primary_diagnosis": c.primary_diagnosis,
            "diagnoses": json.loads(c.diagnoses or "[]"),
            "prescriptions": json.loads(c.prescriptions or "[]"),
            "clinical_notes": c.clinical_notes
        })
    return {
        "success": True,
        "total": len(results),
        "source": "MIMIC-IV (Medical Information Mart for Intensive Care IV)",
        "cohort": results
    }


@router.get("/mimic/cohort/{subject_id}")
def get_mimic_patient(subject_id: int, db: Session = Depends(get_db)):
    """Get full clinical details for a specific MIMIC-IV patient."""
    c = db.query(MIMICPatient).filter(MIMICPatient.subject_id == subject_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="MIMIC-IV subject record not found.")

    return {
        "success": True,
        "patient": {
            "subject_id": c.subject_id,
            "hadm_id": c.hadm_id,
            "patient_name": c.patient_name,
            "age": c.age,
            "gender": c.gender,
            "admission_type": c.admission_type,
            "primary_diagnosis": c.primary_diagnosis,
            "diagnoses": json.loads(c.diagnoses or "[]"),
            "prescriptions": json.loads(c.prescriptions or "[]"),
            "clinical_notes": c.clinical_notes
        }
    }


@router.post("/mimic/extract")
def extract_mimic_data(req: MIMICExtractRequest, db: Session = Depends(get_db)):
    """
    Extract medications and clinical diagnoses from raw MIMIC-IV discharge summaries,
    structured JSON, or pasted CSV records.
    """
    # 1. If subject_id provided, extract directly from database cohort
    if req.subject_id:
        c = db.query(MIMICPatient).filter(MIMICPatient.subject_id == req.subject_id).first()
        if c:
            prescriptions = json.loads(c.prescriptions or "[]")
            diagnoses = json.loads(c.diagnoses or "[]")
            med_names = [p.get("drug_name") for p in prescriptions if p.get("drug_name")]
            cond_names = [d.get("description") for d in diagnoses if d.get("description")]

            return {
                "success": True,
                "source": f"MIMIC-IV Subject #{c.subject_id}",
                "patient_info": {
                    "mrn": f"MIMIC-{c.subject_id}",
                    "name": c.patient_name,
                    "age": str(c.age),
                    "gender": "Male" if c.gender.upper() == "M" else "Female",
                    "primary_diagnosis": c.primary_diagnosis
                },
                "extracted_medications": med_names,
                "medication_details": [
                    {"name": p.get("drug_name"), "dosage": p.get("dose", ""), "frequency": p.get("freq", "")}
                    for p in prescriptions
                ],
                "extracted_conditions": cond_names,
                "icd_diagnoses": diagnoses
            }

    # 2. Parse raw text
    text = req.raw_text or ""
    extracted_meds = []
    med_details = []
    extracted_conds = []

    # Known common drug keywords to search in free text
    drug_pattern = re.compile(
        r'\b(aspirin|clopidogrel|lisinopril|metformin|atorvastatin|furosemide|warfarin|amiodarone|'
        r'digoxin|spironolactone|ibuprofen|levofloxacin|theophylline|citalopram|prednisone|'
        r'omeprazole|ciprofloxacin|glyburide|hydrochlorothiazide|donepezil|alendronate|'
        r'enoxaparin|allopurinol|propranolol|paracetamol|acetaminophen|amlodipine|metoprolol|'
        r'losartan|gabapentin|pantoprazole|simvastatin|sertraline|tramadol|diazepam|lorazepam)\b',
        re.IGNORECASE
    )

    found_drugs = set()
    for match in drug_pattern.finditer(text):
        drug_name = match.group(1).capitalize()
        if drug_name.lower() not in found_drugs:
            found_drugs.add(drug_name.lower())
            extracted_meds.append(drug_name)
            med_details.append({"name": drug_name, "dosage": "", "frequency": ""})

    # Search for conditions / ICD descriptions
    cond_pattern = re.compile(
        r'\b(hypertension|diabetes|myocardial infarction|heart failure|chronic kidney disease|'
        r'atrial fibrillation|copd|asthma|depression|gastritis|ulcer|sepsis|hyperlipidemia|'
        r'osteoarthritis|cirrhosis|gout|pneumonia)\b',
        re.IGNORECASE
    )

    found_conds = set()
    for match in cond_pattern.finditer(text):
        cond_name = match.group(1).title()
        if cond_name.lower() not in found_conds:
            found_conds.add(cond_name.lower())
            extracted_conds.append(cond_name)

    return {
        "success": True,
        "source": "Raw MIMIC-IV Text Extraction",
        "extracted_medications": extracted_meds,
        "medication_details": med_details,
        "extracted_conditions": extracted_conds,
        "raw_character_count": len(text)
    }


# ============================================================
# 4. ANALYSIS HISTORY & SECURE DATABASE MANAGEMENT
# ============================================================

@router.get("/history")
def get_analysis_history(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Retrieve historical analysis reports and safety audits."""
    records = db.query(AnalysisHistory).order_by(AnalysisHistory.created_at.desc()).limit(limit).all()
    results = []
    for r in records:
        results.append({
            "id": r.id,
            "patient_id": r.patient_id,
            "patient_name": r.patient_name,
            "patient_mrn": r.patient_mrn,
            "medications": json.loads(r.medications or "[]"),
            "conditions": json.loads(r.conditions or "[]"),
            "overall_risk_level": r.overall_risk_level,
            "interactions_count": r.interactions_count,
            "major_count": r.major_count,
            "multimorbidity_clashes": r.multimorbidity_clashes,
            "requires_clinical_review": r.requires_clinical_review,
            "summary_data": json.loads(r.summary_data or "{}"),
            "created_at": r.created_at.isoformat() if r.created_at else None
        })
    return {
        "success": True,
        "total": len(results),
        "history": results
    }


@router.get("/history/{history_id}")
def get_single_history(history_id: int, db: Session = Depends(get_db)):
    """Retrieve complete stored report data for a specific historical audit."""
    r = db.query(AnalysisHistory).filter(AnalysisHistory.id == history_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="History record not found.")

    return {
        "success": True,
        "record": {
            "id": r.id,
            "patient_id": r.patient_id,
            "patient_name": r.patient_name,
            "patient_mrn": r.patient_mrn,
            "medications": json.loads(r.medications or "[]"),
            "conditions": json.loads(r.conditions or "[]"),
            "overall_risk_level": r.overall_risk_level,
            "interactions_count": r.interactions_count,
            "major_count": r.major_count,
            "multimorbidity_clashes": r.multimorbidity_clashes,
            "requires_clinical_review": r.requires_clinical_review,
            "summary_data": json.loads(r.summary_data or "{}"),
            "full_result": json.loads(r.full_result or "{}"),
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
    }


@router.delete("/history/{history_id}")
def delete_history_item(history_id: int, db: Session = Depends(get_db)):
    """Delete an analysis history item."""
    r = db.query(AnalysisHistory).filter(AnalysisHistory.id == history_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="History record not found.")
    db.delete(r)
    db.commit()
    return {"success": True, "message": "History record deleted."}


@router.post("/history/save")
def save_analysis_history(
    req: SaveHistoryRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Explicitly save an analysis report to the database."""
    history_obj = AnalysisHistory(
        user_id=current_user.id if current_user else None,
        patient_id=req.patient_id,
        patient_name=req.patient_name or "Anonymous Patient",
        patient_mrn=req.patient_mrn or "",
        medications=json.dumps(req.medications),
        conditions=json.dumps(req.conditions),
        overall_risk_level=req.overall_risk_level or "Low",
        interactions_count=req.interactions_count or 0,
        major_count=req.major_count or 0,
        multimorbidity_clashes=req.multimorbidity_clashes or 0,
        requires_clinical_review=bool(req.requires_clinical_review),
        summary_data=json.dumps(req.summary_data or {}),
        full_result=json.dumps(req.full_result or {})
    )
    db.add(history_obj)
    db.commit()
    db.refresh(history_obj)

    return {
        "success": True,
        "message": "Analysis history saved successfully.",
        "history_id": history_obj.id
    }


# ============================================================
# 5. MACHINE LEARNING MODEL EVALUATION & DUAL PREDICTOR
# ============================================================

@router.get("/ml/evaluation")
def get_ml_model_evaluation():
    """
    Return comprehensive model evaluation metrics for both
    Logistic Regression and Decision Tree models, including Precision,
    Recall, F1-Score, Accuracy, Confusion Matrix, and ROC-AUC.
    """
    metrics = get_evaluation_metrics()
    sample_counts = metrics.get("Logistic Regression", {}).get("sample_counts", {})
    train_sz = sample_counts.get("train_size", 56000)
    test_sz = sample_counts.get("test_size", 14000)
    total_sz = train_sz + test_sz
    return {
        "success": True,
        "dataset_name": "SafeMed DDI Feature Benchmark Dataset",
        "sample_size": total_sz,
        "models_evaluated": ["Logistic Regression", "Decision Tree"],
        "metrics": metrics,
        "note": f"Evaluation performed on a held-out 20% stratified test split ({test_sz:,} medication pairs)."
    }


@router.post("/ml/predict")
def predict_pair_custom(req: MLPredictCustomRequest):
    """
    Run machine learning interaction prediction on any pair of drugs
    using both Logistic Regression and Decision Tree models.
    """
    d1 = req.drug_1.strip().lower()
    d2 = req.drug_2.strip().lower()

    if not d1 or not d2:
        raise HTTPException(status_code=400, detail="Both drug names are required.")

    result = predict_interaction(d1, d2)
    return {
        "success": True,
        "drug_1": d1,
        "drug_2": d2,
        "result": result
    }
