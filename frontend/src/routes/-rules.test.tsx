import { describe, expect, test } from 'vitest';
import { userEvent } from 'vitest/browser';

import { renderApp } from '@tests/harness/renderApp';
import { fillRuleDialog } from '@tests/harness/ruleDialog';
import { recorded, seedRule, seedShareDefault } from '@tests/msw/fakeApi';

const PATH = '/rules';

describe('the rules management screen', () => {
  test('lists every rule with pattern, account, share, max typos and enabled state', async () => {
    seedRule({
      pattern: 'maito',
      expense_account: 'Expenses:Groceries',
      flatmate_share_override: 50,
      max_typos: 2,
    });
    seedRule({
      pattern: 'kynä',
      expense_account: 'Expenses:Office',
      flatmate_share_override: null,
      max_typos: 0,
      enabled: false,
    });
    const { screen } = await renderApp({ path: PATH });

    const table = screen.getByRole('table', { name: 'Classification rules' });
    const maito = table.getByRole('row', { name: /maito/ });
    const kyna = table.getByRole('row', { name: /kynä/ });
    await expect.element(maito).toBeVisible();
    await expect.element(maito.getByText('Expenses:Groceries')).toBeVisible();
    await expect.element(maito.getByText('50%')).toBeVisible();
    await expect.element(maito.getByText('2')).toBeVisible();
    await expect.element(kyna.getByText('Expenses:Office')).toBeVisible();
    // A blank share override shows the account default instead of a number.
    await expect.element(kyna.getByText('default')).toBeVisible();
    await expect.element(kyna.getByText('0')).toBeVisible();
    await expect
      .element(screen.getByRole('checkbox', { name: 'Rule maito enabled' }))
      .toBeChecked();
    await expect
      .element(screen.getByRole('checkbox', { name: 'Rule kynä enabled' }))
      .not.toBeChecked();
  });

  test('creates a rule through the edit dialog', async () => {
    const { screen } = await renderApp({ path: PATH });

    await screen.getByRole('button', { name: 'Add rule' }).click();
    await fillRuleDialog(screen, {
      pattern: 'kynä',
      account: 'Expenses:Office',
      share: '25',
      maxTypos: '2',
    });
    await screen.getByRole('dialog').getByRole('button', { name: 'Save rule' }).click();

    await expect
      .poll(() => recorded.createdRules()[0])
      .toMatchObject({
        pattern: 'kynä',
        expense_account: 'Expenses:Office',
        flatmate_share_override: 25,
        max_typos: 2,
        enabled: true,
      });
    // The list refreshes and shows the new row.
    const row = screen.getByRole('row', { name: /kynä/ });
    await expect.element(row).toBeVisible();
    await expect.element(row.getByText('25%')).toBeVisible();
  });

  test('edits a rule through the edit dialog', async () => {
    const rule = seedRule({
      pattern: 'maito',
      expense_account: 'Expenses:Groceries',
      flatmate_share_override: null,
      max_typos: 1,
    });
    const { screen } = await renderApp({ path: PATH });

    await screen.getByRole('button', { name: 'Edit rule maito' }).click();
    const dialog = screen.getByRole('dialog');
    await expect
      .element(dialog.getByRole('textbox', { name: 'Pattern (normalized product name)' }))
      .toHaveValue('maito');
    await fillRuleDialog(screen, { share: '75' });
    await dialog.getByRole('button', { name: 'Save rule' }).click();

    await expect
      .poll(() => recorded.updatedRules()[0])
      .toMatchObject({
        ruleId: rule.id,
        body: {
          pattern: 'maito',
          expense_account: 'Expenses:Groceries',
          flatmate_share_override: 75,
          max_typos: 1,
          enabled: true,
        },
      });
    await expect.element(screen.getByRole('row', { name: /maito/ }).getByText('75%')).toBeVisible();
  });

  test('disables and re-enables a rule from the table', async () => {
    const rule = seedRule({ pattern: 'maito' });
    const { screen } = await renderApp({ path: PATH });

    const checkbox = screen.getByRole('checkbox', { name: 'Rule maito enabled' });
    await expect.element(checkbox).toBeChecked();
    await checkbox.click();
    await expect
      .poll(() => recorded.enabledChanges())
      .toEqual([{ ruleId: rule.id, enabled: false }]);
    await expect.element(checkbox).not.toBeChecked();
    await checkbox.click();
    await expect
      .poll(() => recorded.enabledChanges())
      .toEqual([
        { ruleId: rule.id, enabled: false },
        { ruleId: rule.id, enabled: true },
      ]);
    await expect.element(checkbox).toBeChecked();
  });

  test('deletes a rule after confirmation', async () => {
    const rule = seedRule({ pattern: 'maito' });
    seedRule({ pattern: 'kynä' });
    const { screen } = await renderApp({ path: PATH });

    await screen.getByRole('button', { name: 'Delete rule maito' }).click();
    const confirm = screen.getByRole('alertdialog');
    await confirm.getByRole('button', { name: 'Delete rule' }).click();

    await expect.poll(() => recorded.deletedRuleIds()).toEqual([rule.id]);
    await expect.element(screen.getByRole('row', { name: /kynä/ })).toBeVisible();
    await expect.element(screen.getByRole('row', { name: /maito/ })).not.toBeInTheDocument();
  });

  test('cancelling the delete keeps the rule', async () => {
    seedRule({ pattern: 'maito' });
    const { screen } = await renderApp({ path: PATH });

    await screen.getByRole('button', { name: 'Delete rule maito' }).click();
    await screen.getByRole('alertdialog').getByRole('button', { name: 'Cancel' }).click();

    await expect.element(screen.getByRole('row', { name: /maito/ })).toBeVisible();
    expect(recorded.deletedRuleIds()).toEqual([]);
  });
});

describe('the per-account default-share section', () => {
  test('adds a default share for an expense account', async () => {
    const { screen } = await renderApp({ path: PATH });

    await screen.getByRole('combobox', { name: 'Account without a default' }).click();
    await screen.getByRole('option', { name: 'Expenses:Office' }).click();
    await screen.getByRole('spinbutton', { name: 'New default share' }).fill('50');
    await screen.getByRole('button', { name: 'Add default' }).click();

    await expect
      .poll(() => recorded.shareDefaultUpserts()[0])
      .toMatchObject({ expense_account: 'Expenses:Office', share: 50 });
    await expect
      .element(screen.getByRole('spinbutton', { name: 'Default share of Expenses:Office' }))
      .toHaveValue(50);
  });

  test('changes an existing default share on Enter', async () => {
    seedShareDefault('Expenses:Groceries', 0);
    const { screen } = await renderApp({ path: PATH });

    const input = screen.getByRole('spinbutton', { name: 'Default share of Expenses:Groceries' });
    await expect.element(input).toHaveValue(0);
    await input.fill('40');
    await userEvent.keyboard('{Enter}');

    await expect
      .poll(() => recorded.shareDefaultUpserts()[0])
      .toMatchObject({ expense_account: 'Expenses:Groceries', share: 40 });
    await expect.element(input).toHaveValue(40);
  });

  test('removes a default share', async () => {
    seedShareDefault('Expenses:Groceries', 25);
    const { screen } = await renderApp({ path: PATH });

    await screen.getByRole('button', { name: 'Remove default for Expenses:Groceries' }).click();

    await expect.poll(() => recorded.deletedShareDefaults()).toEqual(['Expenses:Groceries']);
    await expect
      .element(screen.getByRole('spinbutton', { name: 'Default share of Expenses:Groceries' }))
      .not.toBeInTheDocument();
  });
});
