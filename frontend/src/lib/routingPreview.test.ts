import { describe, expect, test } from 'vitest';

import type { AccountRolesResponse } from '@/api/generated/model';

import { formatCsvNumber, routePreview, type PreviewItem } from './routingPreview';

const ROLES: AccountRolesResponse = {
  personal_cards: ['liabilities:op:credit-card:gold'],
  shared_card: 'liabilities:personal:shared-account',
  flatmate_expense_adjustment: 'expenses:flatmate-expense-adjustment',
  purchase_for_flatmate: 'expenses:purchase-for-flatmate',
  unallocated_account: 'expenses:unallocated',
};

const GOLD = 'liabilities:op:credit-card:gold';
const SHARED = 'liabilities:personal:shared-account';

function input(overrides: Partial<Parameters<typeof routePreview>[0]> = {}) {
  return {
    receipt_id: 7,
    payee: 'Prisma',
    date: '2026-11-01',
    description: 'viikon ostokset',
    currency: 'EUR',
    source_account: GOLD,
    items: [
      { name: 'Kurkku', expense_account: 'expenses:produce', price: 2.49, flatmate_share: 50 },
      {
        name: 'Kinkkupiirakka',
        expense_account: 'expenses:ready-meals',
        price: 6.5,
        flatmate_share: 100,
      },
      { name: 'Olut', expense_account: 'expenses:drinks', price: 4.75, flatmate_share: 0 },
    ] as PreviewItem[],
    roles: ROLES,
    ...overrides,
  };
}

describe('routePreview on a personal card', () => {
  test('renders the merged entry with the card liability balancing leg', () => {
    const preview = routePreview(input());

    expect(preview.role).toBe('personal-card');
    expect(preview.entry).toEqual([
      '2026-11-01 * Prisma | viikon ostokset',
      '    expenses:produce  2.49 EUR  ; items: Kurkku',
      '    expenses:purchase-for-flatmate  6.50 EUR  ; items: Kinkkupiirakka',
      '    expenses:drinks  4.75 EUR  ; items: Olut',
      '    liabilities:op:credit-card:gold  -13.74 EUR',
      '    ; receipt-id: 7',
    ]);
  });

  test('produces the CSV row with exact half-up rounding', () => {
    const preview = routePreview(
      input({
        description: null,
        items: [
          { name: 'Olut', expense_account: 'expenses:drinks', price: 4.75, flatmate_share: 25 },
          { name: 'Kinkku', expense_account: 'expenses:produce', price: 2.49, flatmate_share: 100 },
        ],
      })
    );

    // 2 x 0.25 x 4.75 = 2.375 -> 2.38 half-up; description falls back to item names.
    expect(preview.csv).toEqual({
      shared_cost: 2.38,
      description: '11-01 Prisma Olut, Kinkku',
      purchase_for_flatmate: 2.49,
    });
  });

  test('no CSV row when no row has a flatmate share', () => {
    const preview = routePreview(
      input({
        items: [
          { name: 'Olut', expense_account: 'expenses:drinks', price: 4.75, flatmate_share: 0 },
        ],
      })
    );

    expect(preview.csv).toBeNull();
    expect(preview.notes.some((note) => note.includes('No CSV row'))).toBe(true);
  });

  test('an unconfigured source account routes as personal and is flagged', () => {
    const preview = routePreview(input({ source_account: 'liabilities:unknown' }));

    expect(preview.role).toBe('unconfigured');
    expect(preview.entry?.at(-2)).toBe('    liabilities:unknown  -13.74 EUR');
    expect(preview.notes.some((note) => note.includes('no configured role'))).toBe(true);
  });
});

describe('routePreview on the shared card', () => {
  test('books only share-0 and share-100 rows as legs that sum to zero, never CSV', () => {
    const preview = routePreview(
      input({
        source_account: SHARED,
        items: [
          { name: 'Maito', expense_account: 'expenses:produce', price: 2.5, flatmate_share: 0 },
          {
            name: 'Kinkkupiirakka',
            expense_account: 'expenses:ready-meals',
            price: 6.5,
            flatmate_share: 100,
          },
          { name: 'Kurkku', expense_account: 'expenses:produce', price: 2.49, flatmate_share: 50 },
        ],
      })
    );

    expect(preview.role).toBe('shared-card');
    expect(preview.entry).toEqual([
      '2026-11-01 * Prisma | viikon ostokset',
      '    expenses:produce  2.50 EUR  ; items: Maito',
      '    expenses:flatmate-expense-adjustment  -6.50 EUR  ; items: Kinkkupiirakka',
      '    liabilities:personal:shared-account  -2.50 EUR  ; items: Maito',
      '    liabilities:personal:shared-account  6.50 EUR  ; items: Kinkkupiirakka',
      '    ; receipt-id: 7',
    ]);
    expect(preview.csv).toBeNull();
    expect(preview.notes.some((note) => note.includes('not booked'))).toBe(true);
    expect(preview.notes.some((note) => note.includes('never exported'))).toBe(true);
  });

  test('no entry at all when every row is shared', () => {
    const preview = routePreview(
      input({
        source_account: SHARED,
        items: [
          { name: 'Kurkku', expense_account: 'expenses:produce', price: 2.49, flatmate_share: 50 },
        ],
      })
    );

    expect(preview.entry).toBeNull();
    expect(preview.csv).toBeNull();
  });
});

describe('formatCsvNumber', () => {
  test('two decimals with a comma decimal mark', () => {
    expect(formatCsvNumber(2.5)).toBe('2,50');
    expect(formatCsvNumber(2.38)).toBe('2,38');
  });
});
