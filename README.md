# HealthPulse AI: Autonomous Multi-Hospital Patient Intake, Scheduling & Voice Agent

A production-grade, multi-tenant AI-native healthcare access platform designed to demonstrate end-to-end autonomous patient intake, doctor discovery, real availability scheduling, Mock EHR integration with external verification, idempotent recovery from unknown outcomes (such as network timeouts), post-visit questionnaire collection, background workflow orchestration, and role-based observability (Platform Admin, Hospital Admin, Doctor, Patient).

---

## 🌟 Key Highlights & Architectural Guarantees

1. **Strict Administrative Assistant AI**: The AI assists strictly with administrative discovery and intake. It is barred from diagnosing, prescribing, recommending treatment, or changing medication. Severe clinical symptoms automatically trigger human and emergency escalation.
2. **True Source of Truth in Scheduling**: The AI *never* invents availability. Bookable slots are derived directly from the scheduling engine by checking active doctor calendars, approved hospital status, working hours, doctor leaves, blocked slots, and existing appointments.
3. **EHR Decoupling via Connectors**: Core business logic interacts with EHRs exclusively through an abstract `HealthcareSystemConnector` interface.
4. **Mandatory External Verification Before Confirmation**: An appointment is *never* marked or communicated as `CONFIRMED` until an independent query against the EHR verifies the external record.
5. **Idempotent Recovery from Unknown Outcomes**: When an EHR request experiences a gateway timeout (`TIMEOUT`), the system flags the operation as `UNKNOWN` and searches the EHR by idempotency key/slot parameters. If found, it safely reconciles the internal state to `CONFIRMED` without duplicate creation.
6. **Robust Multi-Tenant Isolation**: Enforced at the database query level. Hospital A can never access Hospital B's doctors, calendars, patients, or appointments.
7. **Interactive Web Voice Interface**: Voice intake powered by browser Web Speech API (STT & TTS) with speech turn-taking, visual speaking/listening wave indicators, and real-time slot selection cards.

---

## 🏗️ Tech Stack

- **Frontend**: React 18, Tailwind CSS, Lucide / FontAwesome icons, Web Speech API (STT: `SpeechRecognition`, TTS: `SpeechSynthesis`), Axios.
- **Backend**: Python 3.11+, FastAPI, SQLAlchemy ORM, Pydantic v2, PyJWT, Bcrypt, Pytest.
- **AI Orchestration**: LangGraph state graph with explicit auditable capabilities and clinical safety boundary checks.
- **Database**: SQLite (default for zero-setup local runs) & PostgreSQL (for containerized cloud deployment).
- **Containerization**: Docker, Docker Compose.

---

## 📁 Repository Structure

```
├── backend/
│   ├── app/
│   │   ├── config.py              # Application settings & environment variables
│   │   ├── database.py            # SQLAlchemy engine, session maker, base model
│   │   ├── main.py                # FastAPI application, CORS, static frontend mount
│   │   ├── models/                # SQLAlchemy models (tenant, doctor, patient, appointment, etc.)
│   │   ├── schemas/               # Pydantic schemas
│   │   ├── auth/                  # JWT security and tenant-isolation dependencies
│   │   ├── services/              # Scheduling, appointment, workflow, notification, audit services
│   │   ├── integrations/          # HealthcareSystemConnector & MockEHRConnector with failure simulation
│   │   ├── ai/                    # LangGraph state machine, prompts, capabilities, and context
│   │   └── routers/               # REST API endpoints (auth, hospital, doctor, appointment, ai, ops)
│   ├── tests/                     # Comprehensive automated pytest suite
│   ├── seed.py                    # Database seeder (hospitals, doctors, users, questionnaires)
│   ├── requirements.txt           # Python dependencies
│   └── Dockerfile                 # Backend container definition
├── frontend/
│   ├── index.html                 # Single Page Application HTML shell
│   ├── app.jsx                    # React component tree (Voice assistant, dashboards, demo switcher)
│   └── Dockerfile                 # Frontend container definition
├── docker-compose.yml             # Docker compose setup with PostgreSQL
├── .env.example                   # Environment variable template
├── ARCHITECTURE.md                # System architecture and Mermaid sequence diagrams
├── AI_DOCUMENTATION.md            # AI safety boundaries, capabilities, and state graph
├── INTEGRATION_DOCUMENTATION.md   # Connector interface and failure simulation guide
├── DEPLOYMENT.md                  # Deployment instructions (Local & Docker)
├── TESTING.md                     # Test execution documentation
└── SECURITY.md                    # Security, RBAC, and HIPAA-inspired privacy controls
```

---

## 🚀 Quick Start (Local Run)

### 1. Prerequisites
- Python 3.11+ (Python 3.14 compatible)
- Modern web browser (Chrome, Edge, Safari)

### 2. Setup Backend & Seed Database
```bash
cd backend
python -m pip install -r requirements.txt
python seed.py
```

### 3. Start the Server
```bash
python -m uvicorn app.main:app --reload --port 8000
```

### 4. Open the Application
Navigate to **`http://localhost:8000`** in your browser.  
Both the REST API and the React Web Application are served on this single port!

---

## 🐳 Docker Deployment

To launch the full stack with a dedicated PostgreSQL database:
```bash
docker-compose up --build
```
- Web Application: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- API Documentation: `http://localhost:8000/docs`

---

## 🔑 Demo Accounts & Credentials

The platform includes a **1-Click Demo Persona Bar** at the top of the screen to quickly switch roles. Alternatively, log in manually using:

| Persona | Email | Password | Role / Tenant |
|---|---|---|---|
| **Platform Admin** | `platform.admin@healthcare.org` | `Admin@123` | Platform Administrator |
| **Hospital Admin** | `admin.abc@hospital.org` | `Admin@123` | ABC Multi-Speciality Hospital |
| **Hospital Admin** | `admin.xyz@hospital.org` | `Admin@123` | XYZ Healthcare Center |
| **Doctor** | `dr.anil.rao@hospital.org` | `Doctor@123` | Dr. Anil Rao (Orthopedics) |
| **Doctor** | `dr.priya.sharma@hospital.org` | `Doctor@123` | Dr. Priya Sharma (General Medicine) |
| **Patient** | `ramesh.varma@patient.org` | `Patient@123` | Ramesh Varma |
| **Patient** | `ananya.reddy@patient.org` | `Patient@123` | Ananya Reddy |

---

## 🧪 Running Automated Tests

Run the complete suite of 9 test suites covering scheduling concurrency, state transitions, idempotency, EHR timeout recovery, AI safety boundaries, and end-to-end booking:

```bash
cd backend
python -m pytest tests/ -v
```

---

## 🎯 How to Demonstrate the End-to-End Workflow

1. **Patient Intake & Discovery**:
   - Log in as **Patient (Ramesh)** or click the Demo Bar button.
   - Click **Speak Voice** or type: *"I need an orthopedic appointment this week"*.
   - The AI understands the intent, executes `search_doctors(specialty='Orthopedics')`, invokes `check_availability()` against the scheduling engine, and displays available slot cards for Dr. Anil Rao at ABC Multi-Speciality Hospital.
2. **Context Resolution**:
   - Type or speak: *"Actually, make that Friday"*.
   - The AI uses conversational context to resolve the doctor and hospital, queries Friday's availability, and displays new slot cards.
3. **Booking with External Verification**:
   - Click one of the suggested slot cards (e.g. `10:00 - 10:30`).
   - The system revalidates availability, reserves the slot in `PENDING` state, creates the external appointment in Mock EHR, verifies the external record, synchronizes internal state to `CONFIRMED`, assigns a pre-visit questionnaire, and delivers in-app notifications.
4. **Pre-Visit Questionnaire**:
   - Click **Fill Pre-Visit Questionnaire** or switch to the **My Scheduled Appointments** tab.
   - Complete the questionnaire (Pain level 1-10, duration, prior surgeries) and click **Submit**.
5. **Doctor Clinical Visibility**:
   - Click the **🩺 Dr. Anil Rao** button on the Demo Bar.
   - Dr. Rao sees the newly confirmed booking on his schedule.
   - Click **Review Intake Form** to inspect the patient's submitted responses.
6. **EHR Timeout & Unknown Outcome Recovery Simulation**:
   - Click **👑 Platform Admin** on the Demo Bar.
   - In the **EHR Failure Injection & Unknown Outcome Simulator**, click **⚡ TIMEOUT (Unknown Outcome Test)**.
   - Switch back to **👤 Patient (Ramesh)** and book another slot.
   - The Mock EHR simulates creating the record but throwing a network timeout.
   - The backend registers an `UNKNOWN` outcome, pauses blind retries, performs an independent verification query by idempotency key, finds the newly created external record, updates internal state to `CONFIRMED`, and presents the verified appointment.
   - Switch back to **Platform Admin** and inspect the audit trail to view the recovery trace!
