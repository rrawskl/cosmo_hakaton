"""Tests use an isolated database, never the user's saved analyses."""

import os
import tempfile
from pathlib import Path

_test_dir = tempfile.TemporaryDirectory(prefix="orbital-tests-")
os.environ["DATABASE_URL"] = (
    "sqlite:///" + (Path(_test_dir.name) / "test.db").as_posix()
)
os.environ["AUTO_REFRESH"] = "false"


def pytest_sessionfinish(session, exitstatus):
    from backend.app.storage import engine

    engine.dispose()
    _test_dir.cleanup()
