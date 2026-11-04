import { BookmarkPlus, Combine, CornerDownLeft, Plus, Trash2, X } from 'lucide-react';
import { useState } from 'react';
import { Controller, useFieldArray, useFormContext, useWatch } from 'react-hook-form';

import { AmountInput } from '@/components/common/AmountInput';
import { Combobox } from '@/components/common/Combobox';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { NumberInput } from '@/components/common/NumberInput';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { useRules } from '@/hooks/useClassification';
import { useAccountRoles, useExpenseAccounts } from '@/hooks/useLedger';
import { amountToInput, formatCurrency, formatSignedCurrency } from '@/lib/format';
import { isBalanced, mergeItems, missingAmount } from '@/lib/receiptMath';
import { cn } from '@/lib/utils';

import { amountOf, emptyItem, type ReceiptFormValues } from './receiptForm';
import { RuleBadge } from './RuleBadge';
import { SaveAsRuleDialog } from './SaveAsRuleDialog';

function FieldError({ message }: { message: string | undefined }) {
  if (!message) return null;
  return <p className="text-destructive mt-1 text-xs">{message}</p>;
}

/**
 * The line items: edit, add and remove them, merge several into one, and
 * move the gap between their sum and the total onto one item. Each row also
 * carries its classification (rule badge, editable expense account and
 * flatmate share, save-as-rule); unmatched rows are highlighted.
 */
export function ReceiptItemsEditor({ showFlags = false }: { showFlags?: boolean }) {
  const { control, register, getValues, setValue, formState } = useFormContext<ReceiptFormValues>();
  const { fields, append, remove, replace } = useFieldArray({ control, name: 'items' });
  const expenseAccounts = useExpenseAccounts();
  const rules = useRules();
  const { roles } = useAccountRoles();

  const items = useWatch({ control, name: 'items' });
  const total = amountOf(useWatch({ control, name: 'total_sum' }));
  const currency = useWatch({ control, name: 'currency' });
  const prices = items.map((item) => amountOf(item.price));
  const missing = missingAmount(total, prices);
  const balanced = isBalanced(total, prices);

  const [mergeMode, setMergeMode] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [assignIndex, setAssignIndex] = useState<number | null>(null);
  const [saveAsRuleIndex, setSaveAsRuleIndex] = useState<number | null>(null);

  const toggle = (index: number) =>
    setSelected((previous) => {
      const next = new Set(previous);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });

  const stopMerging = () => {
    setMergeMode(false);
    setSelected(new Set());
  };

  const mergeSelected = () => {
    const current = getValues('items').map((item) => ({ ...item, price: amountOf(item.price) }));
    replace(
      mergeItems(current, selected).map((item) => ({
        ...item,
        price: amountToInput(item.price, currency),
      }))
    );
    stopMerging();
  };

  const assignTarget = assignIndex === null ? undefined : items[assignIndex];
  const assignDifference = () => {
    if (assignIndex === null || !assignTarget) return;
    const newPrice = amountOf(assignTarget.price) + missing;
    setValue(`items.${assignIndex}.price`, amountToInput(newPrice, currency), {
      shouldDirty: true,
      shouldValidate: true,
    });
    setAssignIndex(null);
  };

  const itemErrors = formState.errors.items;

  return (
    <section aria-labelledby="items-heading">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 id="items-heading" className="text-base font-semibold">
          Items <span className="text-muted-foreground font-normal">({fields.length})</span>
        </h2>
        {mergeMode ? (
          <div className="flex items-center gap-2">
            <Button type="button" variant="ghost" size="sm" onClick={stopMerging}>
              <X /> Cancel
            </Button>
            <Button type="button" size="sm" disabled={selected.size < 2} onClick={mergeSelected}>
              <Combine /> Merge {selected.size > 1 ? `${selected.size} items` : 'items'}
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={fields.length < 2}
              onClick={() => setMergeMode(true)}
            >
              <Combine /> Merge
            </Button>
            <Button type="button" variant="secondary" size="sm" onClick={() => append(emptyItem())}>
              <Plus /> Add item
            </Button>
          </div>
        )}
      </div>

      {mergeMode && (
        <p className="text-muted-foreground mb-3 text-sm">
          Select the items to combine into one. The merged item takes the expense account of the
          last one you select.
        </p>
      )}

      <ul aria-label="Items" className="flex flex-col gap-2">
        {fields.map((field, index) => {
          const errors = itemErrors?.[index];
          const item = items[index];
          const name = item?.name || `item ${index + 1}`;
          const unmatched = showFlags && item?.matched_rule_id == null;
          return (
            <li
              key={field.id}
              aria-label={name}
              className={cn(
                'bg-card rounded-lg border p-3 transition-colors',
                unmatched && 'border-destructive/60 bg-destructive/5',
                mergeMode &&
                  selected.has(index) &&
                  'border-primary bg-accent/50 ring-primary/30 ring-2'
              )}
            >
              <div className="flex items-start gap-3">
                {mergeMode && (
                  <Checkbox
                    className="mt-2.5"
                    aria-label={`Select ${name}`}
                    checked={selected.has(index)}
                    onCheckedChange={() => toggle(index)}
                  />
                )}
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="min-w-0 flex-1">
                      <Input
                        aria-label={`Name of item ${index + 1}`}
                        placeholder="Product"
                        disabled={mergeMode}
                        aria-invalid={!!errors?.name || undefined}
                        {...register(`items.${index}.name`)}
                      />
                      <FieldError message={errors?.name?.message} />
                    </div>
                    {!mergeMode && (
                      <RuleBadge
                        rules={rules}
                        matchedRuleId={item?.matched_rule_id}
                        overridden={item?.classification_overridden}
                        account={item?.expense_account ?? ''}
                        unallocatedAccount={roles?.unallocated_account}
                      />
                    )}
                  </div>
                  <div className="mt-2 grid gap-2 sm:grid-cols-[minmax(0,1fr)_6rem_7rem]">
                    <div>
                      <Controller
                        control={control}
                        name={`items.${index}.expense_account`}
                        render={({ field: account, fieldState }) => (
                          <Combobox
                            label={`Expense account of item ${index + 1}`}
                            placeholder="Expense account"
                            value={account.value}
                            onChange={account.onChange}
                            options={expenseAccounts.names}
                            invalid={!!fieldState.error}
                            disabled={mergeMode}
                          />
                        )}
                      />
                      <FieldError message={errors?.expense_account?.message} />
                    </div>
                    <div>
                      <Controller
                        control={control}
                        name={`items.${index}.flatmate_share`}
                        render={({ field: share, fieldState }) => (
                          <div className="relative">
                            <NumberInput
                              aria-label={`Flatmate share of item ${index + 1}`}
                              min={0}
                              max={100}
                              step={1}
                              className="pr-7 text-right tabular-nums"
                              disabled={mergeMode}
                              aria-invalid={!!fieldState.error || undefined}
                              value={share.value}
                              onChange={(event) => {
                                const parsed = event.target.valueAsNumber;
                                share.onChange(Number.isNaN(parsed) ? 0 : parsed);
                              }}
                              onBlur={share.onBlur}
                            />
                            <span className="text-muted-foreground pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2 text-xs">
                              %
                            </span>
                          </div>
                        )}
                      />
                      <FieldError message={errors?.flatmate_share?.message} />
                    </div>
                    <div>
                      <Controller
                        control={control}
                        name={`items.${index}.price`}
                        render={({ field: price, fieldState }) => (
                          <AmountInput
                            currency={currency}
                            aria-label={`Price of item ${index + 1}`}
                            className="text-right"
                            disabled={mergeMode}
                            aria-invalid={!!fieldState.error || undefined}
                            value={price.value}
                            onChange={price.onChange}
                            onBlur={price.onBlur}
                          />
                        )}
                      />
                      <FieldError message={errors?.price?.message} />
                    </div>
                  </div>
                </div>
                {!mergeMode && (
                  <div className="flex shrink-0 flex-col gap-1 sm:flex-row">
                    {!balanced && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="text-warning-foreground dark:text-warning"
                        aria-label={`Assign the difference to ${name}`}
                        title="Assign the difference to this item"
                        onClick={() => setAssignIndex(index)}
                      >
                        <CornerDownLeft />
                      </Button>
                    )}
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label={`Save ${name} as a rule`}
                      title="Save as rule"
                      onClick={() => setSaveAsRuleIndex(index)}
                    >
                      <BookmarkPlus />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label={`Remove ${name}`}
                      title="Remove item"
                      disabled={fields.length === 1}
                      onClick={() => remove(index)}
                    >
                      <Trash2 />
                    </Button>
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ul>
      <FieldError message={itemErrors?.root?.message ?? itemErrors?.message} />

      <ConfirmDialog
        open={assignTarget !== undefined}
        onOpenChange={(open) => !open && setAssignIndex(null)}
        title="Assign the difference"
        confirmLabel="Assign"
        onConfirm={assignDifference}
      >
        {assignTarget && (
          <>
            <p>
              Add <strong>{formatSignedCurrency(missing, currency)}</strong> to “{assignTarget.name}
              ” so the items add up to the total?
            </p>
            <p className="mt-2 tabular-nums">
              {formatCurrency(amountOf(assignTarget.price), currency)} →{' '}
              {formatCurrency(amountOf(assignTarget.price) + missing, currency)}
            </p>
          </>
        )}
      </ConfirmDialog>

      <SaveAsRuleDialog
        key={saveAsRuleIndex ?? 'none'}
        item={saveAsRuleIndex === null ? undefined : items[saveAsRuleIndex]}
        open={saveAsRuleIndex !== null}
        onOpenChange={(open) => !open && setSaveAsRuleIndex(null)}
      />
    </section>
  );
}
