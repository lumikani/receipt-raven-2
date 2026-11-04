import { useState } from 'react';
import { toast } from 'sonner';

import { apiErrorMessage } from '@/api/errors';
import { ruleFormToRequest } from '@/components/rules/ruleForm';
import { RuleFormFields, type RuleFormValue } from '@/components/rules/RuleFormFields';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useAccountShareDefaults, useClassificationMutations } from '@/hooks/useClassification';
import { useExpenseAccounts } from '@/hooks/useLedger';
import { normalizeName } from '@/lib/classification';

import type { ReceiptFormItem } from './receiptForm';

/**
 * The "save as rule" flow: a corrected row becomes a permanent classification
 * rule. The pattern is prefilled with the normalized row name, the account is
 * a combobox of the ledger's expense accounts, the share override is blank by
 * default (blank = the account's default share).
 */
export function SaveAsRuleDialog({
  item,
  open,
  onOpenChange,
}: {
  item: ReceiptFormItem | undefined;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const expenseAccounts = useExpenseAccounts();
  const shareDefaults = useAccountShareDefaults();
  const { createRule, isSaving } = useClassificationMutations();

  const [form, setForm] = useState<RuleFormValue>(() => ({
    pattern: item ? normalizeName(item.name) : '',
    account: item?.expense_account ?? '',
    share: item ? String(item.flatmate_share) : '',
    maxTypos: 1,
    enabled: true,
  }));
  if (!item) return null;

  const accountDefault = shareDefaults.find(
    (entry) => entry.expense_account === form.account
  )?.share;
  const { body, canSave } = ruleFormToRequest(form);

  const save = async () => {
    try {
      await createRule(body);
      toast.success(`Rule “${body.pattern}” saved`);
      onOpenChange(false);
    } catch (error) {
      toast.error(apiErrorMessage(error, 'The rule could not be saved.'));
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Save “{item.name}” as a rule</DialogTitle>
          <DialogDescription>
            Every future item matching this pattern gets the account and flatmate share below.
          </DialogDescription>
        </DialogHeader>
        <RuleFormFields
          value={form}
          onChange={(patch) => setForm((prev) => ({ ...prev, ...patch }))}
          expenseAccounts={expenseAccounts.names}
          accountDefaultShare={accountDefault}
          showEnabled={false}
        />
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button disabled={!canSave || isSaving} onClick={() => void save()}>
            Save rule
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
