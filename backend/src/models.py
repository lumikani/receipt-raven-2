"""ORM model aggregator.

ORM models live per module under ``src/infrastructure/<module>/orm/``. This
module imports every one of them so they are registered on ``Base.metadata``,
which Alembic autogenerate and the test database read. Add each new model here.
"""

from src.database import Base
from src.infrastructure.classification.orm.classification_model import (
    AccountShareDefaultModel,
    ClassificationRuleModel,
)
from src.infrastructure.jobs.orm.receipt_job_model import ReceiptJobModel
from src.infrastructure.receipts.orm.receipt_model import ReceiptItemModel, ReceiptModel

__all__ = [
    "AccountShareDefaultModel",
    "Base",
    "ClassificationRuleModel",
    "ReceiptItemModel",
    "ReceiptJobModel",
    "ReceiptModel",
]
