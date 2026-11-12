import os

import pytest

# Os testes não leem o .env de quem roda: resultado igual em qualquer máquina.
os.environ["PV_ENV_FILE"] = ""


@pytest.fixture(autouse=True)
def _cache_isolado(tmp_path, monkeypatch):
    """Cada teste com o próprio cache de coleta, para um não ver o que o outro guardou."""
    from app import cache
    monkeypatch.setattr(cache, "DB", str(tmp_path / "cache.db"))
