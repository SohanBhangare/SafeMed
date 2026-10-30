"""
SafeMed Database & Authentication Management
SQLite database with SQLAlchemy for users, patients, analysis history, and MIMIC-IV cohort.
"""

import os
import json
import secrets
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Boolean
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session

DB_DIR = "data"
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "safemed.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ============================================================
# MODELS
# ============================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    salt = Column(String(64), nullable=False)
    full_name = Column(String(120), nullable=True)
    role = Column(String(50), default="clinician") # clinician, pharmacist, researcher
    created_at = Column(DateTime, default=datetime.utcnow)

    patients = relationship("Patient", back_populates="creator")
    analyses = relationship("AnalysisHistory", back_populates="user")


class Token(Base):
    __tablename__ = "tokens"

    token = Column(String(64), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    mrn = Column(String(64), unique=True, index=True, nullable=False) # Medical Record Number
    full_name = Column(String(120), nullable=False)
    age = Column(String(20), nullable=True)
    gender = Column(String(20), nullable=True)
    conditions = Column(Text, default="[]") # JSON list
    allergies = Column(Text, default="")
    medical_history = Column(Text, default="{}") # JSON object: pregnant, kidney_disease, etc.
    prescribed_medications = Column(Text, default="[]") # JSON list of medications
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = relationship("User", back_populates="patients")
    analyses = relationship("AnalysisHistory", back_populates="patient")


class AnalysisHistory(Base):
    __tablename__ = "analysis_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    patient_name = Column(String(120), default="")
    patient_mrn = Column(String(64), default="")
    medications = Column(Text, default="[]") # JSON list
    conditions = Column(Text, default="[]") # JSON list
    overall_risk_level = Column(String(64), default="Low")
    interactions_count = Column(Integer, default=0)
    major_count = Column(Integer, default=0)
    multimorbidity_clashes = Column(Integer, default=0)
    requires_clinical_review = Column(Boolean, default=False)
    summary_data = Column(Text, default="{}") # JSON
    full_result = Column(Text, default="{}") # JSON
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="analyses")
    patient = relationship("Patient", back_populates="analyses")


class MIMICPatient(Base):
    __tablename__ = "mimic_cohort"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, unique=True, index=True, nullable=False)
    hadm_id = Column(Integer, nullable=False)
    patient_name = Column(String(120), nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String(10), nullable=False)
    admission_type = Column(String(64), default="EMERGENCY")
    primary_diagnosis = Column(String(256), nullable=False)
    diagnoses = Column(Text, default="[]") # JSON list of {code, description, system}
    prescriptions = Column(Text, default="[]") # JSON list of {drug_name, dose, route, freq}
    clinical_notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# SECURITY & AUTH HELPERS
# ============================================================

def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return hashed.hex(), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    hashed, _ = hash_password(password, salt)
    return secrets.compare_digest(hashed, password_hash)


def create_auth_token(db: Session, user_id: int) -> str:
    token_str = secrets.token_urlsafe(32)
    token_obj = Token(token=token_str, user_id=user_id)
    db.add(token_obj)
    db.commit()
    return token_str


def get_user_by_token(db: Session, token_str: str) -> Optional[User]:
    if not token_str:
        return None
    token_obj = db.query(Token).filter(Token.token == token_str).first()
    if token_obj:
        return db.query(User).filter(User.id == token_obj.user_id).first()
    return None


# ============================================================
# SEED INITIAL DATA (DEMO USERS, PATIENTS & MIMIC-IV COHORT)
# ============================================================

def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 1. Seed Users
        if db.query(User).count() == 0:
            demo_users = [
                {
                    "username": "doctor",
                    "email": "dr.hayes@safemed-clinical.org",
                    "password": "doctor123",
                    "full_name": "Dr. Alexander Hayes, MD",
                    "role": "Chief of Clinical Pharmacology"
                },
                {
                    "username": "pharmacist",
                    "email": "e.rostova@safemed-clinical.org",
                    "password": "rx123",
                    "full_name": "Dr. Elena Rostova, PharmD",
                    "role": "Senior Clinical Pharmacist"
                },
                {
                    "username": "demo",
                    "email": "demo.user@safemed.internal",
                    "password": "demo123",
                    "full_name": "Dr. Sarah Jenkins",
                    "role": "Attending Physician"
                }
            ]
            for u in demo_users:
                pwd_hash, salt = hash_password(u["password"])
                user = User(
                    username=u["username"],
                    email=u["email"],
                    password_hash=pwd_hash,
                    salt=salt,
                    full_name=u["full_name"],
                    role=u["role"]
                )
                db.add(user)
            db.commit()
            print("[SafeMed DB] Initial demo users seeded.")

        # 2. Seed Default Clinical Patients
        if db.query(Patient).count() == 0:
            default_patients = [
                {
                    "mrn": "SM-2026-9041",
                    "full_name": "Robert M. Vance",
                    "age": "71",
                    "gender": "Male",
                    "conditions": json.dumps(["Hypertension", "Type 2 Diabetes", "Chronic Kidney Disease", "Osteoarthritis"]),
                    "allergies": "Sulfa drugs, Penicillin",
                    "medical_history": json.dumps({
                        "kidney_disease": True,
                        "liver_disease": False,
                        "pregnant": False,
                        "breastfeeding": False
                    }),
                    "prescribed_medications": json.dumps([
                        {"name": "Lisinopril", "dosage": "20mg", "frequency": "Once daily"},
                        {"name": "Metformin", "dosage": "500mg", "frequency": "Twice daily with meals"},
                        {"name": "Ibuprofen", "dosage": "400mg", "frequency": "As needed for joint pain"},
                        {"name": "Amlodipine", "dosage": "5mg", "frequency": "Once daily"}
                    ]),
                    "notes": "Patient with established stage 3 CKD complaining of persistent right knee pain."
                },
                {
                    "mrn": "SM-2026-8812",
                    "full_name": "Eleanor K. Davies",
                    "age": "67",
                    "gender": "Female",
                    "conditions": json.dumps(["Atrial Fibrillation", "Heart Failure", "Hypertension", "Depression"]),
                    "allergies": "Aspirin (GI upset)",
                    "medical_history": json.dumps({
                        "kidney_disease": False,
                        "liver_disease": False,
                        "pregnant": False,
                        "breastfeeding": False
                    }),
                    "prescribed_medications": json.dumps([
                        {"name": "Warfarin", "dosage": "5mg", "frequency": "Daily at bedtime"},
                        {"name": "Amiodarone", "dosage": "200mg", "frequency": "Once daily"},
                        {"name": "Furosemide", "dosage": "40mg", "frequency": "Every morning"},
                        {"name": "Citalopram", "dosage": "20mg", "frequency": "Once daily in the morning"}
                    ]),
                    "notes": "Cardiology outpatient with paroxysmal afib on anticoagulation."
                },
                {
                    "mrn": "SM-2026-7734",
                    "full_name": "Marcus Aurelius Thorne",
                    "age": "58",
                    "gender": "Male",
                    "conditions": json.dumps(["Asthma", "Gout", "Hypertension"]),
                    "allergies": "No known drug allergies",
                    "medical_history": json.dumps({
                        "kidney_disease": False,
                        "liver_disease": False,
                        "pregnant": False,
                        "breastfeeding": False
                    }),
                    "prescribed_medications": json.dumps([
                        {"name": "Propranolol", "dosage": "40mg", "frequency": "Twice daily"},
                        {"name": "Hydrochlorothiazide", "dosage": "25mg", "frequency": "Once daily"},
                        {"name": "Allopurinol", "dosage": "300mg", "frequency": "Daily"}
                    ]),
                    "notes": "Follow-up for blood pressure control and recurrent podagra flares."
                }
            ]
            for p in default_patients:
                pat = Patient(
                    mrn=p["mrn"],
                    full_name=p["full_name"],
                    age=p["age"],
                    gender=p["gender"],
                    conditions=p["conditions"],
                    allergies=p["allergies"],
                    medical_history=p["medical_history"],
                    prescribed_medications=p["prescribed_medications"],
                    notes=p["notes"]
                )
                db.add(pat)
            db.commit()
            print("[SafeMed DB] Initial clinical patients seeded.")

        # 3. Seed Realistic MIMIC-IV ICU Patient Cohort
        if db.query(MIMICPatient).count() == 0:
            mimic_cases = [
                {
                    "subject_id": 10002013,
                    "hadm_id": 23419082,
                    "patient_name": "MIMIC-IV Patient #10002013",
                    "age": 72,
                    "gender": "M",
                    "admission_type": "EMERGENCY (CCU)",
                    "primary_diagnosis": "Acute ST-Elevation Myocardial Infarction (STEMI)",
                    "diagnoses": json.dumps([
                        {"code": "I21.09", "description": "ST elevation (STEMI) myocardial infarction of anterior wall", "system": "ICD-10"},
                        {"code": "E11.22", "description": "Type 2 diabetes mellitus with diabetic chronic kidney disease", "system": "ICD-10"},
                        {"code": "I10", "description": "Essential (primary) hypertension", "system": "ICD-10"},
                        {"code": "E78.5", "description": "Hyperlipidemia, unspecified", "system": "ICD-10"},
                        {"code": "N18.3", "description": "Chronic kidney disease, stage 3 (moderate)", "system": "ICD-10"}
                    ]),
                    "prescriptions": json.dumps([
                        {"drug_name": "Aspirin", "dose": "81 mg", "route": "Oral", "freq": "DAILY"},
                        {"drug_name": "Clopidogrel", "dose": "75 mg", "route": "Oral", "freq": "DAILY"},
                        {"drug_name": "Lisinopril", "dose": "10 mg", "route": "Oral", "freq": "DAILY"},
                        {"drug_name": "Metformin", "dose": "500 mg", "route": "Oral", "freq": "BID"},
                        {"drug_name": "Atorvastatin", "dose": "80 mg", "route": "Oral", "freq": "QPM"},
                        {"drug_name": "Furosemide", "dose": "20 mg", "route": "IV", "freq": "DAILY"}
                    ]),
                    "clinical_notes": "72yo male admitted via ED with crushing substernal chest pain. Emergent PCI with DES to LAD. History of poorly controlled T2D and CKD stage 3."
                },
                {
                    "subject_id": 10014354,
                    "hadm_id": 26781290,
                    "patient_name": "MIMIC-IV Patient #10014354",
                    "age": 68,
                    "gender": "F",
                    "admission_type": "URGENT (MICU)",
                    "primary_diagnosis": "Acute Decompensated Heart Failure with Reduced EF",
                    "diagnoses": json.dumps([
                        {"code": "I50.23", "description": "Acute on chronic systolic (congestive) heart failure", "system": "ICD-10"},
                        {"code": "I48.91", "description": "Unspecified atrial fibrillation", "system": "ICD-10"},
                        {"code": "N18.4", "description": "Chronic kidney disease, stage 4 (severe)", "system": "ICD-10"},
                        {"code": "M17.11", "description": "Unilateral primary osteoarthritis, right knee", "system": "ICD-10"}
                    ]),
                    "prescriptions": json.dumps([
                        {"drug_name": "Warfarin", "dose": "4 mg", "route": "Oral", "freq": "QHS"},
                        {"drug_name": "Amiodarone", "dose": "200 mg", "route": "Oral", "freq": "DAILY"},
                        {"drug_name": "Digoxin", "dose": "0.125 mg", "route": "Oral", "freq": "DAILY"},
                        {"drug_name": "Spironolactone", "dose": "25 mg", "route": "Oral", "freq": "DAILY"},
                        {"drug_name": "Furosemide", "dose": "40 mg", "route": "IV", "freq": "BID"},
                        {"drug_name": "Ibuprofen", "dose": "400 mg", "route": "Oral", "freq": "PRN"}
                    ]),
                    "clinical_notes": "68yo female with biventricular heart failure admitted for fluid overload. Significant drug-drug interaction risk between Warfarin, Amiodarone, and Ibuprofen in the setting of severe CKD."
                },
                {
                    "subject_id": 10025678,
                    "hadm_id": 28910452,
                    "patient_name": "MIMIC-IV Patient #10025678",
                    "age": 54,
                    "gender": "M",
                    "admission_type": "EMERGENCY (MICU)",
                    "primary_diagnosis": "Severe Community-Acquired Pneumonia with Respiratory Failure",
                    "diagnoses": json.dumps([
                        {"code": "J18.9", "description": "Pneumonia, unspecified organism", "system": "ICD-10"},
                        {"code": "J44.1", "description": "Chronic obstructive pulmonary disease with acute exacerbation", "system": "ICD-10"},
                        {"code": "F32.9", "description": "Major depressive disorder, single episode, unspecified", "system": "ICD-10"},
                        {"code": "K25.9", "description": "Gastric ulcer, unspecified as acute or chronic, without hemorrhage", "system": "ICD-10"}
                    ]),
                    "prescriptions": json.dumps([
                        {"drug_name": "Levofloxacin", "dose": "750 mg", "route": "IV", "freq": "DAILY"},
                        {"drug_name": "Theophylline", "dose": "300 mg", "route": "Oral", "freq": "BID"},
                        {"drug_name": "Citalopram", "dose": "40 mg", "route": "Oral", "freq": "DAILY"},
                        {"drug_name": "Prednisone", "dose": "40 mg", "route": "Oral", "freq": "DAILY"},
                        {"drug_name": "Omeprazole", "dose": "20 mg", "route": "Oral", "freq": "DAILY"}
                    ]),
                    "clinical_notes": "54yo male with acute COPD exacerbation and dense right lower lobe infiltrate. Quinolone therapy (Levofloxacin) combined with Theophylline and Citalopram raises major seizure and QTc prolongation alerts."
                },
                {
                    "subject_id": 10034890,
                    "hadm_id": 21094382,
                    "patient_name": "MIMIC-IV Patient #10034890",
                    "age": 79,
                    "gender": "F",
                    "admission_type": "EMERGENCY (TSICU)",
                    "primary_diagnosis": "Urosepsis with Septic Shock",
                    "diagnoses": json.dumps([
                        {"code": "A41.9", "description": "Sepsis, unspecified organism", "system": "ICD-10"},
                        {"code": "N39.0", "description": "Urinary tract infection, site not specified", "system": "ICD-10"},
                        {"code": "E11.65", "description": "Type 2 diabetes mellitus with hyperglycemia", "system": "ICD-10"},
                        {"code": "I10", "description": "Essential hypertension", "system": "ICD-10"},
                        {"code": "F03.90", "description": "Unspecified dementia without behavioral disturbance", "system": "ICD-10"}
                    ]),
                    "prescriptions": json.dumps([
                        {"drug_name": "Ciprofloxacin", "dose": "400 mg", "route": "IV", "freq": "Q12H"},
                        {"drug_name": "Glyburide", "dose": "5 mg", "route": "Oral", "freq": "DAILY"},
                        {"drug_name": "Hydrochlorothiazide", "dose": "25 mg", "route": "Oral", "freq": "DAILY"},
                        {"drug_name": "Donepezil", "dose": "10 mg", "route": "Oral", "freq": "QHS"},
                        {"drug_name": "Alendronate", "dose": "70 mg", "route": "Oral", "freq": "QWEEK"}
                    ]),
                    "clinical_notes": "79yo female with nursing home acquired urosepsis. Polypharmacy with sulfonylurea (Glyburide) in acute illness carries severe hypoglycemia risk; Ciprofloxacin inhibits CYP1A2."
                },
                {
                    "subject_id": 10041235,
                    "hadm_id": 29871634,
                    "patient_name": "MIMIC-IV Patient #10041235",
                    "age": 61,
                    "gender": "M",
                    "admission_type": "EMERGENCY (SICU)",
                    "primary_diagnosis": "Acute Pulmonary Embolism & Decompensated Cirrhosis",
                    "diagnoses": json.dumps([
                        {"code": "I26.99", "description": "Other pulmonary embolism without acute cor pulmonale", "system": "ICD-10"},
                        {"code": "K74.60", "description": "Unspecified cirrhosis of liver", "system": "ICD-10"},
                        {"code": "M10.9", "description": "Gout, unspecified", "system": "ICD-10"},
                        {"code": "I10", "description": "Essential hypertension", "system": "ICD-10"}
                    ]),
                    "prescriptions": json.dumps([
                        {"drug_name": "Enoxaparin", "dose": "80 mg", "route": "Subcutaneous", "freq": "Q12H"},
                        {"drug_name": "Allopurinol", "dose": "100 mg", "route": "Oral", "freq": "DAILY"},
                        {"drug_name": "Propranolol", "dose": "20 mg", "route": "Oral", "freq": "BID"},
                        {"drug_name": "Spironolactone", "dose": "100 mg", "route": "Oral", "freq": "DAILY"},
                        {"drug_name": "Paracetamol", "dose": "500 mg", "route": "Oral", "freq": "PRN"}
                    ]),
                    "clinical_notes": "61yo male with segmental pulmonary emboli and Child-Pugh Class B cirrhosis with portal hypertension on prophylactic beta-blocker."
                }
            ]
            for m in mimic_cases:
                mimic_obj = MIMICPatient(
                    subject_id=m["subject_id"],
                    hadm_id=m["hadm_id"],
                    patient_name=m["patient_name"],
                    age=m["age"],
                    gender=m["gender"],
                    admission_type=m["admission_type"],
                    primary_diagnosis=m["primary_diagnosis"],
                    diagnoses=m["diagnoses"],
                    prescriptions=m["prescriptions"],
                    clinical_notes=m["clinical_notes"]
                )
                db.add(mimic_obj)
            db.commit()
            print("[SafeMed DB] Initial MIMIC-IV patient cohort seeded.")

    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
