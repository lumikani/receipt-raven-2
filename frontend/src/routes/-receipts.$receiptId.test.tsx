import { describe, expect, test } from 'vitest';

import { renderApp } from '@tests/harness/renderApp';
import { recorded, rejectApprovals, seedReceipt } from '@tests/msw/fakeApi';

const pathOf = (id: number) => `/receipts/${id}`;

describe('reviewing a receipt', () => {
  test('approves the edited receipt and returns to the list', async () => {
    const receipt = seedReceipt({
      payee: 'Prisma',
      itemSeeds: [
        ['Maito', 'Expenses:Groceries', 2.5],
        ['Kynä', 'Expenses:Office', 1.99],
      ],
    });
    const { screen, router } = await renderApp({ path: pathOf(receipt.id) });

    await screen.getByRole('textbox', { name: 'Name of item 1' }).fill('Kevytmaito');
    await screen.getByRole('textbox', { name: 'Description' }).fill('Viikon ostokset');
    await screen.getByRole('button', { name: 'Approve and book' }).click();

    await expect
      .element(screen.getByText('Receipt approved and booked to the ledger'))
      .toBeVisible();
    expect(router.state.location.pathname).toBe('/');
    const [approval] = recorded.approvals();
    expect(approval?.body).toMatchObject({
      payee: 'Prisma',
      description: 'Viikon ostokset',
      source_account: 'Assets:Checking',
      total_sum: 4.49,
      items: [
        {
          id: receipt.items[0]?.id,
          name: 'Kevytmaito',
          expense_account: 'Expenses:Groceries',
          price: 2.5,
        },
        { id: receipt.items[1]?.id, name: 'Kynä', expense_account: 'Expenses:Office', price: 1.99 },
      ],
    });
  });

  test('assigns the gap between items and total to an item', async () => {
    const receipt = seedReceipt({
      total_sum: 10,
      itemSeeds: [
        ['Maito', 'Expenses:Groceries', 2.5],
        ['Leipä', 'Expenses:Groceries', 3],
      ],
    });
    const { screen } = await renderApp({ path: pathOf(receipt.id) });
    const approve = screen.getByRole('button', { name: 'Approve and book' });

    await expect.element(approve).toBeDisabled();
    await expect
      .element(screen.getByLabelText('Difference', { exact: true }))
      .toHaveTextContent('4,50');

    await screen.getByRole('button', { name: 'Assign the difference to Leipä' }).click();
    await screen.getByRole('button', { name: 'Assign' }).click();

    await expect
      .element(screen.getByRole('textbox', { name: 'Price of item 2' }))
      .toHaveValue('7,50');
    await expect.element(approve).toBeEnabled();
  });

  test('merges selected items into one, keeping the last one’s account', async () => {
    const receipt = seedReceipt({
      itemSeeds: [
        ['Kahvi', 'Expenses:Groceries', 12.99],
        ['Vihko', 'Expenses:Office', 4.99],
        ['Kynä', 'Expenses:Office', 1.99],
      ],
    });
    const { screen } = await renderApp({ path: pathOf(receipt.id) });

    await screen.getByRole('button', { name: 'Merge', exact: true }).click();
    await screen.getByRole('checkbox', { name: 'Select Kahvi' }).click();
    await screen.getByRole('checkbox', { name: 'Select Kynä' }).click();
    await screen.getByRole('button', { name: 'Merge 2 items' }).click();

    const items = screen.getByRole('list', { name: 'Items' });
    await expect
      .element(items.getByRole('textbox', { name: 'Name of item 1' }))
      .toHaveValue('Kahvi, Kynä');
    await expect
      .element(items.getByRole('textbox', { name: 'Price of item 1' }))
      .toHaveValue('14,98');
    await expect
      .element(items.getByRole('combobox', { name: 'Expense account of item 1' }))
      .toHaveTextContent('Expenses:Office');
    await expect
      .element(items.getByRole('textbox', { name: 'Name of item 3' }))
      .not.toBeInTheDocument();

    await screen.getByRole('button', { name: 'Approve and book' }).click();
    await expect
      .poll(() => recorded.approvals()[0]?.body.items)
      .toEqual([
        {
          id: null,
          name: 'Kahvi, Kynä',
          expense_account: 'Expenses:Office',
          price: 14.98,
          flatmate_share: 0,
        },
        {
          id: receipt.items[1]?.id,
          name: 'Vihko',
          expense_account: 'Expenses:Office',
          price: 4.99,
          flatmate_share: 0,
        },
      ]);
  });

  test('shows why the ledger rejected a receipt and keeps it open', async () => {
    const receipt = seedReceipt();
    rejectApprovals('Account(s) not found in ledger: Assets:Checking');
    const { screen, router } = await renderApp({ path: pathOf(receipt.id) });

    await screen.getByRole('button', { name: 'Approve and book' }).click();

    await expect
      .element(
        screen.getByText(
          'The ledger rejected the receipt: Account(s) not found in ledger: Assets:Checking'
        )
      )
      .toBeVisible();
    expect(router.state.location.pathname).toBe(pathOf(receipt.id));
  });

  test('warns about a date the analysis doubts', async () => {
    const receipt = seedReceipt({
      date: '2025-03-01',
      ocr_notes: {
        suspicious_date: { level: 'SEVERE', message: 'Date is in previous year (2025)' },
      },
    });
    const { screen } = await renderApp({ path: pathOf(receipt.id) });

    await expect
      .element(screen.getByRole('note'))
      .toHaveTextContent('Date is in previous year (2025)');
  });

  test('deletes a receipt after confirmation', async () => {
    const receipt = seedReceipt({ payee: 'Turha' });
    const { screen, router } = await renderApp({ path: pathOf(receipt.id) });

    await screen.getByRole('button', { name: 'Delete' }).click();
    await screen.getByRole('alertdialog').getByRole('button', { name: 'Delete' }).click();

    await expect.element(screen.getByText('Receipt deleted')).toBeVisible();
    expect(router.state.location.pathname).toBe('/');
    expect(recorded.receipts()).toHaveLength(0);
  });

  test('an approved receipt is read-only', async () => {
    const receipt = seedReceipt({ status: 'approved', payee: 'Lidl' });
    const { screen } = await renderApp({ path: pathOf(receipt.id) });

    await expect.element(screen.getByRole('heading', { name: 'Lidl' })).toBeVisible();
    await expect.element(screen.getByText('Approved')).toBeVisible();
    await expect
      .element(screen.getByRole('button', { name: 'Approve and book' }))
      .not.toBeInTheDocument();
    await expect.element(screen.getByRole('button', { name: 'Delete' })).not.toBeInTheDocument();
  });
});

describe('a receipt in another currency', () => {
  test('shows yen amounts and waits unapproved', async () => {
    const receipt = seedReceipt({
      payee: 'Lawson',
      currency: 'JPY',
      itemSeeds: [
        ['Onigiri', 'Expenses:Groceries', 180],
        ['Coffee', 'Expenses:Groceries', 150],
      ],
    });
    const { screen } = await renderApp({ path: pathOf(receipt.id) });

    await expect
      .element(screen.getByRole('textbox', { name: 'Price of item 1' }))
      .toHaveValue('180');
    await expect
      .element(screen.getByRole('combobox', { name: 'Currency' }))
      .toHaveTextContent('JPY');
    await expect.element(screen.getByText(/330\s¥/).first()).toBeVisible();
    await expect.element(screen.getByRole('button', { name: 'Approve and book' })).toBeDisabled();
    await expect
      .element(screen.getByRole('note'))
      .toHaveTextContent('Receipts in JPY cannot be booked to the ledger yet');
  });

  test('a currency corrected to euros can be approved', async () => {
    const receipt = seedReceipt({
      currency: 'JPY',
      itemSeeds: [['Maito', 'Expenses:Groceries', 2.5]],
    });
    const { screen } = await renderApp({ path: pathOf(receipt.id) });

    await screen.getByRole('combobox', { name: 'Currency' }).click();
    await screen.getByRole('option', { name: 'EUR' }).click();
    await screen.getByRole('button', { name: 'Approve and book' }).click();

    await expect.poll(() => recorded.approvals()[0]?.body.currency).toBe('EUR');
  });
});
