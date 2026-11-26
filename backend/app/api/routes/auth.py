from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import AuthServiceDep, CurrentUser, login_rate_limit
from app.schemas import LoginRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(login_rate_limit)])
def login(body: LoginRequest, request: Request, service: AuthServiceDep) -> TokenResponse:
    client = request.client.host if request.client else "unknown"
    return service.login(body.username, body.password, client=client)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return user
