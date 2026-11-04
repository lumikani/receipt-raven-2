import type { RenderResult } from 'vitest-browser-react';

/**
 * Fill the fields of the shared rule dialog (rules screen's edit dialog and
 * the review screen's save-as-rule dialog) in a browser test.
 */
export async function fillRuleDialog(
  screen: RenderResult,
  fields: { pattern?: string; account?: string; share?: string; maxTypos?: string }
) {
  const dialog = screen.getByRole('dialog');
  if (fields.pattern !== undefined) {
    await dialog
      .getByRole('textbox', { name: 'Pattern (normalized product name)' })
      .fill(fields.pattern);
  }
  if (fields.account !== undefined) {
    await dialog.getByRole('combobox', { name: 'Rule expense account' }).click();
    await screen.getByRole('option', { name: fields.account }).click();
  }
  if (fields.share !== undefined) {
    await dialog
      .getByRole('spinbutton', { name: 'Flatmate share override (blank = account default)' })
      .fill(fields.share);
  }
  if (fields.maxTypos !== undefined) {
    await dialog.getByRole('spinbutton', { name: 'Max typos' }).fill(fields.maxTypos);
  }
}
