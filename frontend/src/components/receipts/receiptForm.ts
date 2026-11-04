import { z } from 'zod';

import type { Receipt, ReceiptRequest } from '@/api/generated/model';
import { amountToInput, DEFAULT_CURRENCY, parseAmount, todayIsoDate } from '@/lib/format';

/** Amounts stay text while edited, so "12," can be typed on the way to "12,50". */
const amount = z
  .string()
  .trim()
  .refine((value) => parseAmount(value) !== null, 'Enter an amount, such as 12,50');

const itemSchema = z.object({
  id: z.number().optional(),
  name: z.string().trim().min(1, 'Name the item'),
  expense_account: z.string().min(1, 'Choose an expense account'),
  price: amount,
  /** Percentage of the price attributable to the flatmate, 0–100. */
  flatmate_share: z.number().min(0, '0–100').max(100, '0–100'),
  /** The rule that stamped the row; null when no rule matched. Display only. */
  matched_rule_id: z.number().nullable().optional(),
  /** True when the account or share was edited manually. Display only. */
  classification_overridden: z.boolean().optional(),
});

export const receiptFormSchema = z.object({
  source_account: z.string().min(1, 'Choose the account it was paid from'),
  payee: z.string().trim().min(1, 'Enter the payee'),
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Choose a date'),
  description: z.string(),
  total_sum: amount,
  currency: z
    .string()
    .trim()
    .regex(/^[A-Za-z]{3}$/, 'Use a three-letter code such as EUR or JPY'),
  items: z.array(itemSchema).min(1, 'Add at least one item'),
});

export type ReceiptFormValues = z.infer<typeof receiptFormSchema>;
export type ReceiptFormItem = ReceiptFormValues['items'][number];

/** Currencies offered in the picker; any other three-letter code can be typed. */
export const COMMON_CURRENCIES = ['EUR', 'JPY', 'USD', 'GBP', 'SEK', 'NOK', 'DKK', 'CHF'];

/** Currencies the ledger takes for now; the backend refuses to approve others. */
export const BOOKABLE_CURRENCIES = new Set(['EUR']);

export const emptyItem = (): ReceiptFormItem => ({
  name: '',
  expense_account: '',
  price: '',
  flatmate_share: 0,
  matched_rule_id: null,
  classification_overridden: false,
});

export function toFormValues(receipt: Receipt | undefined): ReceiptFormValues {
  if (!receipt) {
    return {
      source_account: '',
      payee: '',
      date: todayIsoDate(),
      description: '',
      total_sum: '',
      currency: DEFAULT_CURRENCY,
      items: [emptyItem()],
    };
  }
  return {
    source_account: receipt.source_account ?? '',
    payee: receipt.payee,
    date: receipt.date,
    description: receipt.description ?? '',
    total_sum: amountToInput(receipt.total_sum, receipt.currency),
    currency: receipt.currency,
    items: receipt.items.map((item) => ({
      id: item.id,
      name: item.name,
      expense_account: item.expense_account,
      price: amountToInput(item.price, receipt.currency),
      flatmate_share: item.flatmate_share ?? 0,
      matched_rule_id: item.matched_rule_id ?? null,
      classification_overridden: item.classification_overridden ?? false,
    })),
  };
}

/** The amount in a form field, or 0 while it is not a number yet. */
export function amountOf(text: string | undefined): number {
  return parseAmount(text ?? '') ?? 0;
}

export function toRequest(values: ReceiptFormValues): ReceiptRequest {
  return {
    payee: values.payee.trim(),
    description: values.description.trim() || null,
    source_account: values.source_account,
    date: values.date,
    total_sum: amountOf(values.total_sum),
    currency: values.currency.trim().toUpperCase(),
    items: values.items.map((item) => ({
      id: item.id ?? null,
      name: item.name.trim(),
      expense_account: item.expense_account,
      price: amountOf(item.price),
      flatmate_share: item.flatmate_share,
    })),
  };
}
