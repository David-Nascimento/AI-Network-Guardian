from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get_by_username(self, username: str) -> User | None:
        return self._s.scalar(select(User).where(User.username == username))

    def count(self) -> int:
        return self._s.scalar(select(func.count(User.id))) or 0

    def add(self, user: User) -> User:
        self._s.add(user)
        self._s.flush()
        return user
