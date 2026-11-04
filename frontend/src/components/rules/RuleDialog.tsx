import { toast } from 'sonner';

import { apiErrorMessage } from '@/api/errors';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useAccountShareDefaults, useRuleMutations } from '@/hooks/useClassification';
import { useExpenseAccounts } from '@/hooks/useLedger';

import { ruleFormToRequest } from './ruleForm';
import { RuleFormFields, type EditableRule } from './RuleFormFields';

/**
 * The create/edit dialog for one classification rule. The parent owns the
 * form state (`editing`); saving goes through the rules CRUD endpoints.
 */
export function RuleDialog({
  editing,
  onChange,
  onClose,
}: {
  editing: EditableRule | null;
  onChange: (next: EditableRule) => void;
  onClose: () => void;
}) {
  const expenseAccounts = useExpenseAccounts();
  const shareDefaults = useAccountShareDefaults();
  const { createRule, updateRule, isSaving } = useRuleMutations();

  if (!editing) return null;

  const accountDefault = shareDefaults.find(
    (entry) => entry.expense_account === editing.account
  )?.share;
  const { body, canSave } = ruleFormToRequest(editing);

  const save = async () => {
    try {
      if (editing.id === null) {
        await createRule(body);
        toast.success(`Rule “${body.pattern}” created`);
      } else {
        await updateRule(editing.id, body);
        toast.success(`Rule “${body.pattern}” saved`);
      }
      onClose();
    } catch (error) {
      toast.error(apiErrorMessage(error, 'The rule could not be saved.'));
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {editing.id !== null ? `Edit rule “${editing.pattern}”` : 'New rule'}
          </DialogTitle>
          <DialogDescription>
            Every item whose normalized name matches this pattern gets the expense account and
            flatmate share below.
          </DialogDescription>
        </DialogHeader>
        <RuleFormFields
          value={editing}
          onChange={(patch) => onChange({ ...editing, ...patch })}
          expenseAccounts={expenseAccounts.names}
          accountDefaultShare={accountDefault}
        />
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
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
