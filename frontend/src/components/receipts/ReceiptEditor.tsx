import { zodResolver } from '@hookform/resolvers/zod';
import { useNavigate } from '@tanstack/react-router';
import { AlertTriangle, BookCheck, CreditCard, Loader2, RefreshCw, Save } from 'lucide-react';
import { Controller, FormProvider, useForm, useFormContext, useWatch } from 'react-hook-form';
import { toast } from 'sonner';

import { apiErrorMessage } from '@/api/errors';
import type { OcrIssue, Receipt } from '@/api/generated/model';
import { AmountInput } from '@/components/common/AmountInput';
import { Combobox } from '@/components/common/Combobox';
import { MaskedCard } from '@/components/common/MaskedCard';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { useClassificationMutations } from '@/hooks/useClassification';
import { useAccountRoles, usePayees, useSourceAccounts } from '@/hooks/useLedger';
import { useReceiptMutations } from '@/hooks/useReceipts';
import { formatCurrency, formatSignedCurrency } from '@/lib/format';
import { isBalanced, itemsSum, missingAmount } from '@/lib/receiptMath';
import { cn } from '@/lib/utils';

import {
  amountOf,
  BOOKABLE_CURRENCIES,
  COMMON_CURRENCIES,
  receiptFormSchema,
  toFormValues,
  toRequest,
  type ReceiptFormValues,
} from './receiptForm';
import { ReceiptItemsEditor } from './ReceiptItemsEditor';
import { RoutingPreview } from './RoutingPreview';

function Field({
  id,
  label,
  error,
  children,
  className,
}: {
  id: string;
  label: string;
  error?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('flex min-w-0 flex-col gap-1.5', className)}>
      <Label htmlFor={id}>{label}</Label>
      {children}
      {error && <p className="text-destructive text-xs">{error}</p>}
    </div>
  );
}

function DateWarning({ issue }: { issue: OcrIssue }) {
  const severe = issue.level !== 'WARN';
  return (
    <p
      role="note"
      className={cn(
        'flex items-center gap-1.5 text-xs font-medium',
        severe ? 'text-destructive' : 'text-warning-foreground dark:text-warning'
      )}
    >
      <AlertTriangle className="size-3.5 shrink-0" />
      {issue.message}
    </p>
  );
}

function DetailsFields({
  dateIssue,
  cardLastDigits,
}: {
  dateIssue: OcrIssue | null | undefined;
  cardLastDigits?: string | null;
}) {
  const { control, register, formState } = useFormContext<ReceiptFormValues>();
  const sourceAccounts = useSourceAccounts();
  const payees = usePayees();
  const { roles } = useAccountRoles();
  const errors = formState.errors;
  const date = useWatch({ control, name: 'date' });
  const currency = useWatch({ control, name: 'currency' });
  const sourceAccount = useWatch({ control, name: 'source_account' });
  const dirtyDate = formState.dirtyFields.date;
  // A source account without a configured role routes as a personal card and is flagged.
  const unconfigured =
    !!sourceAccount &&
    !!roles &&
    !roles.personal_cards.includes(sourceAccount) &&
    roles.shared_card !== sourceAccount;

  return (
    <section aria-label="Receipt details" className="grid gap-4 sm:grid-cols-2">
      <Field id="payee" label="Payee" error={errors.payee?.message}>
        <Controller
          control={control}
          name="payee"
          render={({ field, fieldState }) => (
            <Combobox
              id="payee"
              label="Payee"
              placeholder="Shop or service"
              value={field.value}
              onChange={field.onChange}
              options={payees}
              allowCustom
              invalid={!!fieldState.error}
            />
          )}
        />
      </Field>
      <Field id="source-account" label="Paid from" error={errors.source_account?.message}>
        <Controller
          control={control}
          name="source_account"
          render={({ field, fieldState }) => (
            <Combobox
              id="source-account"
              label="Paid from"
              placeholder="Account"
              value={field.value}
              onChange={field.onChange}
              options={sourceAccounts.names}
              invalid={!!fieldState.error}
            />
          )}
        />
        {unconfigured && (
          <p
            role="note"
            className="text-warning-foreground dark:text-warning flex items-center gap-1.5 text-xs font-medium"
          >
            <AlertTriangle className="size-3.5 shrink-0" />
            {sourceAccount} has no configured account role — treated as a personal card.
          </p>
        )}
        {cardLastDigits && (
          <p role="note" className="text-muted-foreground flex items-center gap-1.5 text-xs">
            <CreditCard className="size-3.5 shrink-0" />
            Card <MaskedCard digits={cardLastDigits} /> on the receipt
          </p>
        )}
      </Field>
      <Field id="date" label="Date" error={errors.date?.message}>
        <Input
          id="date"
          type="date"
          aria-invalid={!!errors.date || undefined}
          {...register('date')}
        />
        {dateIssue && !dirtyDate && date && <DateWarning issue={dateIssue} />}
      </Field>
      <Field id="total" label="Total" error={errors.total_sum?.message ?? errors.currency?.message}>
        <div className="flex gap-2">
          <Controller
            control={control}
            name="total_sum"
            render={({ field, fieldState }) => (
              <AmountInput
                id="total"
                currency={currency}
                className="min-w-0 flex-1"
                aria-invalid={!!fieldState.error || undefined}
                value={field.value}
                onChange={field.onChange}
                onBlur={field.onBlur}
              />
            )}
          />
          <div className="w-28 shrink-0">
            <Controller
              control={control}
              name="currency"
              render={({ field, fieldState }) => (
                <Combobox
                  label="Currency"
                  value={field.value}
                  onChange={(value) => field.onChange(value.trim().toUpperCase())}
                  options={COMMON_CURRENCIES}
                  allowCustom
                  invalid={!!fieldState.error}
                />
              )}
            />
          </div>
        </div>
      </Field>
      <Field id="description" label="Description" className="sm:col-span-2">
        <Textarea
          id="description"
          rows={2}
          placeholder="What was bought, for the ledger's narration"
          {...register('description')}
        />
      </Field>
    </section>
  );
}

/** Re-run the classification rules on this receipt; overridden rows keep their values. */
function ReclassifyButton({ receipt }: { receipt: Receipt }) {
  const form = useFormContext<ReceiptFormValues>();
  const { reclassifyReceipt, isSaving } = useClassificationMutations();

  const reclassify = async () => {
    try {
      const updated = await reclassifyReceipt(receipt.id);
      form.reset(toFormValues(updated));
      toast.success('Receipt re-classified');
    } catch (error) {
      toast.error(apiErrorMessage(error, 'The receipt could not be re-classified.'));
    }
  };

  return (
    <Button
      type="button"
      variant="outline"
      size="lg"
      disabled={isSaving}
      onClick={() => void reclassify()}
      className="max-sm:w-full"
    >
      <RefreshCw /> Re-classify
    </Button>
  );
}

/** Sum of items against the total, and the buttons that save or approve. */
function ActionBar({ receipt, isSaving }: { receipt?: Receipt; isSaving: boolean }) {
  const { control } = useFormContext<ReceiptFormValues>();
  const isNew = !receipt;
  const items = useWatch({ control, name: 'items' });
  const total = amountOf(useWatch({ control, name: 'total_sum' }));
  const currency = useWatch({ control, name: 'currency' }).toUpperCase();
  const prices = items.map((item) => amountOf(item.price));
  const balanced = isBalanced(total, prices);
  const difference = -missingAmount(total, prices);
  // A new receipt can be saved in any currency; booking waits for EUR-only.
  const bookable = isNew || BOOKABLE_CURRENCIES.has(currency);

  return (
    <div className="bg-card/95 sticky bottom-[calc(5rem+env(safe-area-inset-bottom))] z-20 mt-6 rounded-xl border p-4 shadow-lg backdrop-blur md:bottom-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <dl className="flex gap-6 text-sm tabular-nums">
          <div>
            <dt className="text-muted-foreground">Items</dt>
            <dd className={cn('font-semibold', !balanced && 'text-destructive')}>
              {formatCurrency(itemsSum(prices), currency)}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Total</dt>
            <dd className="font-semibold">{formatCurrency(total, currency)}</dd>
          </div>
          {!balanced && (
            <div>
              <dt className="text-muted-foreground">Difference</dt>
              <dd
                className="text-warning-foreground dark:text-warning font-semibold"
                aria-label="Difference"
              >
                {formatSignedCurrency(difference, currency)}
              </dd>
            </div>
          )}
        </dl>
        <div className="flex flex-wrap items-center gap-2 max-sm:w-full">
          {receipt && <ReclassifyButton receipt={receipt} />}
          <Button
            type="submit"
            size="lg"
            disabled={isSaving || !balanced || !bookable}
            className="max-sm:w-full"
          >
            {isSaving ? <Loader2 className="animate-spin" /> : isNew ? <Save /> : <BookCheck />}
            {isNew ? 'Save receipt' : 'Approve and book'}
          </Button>
        </div>
      </div>
      {!bookable && (
        <p role="note" className="text-muted-foreground mt-2 text-xs">
          Receipts in {currency} cannot be booked to the ledger yet. It stays here to review until
          they can.
        </p>
      )}
      {bookable && !balanced && (
        <p className="text-muted-foreground mt-2 text-xs">
          The items must add up to the total before the receipt can be{' '}
          {isNew ? 'saved' : 'approved'}.
        </p>
      )}
    </div>
  );
}

/**
 * The form for a receipt waiting for review, or for a new one typed by hand.
 * Approving saves the edits and books the receipt to the ledger.
 */
export function ReceiptEditor({ receipt }: { receipt?: Receipt }) {
  const navigate = useNavigate();
  const { createReceipt, approveReceipt, isSaving } = useReceiptMutations();
  const form = useForm<ReceiptFormValues>({
    resolver: zodResolver(receiptFormSchema),
    defaultValues: toFormValues(receipt),
  });

  const submit = async (values: ReceiptFormValues) => {
    const request = toRequest(values);
    try {
      if (receipt) {
        await approveReceipt(receipt.id, request);
        toast.success('Receipt approved and booked to the ledger');
        await navigate({ to: '/' });
      } else {
        const created = await createReceipt(request);
        toast.success('Receipt saved. Approve it to book it to the ledger.');
        await navigate({ to: '/receipts/$receiptId', params: { receiptId: String(created.id) } });
      }
    } catch (error) {
      toast.error(apiErrorMessage(error, 'The receipt could not be saved.'));
    }
  };

  return (
    <FormProvider {...form}>
      <form onSubmit={form.handleSubmit(submit)} noValidate aria-label="Receipt">
        <div className="flex flex-col gap-8">
          <DetailsFields
            dateIssue={receipt?.ocr_notes?.suspicious_date}
            cardLastDigits={receipt?.card_last_digits}
          />
          <ReceiptItemsEditor showFlags={!!receipt} />
          {receipt && <RoutingPreview receiptId={receipt.id} />}
        </div>
        <ActionBar receipt={receipt} isSaving={isSaving} />
      </form>
    </FormProvider>
  );
}
