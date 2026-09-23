"""Shared worker-suite safety setup."""

import os

from platform_testing.database_guard import configure_test_database


configure_test_database(os.environ)
