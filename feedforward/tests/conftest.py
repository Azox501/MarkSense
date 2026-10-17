import pytest

from core.config import get_settings
from core.db import session_factory


@pytest.fixture
def local_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    session_factory.cache_clear()
    yield
    session_factory().kw["bind"].dispose()
    session_factory.cache_clear()
    get_settings.cache_clear()
