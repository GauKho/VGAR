from users.base import BaseService


class UserService(BaseService):
    def normalize(self, name: str) -> str:
        return name.strip()

    def find_user(self, name: str) -> str:
        return self.normalize(name)


def create_user_service() -> UserService:
    return UserService()
