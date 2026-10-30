# 🩺 SafeMed — Intelligent Drug Interaction Analysis

**An AI/ML-powered drug interaction analysis system designed to support safer medication combination analysis for patients with multiple medical conditions (multimorbidity).**

SafeMed is an academic project that combines machine learning, drug interaction data, clinical analysis, and external drug information to help identify potential risks associated with medication combinations.

The project aims to make medication safety analysis more accessible by bringing drug interaction checking, condition-aware assessment, and side-effect information into one system.

## 🎯 Problem Statement

Patients with multiple medical conditions often need to take several medications simultaneously. Combining medications can introduce potential drug interactions and side effects, making medication safety an important concern.

SafeMed explores how machine learning and structured drug information can be used to analyze medication combinations and highlight potential risks for further review.

## ✨ Key Features

- **Drug Interaction Analysis:** Analyze pairs of medications to identify potential interactions.
- **Machine Learning-Based Prediction:** Use trained classification models to support drug interaction analysis.
- **Condition-Aware Analysis:** Incorporate information about medical conditions when reviewing medication combinations.
- **Side-Effect Information:** Work with drug and side-effect data to provide additional context.
- **OpenFDA Integration:** Retrieve or enrich drug-related information using the OpenFDA API.
- **Clinical Analysis Engine:** Organize drug interaction and condition-related checks through dedicated analysis modules.
- **Database Integration:** Use SQLite for local data storage and application support.
- **Testing:** Include automated tests for selected machine learning and patient-consistency functionality.

## 🧠 Machine Learning Approach

SafeMed explores machine learning methods for drug interaction analysis.

The project includes:

- Logistic Regression
- Decision Tree Classification
- Model training and evaluation
- Prediction using trained model artifacts
- Evaluation metrics for assessing model performance

The prediction results are intended to support further investigation. They should not be interpreted as a definitive clinical assessment.

## 🛠️ Technology Stack

| Component | Technologies |
|---|---|
| Backend API | Python, FastAPI |
| Frontend | React.js, JavaScript |
| Machine Learning | Scikit-learn |
| Data Processing | Pandas |
| Database | SQLite |
| External Drug Information | OpenFDA API |
| Testing | Pytest |
| Version Control | Git and GitHub |

## 📂 Project Structure

```text
SafeMed/
├── analysis/
│   ├── clinical_engine.py
│   ├── openfda_client.py
│   ├── condition_checker.py
│   ├── drug_matcher.py
│   ├── ml_predictor.py
│   ├── patient_analyzer.py
│   └── side_effect_checker.py
│
├── data/
│   └── master/
│       └── enrich_with_openfda.py
│
├── ml/
│   ├── models/
│   │   └── model_evaluation_metrics.json
│   └── train_both_models.py
│
├── scripts/
│   └── run_safemed_pipeline.py
│
├── tests/
│   ├── test_ml_models.py
│   └── test_patient_consistency.py
│
├── frontend/
│
├── api.py
├── database.py
├── routes_extended.py
├── requirements.txt
├── .gitignore
└── README.md
```

*Note: The structure above highlights key project components. Additional files and directories may be present in the repository.*

## ⚙️ Getting Started

Follow these steps to run the project locally.

### Prerequisites

Install the following:

- Python and pip
- Node.js and npm
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/SohanBhangare/SafeMed.git
cd SafeMed
```

### 2. Set Up the Backend

Create a Python virtual environment.

**Windows:**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Install the backend dependencies:

```bash
pip install -r requirements.txt
```

Start the API server:

```bash
uvicorn api:app --reload
```

If the server starts successfully, the API documentation is generally available at:

`http://127.0.0.1:8000/docs`

### 3. Set Up the Frontend

Open a separate terminal:

```powershell
cd frontend
npm install
npm run dev
```

Use the local development URL displayed in your terminal to access the frontend.

### 4. Configure Data and Models

Before running the complete application, ensure that:

- The required drug datasets are available in their expected locations.
- The trained model files required by the application have been generated or obtained.
- The SQLite database is initialized as required by the project.
- Any required environment variables or API configuration are correctly set.

Follow the project's implementation and configuration files if your local setup requires additional steps.

## 🧪 Running Tests

From the project root, activate your Python virtual environment and run:

```bash
pytest
```

The test suite includes checks for selected machine learning functionality and patient-consistency logic.

## 🔬 Project Scope

SafeMed is an academic project exploring the application of machine learning and structured drug information to medication safety analysis for multimorbidity.

The system is intended to demonstrate how data-driven methods can assist in identifying potential drug interaction risks and organizing relevant information for review.

## ⚠️ Disclaimer

**SafeMed is an academic prototype, not a medical device or a substitute for professional medical advice.**

Its predictions and outputs may be incomplete or inaccurate. They must not be used independently to make medication, diagnosis, or treatment decisions.

Always consult a qualified healthcare professional or pharmacist before starting, stopping, or changing medications.

## 👨‍💻 Author

**Sohan Bhangare**

GitHub: [@SohanBhangare](https://github.com/SohanBhangare)

## 📌 Project Repository

[https://github.com/SohanBhangare/SafeMed](https://github.com/SohanBhangare/SafeMed)