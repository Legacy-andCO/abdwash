import uuid
from collections.abc import Iterable
from typing import Any

from app.models.entities import BookingService, BookingVehicle
from app.schemas.public import BookingAddonSummary, BookingVehicleSummary


def vehicle_summaries_from_rows(
    rows: Iterable[Any],
) -> dict[uuid.UUID, list[BookingVehicleSummary]]:
    grouped: dict[
        uuid.UUID,
        dict[uuid.UUID, tuple[BookingVehicle, BookingService, list[BookingAddonSummary]]],
    ] = {}
    for vehicle, service, addon in rows:
        vehicles = grouped.setdefault(vehicle.booking_id, {})
        current = vehicles.setdefault(vehicle.id, (vehicle, service, []))
        if addon is not None:
            current[2].append(
                BookingAddonSummary(
                    id=addon.service_addon_id,
                    name=addon.addon_name,
                    price_minor=addon.unit_price_minor,
                    expected_duration_minutes=addon.expected_duration_minutes,
                )
            )
    output: dict[uuid.UUID, list[BookingVehicleSummary]] = {}
    for booking_id, vehicles in grouped.items():
        output[booking_id] = [
            BookingVehicleSummary(
                make=vehicle.make,
                model=vehicle.model,
                year=vehicle.year,
                vehicle_type=vehicle.vehicle_type,
                colour=vehicle.colour,
                plate_number=vehicle.plate_number,
                service_name=service.service_name,
                service_id=service.service_id,
                line_total_minor=service.line_total_minor
                + sum(addon.price_minor for addon in addons),
                list_price_minor=service.list_price_minor or service.unit_price_minor,
                discount_minor=service.discount_minor or 0,
                discount_type=service.discount_type,
                loyalty_reward_id=service.loyalty_reward_id,
                expected_duration_minutes=service.expected_duration_minutes or 120,
                addons=addons,
            )
            for vehicle, service, addons in vehicles.values()
        ]
    return output
