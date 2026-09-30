from auth.service import login


def login_handler(username: str, password: str) -> bool:
    return login(username, password)
