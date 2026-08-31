from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

import httpx

from app.core.providers import observe_provider_call


@dataclass(frozen=True)
class EtaResult:
    duration: timedelta


class EtaProvider(Protocol):
    async def estimate(
        self, *, origin: tuple[float, float], destination: tuple[float, float]
    ) -> EtaResult | None: ...


class GoogleRoutesEtaProvider:
    def __init__(self, client: httpx.AsyncClient, api_key: str) -> None:
        self.client = client
        self.api_key = api_key

    async def estimate(
        self, *, origin: tuple[float, float], destination: tuple[float, float]
    ) -> EtaResult | None:
        response = await observe_provider_call(
            "google_routes",
            "eta",
            lambda: self.client.post(
                "https://routes.googleapis.com/directions/v2:computeRoutes",
                headers={
                    "X-Goog-Api-Key": self.api_key,
                    "X-Goog-FieldMask": "routes.duration",
                },
                json={
                    "origin": {
                        "location": {"latLng": {"latitude": origin[0], "longitude": origin[1]}}
                    },
                    "destination": {
                        "location": {
                            "latLng": {
                                "latitude": destination[0],
                                "longitude": destination[1],
                            }
                        }
                    },
                    "travelMode": "DRIVE",
                    "routingPreference": "TRAFFIC_AWARE",
                },
            ),
        )
        response.raise_for_status()
        value = response.json().get("routes", [{}])[0].get("duration")
        if not isinstance(value, str) or not value.endswith("s"):
            return None
        return EtaResult(timedelta(seconds=float(value[:-1])))
