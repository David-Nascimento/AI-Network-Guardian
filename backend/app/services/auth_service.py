from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AuthenticationError
from app.core.logging import audit
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.repositories import UserRepository
from app.schemas import TokenResponse

# Hash fixo para igualar o tempo de resposta quando o usuário não existe.
_DUMMY_HASH = hash_password("dummy-password-for-timing")


class AuthService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._users = UserRepository(session)
        self._settings = settings

    def login(self, username: str, password: str, *, client: str) -> TokenResponse:
        user = self._users.get_by_username(username)
        valid = verify_password(password, user.password_hash if user else _DUMMY_HASH)
        if user is None or not valid or not user.is_active:
            audit("login_failed", actor=username, client=client)
            raise AuthenticationError("Usuário ou senha inválidos")
        audit("login_ok", actor=username, client=client)
        minutes = self._settings.access_token_minutes
        token = create_access_token(
            subject=user.username,
            role=user.role,
            secret=self._settings.secret_key.get_secret_value(),
            minutes=minutes,
        )
        return TokenResponse(access_token=token, expires_in=minutes * 60)

    def bootstrap_admin(self) -> bool:
        """Cria o admin inicial a partir do ambiente se ainda não houver usuários."""
        password = self._settings.admin_password
        if password is None or self._users.count() > 0:
            return False
        self._users.add(
            User(
                username=self._settings.admin_username,
                password_hash=hash_password(password.get_secret_value()),
                role="admin",
            )
        )
        audit("admin_bootstrapped", actor="system", username=self._settings.admin_username)
        return True
