"""Shared worker-suite safety setup."""

import os

from platform_testing.ai_guard import (  # noqa: F401 — fixtures registered by import
    enable_no_external_ai,
    no_paid_ai_calls,
    stubbed_ai_transport,
)
from platform_testing.database_guard import configure_test_database


configure_test_database(os.environ)
# A worker test must never draw a picture or call a model on a paid key.
enable_no_external_ai(os.environ)
