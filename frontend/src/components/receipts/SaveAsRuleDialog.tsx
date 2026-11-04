import { useState } from 'react';
import { toast } from 'sonner';

import { apiErrorMessage } from '@/api/errors';
import { Combobox } from '@/components/common/Combobox';
import { NumberInput } from '@/components/common/NumberInput';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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

  const [pattern, setPattern] = useState(() => (item ? normalizeName(item.name) : ''));
  const [account, setAccount] = useState(item?.expense_account ?? '');
  const [share, setShare] = useState(item ? String(item.flatmate_share) : '');
  const [maxTypos, setMaxTypos] = useState(1);
  if (!item) return null;

  const accountDefault = shareDefaults.find((entry) => entry.expense_account === account)?.share;
  const trimmedPattern = pattern.trim();
  const shareOverride = share.trim() === '' ? null : Number(share);
  const shareValid =
    shareOverride === null ||
    (!Number.isNaN(shareOverride) && shareOverride >= 0 && shareOverride <= 100);
  const canSave = trimmedPattern !== '' && account.trim() !== '' && shareValid;

  const save = async () => {
    try {
      await createRule({
        pattern: trimmedPattern,
        max_typos: maxTypos,
        expense_account: account,
        flatmate_share_override: shareOverride,
        enabled: true,
      });
      toast.success(`Rule “${trimmedPattern}” saved`);
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
        <div className="grid gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="rule-pattern">Pattern (normalized product name)</Label>
            <Input
              id="rule-pattern"
              value={pattern}
              onChange={(event) => setPattern(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Expense account</Label>
            <Combobox
              label="Rule expense account"
              value={account}
              onChange={setAccount}
              options={expenseAccounts.names}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="rule-share">Flatmate share override (blank = account default)</Label>
              <NumberInput
                id="rule-share"
                min={0}
                max={100}
                step={1}
                placeholder={
                  accountDefault !== undefined ? `default: ${accountDefault}%` : 'default: none'
                }
                value={share}
                onChange={(event) => setShare(event.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="rule-typos">Max typos</Label>
              <NumberInput
                id="rule-typos"
                min={0}
                max={2}
                step={1}
                value={maxTypos}
                onChange={(event) => {
                  const parsed = event.target.valueAsNumber;
                  setMaxTypos(Number.isNaN(parsed) ? 0 : parsed);
                }}
              />
            </div>
          </div>
        </div>
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
