"""The flatmate share percentage, shared by receipts and classification."""

from src.domain.common.exceptions import ValidationError

SHARE_MIN = 0.0
SHARE_MAX = 100.0


def check_share(value: float, field_name: str) -> None:
    """Validate a flatmate share percentage (0-100)."""
    if not SHARE_MIN <= value <= SHARE_MAX:
        raise ValidationError(
            "Flatmate share must be between 0 and 100", field=field_name, value=value
        )
