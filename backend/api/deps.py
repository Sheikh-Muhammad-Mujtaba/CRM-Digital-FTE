from fastapi import Header, HTTPException

from settings import get_settings


def require_admin_auth(
    x_admin_user: str | None = Header(default=None),
    x_admin_password: str | None = Header(default=None),
):
    settings = get_settings()
    if x_admin_user != settings.admin_username or x_admin_password != settings.admin_password:
        raise HTTPException(status_code=401, detail="Unauthorized admin access")
