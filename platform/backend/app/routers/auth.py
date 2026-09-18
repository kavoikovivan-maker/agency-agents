from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from ..security import check_password, issue_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(payload: dict, response: Response) -> dict:
    password = str(payload.get("password", ""))
    if not check_password(password):
        raise HTTPException(status_code=401, detail="Invalid password")
    token = issue_token()
    response.set_cookie("app_token", token, httponly=True, samesite="lax")
    return {"token": token}
