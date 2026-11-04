import { Plus, Trash2 } from 'lucide-react';
import { useState, type KeyboardEvent } from 'react';
import { toast } from 'sonner';

import { apiErrorMessage } from '@/api/errors';
import type { AccountShareDefault } from '@/api/generated/model';
import { Combobox } from '@/components/common/Combobox';
import { NumberInput } from '@/components/common/NumberInput';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useRuleMutations, useShareDefaultsQuery } from '@/hooks/useClassification';
import { useExpenseAccounts } from '@/hooks/useLedger';

import { parseRequiredShare } from './ruleForm';

/** A 0-100 share input with a % suffix. */
function SharePercentInput({
  ariaLabel,
  value,
  onChange,
  onBlur,
  onKeyDown,
}: {
  ariaLabel: string;
  value: string;
  onChange: (value: string) => void;
  onBlur?: () => void;
  onKeyDown?: (event: KeyboardEvent<HTMLInputElement>) => void;
}) {
  return (
    <div className="relative w-24">
      <NumberInput
        min={0}
        max={100}
        step={1}
        aria-label={ariaLabel}
        className="pr-7 text-right tabular-nums"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onBlur={onBlur}
        onKeyDown={onKeyDown}
      />
      <span className="text-muted-foreground pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2 text-xs">
        %
      </span>
    </div>
  );
}

/** One account's default share, committed to the API on blur or Enter. */
function ShareDefaultRow({ entry }: { entry: AccountShareDefault }) {
  const { setShareDefault, deleteShareDefault } = useRuleMutations();
  const [draft, setDraft] = useState(String(entry.share));
  const [dirty, setDirty] = useState(false);

  const commit = async () => {
    if (!dirty) return;
    setDirty(false);
    const share = parseRequiredShare(draft);
    if (share === null || share === entry.share) {
      setDraft(String(entry.share));
      return;
    }
    try {
      await setShareDefault({ expense_account: entry.expense_account, share });
      toast.success(`Default share of ${entry.expense_account} set to ${share}%`);
    } catch (error) {
      toast.error(apiErrorMessage(error, 'The default share could not be saved.'));
      setDraft(String(entry.share));
    }
  };

  const remove = async () => {
    try {
      await deleteShareDefault(entry.expense_account);
      toast.success(`Default for ${entry.expense_account} removed`);
    } catch (error) {
      toast.error(apiErrorMessage(error, 'The default could not be removed.'));
    }
  };

  return (
    <li className="bg-card flex items-center gap-3 rounded-lg border p-3">
      <span className="min-w-0 flex-1 truncate text-sm">{entry.expense_account}</span>
      <SharePercentInput
        ariaLabel={`Default share of ${entry.expense_account}`}
        value={draft}
        onChange={(value) => {
          setDraft(value);
          setDirty(true);
        }}
        onBlur={() => void commit()}
        onKeyDown={(event) => {
          if (event.key === 'Enter') void commit();
        }}
      />
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label={`Remove default for ${entry.expense_account}`}
        onClick={() => void remove()}
      >
        <Trash2 />
      </Button>
    </li>
  );
}

/**
 * The per-account default flatmate shares, below the rules table. A rule
 * without a share override falls back to its account's default here; an
 * account without a default gets 0% and its items are flagged for review.
 */
export function ShareDefaultsSection() {
  const query = useShareDefaultsQuery();
  const expenseAccounts = useExpenseAccounts();
  const { setShareDefault } = useRuleMutations();
  const [newAccount, setNewAccount] = useState('');
  const [newShare, setNewShare] = useState('50');

  const defaults = query.data?.items ?? [];
  const addable = expenseAccounts.names.filter(
    (account) => !defaults.some((entry) => entry.expense_account === account)
  );
  const parsedShare = parseRequiredShare(newShare);
  const canAdd = newAccount !== '' && parsedShare !== null;

  const add = async () => {
    if (parsedShare === null || newAccount === '') return;
    try {
      await setShareDefault({ expense_account: newAccount, share: parsedShare });
      toast.success(`Default share of ${newAccount} set to ${parsedShare}%`);
      setNewAccount('');
      setNewShare('50');
    } catch (error) {
      toast.error(apiErrorMessage(error, 'The default share could not be saved.'));
    }
  };

  return (
    <section aria-labelledby="share-defaults-heading" className="mt-10">
      <h2 id="share-defaults-heading" className="text-base font-semibold">
        Default flatmate share per account
      </h2>
      <p className="text-muted-foreground mt-1 text-sm">
        Used when a rule has no share override. An account without a default gets 0% and its items
        are flagged for review.
      </p>
      {query.isPending && (
        <Skeleton aria-label="Loading share defaults" className="mt-3 h-24 w-full" />
      )}
      {query.isError && (
        <p role="alert" className="text-destructive mt-3">
          The account defaults could not be loaded.
        </p>
      )}
      {query.data && (
        <>
          <ul className="mt-3 flex flex-col gap-2">
            {defaults.map((entry) => (
              <ShareDefaultRow key={entry.expense_account} entry={entry} />
            ))}
          </ul>
          <div className="bg-card mt-2 flex flex-wrap items-center gap-3 rounded-lg border border-dashed p-3">
            <div className="min-w-0 flex-1">
              <Combobox
                label="Account without a default"
                value={newAccount}
                onChange={setNewAccount}
                options={addable}
                placeholder={
                  addable.length === 0 ? 'Every expense account has a default' : 'Select account…'
                }
              />
            </div>
            <SharePercentInput
              ariaLabel="New default share"
              value={newShare}
              onChange={setNewShare}
            />
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={!canAdd}
              onClick={() => void add()}
            >
              <Plus /> Add default
            </Button>
          </div>
        </>
      )}
    </section>
  );
}
