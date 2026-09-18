# HealthPulse AI: Architecture Documentation

## 1. High-Level Architecture Overview

The system follows a decoupled, layered architecture where the AI agent operates strictly as an administrative facilitator with zero direct access to databases or external EHRs.

```mermaid
flowchart TD
    subgraph ClientLayer ["Client & Interface Layer"]
        Voice["Browser Web Speech API (STT / TTS)"]
        Chat["React Single Page Application"]
    end

    subgraph OrchestrationLayer ["AI & Orchestration Layer"]
        LangGraph["LangGraph Stateful Agent"]
        Safety["Clinical Safety Guardrail"]
        Context["Structured AI Context"]
        Capabilities["Auditable AI Capabilities"]
    end

    subgraph CoreServicesLayer ["Core Application Services"]
        Scheduling["Scheduling Engine (Source of Truth)"]
        AppointmentSvc["Appointment Lifecycle & Idempotency"]
        WorkflowEng["Workflow & Pre-Visit Engine"]
        NotificationSvc["Notification Dispatcher"]
        AuditSvc["Structured Audit & Traceability"]
    end

    subgraph IntegrationLayer ["Integration & Connector Layer"]
        Connector["HealthcareSystemConnector Interface"]
        MockEHR["Mock EHR System with Failure Simulation"]
    end

    subgraph DataLayer ["Data & Persistence Layer"]
        TenantDB[("Multi-Tenant Database")]
    end

    Voice --> Chat
    Chat -->|REST /ai/chat| LangGraph
    LangGraph --> Safety
    Safety -->|Pass| Capabilities
    Capabilities --> Scheduling
    Capabilities --> AppointmentSvc
    AppointmentSvc --> Connector
    Connector --> MockEHR
    AppointmentSvc --> WorkflowEng
    AppointmentSvc --> NotificationSvc
    AppointmentSvc --> AuditSvc
    Scheduling --> TenantDB
    AppointmentSvc --> TenantDB
```

---

## 2. Tenant Isolation Model

Tenant isolation is strictly enforced at the database query level via FastAPI security dependencies.

```mermaid
flowchart LR
    UserReq["User Request with JWT"] --> AuthGuard{"Role & Tenant Guard"}
    
    AuthGuard -->|Platform Admin| FullAccess["Global Access Across Hospitals"]
    AuthGuard -->|Hospital Admin| HospitalFilter["Scoped to user.hospital_id"]
    AuthGuard -->|Doctor| DoctorFilter["Scoped to doctor.hospital_id & doctor_id"]
    AuthGuard -->|Patient| PatientFilter["Scoped to patient_id"]

    HospitalFilter --> TenantDB[("Multi-Tenant Database")]
    DoctorFilter --> TenantDB
    PatientFilter --> TenantDB
    FullAccess --> TenantDB
```

### Authorization Principles:
- **Hospital Admins** can only manage doctors, availability windows, questionnaires, and workflows belonging to their own hospital.
- **Doctors** can only review appointments and questionnaires for patients scheduled with them.
- **Patients** can only access their own appointments and profiles.
- Cross-tenant database queries return `HTTP 403 Forbidden` with error code `TENANT_ACCESS_DENIED`.

---

## 3. Database Entity Relationship (ER) Diagram

```mermaid
erDiagram
    Hospital ||--o{ Department : has
    Hospital ||--o{ Specialty : has
    Hospital ||--o{ Doctor : employs
    Hospital ||--o{ Appointment : hosts
    Hospital ||--o{ Questionnaire : configures
    Doctor ||--o{ Calendar : maintains
    Calendar ||--o{ Availability : defines
    Doctor ||--o{ BlockedSlot : blocks
    Doctor ||--o{ Appointment : attends
    Patient ||--o{ Appointment : books
    Patient ||--o{ AIConversation : owns
    Patient ||--o{ QuestionnaireResponse : submits
    Appointment ||--o{ AppointmentStateHistory : tracks_history
    Appointment ||--o{ QuestionnaireResponse : attaches
    Appointment ||--o{ WorkflowExecution : triggers
    Appointment ||--o{ Notification : notifies
    Appointment ||--o{ IntegrationVerification : verifies
    Appointment ||--o{ ReconciliationRecord : reconciles

    AppointmentStateHistory {
        int id PK
        int appointment_id FK
        string previous_status
        string new_status
        string reason
        string changed_by
        string correlation_id
        datetime created_at
    }

    Hospital {
        int id PK
        string name
        string city
        string status
    }
    Doctor {
        int id PK
        int hospital_id FK
        string name
        string qualifications
        string status
    }
    Appointment {
        int id PK
        int hospital_id FK
        int doctor_id FK
        int patient_id FK
        string date
        string start_time
        string status
        string external_appointment_id
        string idempotency_key
        string correlation_id
    }
    Questionnaire {
        int id PK
        int hospital_id FK
        string name
        string status
    }
```

---

## 4. State Machine & Transition Rules (§9, §26)

All appointment status transitions are strictly validated against a finite state machine:

| Current Status | Allowed Next Statuses | Disallowed Invalid Transitions |
|---|---|---|
| `PENDING` | `CONFIRMED`, `FAILED`, `CANCELLED` | `COMPLETED` |
| `CONFIRMED` | `RESCHEDULED`, `CANCELLED`, `COMPLETED` | `PENDING`, `FAILED` |
| `RESCHEDULED` | `CONFIRMED`, `CANCELLED` | `PENDING` |
| `CANCELLED` | *Terminal State (None)* | `CONFIRMED`, `PENDING`, `RESCHEDULED` |
| `COMPLETED` | *Terminal State (None)* | `CANCELLED`, `CONFIRMED`, `RESCHEDULED` |
| `FAILED` | `PENDING`, `CANCELLED` | `COMPLETED`, `CONFIRMED` (without retry) |

Every transition automatically records an immutable row in `AppointmentStateHistory` with actor email and `correlation_id`.

## 5. Booking & Verification Sequence

An appointment is **never** confirmed until independent external verification succeeds.

```mermaid
sequenceDiagram
    autonumber
    actor Patient
    participant AI as LangGraph Agent
    participant Sched as Scheduling Engine
    participant Appt as Appointment Service
    participant EHR as Mock EHR Connector
    participant WF as Workflow Service

    Patient->>AI: "Book slot at 10:00 AM"
    AI->>Sched: validate_slot(doctor_id, date, 10:00, 10:30)
    Sched-->>AI: Valid (No conflicts)
    AI->>Appt: create_appointment_with_verification()
    Appt->>Appt: Save internal status = PENDING
    Appt->>EHR: create_appointment(payload, idempotency_key)
    EHR-->>Appt: External Response (EXT-APT-101)
    Appt->>EHR: verify_appointment(EXT-APT-101)
    EHR-->>Appt: Verified: Record Exists & Matched
    Appt->>Appt: Update internal status = CONFIRMED
    Appt->>WF: trigger_appointment_workflow()
    WF->>Patient: Send In-App Confirmation & Questionnaire Alert
    Appt-->>AI: Confirmed Appointment Details
    AI-->>Patient: "Your appointment is verified and confirmed! (Ref: EXT-APT-101)"
```

---

## 6. Unknown Outcome & Timeout Recovery Sequence

Demonstrates recovery when network timeout occurs during EHR creation.

```mermaid
sequenceDiagram
    autonumber
    participant Appt as Appointment Service
    participant EHR as Mock EHR
    participant Audit as Audit Service
    actor Admin as Platform Admin

    Appt->>EHR: create_appointment(payload, idempotency_key)
    Note over EHR: EHR saves record EXT-APT-99,<br/>but HTTP response times out!
    EHR--xAppt: TimeoutError (EHR Gateway 504)
    Note over Appt: DO NOT BLINDLY RETRY CREATE!<br/>Mark status = UNKNOWN
    Appt->>Appt: Set status = SYNCHRONIZATION_PENDING
    Appt->>Audit: Log IntegrationOperation (status=UNKNOWN)
    
    Appt->>EHR: verify_appointment(idempotency_key)
    Note over EHR: Search external records by idempotency key
    EHR-->>Appt: Record FOUND (EXT-APT-99, status=SCHEDULED)
    
    Appt->>Appt: Synchronize status = CONFIRMED
    Appt->>Appt: Save external_appointment_id = EXT-APT-99
    Appt->>Audit: Log IntegrationVerification (status=VERIFIED)
    Appt-->>Admin: Observable in Audit Trail as Successful Recovery
```

---

## 7. Voice & Telephony Architecture (PRD §11)

HealthPulse AI includes an enterprise-grade, pluggable telephony layer designed to accept inbound telephone calls, resolve patient identity by caller ID, stream conversational audio to the AI state machine, synthesize speech, and handle network disconnects.

```mermaid
flowchart TD
    subgraph InboundCall ["Inbound Phone Call Event"]
        PSTN["Inbound Telephone Caller (+91 9848022338)"]
        TwilioGateway["Twilio Voice / SIP Trunk"]
        MockGateway["MockTelephonyConnector"]
    end

    subgraph TelephonyBridge ["Telephony Integration Bridge"]
        InboundAPI["POST /api/telephony/inbound"]
        PatientLookup["Caller ID Patient Resolver"]
        StreamAPI["POST /api/telephony/stream"]
        STTBridge["Speech-to-Text Pipeline"]
        TTSBridge["Text-to-Speech Synthesis"]
        DisconnectAPI["POST /api/telephony/disconnect"]
    end

    subgraph AIWorkflow ["AI Conversational Engine"]
        AgentEngine["run_ai_agent(patient_id, conv_id)"]
        Guardrail["Clinical Safety Check"]
        Caps["AICapabilities"]
    end

    PSTN --> TwilioGateway
    TwilioGateway --> InboundAPI
    MockGateway --> InboundAPI
    InboundAPI --> PatientLookup
    PatientLookup --> StreamAPI
    StreamAPI --> STTBridge
    STTBridge --> AgentEngine
    AgentEngine --> Guardrail
    Guardrail --> Caps
    AgentEngine --> TTSBridge
    TTSBridge --> PSTN
    PSTN -.->|Network Drop / Disconnect| DisconnectAPI
```

### Inbound Phone Call & Failure Handling Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Caller as Inbound Telephone Caller
    participant Gateway as Telephony Gateway (Twilio / Mock)
    participant Telephony as Telephony Connector
    participant PatientDB as Patient Directory
    participant AI as LangGraph run_ai_agent
    participant Audit as Audit Service

    Caller->>Gateway: Dials Hospital Inbound Number (+91 866 247 1111)
    Gateway->>Telephony: initiate_inbound_call(caller_phone)
    Telephony->>PatientDB: Lookup patient by phone number
    PatientDB-->>Telephony: Match: Ramesh Varma (ID: 1)
    Telephony->>Telephony: Create active Call Session (CALL-9848A)
    Telephony-->>Caller: "Hello Ramesh! Thank you for calling HealthPulse AI..."
    
    loop Conversational Turns
        Caller->>Gateway: Speaks: "I need Dr. Anil Rao on Friday"
        Gateway->>Telephony: process_audio_stream(call_id, speech_transcript)
        Telephony->>AI: run_ai_agent(message, patient_id=1)
        AI-->>Telephony: reply, suggested_slots, intent=FIND_DOCTOR
        Telephony->>Telephony: Synthesize audio response WAV
        Telephony-->>Caller: Plays back speech reply
    end

    alt Emergency Symptom Escalation
        Caller->>Gateway: "I have acute chest pain and dizziness"
        Gateway->>Telephony: process_audio_stream(call_id, transcript)
        Telephony->>AI: run_ai_agent()
        AI-->>Telephony: intent=HUMAN_ESCALATION, is_escalated=True
        Telephony->>Telephony: Mark session = ESCALATED_TO_HUMAN
        Telephony->>Audit: Log emergency transfer event
        Telephony-->>Caller: Immediate ER hotline transfer (108 / ER)
    else Abnormal Network Drop (PRD §11)
        Caller-xGateway: Unexpected Carrier Disconnect
        Gateway->>Telephony: handle_call_disconnect(reason=NETWORK_DROP)
        Telephony->>Telephony: Mark session = FAILED (failure_reason=NETWORK_DROP)
        Telephony->>Audit: Log TELEPHONY_CALL_FAILURE
    end
```

