from typing import Final

VEHICLE_TYPES: Final[tuple[str, ...]] = (
    "sedan",
    "suv",
    "hatchback",
    "coupe",
    "pickup",
    "van",
    "other",
)


def is_vehicle_type(value: str) -> bool:
    return value in VEHICLE_TYPES
