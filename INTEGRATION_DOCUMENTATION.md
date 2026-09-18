# HealthPulse AI: Healthcare Integration & EHR Connector Documentation

## 1. Abstract Connector Interface

To decouple the scheduling and intake engine from specific hospital EHR implementations (such as Epic, Cerner, or HL7 FHIR servers), all external communication passes through the `HealthcareSystemConnector` abstract base class:

```python
class HealthcareSystemConnector(ABC):
    @abstractmethod
    def lookup_patient(self, external_id: str) -> Optional[Dict[str, Any]]: ...
    
    @abstractmethod
    def lookup_provider(self, external_id: str) -> Optional[Dict[str, Any]]: ...
    
    @abstractmethod
    def lookup_facility(self, external_id: str) -> Optional[Dict[str, Any]]: ...
    
    @abstractmethod
    def lookup_calendar(self, provider_id: str) -> Dict[str, Any]: ...
    
    @abstractmethod
    def lookup_availability(self, provider_id: str, date: str) -> list: ...
    
    @abstractmethod
    def create_appointment(self, payload: Dict[str, Any], idempotency_key: str) -> Dict[str, Any]: ...
    
    @abstractmethod
    def update_appointment(self, external_id: str, payload: Dict[str, Any]) -> Dict[str, Any]: ...
    
    @abstractmethod
    def cancel_appointment(self, external_id: str, reason: Optional[str] = None) -> Dict[str, Any]: ...
    
    @abstractmethod
    def get_appointment(self, external_id: str) -> Optional[Dict[str, Any]]: ...
    
    @abstractmethod
    def verify_appointment(self, external_id=None, idempotency_key=None, ...) -> Optional[Dict[str, Any]]: ...
```

---

## 2. Failure Simulation Modes

The platform includes an evaluator-controlled failure injection engine managed by Platform Admins via `/api/integrations/failure-mode`:

| Mode | Simulated Behavior | System Recovery Behavior |
|---|---|---|
| `NONE` | Normal successful EHR roundtrip | Direct verification and instant confirmation |
| `TIMEOUT` | EHR creates record, but network timeout occurs before response | Marks operation as `UNKNOWN`, runs query by idempotency key, discovers created record, updates to `CONFIRMED` |
| `NETWORK_ERROR` | Gateway connection dropped | Rejects transaction, sets `FAILED`, leaves slot bookable |
| `AUTH_ERROR` | Token expired or invalid | Raises `502 Bad Gateway`, flags integration incident |
| `SLOT_CONFLICT` | External provider slot locked | Detects conflict, marks `FAILED`, alerts patient |

---

## 3. Unknown Outcome Handling & Reconciliation

A major risk in healthcare appointment scheduling is the **Unknown Outcome Scenario**:
1. Client sends request to create an appointment.
2. The EHR executes the insert and reserves the provider's calendar.
3. A network glitch drops the HTTP connection before the client receives the `201 Created` acknowledgment.
4. **Incorrect behavior**: Blindly retrying the request will create a duplicate booking in the EHR.
5. **HealthPulse AI behavior**:
   - The operation status is set to `UNKNOWN`.
   - The internal appointment transitions to `SYNCHRONIZATION_PENDING`.
   - The system executes `verify_appointment(idempotency_key=idem_key)`.
   - If the record is found: it binds `external_appointment_id` and promotes the internal state to `CONFIRMED`.
   - If the record cannot be determined after retries: a `ReconciliationRecord` is generated with status `RECONCILIATION_REQUIRED` and escalated to the Platform Admin dashboard for manual review.
