import { ListFilter, Pencil, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { apiErrorMessage } from '@/api/errors';
import type { ClassificationRule } from '@/api/generated/model';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { EmptyState } from '@/components/common/EmptyState';
import { PageHeader } from '@/components/common/PageHeader';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useRuleMutations, useRulesQuery } from '@/hooks/useClassification';

import { RuleDialog } from './RuleDialog';
import { blankRuleForm, ruleToForm } from './ruleForm';
import type { EditableRule } from './RuleFormFields';
import { ShareDefaultsSection } from './ShareDefaultsSection';

/**
 * The rules management screen: every classification rule in a table, created
 * and edited in a dialog, with enable/disable and delete per row and the
 * per-account default flatmate shares below.
 */
export function RulesPage() {
  const rulesQuery = useRulesQuery();
  const rules = rulesQuery.data?.items ?? [];
  const { setRuleEnabled, deleteRule } = useRuleMutations();
  const [editing, setEditing] = useState<EditableRule | null>(null);
  const [deleting, setDeleting] = useState<ClassificationRule | null>(null);

  const toggleEnabled = async (rule: ClassificationRule, enabled: boolean) => {
    try {
      await setRuleEnabled(rule.id, enabled);
      toast.success(enabled ? `Rule “${rule.pattern}” enabled` : `Rule “${rule.pattern}” disabled`);
    } catch (error) {
      toast.error(apiErrorMessage(error, 'The rule could not be enabled or disabled.'));
    }
  };

  const confirmDelete = async () => {
    if (!deleting) return;
    try {
      await deleteRule(deleting.id);
      toast.success(`Rule “${deleting.pattern}” deleted`);
      setDeleting(null);
    } catch (error) {
      toast.error(apiErrorMessage(error, 'The rule could not be deleted.'));
    }
  };

  return (
    <>
      <PageHeader
        title="Classification rules"
        description="Every receipt item is matched against these patterns, best match wins. Disabled rules never match."
        actions={
          <Button type="button" onClick={() => setEditing({ id: null, ...blankRuleForm() })}>
            <Plus /> Add rule
          </Button>
        }
      />

      {rulesQuery.isPending && <Skeleton aria-label="Loading rules" className="h-48 w-full" />}
      {rulesQuery.isError && (
        <p role="alert" className="text-destructive">
          The rules could not be loaded.
        </p>
      )}
      {rulesQuery.data && rules.length === 0 && (
        <EmptyState icon={ListFilter} title="No rules yet">
          Add a rule so matching receipt items get an expense account and flatmate share
          automatically.
        </EmptyState>
      )}
      {rules.length > 0 && (
        <Table aria-label="Classification rules">
          <TableHeader>
            <TableRow>
              <TableHead>Pattern</TableHead>
              <TableHead>Expense account</TableHead>
              <TableHead className="text-right">Share</TableHead>
              <TableHead className="text-right">Max typos</TableHead>
              <TableHead>Enabled</TableHead>
              <TableHead aria-label="Actions" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {rules.map((rule) => (
              <TableRow key={rule.id}>
                <TableCell className="font-medium">{rule.pattern}</TableCell>
                <TableCell>{rule.expense_account}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {rule.flatmate_share_override == null
                    ? 'default'
                    : `${rule.flatmate_share_override}%`}
                </TableCell>
                <TableCell className="text-right tabular-nums">{rule.max_typos}</TableCell>
                <TableCell>
                  <Checkbox
                    checked={rule.enabled}
                    aria-label={`Rule ${rule.pattern} enabled`}
                    onCheckedChange={(checked) => void toggleEnabled(rule, checked === true)}
                  />
                </TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label={`Edit rule ${rule.pattern}`}
                      onClick={() => setEditing({ id: rule.id, ...ruleToForm(rule) })}
                    >
                      <Pencil />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label={`Delete rule ${rule.pattern}`}
                      onClick={() => setDeleting(rule)}
                    >
                      <Trash2 />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <RuleDialog editing={editing} onChange={setEditing} onClose={() => setEditing(null)} />
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={deleting ? `Delete rule “${deleting.pattern}”?` : 'Delete rule'}
        confirmLabel="Delete rule"
        destructive
        onConfirm={() => void confirmDelete()}
      >
        Items that matched this rule fall back to the account default (or get flagged when the
        account has none) on the next re-classification.
      </ConfirmDialog>

      <ShareDefaultsSection />
    </>
  );
}
