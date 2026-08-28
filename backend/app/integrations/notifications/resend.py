from datetime import datetime
from html import escape
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.core.providers import observe_provider_call


class ResendNotificationProvider:
    def __init__(self, client: httpx.AsyncClient, *, api_key: str, email_from: str) -> None:
        self._client = client
        self._api_key = api_key
        self._email_from = email_from

    async def send(
        self,
        *,
        channel: str,
        recipient: str,
        notification_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> None:
        if channel != "email":
            raise ValueError(f"Resend cannot deliver channel {channel!r}")
        subject, html = render_email(notification_type, payload)
        response = await observe_provider_call(
            "resend",
            "send_email",
            lambda: self._client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Idempotency-Key": idempotency_key,
                },
                json={
                    "from": self._email_from,
                    "to": [recipient],
                    "subject": subject,
                    "html": html,
                },
            ),
        )
        response.raise_for_status()


def render_email(notification_type: str, payload: dict[str, Any]) -> tuple[str, str]:
    if notification_type == "booking_confirmed":
        return render_booking_confirmation(payload)
    if notification_type == "driver_en_route":
        return render_driver_en_route(payload)
    if notification_type == "cancellation_requested":
        reference = escape(str(payload["booking_reference"]))
        return (
            f"Cancellation request received — {reference}",
            _email_shell(
                "Cancellation request received",
                "<p>We received your cancellation request for booking "
                f"<strong>{reference}</strong>. "
                "Your booking remains active until the Trifecta team reviews it.</p>",
            ),
        )
    raise ValueError(f"Unsupported notification type {notification_type!r}")


def render_driver_en_route(payload: dict[str, Any]) -> tuple[str, str]:
    reference = escape(str(payload["booking_reference"]))
    first_name = escape(str(payload["customer_first_name"]))
    timezone = ZoneInfo(str(payload["timezone"]))
    start = datetime.fromisoformat(str(payload["scheduled_start"])).astimezone(timezone)
    end = datetime.fromisoformat(str(payload["scheduled_end"])).astimezone(timezone)
    eta_value = payload.get("estimated_arrival_at")
    eta = datetime.fromisoformat(str(eta_value)).astimezone(timezone) if eta_value else None
    manage_url = escape(str(payload["management_url"]), quote=True)
    vehicles = payload.get("vehicles", [])
    vehicle = vehicles[0] if isinstance(vehicles, list) and vehicles else None
    vehicle_detail = (
        _detail(
            "Vehicle",
            f"{escape(str(vehicle['make']))} {escape(str(vehicle['model']))}",
        )
        if vehicle
        else ""
    )
    manage_button = (
        f'<p style="margin:30px 0"><a href="{manage_url}" '
        'style="background:#D65A1F;color:#fff;text-decoration:none;padding:13px 22px;'
        'border-radius:8px;display:inline-block;font-weight:700">View booking</a></p>'
    )
    content = f"""
      <p style="margin:0 0 24px">Hi {first_name},</p>
      <p style="margin:0 0 24px">Your Trifecta driver is on the way.</p>
      {(_detail("Estimated arrival", eta.strftime("%H:%M")) if eta else "")}
      {_detail("Appointment", f"{start:%H:%M}–{end:%H:%M}")}
      {vehicle_detail}
      {manage_button}
    """
    return f"Your Trifecta driver is on the way — {reference}", _email_shell(
        "Your Trifecta driver is on the way", content
    )


def render_booking_confirmation(payload: dict[str, Any]) -> tuple[str, str]:
    reference = escape(str(payload["booking_reference"]))
    first_name = escape(str(payload["customer_first_name"]))
    timezone = ZoneInfo(str(payload["timezone"]))
    start = datetime.fromisoformat(str(payload["scheduled_start"])).astimezone(timezone)
    end = datetime.fromisoformat(str(payload["scheduled_end"])).astimezone(timezone)
    total_minor = int(payload["total_amount_minor"])
    currency = escape(str(payload["currency_code"]))
    payment_choice = str(payload["payment_choice"])
    payment_label = "Pay after service" if payment_choice == "pay_after_service" else "Pay now"
    payment_status = escape(str(payload["payment_status"]).replace("_", " ").title())
    manage_url = escape(str(payload["management_url"]), quote=True)
    address = escape(str(payload["written_address"]))
    cutoff = int(payload["cancellation_cutoff_hours"])
    vehicle_rows = "".join(
        "<li style='margin:0 0 8px'>"
        f"<strong>{escape(str(vehicle['make']))} {escape(str(vehicle['model']))}</strong>"
        f" — {escape(str(vehicle['service_name']))}</li>"
        for vehicle in payload.get("vehicles", [])
    )
    content = f"""
      <p style="margin:0 0 24px">Hi {first_name},</p>
      <p style="margin:0 0 24px">Your appointment is booked.</p>
      {_detail("Booking", reference)}
      {_detail("Date", start.strftime("%d %B %Y"))}
      {_detail("Time", f"{start:%H:%M}–{end:%H:%M}")}
      {_detail("Vehicles", str(payload["vehicle_count"]))}
      {f"<ul style='padding-left:20px;margin:0 0 20px'>{vehicle_rows}</ul>" if vehicle_rows else ""}
      {_detail("Location", address)}
      {_detail("Total", f"{currency} {total_minor / 100:,.2f}")}
      {_detail("Payment", f"{payment_label} · {payment_status}")}
      <p style="margin:30px 0">
        <a href="{manage_url}" style="background:#D65A1F;color:#fff;text-decoration:none;
          padding:13px 22px;border-radius:8px;display:inline-block;font-weight:700">
          Manage booking
        </a>
      </p>
      <p style="color:#8A8A88;font-size:14px;line-height:1.6;margin:0">
        Need to make a change? Cancellation requests can be submitted until {cutoff} hours
        before the appointment.
      </p>
    """
    return f"Your Trifecta booking is confirmed — {reference}", _email_shell(
        "Your Trifecta booking is confirmed", content
    )


def _detail(label: str, value: str) -> str:
    return (
        "<div style='margin:0 0 16px'>"
        "<div style='color:#8A8A88;font-size:12px;font-weight:700;"
        f"text-transform:uppercase;letter-spacing:.06em'>{label}</div>"
        f"<div style='color:#241C1A;font-size:16px;font-weight:700;margin-top:3px'>{value}</div>"
        "</div>"
    )


def _email_shell(title: str, content: str) -> str:
    return f"""<!doctype html>
<html><body style="margin:0;background:#F4EDE4;font-family:Arial,sans-serif;color:#241C1A">
  <div style="display:none;max-height:0;overflow:hidden">{escape(title)}</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
    style="background:#F4EDE4">
    <tr><td align="center" style="padding:32px 16px">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
        style="max-width:600px;background:#fff;border-radius:16px">
        <tr><td style="padding:32px">
          <div style="font-size:20px;font-weight:800;color:#D65A1F;
            margin-bottom:26px">TRIFECTA</div>
          <h1 style="font-size:28px;line-height:1.2;margin:0 0 24px;color:#241C1A">
            {escape(title)}
          </h1>
          {content}
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""
