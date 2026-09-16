import pytest
import uuid


@pytest.fixture
def mock_business_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_identity_id() -> uuid.UUID:
    return uuid.uuid4()
