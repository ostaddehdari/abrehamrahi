import os
from pathlib import Path

os.environ.setdefault("ENCRYPTION_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault("DATABASE_PATH", "/tmp/abrehamrahi-pytest.sqlite3")
os.environ.setdefault("PUBLIC_BASE_URL", "https://srun.ir/abrehamrahi")
os.environ.setdefault("APP_ROOT_PATH", "")
os.environ.setdefault("COOKIE_SECURE", "false")


def pytest_sessionstart(session):
    Path(os.environ["DATABASE_PATH"]).unlink(missing_ok=True)

