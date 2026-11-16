import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["APP_PASSWORD"] = "segredo"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["LLM_PROVIDER"] = "fake"
os.environ["CACHE_DIR"] = f"{_tmp}/cache"
os.environ["MAX_LLM_CALLS_PER_DAY"] = "50"

import pytest  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402


@pytest.fixture()
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        yield s


@pytest.fixture()
def client(db):
    from fastapi.testclient import TestClient

    from app.main import app
    return TestClient(app)
