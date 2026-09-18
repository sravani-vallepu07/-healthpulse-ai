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

---

## ⚙️ Environment Variables (PRD §29.6)

All system settings are configurable through environment variables or a root `.env` file:

| Variable | Default Value | Description |
|---|---|---|
| `PROJECT_NAME` | `Autonomous Multi-Hospital Healthcare Access Platform` | Application title reported in logs and health endpoints |
| `API_V1_STR` | `/api` | Base URI path prefix for all REST endpoints |
| `DATABASE_URL` | `sqlite:///./healthcare_platform.db` | SQLAlchemy database connection URI (SQLite or PostgreSQL) |
| `JWT_SECRET` | `super-secret-healthcare-prototype-key-38472918` | Secret key used for signing HS256 auth tokens |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| `1440` (24 hours) | Expiry window for issued JWT access tokens |
| `LLM_PROVIDER` | `structured_agent` | Active NLU/LLM engine (`structured_agent`, `openai`, `anthropic`, `gemini`) |
| `LLM_API_KEY` | `None` | Master API key for selected LLM provider |
| `OPENAI_API_KEY` | `None` | Provider-specific API key for OpenAI GPT models |
| `ANTHROPIC_API_KEY` | `None` | Provider-specific API key for Anthropic Claude models |
| `GEMINI_API_KEY` | `None` | Provider-specific API key for Google Gemini models |
| `LLM_MODEL` | `gpt-4o-mini` | Specific model identifier (e.g. `claude-3-5-sonnet-20241022`, `gemini-1.5-pro`) |
| `VOICE_PROVIDER` | `browser` | Voice interface mode (`browser`, `mock_telephony`, `twilio`) |
| `TELEPHONY_PROVIDER`| `mock` | Inbound telephony connector mode (`mock`, `twilio`) |
| `VOICE_API_KEY` | `None` | API key for third-party cloud voice synthesis providers |

---

## 🤖 AI Setup & Configuration

HealthPulse AI uses a layered approach combining deterministic safety boundaries, LangGraph state machine execution, and multi-model LLM/NLU extraction:

1. **Deterministic Clinical Guardrail**: Runs *prior* to LLM parsing. Detects emergency keywords (acute chest pain, severe breathlessness, fainting, severe bleeding). If found, the agent short-circuits to `transfer_to_human`, instructs the caller to contact emergency services (108 / ER), and logs an immediate audit event.
2. **Pluggable LLM Providers**:
   - **OpenAI**: Set `LLM_PROVIDER=openai` and `OPENAI_API_KEY=sk-...` (uses JSON response format).
   - **Anthropic**: Set `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY=sk-ant-...` (uses Messages API).
   - **Google Gemini**: Set `LLM_PROVIDER=gemini` and `GEMINI_API_KEY=...` (uses generateContent JSON mode).
   - **Structured Deterministic Fallback**: Default mode with zero API key requirement; provides offline slot and intent extraction for development and automated test suites.
3. **Clarification Over Guessing (PRD §9/§10)**: If a booking intent is received with missing or ambiguous entities (e.g., *"Can you schedule an appointment for me?"*), the AI sets `intent="CLARIFICATION_NEEDED"` and generates an empathetic clarifying question rather than guessing doctors or slots.
4. **Enforcement Boundary**: The LLM *never* interacts directly with the database or external EHR. All queries and mutations route strictly through auditable `AICapabilities` methods (`search_doctors`, `check_availability`, `create_appointment`).

---

## 📞 Voice & Telephony Setup (PRD §11)

HealthPulse AI provides two complementary voice intake modalities:

### 1. Web Browser Voice (Interactive Demo)
- **STT**: Browser native `webkitSpeechRecognition` / `SpeechRecognition` with continuous phrase capture and visual audio pulse animation.
- **TTS**: Browser native `window.speechSynthesis` with natural speech rate and voice pitch control.
- **Endpoint**: `POST /api/ai/voice`

### 2. Telephony & Inbound Phone Agent (TelephonyConnector)
- **Architecture**: Decoupled telephony gateway pattern with `TelephonyConnector` base interface and `MockTelephonyConnector` singleton.
- **Caller Identification**: When an inbound call arrives at `POST /api/telephony/inbound`, the system extracts caller phone metadata (e.g. `+91 9848022338`), searches the registered patient directory, loads the patient profile (e.g. Ramesh Varma), and greets them by name.
- **Audio Stream Pipeline**: Inbound transcript turns stream into `POST /api/telephony/stream`, feeding the exact same `run_ai_agent` state graph used by web chat. The agent's response is converted to speech and returned with an audio stream URL.
- **Call Failure Handling (PRD §11)**: Disconnections or carrier drops (`POST /api/telephony/disconnect` with reason `NETWORK_DROP`, `TIMEOUT`, or `CARRIER_FAILURE`) are marked as `FAILED`, audited, and flagged for callback recovery.
- **Twilio Voice Integration**: Provides a native webhook handler at `POST /api/telephony/webhook/twilio` returning standard TwiML XML (`<Say>`, `<Gather>`), making the service directly connectable to live Twilio phone numbers without code modification.

---

## 🏥 Mock EHR & External Verification

The core integration engine interacts with external hospital EHRs via `HealthcareSystemConnector`:

1. **Idempotency**: Every external creation requires a unique idempotency key. Repeating a request returns the previously created external appointment without generating duplicate records.
2. **Failure Injection**: Accessible via the Platform Admin panel or `POST /api/integrations/failure-mode`:
   - `NONE`: Normal instantaneous EHR confirmation.
   - `NETWORK_ERROR`: Simulates upstream network disconnects (HTTP 502).
   - `AUTH_ERROR`: Simulates expired OAuth tokens (HTTP 401).
   - `VALIDATION_ERROR`: Simulates payload schema rejections (HTTP 422).
   - `SLOT_CONFLICT`: Simulates provider schedule locks (HTTP 409).
   - `TIMEOUT`: Simulates HTTP gateway timeout where the external record was created but the response was lost in transit.
3. **Mandatory External Verification**: An appointment is only transitioned to `CONFIRMED` after independent query verification confirms the record in the external system. If verification fails after a timeout, the appointment enters `RECONCILIATION_REQUIRED` for administrative review.

---

## 🔄 Automated Intake Workflows

When an appointment is verified and confirmed, post-booking background workflows execute automatically (`backend/app/services/workflow_service.py`):

1. **Pre-Visit Questionnaire Assignment**: Automatically matches the doctor's specialty (e.g., Orthopedics) to approved questionnaires and attaches them to the patient's portal.
2. **Patient Notification**: Generates in-app and SMS appointment confirmation alerts with date, time, and doctor information.
3. **Doctor Clinical Notification**: Alerts the attending physician with patient intake details.
4. **Clinical Intake Review**: When the patient submits the questionnaire, the system dispatches a completion notice directly to the doctor's dashboard.

---

## ⚠️ Known Limitations (PRD §29.6)

1. **Real Telephony Carrier vs. Pluggable Mock Connector**: The platform provides a complete, tested `MockTelephonyConnector` simulating all call lifecycle events, caller ID patient identification, stream piping to `run_ai_agent`, audio playback synthesis, and call drop handling, plus a live TwiML XML generator for Twilio. Direct PSTN carrier termination requires an active Twilio account with configured phone numbers and webhook URLs pointing to a public HTTPS tunnel (e.g. ngrok).
2. **LLM Provider Default Mode**: When API keys are not supplied in `.env`, the system defaults to the high-accuracy `structured_agent` deterministic NLU parser. Real external LLM calls (Anthropic Claude, OpenAI GPT, Google Gemini) activate automatically once their respective API keys are configured.
3. **Single-Node SQLite Demo Default**: Local runs use SQLite with a partial unique index on `(doctor_id, date, start_time) WHERE status NOT IN ('CANCELLED', 'FAILED')`. In multi-container production deployments with high concurrency, PostgreSQL with transaction row locks (`SELECT ... FOR UPDATE`) is recommended and supported via Docker Compose.
4. **Browser Speech API Browser Variations**: Web Speech API support varies by browser (best experience on Chromium-based browsers such as Google Chrome and Microsoft Edge).

---

## 🔮 Future Improvements

1. **WebRTC & SIP Trunking**: Direct SIP trunk termination for enterprise PBX systems (Cisco, Avaya, Asterisk) in addition to Twilio Webhooks.
2. **HL7 FHIR R4 Integration**: Standardized FHIR API adapters (`Appointment`, `Patient`, `Schedule`, `Slot` resources) replacing proprietary connector mocks.
3. **Multi-Language Speech Models**: Integration with Bhashini / Whisper for real-time multilingual voice intake across Indian regional languages (Telugu, Hindi, Tamil).
4. **Automated Waitlist & Slot Bump**: Automatic backfill of cancelled slots to waitlisted patients using AI conversational outreach.

