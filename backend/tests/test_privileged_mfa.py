import time
import uuid

import pytest
from fastapi import HTTPException

from app.auth.mfa import require_privileged_totp
from app.auth.verifier import VerifiedIdentity


@pytest.mark.parametrize(
    "claims",
    [
        {},
        {"aal": "aal1", "user_metadata": {"aal": "aal2"}},
        {"aal": "aal2"},
        {"aal": "aal2", "amr": [{"method": "password", "timestamp": time.time()}]},
        {"aal": "aal2", "amr": [{"method": "totp", "timestamp": time.time() + 1000}]},
    ],
)
def test_missing_or_forged_assurance_denied(claims):
    with pytest.raises(HTTPException) as e:
        require_privileged_totp(VerifiedIdentity(uuid.uuid4(), claims), sensitive=False)
    assert e.value.status_code == 403


def test_recent_totp_required_for_privileged_mutations():
    identity = VerifiedIdentity(
        uuid.uuid4(), {"aal": "aal2", "amr": [{"method": "totp", "timestamp": time.time() - 600}]}
    )
    require_privileged_totp(identity, sensitive=False)
    with pytest.raises(HTTPException) as e:
        require_privileged_totp(identity, sensitive=True)
    assert e.value.detail["code"] == "MFA_REAUTHENTICATION_REQUIRED"
    require_privileged_totp(
        VerifiedIdentity(
            uuid.uuid4(), {"aal": "aal2", "amr": [{"method": "totp", "timestamp": time.time()}]}
        ),
        sensitive=True,
    )


def test_small_native_totp_clock_skew_is_bounded():
    require_privileged_totp(
        VerifiedIdentity(
            uuid.uuid4(), {"aal": "aal2", "amr": [{"method": "totp", "timestamp": time.time() + 2}]}
        ),
        sensitive=True,
    )
    with pytest.raises(HTTPException):
        require_privileged_totp(
            VerifiedIdentity(
                uuid.uuid4(),
                {"aal": "aal2", "amr": [{"method": "totp", "timestamp": time.time() + 20}]},
            ),
            sensitive=True,
        )
