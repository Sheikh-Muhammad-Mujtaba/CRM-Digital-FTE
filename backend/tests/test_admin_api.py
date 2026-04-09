import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/testdb")

from api.deps import require_admin_auth


def test_admin_auth_rejects_invalid():
    try:
        require_admin_auth("wrong", "wrong")
    except Exception as exc:
        assert "Unauthorized" in str(exc.detail)
        return
    assert False, "Expected unauthorized exception"
