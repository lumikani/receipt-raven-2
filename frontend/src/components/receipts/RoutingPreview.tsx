import { useMemo, useState } from 'react';
import { useFormContext, useWatch } from 'react-hook-form';

import { Combobox } from '@/components/common/Combobox';
import { useAccountRoles, useSourceAccounts } from '@/hooks/useLedger';
import { formatCsvNumber, routePreview } from '@/lib/routingPreview';

import { amountOf, type ReceiptFormValues } from './receiptForm';

const ROLE_LABELS = {
  'personal-card': 'personal card',
  'shared-card': 'shared card',
  unconfigured: 'personal card (unconfigured — flagged)',
} as const;

/**
 * What approval will do with the receipt as currently edited: the ledger
 * entry and the balancing CSV row (or why there are none), live as the form
 * changes. The "Paid from (preview)" combobox toggles the source account
 * between personal and shared to preview both routings.
 */
export function RoutingPreview({ receiptId }: { receiptId: number }) {
  const { control } = useFormContext<ReceiptFormValues>();
  const payee = useWatch({ control, name: 'payee' });
  const date = useWatch({ control, name: 'date' });
  const description = useWatch({ control, name: 'description' });
  const currency = useWatch({ control, name: 'currency' });
  const sourceAccount = useWatch({ control, name: 'source_account' });
  const items = useWatch({ control, name: 'items' });
  const { roles } = useAccountRoles();
  const sourceAccounts = useSourceAccounts();

  const [sourceOverride, setSourceOverride] = useState<string | null>(null);
  const previewSource = sourceOverride ?? sourceAccount;

  const preview = useMemo(() => {
    if (!roles) return null;
    return routePreview({
      receipt_id: receiptId,
      payee,
      date,
      description: description.trim() || null,
      currency: currency.toUpperCase(),
      source_account: previewSource,
      items: items.map((item) => ({
        name: item.name,
        expense_account: item.expense_account,
        price: amountOf(item.price),
        flatmate_share: item.flatmate_share,
      })),
      roles,
    });
  }, [roles, receiptId, payee, date, description, currency, previewSource, items]);

  if (!preview) return null;

  return (
    <section aria-label="Routing preview" className="bg-muted/30 rounded-xl border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">What approval will do</h3>
        <div className="w-72">
          <Combobox
            label="Paid from (preview)"
            value={previewSource}
            onChange={setSourceOverride}
            options={sourceAccounts.names}
            allowCustom
          />
        </div>
      </div>
      <p className="text-muted-foreground mt-1 text-xs">
        source account role: {ROLE_LABELS[preview.role]}
      </p>
      {preview.entry ? (
        <pre
          aria-label="Ledger entry preview"
          className="bg-card mt-3 overflow-x-auto rounded-lg border p-3 text-xs whitespace-pre tabular-nums"
        >
          {preview.entry.join('\n')}
        </pre>
      ) : (
        <p className="mt-3 text-sm">No ledger entry — the receipt is approved without booking.</p>
      )}
      {preview.csv ? (
        <div className="mt-3">
          <p className="text-xs font-medium">Balancing CSV row</p>
          <pre
            aria-label="CSV row preview"
            className="bg-card mt-1 overflow-x-auto rounded-lg border p-3 text-xs whitespace-pre tabular-nums"
          >
            {`shared_cost;description;purchase_for_flatmate\n${formatCsvNumber(preview.csv.shared_cost)};${preview.csv.description};${formatCsvNumber(preview.csv.purchase_for_flatmate)}`}
          </pre>
        </div>
      ) : (
        <p className="text-muted-foreground mt-3 text-xs">Not exported to the balancing CSV.</p>
      )}
      {preview.notes.length > 0 && (
        <ul className="text-muted-foreground mt-3 list-disc space-y-1 pl-4 text-xs">
          {preview.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
