from app.domain.errors import DomainError


def authoritative_cash_change(
    *, due_minor: int, tendered_minor: int, submitted_change_minor: int
) -> int:
    if tendered_minor < due_minor:
        raise DomainError(
            "CASH_TENDER_INSUFFICIENT",
            "Amount received is less than the amount due.",
            status_code=422,
        )
    change_minor = tendered_minor - due_minor
    if submitted_change_minor != change_minor:
        raise DomainError(
            "CASH_CHANGE_MISMATCH",
            "Cash change does not match the authoritative amount due.",
            status_code=422,
            details={"authoritative_change_minor": change_minor},
        )
    return change_minor
