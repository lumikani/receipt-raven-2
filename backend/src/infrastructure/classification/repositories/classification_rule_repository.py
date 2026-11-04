"""Repository for ClassificationRule aggregates."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.classification.entities.classification_rule import ClassificationRule
from src.infrastructure.classification.mappers.classification_mapper import ClassificationRuleMapper
from src.infrastructure.classification.orm.classification_model import ClassificationRuleModel
from src.infrastructure.common.repositories import BaseRepository


class ClassificationRuleRepository(BaseRepository[ClassificationRule, ClassificationRuleModel]):
    """Stores rules; the normalized pattern is unique (DB constraint)."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, ClassificationRuleModel, ClassificationRuleMapper())

    async def find_all(self) -> list[ClassificationRule]:
        """Every rule, oldest first (the fuzzy tie-break order)."""
        stmt = select(ClassificationRuleModel).order_by(
            ClassificationRuleModel.created_at, ClassificationRuleModel.id
        )
        result = await self.db.execute(stmt)
        return [self._mapper.to_domain(row) for row in result.scalars().all()]

    async def find_by_normalized_pattern(
        self, normalized_pattern: str
    ) -> ClassificationRule | None:
        stmt = select(ClassificationRuleModel).where(
            ClassificationRuleModel.normalized_pattern == normalized_pattern
        )
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        return self._mapper.to_domain(row) if row is not None else None
