"""Mappers for the classification ORM models <-> domain aggregates."""

from src.domain.classification.entities.account_share_default import AccountShareDefault
from src.domain.classification.entities.classification_rule import ClassificationRule
from src.domain.common.value_objects import AccountShareDefaultId, ClassificationRuleId
from src.infrastructure.classification.orm.classification_model import (
    AccountShareDefaultModel,
    ClassificationRuleModel,
)
from src.infrastructure.common.mappers import orm_id


class ClassificationRuleMapper:
    """Convert between ClassificationRule and its row."""

    def to_domain(self, orm_model: ClassificationRuleModel) -> ClassificationRule:
        return ClassificationRule.create_with_id(
            id=ClassificationRuleId(orm_model.id),
            pattern=orm_model.pattern,
            max_typos=orm_model.max_typos,
            expense_account=orm_model.expense_account,
            flatmate_share_override=orm_model.flatmate_share_override,
            enabled=orm_model.enabled,
            created_at=orm_model.created_at,
        )

    def to_orm(
        self, domain_entity: ClassificationRule, orm_model: ClassificationRuleModel | None = None
    ) -> ClassificationRuleModel:
        if orm_model is None:
            orm_model = ClassificationRuleModel(id=orm_id(domain_entity.id))
        orm_model.pattern = domain_entity.pattern
        orm_model.normalized_pattern = domain_entity.normalized_pattern
        orm_model.max_typos = domain_entity.max_typos
        orm_model.expense_account = domain_entity.expense_account
        orm_model.flatmate_share_override = domain_entity.flatmate_share_override
        orm_model.enabled = domain_entity.enabled
        orm_model.created_at = domain_entity.created_at
        return orm_model


class AccountShareDefaultMapper:
    """Convert between AccountShareDefault and its row."""

    def to_domain(self, orm_model: AccountShareDefaultModel) -> AccountShareDefault:
        return AccountShareDefault.create_with_id(
            id=AccountShareDefaultId(orm_model.id),
            expense_account=orm_model.expense_account,
            share=orm_model.share,
            created_at=orm_model.created_at,
        )

    def to_orm(
        self,
        domain_entity: AccountShareDefault,
        orm_model: AccountShareDefaultModel | None = None,
    ) -> AccountShareDefaultModel:
        if orm_model is None:
            orm_model = AccountShareDefaultModel(id=orm_id(domain_entity.id))
        orm_model.expense_account = domain_entity.expense_account
        orm_model.share = domain_entity.share
        orm_model.created_at = domain_entity.created_at
        return orm_model
