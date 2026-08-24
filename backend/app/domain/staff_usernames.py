import re

from app.domain.errors import DomainError

STAFF_EMAIL_DOMAIN = "staff.abdwash.local"
USERNAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{1,62}[a-z0-9])?$")


def normalize_staff_username(value: str) -> str:
    username = value.strip().lower()
    if not USERNAME_PATTERN.fullmatch(username):
        raise DomainError(
            "INVALID_STAFF_USERNAME",
            "Staff usernames must be 3–64 lowercase letters, numbers, "
            "dots, dashes, or underscores.",
        )
    return username


def staff_synthetic_email(username: str) -> str:
    return f"{normalize_staff_username(username)}@{STAFF_EMAIL_DOMAIN}"
