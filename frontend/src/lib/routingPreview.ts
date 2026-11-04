/**
 * The routing preview for the review screen: what approving the receipt will
 * book to the ledger and export to the balancing CSV. A port of the prototype
 * (`prototype/review-ui`) onto the real semantics of the backend's
 * `build_routed_transaction` / `export_row` and the hledger entry renderer,
 * driven by the configured account roles (never hardcoded account names).
 */

import type { AccountRolesResponse } from '@/api/generated/model';

export interface PreviewItem {
  name: string;
  expense_account: string;
  price: number;
  flatmate_share: number;
}

export interface RoutePreviewInput {
  receipt_id: number;
  payee: string;
  /** `YYYY-MM-DD`. */
  date: string;
  description: string | null;
  currency: string;
  source_account: string;
  items: PreviewItem[];
  roles: AccountRolesResponse;
}

interface CsvPreview {
  shared_cost: number;
  description: string;
  purchase_for_flatmate: number;
}

type SourceRole = 'personal-card' | 'shared-card' | 'unconfigured';

export interface RoutePreview {
  role: SourceRole;
  /** The hledger entry lines approval will write, or null when nothing is booked. */
  entry: string[] | null;
  /** The balancing CSV row approval will produce, or null when not exported. */
  csv: CsvPreview | null;
  /** Human-readable notes about what is excluded and why. */
  notes: string[];
}

const round2 = (value: number) => Math.round(value * 100) / 100;

/**
 * Round once, half-up, to two decimals — computed in integer milli-cents so
 * float artifacts (0.1 + 0.2) never leak into the preview. The backend's
 * Decimal computation stays authoritative.
 */
function roundHalfUp2(value: number): number {
  return Math.round(value * 100 + Number.EPSILON) / 100;
}

/** Sum of 2 x (share/100) x price over partially shared rows, in 1/100000 currency units. */
function sharedCostCents(items: PreviewItem[]): number {
  return items.reduce(
    (sum, item) => sum + 2 * item.flatmate_share * Math.round(item.price * 100) * 10,
    0
  );
}

function mergeByAccount(
  items: PreviewItem[],
  remap: (item: PreviewItem) => string
): { account: string; name: string; amount: number }[] {
  const groups = new Map<string, { name: string[]; amount: number }>();
  for (const item of items) {
    const account = remap(item);
    const group = groups.get(account) ?? { name: [], amount: 0 };
    group.name.push(item.name);
    group.amount = round2(group.amount + item.price);
    groups.set(account, group);
  }
  return [...groups.entries()].map(([account, group]) => ({
    account,
    name: group.name.join(', '),
    amount: group.amount,
  }));
}

function entryLines(
  input: RoutePreviewInput,
  postings: { account: string; name: string; amount: number }[]
): string[] {
  const header = `${input.date} * ${input.payee}${input.description ? ` | ${input.description}` : ''}`;
  const lines = [header];
  let sum = 0;
  for (const posting of postings) {
    sum = round2(sum + posting.amount);
    let line = `    ${posting.account}  ${posting.amount.toFixed(2)} ${input.currency}`;
    if (posting.name) line += `  ; items: ${posting.name}`;
    lines.push(line);
  }
  if (sum !== 0) {
    lines.push(`    ${input.source_account}  ${(-sum).toFixed(2)} ${input.currency}`);
  }
  lines.push(`    ; receipt-id: ${input.receipt_id}`);
  return lines;
}

function csvRow(input: RoutePreviewInput): CsvPreview | null {
  if (!input.items.some((item) => item.flatmate_share > 0)) return null;
  const shared = input.items.filter((item) => item.flatmate_share > 0 && item.flatmate_share < 100);
  const flatmateOnly = input.items.filter((item) => item.flatmate_share === 100);
  const detail = input.description || input.items.map((item) => item.name).join(', ');
  return {
    // Milli-cents summed exactly, rounded once half-up to cents.
    shared_cost: roundHalfUp2(sharedCostCents(shared) / 100_000),
    description: `${input.date.slice(5)} ${input.payee} ${detail}`,
    purchase_for_flatmate: roundHalfUp2(
      flatmateOnly.reduce((sum, item) => sum + Math.round(item.price * 100), 0) / 100
    ),
  };
}

export function routePreview(input: RoutePreviewInput): RoutePreview {
  const { roles, items, source_account: sourceAccount } = input;
  const notes: string[] = [];

  if (roles.shared_card !== null && sourceAccount === roles.shared_card) {
    const mine = items.filter((item) => item.flatmate_share === 0);
    const flatmates = items.filter((item) => item.flatmate_share === 100);
    const shared = items.filter((item) => item.flatmate_share > 0 && item.flatmate_share < 100);
    const postings = mergeByAccount(mine, (item) => item.expense_account);
    if (flatmates.length > 0 && roles.flatmate_expense_adjustment !== null) {
      postings.push({
        account: roles.flatmate_expense_adjustment,
        name: flatmates.map((item) => item.name).join(', '),
        amount: round2(-flatmates.reduce((sum, item) => sum + item.price, 0)),
      });
    }
    if (mine.length > 0) {
      postings.push({
        account: sourceAccount,
        name: mine.map((item) => item.name).join(', '),
        amount: round2(-mine.reduce((sum, item) => sum + item.price, 0)),
      });
    }
    if (flatmates.length > 0) {
      postings.push({
        account: sourceAccount,
        name: flatmates.map((item) => item.name).join(', '),
        amount: round2(flatmates.reduce((sum, item) => sum + item.price, 0)),
      });
    }
    if (shared.length > 0) {
      notes.push(
        `${shared.map((item) => `“${item.name}” (${item.flatmate_share}%)`).join(', ')}: shared rows are not booked — they only feed the spreadsheet.`
      );
    }
    return {
      role: 'shared-card',
      entry: postings.length > 0 ? entryLines(input, postings) : null,
      csv: null,
      notes: [...notes, 'Shared-card receipts are never exported to CSV.'],
    };
  }

  const personal = roles.personal_cards.includes(sourceAccount);
  if (!personal) {
    notes.push(`${sourceAccount} has no configured role — treated as a personal card (flagged).`);
  }
  const purchaseForFlatmate = roles.purchase_for_flatmate;
  const postings = mergeByAccount(items, (item) =>
    item.flatmate_share === 100 && purchaseForFlatmate !== null
      ? purchaseForFlatmate
      : item.expense_account
  );
  const flatmateOnly = items.filter((item) => item.flatmate_share === 100);
  if (flatmateOnly.length > 0 && purchaseForFlatmate !== null) {
    notes.push(
      `${flatmateOnly.map((item) => `“${item.name}”`).join(', ')}: share 100% → posted to ${purchaseForFlatmate}.`
    );
  }
  const csv = csvRow(input);
  return {
    role: personal ? 'personal-card' : 'unconfigured',
    entry: entryLines(input, postings),
    csv,
    notes: [
      ...notes,
      csv
        ? 'CSV row produced (at least one row has a flatmate share > 0).'
        : 'No CSV row (no row has a flatmate share > 0).',
    ],
  };
}

/** The CSV cell format of the export: two decimals, comma decimal mark. */
export function formatCsvNumber(value: number): string {
  return value.toFixed(2).replace('.', ',');
}
