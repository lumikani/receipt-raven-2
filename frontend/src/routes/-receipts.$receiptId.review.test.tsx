import { describe, expect, test } from 'vitest';

import { renderApp } from '@tests/harness/renderApp';
import { fillRuleDialog } from '@tests/harness/ruleDialog';
import { recorded, seedReceipt, seedRule, seedShareDefault } from '@tests/msw/fakeApi';

const pathOf = (id: number) => `/receipts/${id}`;

describe('the review screen’s classification rows', () => {
  test('shows each row’s rule badge and flags unmatched rows', async () => {
    const rule = seedRule({
      pattern: 'maito',
      expense_account: 'Expenses:Groceries',
      flatmate_share_override: 50,
    });
    const receipt = seedReceipt({
      itemSeeds: [
        ['Maito 1 l', 'Expenses:Groceries', 2.5, 50, rule.id],
        ['Kynä', 'Expenses:Unallocated', 1.99, 0, null],
      ],
    });
    const { screen } = await renderApp({ path: pathOf(receipt.id) });

    const items = screen.getByRole('list', { name: 'Items' });
    const maitoRow = items.getByRole('listitem', { name: 'Maito 1 l' });
    const kynaRow = items.getByRole('listitem', { name: 'Kynä' });
    await expect.element(maitoRow.getByText('rule: maito')).toBeVisible();
    await expect.element(kynaRow.getByText(/no rule/)).toBeVisible();
    expect(kynaRow.element().className).toContain('border-destructive/60');
    expect(maitoRow.element().className).not.toContain('border-destructive/60');
    // The stamped share is editable per row.
    await expect
      .element(screen.getByRole('spinbutton', { name: 'Flatmate share of item 1' }))
      .toHaveValue(50);
  });

  test('editing the flatmate share approves with it as a manual override', async () => {
    const rule = seedRule({ pattern: 'maito', flatmate_share_override: 50 });
    const receipt = seedReceipt({
      itemSeeds: [['Maito', 'Expenses:Groceries', 2.5, 50, rule.id]],
    });
    const { screen } = await renderApp({ path: pathOf(receipt.id) });

    await screen.getByRole('spinbutton', { name: 'Flatmate share of item 1' }).fill('75');
    await screen.getByRole('button', { name: 'Approve and book' }).click();

    await expect
      .poll(() => recorded.approvals()[0]?.body.items[0])
      .toMatchObject({ id: receipt.items[0]?.id, flatmate_share: 75 });
  });

  test('save-as-rule prefills the normalized name and creates the rule', async () => {
    seedShareDefault('Expenses:Office', 50);
    const receipt = seedReceipt({
      itemSeeds: [['Thunder Sour Apple 0,5 l 1,99 €', 'Expenses:Unallocated', 1.99, 0, null]],
    });
    const { screen } = await renderApp({ path: pathOf(receipt.id) });

    await screen
      .getByRole('button', { name: 'Save Thunder Sour Apple 0,5 l 1,99 € as a rule' })
      .click();
    const dialog = screen.getByRole('dialog');
    await expect
      .element(dialog.getByRole('textbox', { name: 'Pattern (normalized product name)' }))
      .toHaveValue('thunder sour apple 0 5 l');

    await fillRuleDialog(screen, { account: 'Expenses:Office', share: '25' });
    await dialog.getByRole('button', { name: 'Save rule' }).click();

    await expect
      .poll(() => recorded.createdRules()[0])
      .toMatchObject({
        pattern: 'thunder sour apple 0 5 l',
        expense_account: 'Expenses:Office',
        flatmate_share_override: 25,
        max_typos: 1,
      });
    await expect.element(screen.getByText('Rule “thunder sour apple 0 5 l” saved')).toBeVisible();
  });

  test('re-classify re-stamps unmatched rows but keeps manual overrides', async () => {
    seedRule({
      pattern: 'kynä',
      expense_account: 'Expenses:Office',
      flatmate_share_override: 100,
    });
    const receipt = seedReceipt({
      itemSeeds: [
        ['Kynä 2 kpl', 'Expenses:Unallocated', 1.99, 0, null],
        ['Maito', 'Expenses:Groceries', 2.5, 50, null, true],
      ],
    });
    const { screen } = await renderApp({ path: pathOf(receipt.id) });

    const items = screen.getByRole('list', { name: 'Items' });
    await expect
      .element(items.getByRole('listitem', { name: 'Kynä 2 kpl' }).getByText(/no rule/))
      .toBeVisible();

    await screen.getByRole('button', { name: 'Re-classify' }).click();

    await expect.poll(() => recorded.reclassifications()).toEqual([receipt.id]);
    await expect
      .element(items.getByRole('listitem', { name: 'Kynä 2 kpl' }).getByText(`rule: kynä`))
      .toBeVisible();
    await expect
      .element(screen.getByRole('spinbutton', { name: 'Flatmate share of item 1' }))
      .toHaveValue(100);
    // The overridden row keeps its share.
    await expect
      .element(screen.getByRole('spinbutton', { name: 'Flatmate share of item 2' }))
      .toHaveValue(50);
  });
});

describe('the card read from the receipt', () => {
  test('shows the last four digits next to Paid from on the review screen', async () => {
    const receipt = seedReceipt({ card_last_digits: '9841' });
    const { screen } = await renderApp({ path: pathOf(receipt.id) });

    await expect.element(screen.getByText('Card •••• 9841 on the receipt')).toBeVisible();
  });

  test('shows the last four digits on the approved read-only view', async () => {
    const receipt = seedReceipt({ status: 'approved', booked: true, card_last_digits: '0244' });
    const { screen } = await renderApp({ path: pathOf(receipt.id) });

    await expect.element(screen.getByText('Card')).toBeVisible();
    await expect.element(screen.getByText('•••• 0244')).toBeVisible();
  });
});

describe('the routing preview', () => {
  test('shows the personal-card ledger entry and CSV row approval will produce', async () => {
    const receipt = seedReceipt({
      itemSeeds: [
        ['Maito', 'Expenses:Groceries', 2.5, 50, null],
        ['Kinkkupiirakka', 'Expenses:Clothes', 6.5, 100, null],
      ],
    });
    const { screen } = await renderApp({ path: pathOf(receipt.id) });

    const preview = screen.getByRole('region', { name: 'Routing preview' });
    await expect.element(preview.getByText('source account role: personal card')).toBeVisible();

    const entry = preview.getByLabelText('Ledger entry preview');
    await expect.element(entry).toHaveTextContent('2026-10-09 * Prisma | Ruokaostokset');
    await expect
      .element(entry)
      .toHaveTextContent(/Expenses:Groceries\s+2\.50 EUR\s+; items: Maito/);
    await expect
      .element(entry)
      .toHaveTextContent(/Expenses:PurchaseForFlatmate\s+6\.50 EUR\s+; items: Kinkkupiirakka/);
    await expect.element(entry).toHaveTextContent(/Assets:Checking\s+-9\.00 EUR/);
    await expect.element(entry).toHaveTextContent(new RegExp(`; receipt-id: ${receipt.id}`));

    const csv = preview.getByLabelText('CSV row preview');
    await expect.element(csv).toHaveTextContent('shared_cost;description;purchase_for_flatmate');
    await expect.element(csv).toHaveTextContent('2,50;10-09 Prisma Ruokaostokset;6,50');
  });

  test('the source toggle previews the shared-card routing (no CSV)', async () => {
    const receipt = seedReceipt({
      source_account: 'Assets:Checking',
      itemSeeds: [
        ['Maito', 'Expenses:Groceries', 2.5, 0, null],
        ['Kinkku', 'Expenses:Clothes', 6.5, 100, null],
      ],
    });
    const { screen } = await renderApp({ path: pathOf(receipt.id) });

    const preview = screen.getByRole('region', { name: 'Routing preview' });
    await preview.getByRole('combobox', { name: 'Paid from (preview)' }).click();
    await screen.getByRole('option', { name: 'Liabilities:SharedAccount' }).click();

    await expect.element(preview.getByText('source account role: shared card')).toBeVisible();
    const entry = preview.getByLabelText('Ledger entry preview');
    await expect.element(entry).toHaveTextContent(/Expenses:Groceries\s+2\.50 EUR/);
    await expect.element(entry).toHaveTextContent(/Expenses:FlatmateAdjustment\s+-6\.50 EUR/);
    await expect.element(entry).toHaveTextContent(/Liabilities:SharedAccount\s+-2\.50 EUR/);
    await expect.element(entry).toHaveTextContent(/Liabilities:SharedAccount\s+6\.50 EUR/);
    await expect.element(preview.getByText('Not exported to the balancing CSV.')).toBeVisible();
  });

  test('flags a source account without a configured role', async () => {
    const receipt = seedReceipt({ source_account: 'Liabilities:Unknown' });
    const { screen } = await renderApp({ path: pathOf(receipt.id) });

    await expect
      .element(screen.getByText(/has no configured account role — treated as a personal card/))
      .toBeVisible();
    const preview = screen.getByRole('region', { name: 'Routing preview' });
    await expect
      .element(preview.getByText('source account role: personal card (unconfigured — flagged)'))
      .toBeVisible();
  });
});

describe('the booked badge on the detail view', () => {
  test('approved and booked shows Booked', async () => {
    const receipt = seedReceipt({ status: 'approved', booked: true, payee: 'Lidl' });
    const { screen } = await renderApp({ path: pathOf(receipt.id) });

    await expect.element(screen.getByText('Booked')).toBeVisible();
  });

  test('approved without a ledger entry shows Not booked', async () => {
    const receipt = seedReceipt({ status: 'approved', booked: false, payee: 'Lidl' });
    const { screen } = await renderApp({ path: pathOf(receipt.id) });

    await expect.element(screen.getByText('Not booked')).toBeVisible();
  });
});
