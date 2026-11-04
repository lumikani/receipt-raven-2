import type { ClassificationRule, ClassificationRuleRequest } from '@/api/generated/model';

import type { RuleFormValue } from './RuleFormFields';

export function blankRuleForm(): RuleFormValue {
  return { pattern: '', account: '', share: '', maxTypos: 1, enabled: true };
}

export function ruleToForm(rule: ClassificationRule): RuleFormValue {
  return {
    pattern: rule.pattern,
    account: rule.expense_account,
    share: rule.flatmate_share_override == null ? '' : String(rule.flatmate_share_override),
    maxTypos: rule.max_typos,
    enabled: rule.enabled,
  };
}

function inShareRange(share: number): boolean {
  return share >= 0 && share <= 100;
}

/** Parse a required share percentage (0-100); blank or out of range is null. */
export function parseRequiredShare(text: string): number | null {
  if (text.trim() === '') return null;
  const parsed = Number(text);
  return Number.isNaN(parsed) || !inShareRange(parsed) ? null : parsed;
}

/** The share override of a rule form: blank means the account default (null). */
function shareOverrideOf(share: string): { value: number | null; valid: boolean } {
  if (share.trim() === '') return { value: null, valid: true };
  const parsed = Number(share);
  if (Number.isNaN(parsed) || !inShareRange(parsed)) return { value: null, valid: false };
  return { value: parsed, valid: true };
}

/** The API request body for a rule form, and whether the form can be saved. */
export function ruleFormToRequest(form: RuleFormValue): {
  body: ClassificationRuleRequest;
  canSave: boolean;
} {
  const pattern = form.pattern.trim();
  const account = form.account.trim();
  const share = shareOverrideOf(form.share);
  return {
    body: {
      pattern,
      max_typos: form.maxTypos,
      expense_account: account,
      flatmate_share_override: share.value,
      enabled: form.enabled,
    },
    canSave: pattern !== '' && account !== '' && share.valid,
  };
}
