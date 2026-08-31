import re
from datetime import datetime
from html import escape
from typing import Any

import httpx

from app.core.providers import observe_provider_call
from app.domain.timezones import TRIFECTA_ZONE

_EMAIL_PATTERN = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")


class ResendDeliveryError(RuntimeError):
    def __init__(self, *, status_code: int, provider_code: str, message: str) -> None:
        self.status_code = status_code
        self.provider_code = provider_code
        self.safe_message = message
        super().__init__(f"Resend {status_code}: {provider_code}: {message}")

    @property
    def retryable(self) -> bool:
        return self.status_code in {408, 429} or 500 <= self.status_code < 600


def _safe_provider_value(value: object, *, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    text = " ".join(value.split())
    text = _EMAIL_PATTERN.sub("[email redacted]", text)
    return text[:240] or fallback


def _delivery_error(response: httpx.Response) -> ResendDeliveryError:
    try:
        body = response.json()
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    return ResendDeliveryError(
        status_code=response.status_code,
        provider_code=_safe_provider_value(body.get("name"), fallback="provider_error"),
        message=_safe_provider_value(body.get("message"), fallback="Request rejected"),
    )


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
        if response.is_error:
            raise _delivery_error(response)


def render_email(notification_type: str, payload: dict[str, Any]) -> tuple[str, str]:
    if notification_type == "booking_confirmed":
        return render_booking_confirmation(payload)
    if notification_type == "driver_en_route":
        return render_driver_en_route(payload)
    if notification_type == "booking_rescheduled":
        return render_booking_rescheduled(payload)
    if notification_type == "job_completed":
        return render_job_completed(payload)
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
    if notification_type == "appointment_reminder":
        return render_appointment_reminder(payload)
    if notification_type == "team_arrived":
        return render_simple_booking_update(
            payload,
            title="Your Trifecta team has arrived",
            message="Your Trifecta team has arrived at the service location.",
            subject_prefix="Your Trifecta team has arrived",
        )
    if notification_type == "team_delayed":
        minutes = int(payload["delay_minutes"])
        return render_team_delayed(payload, minutes)
    if notification_type == "payment_pending":
        return render_simple_booking_update(
            payload,
            title="Payment remains pending",
            message=(
                "Your service is complete and payment remains pending. "
                "Please contact Trifecta if you need assistance."
            ),
            subject_prefix="Payment pending for your Trifecta booking",
        )
    if notification_type == "payment_received":
        return render_payment_received(payload)
    if notification_type == "booking_cancelled":
        return render_simple_booking_update(
            payload,
            title="Your booking has been cancelled",
            message="Your cancellation request has been approved and the booking is cancelled.",
            subject_prefix="Your Trifecta booking was cancelled",
        )
    raise ValueError(f"Unsupported notification type {notification_type!r}")


def render_appointment_reminder(payload: dict[str, Any]) -> tuple[str, str]:
    reference = escape(str(payload["booking_reference"]))
    first_name = escape(str(payload["customer_first_name"]))
    start, end = _scheduled_times(payload)
    manage_url = escape(str(payload["management_url"]), quote=True)
    content = f"""
      <p style="margin:0 0 24px">Hi {first_name},</p>
      <p style="margin:0 0 24px">This is a reminder about your upcoming Trifecta appointment.</p>
      {_detail("Booking", reference)}
      {_detail("Date", start.strftime("%d %B %Y"))}
      {_detail("Time", f"{start:%H:%M}–{end:%H:%M}")}
      <p style="margin:30px 0"><a href="{manage_url}"
        style="background:#D65A1F;color:#fff;text-decoration:none;padding:13px 22px;
        border-radius:8px;display:inline-block;font-weight:700">View booking</a></p>
    """
    return f"Reminder: your Trifecta appointment — {reference}", _email_shell(
        "Your appointment is coming up", content
    )


def render_simple_booking_update(
    payload: dict[str, Any], *, title: str, message: str, subject_prefix: str
) -> tuple[str, str]:
    reference = escape(str(payload["booking_reference"]))
    first_name = escape(str(payload["customer_first_name"]))
    manage_url = escape(str(payload["management_url"]), quote=True)
    content = f"""
      <p style="margin:0 0 24px">Hi {first_name},</p>
      <p style="margin:0 0 24px">{escape(message)}</p>
      {_detail("Booking", reference)}
      <p style="margin:30px 0"><a href="{manage_url}"
        style="background:#D65A1F;color:#fff;text-decoration:none;padding:13px 22px;
        border-radius:8px;display:inline-block;font-weight:700">View booking</a></p>
    """
    return f"{subject_prefix} — {reference}", _email_shell(title, content)


def render_team_delayed(payload: dict[str, Any], minutes: int) -> tuple[str, str]:
    reference = escape(str(payload["booking_reference"]))
    first_name = escape(str(payload["customer_first_name"]))
    start, end = _scheduled_times(payload)
    manage_url = escape(str(payload["management_url"]), quote=True)
    content = f"""
      <p style="margin:0 0 24px">Hi {first_name},</p>
      <p style="margin:0 0 24px">Your Trifecta team is running approximately
        {minutes} minutes late.</p>
      {_detail("Booking", reference)}
      {_detail("Scheduled appointment", f"{start:%H:%M}–{end:%H:%M} UAE time")}
      <p style="margin:30px 0"><a href="{manage_url}"
        style="background:#D65A1F;color:#fff;text-decoration:none;padding:13px 22px;
        border-radius:8px;display:inline-block;font-weight:700">View booking</a></p>
    """
    return f"Update about your Trifecta appointment — {reference}", _email_shell(
        "A quick update about your appointment", content
    )


def render_booking_rescheduled(payload: dict[str, Any]) -> tuple[str, str]:
    reference = escape(str(payload["booking_reference"]))
    first_name = escape(str(payload["customer_first_name"]))
    start, end = _scheduled_times(payload)
    manage_url = escape(str(payload["management_url"]), quote=True)
    content = f"""
      <p style="margin:0 0 24px">Hi {first_name},</p>
      <p style="margin:0 0 24px">Your Trifecta appointment has been rescheduled.</p>
      {_detail("Booking", reference)}
      {_detail("New date", start.strftime("%d %B %Y"))}
      {_detail("New scheduled time", f"{start:%H:%M}–{end:%H:%M}")}
      <p style="margin:30px 0"><a href="{manage_url}"
        style="background:#D65A1F;color:#fff;text-decoration:none;padding:13px 22px;
        border-radius:8px;display:inline-block;font-weight:700">View booking</a></p>
    """
    return f"Your Trifecta booking was rescheduled — {reference}", _email_shell(
        "Your appointment has been rescheduled", content
    )


def _human_duration(seconds: int | None) -> str | None:
    if seconds is None:
        return None
    minutes = max(0, round(seconds / 60))
    hours, remainder = divmod(minutes, 60)
    if hours and remainder:
        return f"{hours} hr {remainder} min"
    if hours:
        return f"{hours} hr" if hours == 1 else f"{hours} hrs"
    return f"{remainder} min"


def render_job_completed(payload: dict[str, Any]) -> tuple[str, str]:
    reference = escape(str(payload["booking_reference"]))
    first_name = escape(str(payload["customer_first_name"]))
    start, _end = _scheduled_times(payload)
    duration = _human_duration(
        int(payload["actual_service_duration_seconds"])
        if payload.get("actual_service_duration_seconds") is not None
        else None
    )
    currency = escape(str(payload["currency_code"]))
    paid = str(payload.get("payment_status")) == "paid"
    amount_paid_minor = int(payload.get("amount_paid_minor") or 0)
    payment = (
        _detail("Amount paid", f"{currency} {amount_paid_minor / 100:,.2f}")
        if paid
        else _detail("Payment status", "Pending")
    )
    vehicle_rows = "".join(
        "<li style='margin:0 0 8px'>"
        f"<strong>{escape(str(vehicle['make']))} {escape(str(vehicle['model']))}</strong>"
        f" — {escape(str(vehicle['service_name']))}</li>"
        for vehicle in payload.get("vehicles", [])
    )
    manage_url = escape(str(payload["management_url"]), quote=True)
    content = f"""
      <p style="margin:0 0 24px">Hi {first_name},</p>
      <p style="margin:0 0 24px">Your Trifecta service is complete.</p>
      {_detail("Booking", reference)}
      {_detail("Scheduled service time", start.strftime("%d %B %Y at %H:%M"))}
      {(_detail("Service duration", duration) if duration else "")}
      {f"<ul style='padding-left:20px;margin:0 0 20px'>{vehicle_rows}</ul>" if vehicle_rows else ""}
      {payment}
      <p style="margin:30px 0"><a href="{manage_url}"
        style="background:#D65A1F;color:#fff;text-decoration:none;padding:13px 22px;
        border-radius:8px;display:inline-block;font-weight:700">View booking</a></p>
    """
    return f"Your Trifecta service is complete — {reference}", _email_shell(
        "Your Trifecta service is complete", content
    )


def render_payment_received(payload: dict[str, Any]) -> tuple[str, str]:
    reference = escape(str(payload["booking_reference"]))
    first_name = escape(str(payload["customer_first_name"]))
    invoice_number = escape(str(payload["invoice_number"]))
    currency = escape(str(payload["currency_code"]))
    amount_minor = int(payload["amount_paid_minor"])
    payment_method = escape(
        str(payload.get("payment_method") or "payment").replace("_", " ").title()
    )
    invoice_url = escape(str(payload["invoice_url"]), quote=True)
    content = f"""
      <p style="margin:0 0 24px">Hi {first_name},</p>
      <p style="margin:0 0 24px">We received your payment. Thank you.</p>
      {_detail("Booking", reference)}
      {_detail("Invoice", invoice_number)}
      {_detail("Amount received", f"{currency} {amount_minor / 100:,.2f}")}
      {_detail("Payment method", payment_method)}
      <p style="margin:30px 0"><a href="{invoice_url}"
        style="background:#D65A1F;color:#fff;text-decoration:none;padding:13px 22px;
        border-radius:8px;display:inline-block;font-weight:700">View invoice</a></p>
    """
    return f"Payment received — {reference}", _email_shell("Payment received", content)


def render_driver_en_route(payload: dict[str, Any]) -> tuple[str, str]:
    reference = escape(str(payload["booking_reference"]))
    first_name = escape(str(payload["customer_first_name"]))
    start, end = _scheduled_times(payload)
    eta_value = payload.get("estimated_arrival_at")
    eta = datetime.fromisoformat(str(eta_value)).astimezone(TRIFECTA_ZONE) if eta_value else None
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
    start, end = _scheduled_times(payload)
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


def _scheduled_times(payload: dict[str, Any]) -> tuple[datetime, datetime]:
    start = datetime.fromisoformat(str(payload["scheduled_start"])).astimezone(TRIFECTA_ZONE)
    end = datetime.fromisoformat(str(payload["scheduled_end"])).astimezone(TRIFECTA_ZONE)
    return start, end


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
