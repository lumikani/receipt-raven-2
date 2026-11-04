import type { Receipt } from '@/api/generated/model';
import { MaskedCard } from '@/components/common/MaskedCard';
import { formatCurrency, formatDate } from '@/lib/format';

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="bg-muted/50 rounded-lg px-3 py-2">
      <dt className="text-muted-foreground text-xs font-medium">{label}</dt>
      <dd className="mt-0.5 break-words">{children}</dd>
    </div>
  );
}

/** An approved receipt: booked to the ledger, so shown read-only. */
export function ReceiptView({ receipt }: { receipt: Receipt }) {
  return (
    <div className="flex flex-col gap-8">
      <dl aria-label="Receipt details" className="grid gap-2 sm:grid-cols-2">
        <Detail label="Payee">{receipt.payee}</Detail>
        <Detail label="Paid from">{receipt.source_account ?? '—'}</Detail>
        {receipt.card_last_digits && (
          <Detail label="Card">
            <MaskedCard digits={receipt.card_last_digits} />
          </Detail>
        )}
        <Detail label="Date">{formatDate(receipt.date)}</Detail>
        <Detail label="Total">
          <span className="font-semibold tabular-nums">
            {formatCurrency(receipt.total_sum, receipt.currency)}
          </span>
        </Detail>
        <div className="sm:col-span-2">
          <Detail label="Description">{receipt.description ?? '—'}</Detail>
        </div>
      </dl>

      <section aria-labelledby="items-heading">
        <h2 id="items-heading" className="mb-3 text-base font-semibold">
          Items <span className="text-muted-foreground font-normal">({receipt.items.length})</span>
        </h2>
        <ul aria-label="Items" className="divide-y rounded-lg border">
          {receipt.items.map((item) => (
            <li key={item.id} className="flex items-center justify-between gap-4 px-4 py-3">
              <div className="min-w-0">
                <p className="truncate font-medium">{item.name}</p>
                <p className="text-muted-foreground truncate text-xs">{item.expense_account}</p>
              </div>
              <span className="font-medium tabular-nums">
                {formatCurrency(item.price, receipt.currency)}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
