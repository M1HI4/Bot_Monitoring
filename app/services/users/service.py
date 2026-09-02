from __future__ import annotations

from app.models.common import Role
from app.models.config import UserDefinition, UsersFile
from app.services.config.service import ConfigService
from app.utils.exceptions import AccessDeniedError


class UsersService:
    def __init__(self, config_service: ConfigService) -> None:
        self.config_service = config_service

    def list_users(self, enabled_only: bool = False) -> list[UserDefinition]:
        users = self.config_service.load_users().users
        if enabled_only:
            return [user for user in users if user.enabled]
        return users

    def list_whitelist(self) -> list[UserDefinition]:
        return self.list_users(enabled_only=True)

    def get_user(self, user_id: int, chat_id: int) -> UserDefinition | None:
        for user in self.config_service.load_users().users:
            if user.user_id == user_id and user.chat_id == chat_id and user.enabled:
                return user
        return None

    def get_by_user_id(self, user_id: int) -> UserDefinition | None:
        for user in self.config_service.load_users().users:
            if user.user_id == user_id:
                return user
        return None

    def require_user(self, user_id: int, chat_id: int) -> UserDefinition:
        user = self.get_user(user_id=user_id, chat_id=chat_id)
        if user is None:
            raise AccessDeniedError("Пользователь не найден в whitelist или выключен.")
        return user

    def is_admin(self, user: UserDefinition | None) -> bool:
        return bool(user and user.role == Role.ADMIN)

    def require_admin(self, user: UserDefinition | None) -> UserDefinition:
        if user is None or user.role != Role.ADMIN:
            raise AccessDeniedError("Команда доступна только для admin.")
        return user

    def add_user(
        self,
        *,
        user_id: int,
        chat_id: int,
        role: Role,
        username: str | None = None,
        enabled: bool = True,
    ) -> UserDefinition:
        users_file = self.config_service.load_users()
        existing = next((user for user in users_file.users if user.user_id == user_id), None)
        if existing is not None:
            existing.chat_id = chat_id
            existing.role = role
            existing.username = username
            existing.enabled = enabled
            result = existing
        else:
            result = UserDefinition(
                user_id=user_id,
                chat_id=chat_id,
                role=role,
                username=username,
                enabled=enabled,
            )
            users_file.users.append(result)
        updated = UsersFile(version=users_file.version, users=users_file.users)
        self.config_service.save_users(updated)
        return result

    def remove_user(self, user_id: int) -> bool:
        users_file = self.config_service.load_users()
        filtered = [user for user in users_file.users if user.user_id != user_id]
        if len(filtered) == len(users_file.users):
            return False
        updated = UsersFile(version=users_file.version, users=filtered)
        self.config_service.save_users(updated)
        return True

    def set_role(self, user_id: int, role: Role) -> UserDefinition:
        users_file = self.config_service.load_users()
        for user in users_file.users:
            if user.user_id == user_id:
                user.role = role
                updated = UsersFile(version=users_file.version, users=users_file.users)
                self.config_service.save_users(updated)
                return user
        raise AccessDeniedError("Пользователь для смены роли не найден.")
