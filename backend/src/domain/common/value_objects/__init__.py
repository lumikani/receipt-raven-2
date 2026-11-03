"""Value objects shared across domain modules.

Entity ids live here rather than in their owning module so that one module can
reference another module's aggregate by a typed id without importing it.
"""

from .ids import (
    AccountShareDefaultId,
    ClassificationRuleId,
    ReceiptId,
    ReceiptItemId,
    ReceiptJobId,
)
from .share import SHARE_MAX, SHARE_MIN, check_share

__all__ = [
    "SHARE_MAX",
    "SHARE_MIN",
    "AccountShareDefaultId",
    "ClassificationRuleId",
    "ReceiptId",
    "ReceiptItemId",
    "ReceiptJobId",
    "check_share",
]
