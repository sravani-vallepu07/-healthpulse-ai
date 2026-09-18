"""
conftest.py - Shared test fixtures and helpers.
Provides slot conflict avoidance by using far-future dates + unique times.
"""
import uuid
import random
import pytest
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.integrations.mock_ehr import mock_ehr_connector
from app.integrations.failure_modes import FailureMode


def unique_future_slot(offset_days: int = None, hour: int = None):
    """
    Returns (date_str, start_time, end_time) for a booking slot guaranteed to be unique.
    Uses a far future date (2 years out) + UUID-derived hour to avoid DB conflicts.
    """
    if offset_days is None:
        # Use 2030 base year + random day to avoid any conflicts
        base = datetime(2030, 1, 1)
        offset_days = random.randint(0, 365 * 3)
    else:
        base = datetime.utcnow()

    date = (base + timedelta(days=offset_days)).strftime("%Y-%m-%d")
    if hour is None:
        hour = random.randint(7, 19)  # 7am - 7pm
    minute = random.choice([0, 30])
    start = f"{hour:02d}:{minute:02d}"
    end_hour = hour if minute == 0 else hour + 1
    end_minute = 30 if minute == 0 else 0
    end = f"{end_hour:02d}:{end_minute:02d}"
    return date, start, end


@pytest.fixture(autouse=True)
def reset_ehr_failure_mode():
    """Always reset EHR failure mode to NONE before/after each test."""
    mock_ehr_connector.set_failure_mode(FailureMode.NONE)
    yield
    mock_ehr_connector.set_failure_mode(FailureMode.NONE)
