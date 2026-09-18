import uuid
import time
from typing import Dict, Any, Optional
from app.integrations.base import HealthcareSystemConnector
from app.integrations.failure_modes import FailureMode

class MockEHRConnector(HealthcareSystemConnector):
    """
    Mock EHR simulating an enterprise healthcare system (e.g. Cerner/Epic/HL7 FHIR).
    Maintains external records and supports failure simulation for evaluation.
    """

    def __init__(self):
        self.failure_mode: FailureMode = FailureMode.NONE
        self.delay_seconds: float = 0.0
        
        # Simulated external storage
        self._external_appointments: Dict[str, Dict[str, Any]] = {}
        self._idempotency_index: Dict[str, str] = {} # idempotency_key -> external_id
        
        self._external_patients: Dict[str, Dict[str, Any]] = {
            "EXT-PAT-001": {"name": "Ramesh Varma", "dob": "1988-04-12", "phone": "9848022338"},
            "EXT-PAT-002": {"name": "Ananya Reddy", "dob": "1994-09-21", "phone": "9848033449"}
        }
        self._external_providers: Dict[str, Dict[str, Any]] = {
            "EXT-DOC-001": {"name": "Dr. Anil Rao", "specialty": "Orthopedics", "npi": "1942048591"},
            "EXT-DOC-002": {"name": "Dr. Priya Sharma", "specialty": "General Medicine", "npi": "1942048592"},
            "EXT-DOC-003": {"name": "Dr. Kiran Kumar", "specialty": "Dermatology", "npi": "1942048593"}
        }
        self._external_facilities: Dict[str, Dict[str, Any]] = {
            "EXT-FAC-001": {"name": "ABC Multi-Speciality Hospital", "city": "Vijayawada"},
            "EXT-FAC-002": {"name": "XYZ Healthcare Center", "city": "Vijayawada"}
        }

    def set_failure_mode(self, mode: FailureMode, delay_seconds: float = 0.0):
        self.failure_mode = mode
        self.delay_seconds = delay_seconds

    def get_failure_mode(self) -> FailureMode:
        return self.failure_mode

    def lookup_patient(self, external_id: str) -> Optional[Dict[str, Any]]:
        return self._external_patients.get(external_id)

    def lookup_provider(self, external_id: str) -> Optional[Dict[str, Any]]:
        return self._external_providers.get(external_id)

    def lookup_facility(self, external_id: str) -> Optional[Dict[str, Any]]:
        return self._external_facilities.get(external_id)

    def lookup_calendar(self, provider_id: str) -> Dict[str, Any]:
        return {"provider_id": provider_id, "calendar_status": "ACTIVE"}

    def lookup_availability(self, provider_id: str, date: str) -> list:
        return [{"time": "09:00"}, {"time": "10:00"}, {"time": "11:00"}, {"time": "14:00"}]

    def create_appointment(self, payload: Dict[str, Any], idempotency_key: str) -> Dict[str, Any]:
        """
        Creates appointment in external EHR with idempotency protection and failure simulation.
        """
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)

        # 1. Check idempotency: If already created, return existing record
        if idempotency_key in self._idempotency_index:
            existing_ext_id = self._idempotency_index[idempotency_key]
            return self._external_appointments[existing_ext_id]

        # 2. Simulate Failure Modes
        if self.failure_mode in (FailureMode.NETWORK_ERROR, FailureMode.FAIL):
            raise ConnectionError("EHR Connection reset by peer [EHR-ERR-502]")

        if self.failure_mode == FailureMode.AUTH_ERROR:
            raise PermissionError("EHR OAuth2 Client Token Expired or Invalid [EHR-ERR-401]")

        if self.failure_mode == FailureMode.VALIDATION_ERROR:
            raise ValueError("EHR Validation Error: Required patient identifier missing [EHR-ERR-422]")

        if self.failure_mode == FailureMode.SLOT_CONFLICT:
            raise RuntimeError("EHR Slot Conflict: Requested provider slot is locked externally [EHR-ERR-409]")

        if self.failure_mode == FailureMode.TIMEOUT:
            # IMPORTANT: UNKNOWN OUTCOME SCENARIO
            # The EHR actually created the record internally, but the HTTP response timed out
            # before reaching the client!
            ext_id = f"EXT-APT-{uuid.uuid4().hex[:8].upper()}"
            record = {
                "external_id": ext_id,
                "idempotency_key": idempotency_key,
                "patient_id": payload.get("patient_id"),
                "provider_id": payload.get("provider_id"),
                "facility_id": payload.get("facility_id"),
                "date": payload.get("date"),
                "start_time": payload.get("start_time"),
                "end_time": payload.get("end_time"),
                "status": "SCHEDULED",
                "created_at": time.time()
            }
            self._external_appointments[ext_id] = record
            self._idempotency_index[idempotency_key] = ext_id
            raise TimeoutError("Gateway Timeout: EHR server did not acknowledge HTTP response within 5000ms [EHR-ERR-504]")

        # Normal successful creation
        ext_id = f"EXT-APT-{uuid.uuid4().hex[:8].upper()}"
        record = {
            "external_id": ext_id,
            "idempotency_key": idempotency_key,
            "patient_id": payload.get("patient_id"),
            "provider_id": payload.get("provider_id"),
            "facility_id": payload.get("facility_id"),
            "date": payload.get("date"),
            "start_time": payload.get("start_time"),
            "end_time": payload.get("end_time"),
            "status": "SCHEDULED",
            "created_at": time.time()
        }
        self._external_appointments[ext_id] = record
        self._idempotency_index[idempotency_key] = ext_id
        return record

    def update_appointment(self, external_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if external_id not in self._external_appointments:
            raise KeyError(f"External appointment {external_id} not found")
        record = self._external_appointments[external_id]
        if "date" in payload:
            record["date"] = payload["date"]
        if "start_time" in payload:
            record["start_time"] = payload["start_time"]
        if "end_time" in payload:
            record["end_time"] = payload["end_time"]
        record["status"] = "RESCHEDULED"
        record["updated_at"] = time.time()
        return record

    def cancel_appointment(self, external_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        if external_id not in self._external_appointments:
            raise KeyError(f"External appointment {external_id} not found")
        record = self._external_appointments[external_id]
        record["status"] = "CANCELLED"
        record["cancellation_reason"] = reason
        record["cancelled_at"] = time.time()
        return record

    def get_appointment(self, external_id: str) -> Optional[Dict[str, Any]]:
        return self._external_appointments.get(external_id)

    def verify_appointment(
        self,
        external_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        provider_id: Optional[str] = None,
        date: Optional[str] = None,
        start_time: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Independent verification query used to confirm external EHR state.
        Searches by external_id or idempotency_key or slot parameters.
        """
        if external_id and external_id in self._external_appointments:
            return self._external_appointments[external_id]

        if idempotency_key and idempotency_key in self._idempotency_index:
            ext_id = self._idempotency_index[idempotency_key]
            return self._external_appointments.get(ext_id)

        # Query by parameters
        for rec in self._external_appointments.values():
            if (provider_id is None or rec.get("provider_id") == provider_id) and \
               (date is None or rec.get("date") == date) and \
               (start_time is None or rec.get("start_time") == start_time):
                return rec

        return None

# Singleton connector instance
mock_ehr_connector = MockEHRConnector()
