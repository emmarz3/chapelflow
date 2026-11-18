import os
import subprocess
import sys
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[2]
DEVELOPMENT_SECRET_KEYS = [
    "unsafe-dev-secret-change-me",
    "unsafe-development-secret-key-change-me-local-only",
]


@pytest.mark.parametrize("secret_key", [None, *DEVELOPMENT_SECRET_KEYS])
def test_production_startup_rejects_insecure_secret_key(secret_key):
    env = os.environ.copy()
    if secret_key is None:
        env.pop("SECRET_KEY", None)
    else:
        env["SECRET_KEY"] = secret_key

    result = subprocess.run(
        [sys.executable, "-c", "import config.settings.production"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "SECRET_KEY must be set to a non-development value" in result.stderr


def test_production_settings_accept_secure_secret_key():
    env = os.environ.copy()
    env["SECRET_KEY"] = "test-only-production-secret-with-sufficient-entropy-123"

    result = subprocess.run(
        [sys.executable, "-c", "import config.settings.production"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
