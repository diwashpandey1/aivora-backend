# Spam Detector Backend

Production-style FastAPI backend for AI-powered spam detection across SMS and
email content. The backend trains separate Scikit-learn models for SMS and
email, auto-detects the input type, stores anonymous browser-level scan history
in MongoDB, and returns chart-ready analytics JSON for the React frontend.

## Structure

```text
backend-python/
  app.py
  src/
    routes/        FastAPI routers
    services/      prediction, history, analytics service layer
    database/      MongoDB connection and repository abstraction
    schemas/       Pydantic request/response contracts
    ml/            preprocessing, type detection, training scripts
    utils/         logging helpers
  dataset/
    sms_spam/
    email_spam/
    processed/
  models_saved/
    sms/
    email/
  logs/
```

## Setup

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Update `.env` with your MongoDB URI if it is not running at
`mongodb://localhost:27017`.

## Train Models

```powershell
python -m src.ml.train --domain all
```

This command:

- preprocesses SMS and email datasets into `dataset/processed/`
- trains separate SMS and email classifiers
- compares `MultinomialNB`, `LogisticRegression`, and calibrated `LinearSVC`
- saves the best model bundles in `models_saved/`
- trains the lightweight SMS/email type detector

## Run API

```powershell
uvicorn app:app --reload
```

API: http://localhost:8000
Docs: http://localhost:8000/docs

## Routes

- `POST /analyze`
- `GET /history/{client_id}`
- `DELETE /history/{client_id}`
- `GET /stats`
- `GET /health`

## Analyze Contract

```json
{
  "message": "sample message",
  "client_id": "browser_unique_id"
}
```

The response includes `detected_type`, `prediction`, `confidence`,
`spam_probability`, `safe_probability`, `keywords_detected`, `risk_level`,
`chart_data`, and detailed `analytics`.

The frontend generates a stable `client_id`, stores it in localStorage, and sends
it with each `/analyze` request. No auth or personal user data is used.

## Environment

```env
APP_NAME=Spam Detector API
ENVIRONMENT=development
API_VERSION=v1
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=spam_detector
MONGODB_COLLECTION=scans
MONGODB_SERVER_SELECTION_TIMEOUT_MS=2500

DATASET_DIR=dataset
MODELS_DIR=models_saved
PROCESSED_DATASET_DIR=dataset/processed
MAX_TRAIN_ROWS=
```
