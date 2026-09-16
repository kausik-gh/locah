import pytest
from platform_worker.main import main
from typing import Any


@pytest.mark.asyncio
async def test_worker_unconfigured_behavior(monkeypatch: Any) -> None:
    # Ensure DATABASE_URL is not set
    monkeypatch.delenv("DATABASE_URL", raising=False)

    # Worker should explicitly fail and exit if DATABASE_URL is not provided
    with pytest.raises(SystemExit) as exc_info:
        await main()

    assert exc_info.value.code == 1
