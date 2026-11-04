import { afterEach, describe, expect, test, vi } from 'vitest';

import { renderApp } from '@tests/harness/renderApp';
import { recorded, seedReceipt } from '@tests/msw/fakeApi';

/** An approved personal-card receipt with a 50%-shared 4,00 item: export-eligible. */
function seedEligible(overrides: Parameters<typeof seedReceipt>[0] = {}) {
  return seedReceipt({
    status: 'approved',
    booked: true,
    itemSeeds: [['Maito', 'Expenses:Groceries', 4.0, 50]],
    ...overrides,
  });
}

/** Narrow the createObjectURL argument for the download capture in the tests. */
function asBlob(value: Blob | MediaSource): Blob {
  if (!(value instanceof Blob)) throw new Error('expected a Blob');
  return value;
}

/** Capture the browser download a CSV action triggers: the blob and the filename. */
function captureDownload() {
  const blobs: Blob[] = [];
  const filenames: string[] = [];
  vi.spyOn(URL, 'createObjectURL').mockImplementation((obj) => {
    blobs.push(asBlob(obj));
    return 'blob:test';
  });
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
    this: HTMLAnchorElement
  ) {
    filenames.push(this.download);
  });
  return { blobs, filenames };
}

describe('receipt list', () => {
  test('shows the receipts to review, with a warning on a doubtful date', async () => {
    seedReceipt({ payee: 'Prisma', status: 'unapproved' });
    seedReceipt({
      payee: 'Alko',
      status: 'unapproved',
      ocr_notes: {
        suspicious_date: { level: 'SEVERE', message: 'Date is in previous year (2025)' },
      },
    });
    seedReceipt({ payee: 'Lidl', status: 'approved' });

    const { screen } = await renderApp({ path: '/' });

    const table = screen.getByRole('table', { name: 'Receipts' });
    await expect.element(table.getByRole('link', { name: 'Prisma' })).toBeVisible();
    await expect.element(table.getByRole('link', { name: 'Alko' })).toBeVisible();
    await expect.element(table.getByRole('img', { name: 'Check the date' })).toBeVisible();
    await expect.element(table.getByText('Lidl')).not.toBeInTheDocument();
    await expect.element(screen.getByRole('tab', { name: 'To review (2)' })).toBeVisible();
  });

  test('the All tab includes approved receipts', async () => {
    seedReceipt({ payee: 'Prisma' });
    seedReceipt({ payee: 'Lidl', status: 'approved' });
    const { screen } = await renderApp({ path: '/' });

    await screen.getByRole('tab', { name: 'All' }).click();

    const table = screen.getByRole('table', { name: 'Receipts' });
    await expect.element(table.getByRole('link', { name: 'Lidl' })).toBeVisible();
    await expect.element(table.getByRole('link', { name: 'Prisma' })).toBeVisible();
  });

  test('says when there is nothing to review', async () => {
    const { screen } = await renderApp({ path: '/' });

    await expect.element(screen.getByText('No receipts here')).toBeVisible();
  });
});

describe('balancing export on the receipt history', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test('only export-eligible rows are checkable, and approved rows carry the booked badge', async () => {
    seedEligible({ payee: 'Eligible', booked: true });
    seedReceipt({
      payee: 'Unapproved',
      itemSeeds: [['Maito', 'Expenses:Groceries', 4.0, 50]],
    });
    seedEligible({ payee: 'NoShare', itemSeeds: [['Maito', 'Expenses:Groceries', 4.0]] });
    seedEligible({
      payee: 'SharedCard',
      booked: false,
      source_account: 'Liabilities:SharedAccount',
    });
    seedEligible({ payee: 'OtherCurrency', currency: 'USD' });
    const { screen } = await renderApp({ path: '/' });

    await screen.getByRole('tab', { name: 'All' }).click();
    const table = screen.getByRole('table', { name: 'Receipts' });

    await expect
      .element(table.getByRole('checkbox', { name: 'Select Eligible for export' }))
      .toBeEnabled();
    for (const name of ['Unapproved', 'NoShare', 'SharedCard', 'OtherCurrency']) {
      await expect
        .element(table.getByRole('checkbox', { name: `Select ${name} for export` }))
        .toBeDisabled();
    }
    // Approved-and-booked vs approved-but-not-booked badges on the rows.
    const eligibleRow = table.getByRole('row', { name: /Eligible/ });
    await expect.element(eligibleRow.getByText('Booked')).toBeVisible();
    const sharedRow = table.getByRole('row', { name: /SharedCard/ });
    await expect.element(sharedRow.getByText('Not booked')).toBeVisible();
    const unapprovedRow = table.getByRole('row', { name: /Unapproved/ });
    await expect.element(unapprovedRow.getByText('Booked')).not.toBeInTheDocument();
  });

  test('the header checkbox selects exactly the eligible rows of the page', async () => {
    seedEligible({ payee: 'One' });
    seedEligible({ payee: 'Two' });
    seedEligible({ payee: 'SharedCard', source_account: 'Liabilities:SharedAccount' });
    const { screen } = await renderApp({ path: '/' });

    await screen.getByRole('tab', { name: 'All' }).click();
    const header = screen.getByRole('checkbox', {
      name: 'Select all eligible receipts on this page',
    });
    await expect.element(header).toBeVisible();
    await header.click();

    const table = screen.getByRole('table', { name: 'Receipts' });
    await expect
      .element(table.getByRole('checkbox', { name: 'Select One for export' }))
      .toBeChecked();
    await expect
      .element(table.getByRole('checkbox', { name: 'Select Two for export' }))
      .toBeChecked();
    await expect
      .element(table.getByRole('checkbox', { name: 'Select SharedCard for export' }))
      .toBeDisabled();
    await expect.element(screen.getByText('2 selected')).toBeVisible();

    await header.click();
    await expect
      .element(table.getByRole('checkbox', { name: 'Select One for export' }))
      .not.toBeChecked();
    await expect.element(screen.getByText('All eligible receipts')).toBeVisible();
  });

  test('checked rows map to the ids= parameter of the CSV download', async () => {
    const one = seedEligible({ payee: 'One', date: '2026-10-01' });
    const two = seedEligible({ payee: 'Two', date: '2026-10-09' });
    seedEligible({ payee: 'Three', date: '2026-10-05' });
    const { screen } = await renderApp({ path: '/' });

    await screen.getByRole('tab', { name: 'All' }).click();
    const table = screen.getByRole('table', { name: 'Receipts' });
    await table.getByRole('checkbox', { name: 'Select Two for export' }).click();
    await table.getByRole('checkbox', { name: 'Select One for export' }).click();

    // Capture the browser download the action triggers.
    const { blobs, filenames } = captureDownload();

    await screen.getByRole('button', { name: 'Download CSV' }).click();

    await expect
      .poll(() => recorded.exportRequests())
      .toEqual([
        {
          ids: `${Math.min(one.id, two.id)},${Math.max(one.id, two.id)}`,
          from: null,
          to: null,
          format: 'csv',
        },
      ]);
    await expect.poll(() => filenames).toEqual(['receipts-export.csv']);
    await expect.poll(() => blobs.length).toBe(1);
    const [blob] = blobs;
    expect(await blob?.text()).toBe(
      'shared_cost;description;purchase_for_flatmate\r\n' +
        '4,00;10-01 One Ruokaostokset;0,00\r\n' +
        '4,00;10-09 Two Ruokaostokset;0,00\r\n'
    );
  });

  test('the from/to inputs map to the from and to parameters', async () => {
    seedEligible({ payee: 'Before', date: '2026-10-01' });
    seedEligible({ payee: 'In', date: '2026-10-09' });
    const { screen } = await renderApp({ path: '/' });

    await screen.getByRole('tab', { name: 'All' }).click();
    await screen.getByLabelText('From date').fill('2026-10-09');
    await screen.getByLabelText('To date').fill('2026-10-09');

    const { blobs } = captureDownload();

    await screen.getByRole('button', { name: 'Download CSV' }).click();

    await expect
      .poll(() => recorded.exportRequests())
      .toEqual([{ ids: null, from: '2026-10-09', to: '2026-10-09', format: 'csv' }]);
    await expect.poll(() => blobs.length).toBe(1);
    const [blob] = blobs;
    expect(await blob?.text()).toBe(
      'shared_cost;description;purchase_for_flatmate\r\n' + '4,00;10-09 In Ruokaostokset;0,00\r\n'
    );
  });

  test('Copy for Sheets requests the tsv variant and copies headerless rows to the clipboard', async () => {
    seedEligible({ payee: 'Prisma', date: '2026-10-09' });
    const { screen } = await renderApp({ path: '/' });

    const written: string[] = [];
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: async (text: string) => void written.push(text) },
      configurable: true,
    });

    await screen.getByRole('tab', { name: 'All' }).click();
    await screen.getByRole('button', { name: 'Copy for Sheets' }).click();

    await expect
      .poll(() => recorded.exportRequests())
      .toEqual([{ ids: null, from: null, to: null, format: 'tsv' }]);
    await expect.poll(() => written).toEqual(['4,00\t10-09 Prisma Ruokaostokset\t0,00\r\n']);
  });
});
