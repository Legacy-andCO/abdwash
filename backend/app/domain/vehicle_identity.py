def normalize_vehicle_plate(value: str) -> str:
    """Stable comparison key for customer-owned vehicles; preserves the stored display value."""

    return "".join(character.casefold() for character in value if character.isalnum())
