import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from unittest.mock import MagicMock

from app import auth


async def test_auth_error_hides_internal_detail(monkeypatch):
    sb = MagicMock()
    sb.auth.get_user.side_effect = Exception("internal boom at db-host-7")
    monkeypatch.setattr(auth, "supabase", sb)
    with pytest.raises(HTTPException) as err:
        await auth.get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials="tok-unique-1"))
    assert err.value.status_code == 401
    assert "boom" not in err.value.detail and "db-host" not in err.value.detail
    assert err.value.headers == {"WWW-Authenticate": "Bearer"}
