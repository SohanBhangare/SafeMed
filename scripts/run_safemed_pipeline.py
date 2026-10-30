"""
SafeMed: Master End-to-End Pipeline Script
==========================================
Demonstrates the complete Clinical Decision Support System (CDSS)
and Machine Learning pipeline in a single executable script:
1. Environment & Database Initialization
2. Dataset Validation & Graph Metrics
3. Machine Learning Model Evaluation & Feature Benchmark
4. Clinical Decision Support System (CDSS) Multi-Disease Patient Simulation
5. Full Patient Risk Audit & Report Generation
"""

import os
import sys
import json
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import init_db, SessionLocal, Patient, AnalysisHistory
from analysis.ml_predictor import predict_interaction, get_evaluation_metrics, create_features
from analysis.clinical_engine import (
    analyze_multimorbidity,
    classify_interaction_severity,
    perform_clinical_risk_assessment,
    analyze_compounded_side_effects
)


def print_banner(title: str):
    print("\n" + "=" * 80)
    print(f" {title.upper()} ".center(80, "="))
    print("=" * 80)


def step_1_initialize_environment():
    print_banner("Step 1: Database & Environment Initialization")
    print("[*] Initializing SQLite clinical database...")
    init_db()
    print("[+] Database initialized successfully: safemed.db")
    print(f"[+] Python runtime: {sys.version.split()[0]} on {sys.platform}")


def step_2_ml_benchmark_evaluation():
    print_banner("Step 2: Machine Learning Model Evaluation & Benchmarks")
    metrics = get_evaluation_metrics()
    if not metrics:
        print("[!] No evaluation metrics found. Please train models first.")
        return

    lr = metrics.get("Logistic Regression", {})
    dt = metrics.get("Decision Tree", {})

    print(f"{'METRIC':<24} | {'LOGISTIC REGRESSION':<22} | {'DECISION TREE':<22}")
    print("-" * 74)
    print(f"{'Accuracy':<24} | {lr.get('accuracy', 0)*100:>20.2f}% | {dt.get('accuracy', 0)*100:>20.2f}%")
    print(f"{'Precision':<24} | {lr.get('precision', 0)*100:>20.2f}% | {dt.get('precision', 0)*100:>20.2f}%")
    print(f"{'Recall (Sensitivity)':<24} | {lr.get('recall', 0)*100:>20.2f}% | {dt.get('recall', 0)*100:>20.2f}%")
    print(f"{'F1-Score':<24} | {lr.get('f1_score', 0)*100:>20.2f}% | {dt.get('f1_score', 0)*100:>20.2f}%")
    print(f"{'ROC-AUC':<24} | {lr.get('roc_auc', 0):>21.4f} | {dt.get('roc_auc', 0):>21.4f}")
    
    lr_cm = lr.get("confusion_matrix", {})
    print("-" * 74)
    print(f"Confusion Matrix (Test Split: 14,000 samples):")
    print(f"  - Logistic Regression: TN={lr_cm.get('true_negative')}, FP={lr_cm.get('false_positive')}, FN={lr_cm.get('false_negative')}, TP={lr_cm.get('true_positive')}")
    dt_cm = dt.get("confusion_matrix", {})
    print(f"  - Decision Tree:       TN={dt_cm.get('true_negative')}, FP={dt_cm.get('false_positive')}, FN={dt_cm.get('false_negative')}, TP={dt_cm.get('true_positive')}")


def step_3_ml_inference_demonstration():
    print_banner("Step 3: Dual-Model ML Inference on Diverse Medication Pairs")
    test_pairs = [
        ("Lisinopril", "Ibuprofen", "High-Risk RAAS Inhibitor + NSAID"),
        ("Atorvastatin", "Clarithromycin", "Severe CYP3A4 Statin Toxicity"),
        ("Metformin", "Lisinopril", "Standard Diabetic Nephropathy Co-Therapy"),
        ("Amoxicillin", "Acetaminophen", "Safe Co-Prescription (Non-Interacting)"),
        ("Doxycycline", "Trioxsalen", "Independent / Unrelated Agents"),
        ("Warfarin", "Aspirin", "Antiplatelet + Anticoagulant Bleed Risk")
    ]

    print(f"{'DRUG PAIR':<30} | {'LR PROB':<10} | {'DT PROB':<10} | {'CONSENSUS STATUS':<24}")
    print("-" * 82)
    for d1, d2, note in test_pairs:
        res = predict_interaction(d1, d2)
        lr_p = f"{res['logistic_regression']['probability']*100:.1f}%"
        dt_p = f"{res['decision_tree']['probability']*100:.1f}%"
        consensus = res.get("consensus_label", "Agreed")
        pair_str = f"{d1} + {d2}"
        print(f"{pair_str:<30} | {lr_p:>10} | {dt_p:>10} | {consensus:<24}")


def step_4_clinical_patient_simulation():
    print_banner("Step 4: Clinical Multimorbidity Patient Simulation")
    patient_data = {
        "name": "John Doe",
        "mrn": "SM-2026-T2D",
        "age": 58,
        "gender": "Male",
        "conditions": ["Type 2 Diabetes", "Hypertension"],
        "medications": ["Metformin", "Lisinopril", "Ibuprofen"]
    }

    print(f"Patient Profile: {patient_data['name']} (MRN: {patient_data['mrn']}, Age: {patient_data['age']}, Gender: {patient_data['gender']})")
    print(f"Diagnosed Conditions: {', '.join(patient_data['conditions'])}")
    print(f"Current Prescriptions: {', '.join(patient_data['medications'])}")
    print("-" * 80)

    # 1. Multimorbidity Analysis
    mm_result = analyze_multimorbidity(patient_data["medications"], patient_data["conditions"])
    print(f"\n[+] Multimorbidity Complexity Score: {mm_result.get('complexity_score')}/100 ({mm_result.get('complexity_tier')})")
    print(f"[+] Documented Disease-Drug Clashes: {mm_result.get('clashes_count')}")

    for contra in mm_result.get("disease_drug_contraindications", []):
        print(f"    - CONTRAINDICATION: Condition [{contra.get('condition')}] vs Drug [{contra.get('medication')}]")
        print(f"      Severity: {contra.get('risk_level')}")
        print(f"      Mechanism: {contra.get('mechanism')}")
        print(f"      Recommendation: {contra.get('recommendation')}")

    # 2. Executive Clinical Risk Score
    interactions = [
        {
            "drug_1": "Lisinopril",
            "drug_2": "Ibuprofen",
            "severity": "Moderate",
            "effect": "NSAIDs may decrease the antihypertensive effect of ACE inhibitors and increase nephrotoxicity."
        }
    ]
    risk_assessment = perform_clinical_risk_assessment(
        medications=patient_data["medications"],
        interactions=interactions,
        multimorbidity_data=mm_result,
        patient_info={"age": patient_data["age"], "gender": patient_data["gender"]}
    )
    risk_str = risk_assessment.get("overall_risk_level", "").upper()
    overall_risk_score = (
        85 if "CRITICAL" in risk_str
        else 65 if "HIGH" in risk_str
        else 45 if "MODERATE" in risk_str
        else 15
    )
    print(f"\n[+] Executive Clinical Risk Score: {overall_risk_score}/100")
    print(f"[+] Clinical Risk Level: {risk_assessment.get('overall_risk_level')}")
    print(f"[+] Requires Urgent Clinical Review: {risk_assessment.get('requires_clinical_review')}")

    # 3. Compounded Organ Toxicities
    side_effects = [
        {"matched_drug": "Metformin", "side_effects": "hypoglycemia, lactic acidosis, gastrointestinal nausea diarrhea"},
        {"matched_drug": "Lisinopril", "side_effects": "hyperkalemia, renal impairment, dizziness, hypotension"},
        {"matched_drug": "Ibuprofen", "side_effects": "peptic ulcer, gastrointestinal bleeding, renal failure, fluid retention"}
    ]
    compounded = analyze_compounded_side_effects(side_effects)
    risks = compounded.get("compounded_risks", [])
    print(f"\n[+] Compounded Organ Systems Evaluated ({len(risks)} overlapping risks):")
    for r in risks:
        print(f"    - {r.get('organ_system'):<26}: Severity {r.get('severity'):<8} | Drugs: {', '.join(r.get('affecting_drugs', []))}")
        print(f"      Alert: {r.get('alert')}")


def main():
    start = time.time()
    print_banner("SafeMed: Clinical Decision Support System Execution")
    step_1_initialize_environment()
    step_2_ml_benchmark_evaluation()
    step_3_ml_inference_demonstration()
    step_4_clinical_patient_simulation()
    duration = time.time() - start
    print_banner(f"Execution Completed in {duration:.2f} seconds")


if __name__ == "__main__":
    main()
