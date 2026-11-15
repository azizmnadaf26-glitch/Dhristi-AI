# Dhristi-AI (RetinaGuide XAI)

> **Clinical Decision Support Only. Not an Autonomous Diagnosis.**  
> Explainable AI (XAI) System for Diabetic Retinopathy Screening, Clinical Grading, and Pathology Heatmap Analysis.

---

## 🌟 Overview

**Dhristi-AI** is an end-to-end, clinical-grade decision-support platform designed to assist clinicians and healthcare operators in the early detection and severity grading of **Diabetic Retinopathy (DR)** from digital retinal fundus photography.

### Key Capabilities
- **Multi-Class DR Severity Grading:** Classifies fundus scans according to the International Clinical Diabetic Retinopathy scale (Grade 0: No DR, Grade 1: Mild, Grade 2: Moderate, Grade 3: Severe, Grade 4: Proliferative DR).
- **Explainable AI (Grad-CAM):** Generates high-fidelity visual attention heatmaps that highlight specific retinal abnormalities (microaneurysms, hemorrhages, hard/soft exudates, and neovascularization) to foster clinician trust and transparency.
- **Quality Verification:** Automatic pre-screening checks for scan clarity, focus, and illumination before running inference.
- **Interactive Diagnostic Viewer:** Web-based image viewer with zoom, pan, split-screen comparison, and real-time Grad-CAM opacity adjustments.
- **Clinical PDF Reports:** Automated export of patient screening reports with case details, diagnostic breakdown, heatmaps, and clinician sign-off notes.
- **Role-Based Access Control (RBAC):** Distinct workflows and permission boundaries for **Clinicians**, **Operators**, **Admins**, and **Planners**.

---

## 🏗️ Architecture

```
Dhristi-AI/
├── backend/                  # FastAPI Application & ML Integration
│   ├── alembic/              # Database migrations
│   ├── app/
│   │   ├── models/           # SQLAlchemy ORM models (Cases, Users, Images, Audits)
│   │   ├── routers/          # REST API endpoints (Auth, Cases, Images, Admin, Meta)
│   │   ├── schemas/          # Pydantic validation schemas
│   │   ├── security/         # JWT authentication, password hashing & permissions
│   │   └── services/         # Engine adapters (MATLAB / Fake Engine), PDF generator, Job queue
│   ├── docs/                 # OpenAPI contract specifications & documentation
│   ├── scripts/              # User management & administration scripts
│   ├── tests/                # Comprehensive test suites
│   ├── requirements.txt      # Python dependencies
│   └── README.md             # Backend architecture details
│
├── frontend/                 # Vite + React 19 Web Interface
│   ├── public/               # Static assets & demo retinal images
│   ├── src/
│   │   ├── components/       # UI components & diagnostic viewer
│   │   ├── layouts/          # Dashboard & authentication layouts
│   │   ├── pages/            # Viewports (Upload, Cases, Analysis, Admin)
│   │   ├── routes/           # Protected routing and guards
│   │   └── services/         # API clients
│   ├── package.json          # Node dependencies and scripts
│   └── README.md             # Frontend guide
│
└── README.md                 # Project root documentation
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- **Python 3.11+**
- **Node.js 18+** and **npm**
- *(Optional for Live ML Inference)*: MATLAB R2026b with MATLAB Engine for Python and Deep Learning Toolbox. For quick local development without MATLAB, a deterministic demo engine is included (`MATLAB_FAKE=true`).

---

### 2. Backend Setup

```bash
# Navigate to the backend directory
cd backend

# Create and activate virtual environment
python -m venv .venv
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and configure JWT_SECRET, DATABASE_URL, etc.

# Run database migrations
alembic upgrade head

# Seed initial admin user (optional)
python -m scripts.create_admin

# Start FastAPI development server (Single worker required for queue safety)
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- **API Documentation:** [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs)
- **Health Endpoint:** [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

---

### 3. Frontend Setup

```bash
# In a new terminal, navigate to the frontend directory
cd frontend

# Install Node dependencies
npm install

# Configure environment variables
cp .env.example .env

# Start Vite development server
npm run dev
```

- **Web Application:** [http://localhost:5173](http://localhost:5173)

---

## 🔒 Security & Compliance

- **No PHI in Git:** All local patient scans, databases (`*.db`), and `.env` secret keys are strictly ignored and never committed.
- **Stateless Authentication:** Secure JWT access tokens with HTTP-only refresh cookies and configurable session timeouts.
- **Audit Logging:** Immutably logs all diagnostic reviews, logins, and administrative actions.
- **Fail-Safe Operation:** If model inference confidence falls below clinical thresholds, cases are automatically flagged for mandatory manual review.

---

## 📄 License & Attribution

Designed and developed for clinical decision support in diabetic retinopathy screening.
Decision support only — not a standalone diagnostic device.
