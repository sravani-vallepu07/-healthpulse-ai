# HealthPulse AI: Testing Documentation

The repository includes a comprehensive automated test suite powered by `pytest`.

## 1. Running the Automated Tests

From the `backend` directory:
```bash
python -m pytest tests/ -v
```

### Current Test Execution Summary
- **Total Tests**: 36
- **Passed**: 36 (100% Pass Rate)
- **Failed**: 0
- **Skipped**: 0

---

## 2. Test Suite Breakdown (8 Test Modules)

### `test_ai_capabilities.py`
- **`test_ai_safety_boundary_emergency_escalation`**: Verifies that dangerous symptom keywords (*"acute chest pain"*) immediately trigger `transfer_to_human` escalation and emergency medical advice.
- **`test_ai_orthopedic_discovery_and_availability`**: Tests natural language intent detection, doctor discovery, and real slot lookup.

### `test_ai_evaluation.py`
- Evaluates LangGraph state machine across 14 deterministic scenario turns:
  - Context retention across multi-turn date shifts (*"Actually, make that Friday"*)
  - Controlled capability parameter binding
  - Emergency clinical boundary enforcement
  - Ambiguous slot clarification handling

### `test_appointments.py`
- **`test_idempotent_booking_and_double_creation_prevention`**: Proves that sending identical booking requests with the same idempotency key returns the existing appointment and prevents duplicate bookings.
- **`test_reschedule_and_cancellation_flow`**: Validates safe slot relocation, EHR updates, and availability release.
- **`test_state_history_recording`**: Confirms that state transitions record an immutable audit row in `AppointmentStateHistory`.

### `test_ehr_recovery.py`
- **`test_unknown_outcome_and_timeout_recovery`**:
  1. Injects `FailureMode.TIMEOUT` into Mock EHR connector.
  2. Initiates appointment booking.
  3. Catches network timeout, registers `UNKNOWN` outcome.
  4. Runs verification query against Mock EHR by idempotency key.
  5. Recovers and synchronizes internal appointment state to `CONFIRMED` without duplicate creation.
- **`test_hard_failure_handling`**: Injects `FailureMode.FAIL` to verify proper transition to `FAILED` and error handling.

### `test_scheduling.py`
- **`test_available_slots_calculation`**: Verifies dynamic slot calculation across doctor working hours and calendars.
- **`test_blocked_slot_exclusion`**: Verifies that doctor leaves and blocked administrative periods are filtered out of available slots.
- **`test_inactive_doctor_rejected`**: Ensures inactive or suspended doctors cannot receive booking requests.

### `test_security_isolation.py`
- **`test_patient_can_only_see_own_appointments`**: Verifies that patient tokens can only access their own appointments.
- **`test_state_transition_validation`**: Tests that illegal status jumps (e.g. `COMPLETED` -> `CANCELLED`) are rejected.
- **`test_capability_get_appointment_scoped_to_patient`**: Confirms capability scopes data retrieval by tenant.
- **`test_capability_synchronize_state_rejects_invalid_transition`**: Validates capability state machine enforcement.

### `test_workflows.py`
- **`test_workflow_execution_and_step_logging`**: Validates multi-step post-booking workflow execution.
- **`test_workflow_idempotency`**: Confirms workflows are not executed twice for identical idempotency keys.
- **`test_workflow_conditional_branch_questionnaire`**: Verifies dynamic branching (`QUESTIONNAIRE_AVAILABLE` vs `NO_QUESTIONNAIRE`).

### `test_e2e.py`
- **`test_complete_end_to_end_chain`**:
  Validates the entire lifecycle: Patient Voice Request $\to$ AI Understanding $\to$ Discovery $\to$ Availability Check $\to$ Booking $\to$ Mock EHR Verification $\to$ Internal Synchronization $\to$ Post-Confirmation Workflow $\to$ Pre-Visit Questionnaire Submission $\to$ Doctor Review $\to$ Audit Trail.
