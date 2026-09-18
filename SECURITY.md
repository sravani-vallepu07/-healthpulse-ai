# HealthPulse AI: Security & Compliance Documentation

## 1. Authentication & Role-Based Access Control (RBAC)

- **JWT Tokens**: Secure signing with HS256 algorithm and configurable token expiry.
- **Password Hashing**: Salted hashing via `bcrypt`.
- **Role Scoping**:
  - `PLATFORM_ADMIN`: Global oversight, hospital lifecycle approval, and system failure simulation.
  - `HOSPITAL_ADMIN`: Scoped to `user.hospital_id`. Controls doctors, working hours, and questionnaires for their specific facility.
  - `DOCTOR`: Scoped to `doctor_id`. Authorized to review appointments and pre-visit intake questionnaires for scheduled patients.
  - `PATIENT`: Scoped to `patient_id`. Access restricted to personal appointments and assigned questionnaires.

---

## 2. Multi-Tenant Data Isolation

- Tenant boundary enforcement occurs at the **database query layer** via `verify_tenant_access()`.
- Cross-tenant access attempts return `HTTP 403 Forbidden` with error code `TENANT_ACCESS_DENIED`.
- APIs never rely on frontend filtering to isolate hospital records.

---

## 3. Healthcare Privacy & PHI Protection in Audit Logs

- **Safe Metadata Policy**: The `AuditEvent` table explicitly restricts storing raw Protected Health Information (PHI), patient medical history, or freeform medical queries in logs.
- Audit logs capture operational trace elements:
  - `actor` (User email or system actor)
  - `role`
  - `event_type` (e.g. `APPOINTMENT_REQUESTED`, `APPOINTMENT_CONFIRMED`, `SLOT_RESERVED`)
  - `resource_type` and `resource_id`
  - `correlation_id` (Used for tracing without exposing clinical details)
  - `safe_metadata` (Contains doctor IDs, slot times, and status strings only)

---

## 4. Concurrency & Idempotency Safeguards

- **Idempotency Keys**: Generated for every booking transaction (`idempotency_key`), preventing duplicate appointment creation across duplicate submissions or network retries.
- **Correlation IDs**: Propagated through HTTP headers (`X-Correlation-ID`) across AI decisions, capability executions, EHR calls, workflows, and audit events for end-to-end distributed traceability.
