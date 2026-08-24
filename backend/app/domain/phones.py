import phonenumbers


def normalize_phone_number(value: object, default_region: str = "AE") -> str:
    if not isinstance(value, str):
        raise ValueError("Enter a valid international phone number.")
    try:
        number = phonenumbers.parse(value, default_region)
    except phonenumbers.NumberParseException as exc:
        raise ValueError("Enter a valid international phone number.") from exc
    if not phonenumbers.is_valid_number(number):
        raise ValueError("Enter a valid international phone number.")
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
