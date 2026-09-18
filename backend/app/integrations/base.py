from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class HealthcareSystemConnector(ABC):
    """
    Abstract interface for Healthcare System / EHR Integrations
    (e.g., Epic, Cerner, FHIR gateway, or Mock EHR).
    """

    @abstractmethod
    def lookup_patient(self, external_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def lookup_provider(self, external_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def lookup_facility(self, external_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def lookup_calendar(self, provider_id: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def lookup_availability(self, provider_id: str, date: str) -> list:
        pass

    @abstractmethod
    def create_appointment(self, payload: Dict[str, Any], idempotency_key: str) -> Dict[str, Any]:
        """
        Creates an appointment in the external EHR.
        Returns external appointment payload with external_id.
        """
        pass

    @abstractmethod
    def update_appointment(self, external_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def cancel_appointment(self, external_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_appointment(self, external_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def verify_appointment(
        self,
        external_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        provider_id: Optional[str] = None,
        date: Optional[str] = None,
        start_time: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Independently queries external system to verify record existence and attributes.
        """
        pass
