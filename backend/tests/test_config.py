import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_reject_unknown_environment() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="unsupported")


def test_settings_normalize_log_level() -> None:
    assert Settings(log_level="warning").log_level == "WARNING"
