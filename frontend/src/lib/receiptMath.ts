/** Arithmetic on receipt items, shared by the editor and its summary. */

export interface PricedItem {
  name: string;
  expense_account: string;
  price: number;
}

/** Item prices must add up to the total to the cent, as the ledger balances them. */
const BALANCE_TOLERANCE = 0.005;

function roundToCents(amount: number): number {
  return Math.round(amount * 100) / 100;
}

export function itemsSum(prices: readonly number[]): number {
  return roundToCents(prices.reduce((sum, price) => sum + price, 0));
}

/** How much the items are short of the total (negative: they exceed it). */
export function missingAmount(total: number, prices: readonly number[]): number {
  return roundToCents(total - itemsSum(prices));
}

export function isBalanced(total: number, prices: readonly number[]): boolean {
  return Math.abs(missingAmount(total, prices)) < BALANCE_TOLERANCE;
}

/**
 * Merge the selected items into one, placed where the first of them was.
 * Names are joined with ", ", prices summed to the cent, and the expense
 * account and classification taken from the last selected item. The merged
 * item is new: it has no id, so the backend replaces the originals with it.
 */
export function mergeItems<T extends PricedItem & { id?: number }>(
  items: readonly T[],
  selected: ReadonlySet<number>
): T[] {
  const picked = items.filter((_, index) => selected.has(index));
  const [first] = picked;
  const last = picked.at(-1);
  if (picked.length < 2 || !first || !last) return [...items];

  // The merged item keeps the last selected item's classification but is new:
  // it has no id, so the backend replaces the originals with it.
  const { id: _mergedId, ...rest } = last;
  const merged: T = {
    ...rest,
    name: picked.map((item) => item.name).join(', '),
    price: itemsSum(picked.map((item) => item.price)),
  } as T;
  const firstIndex = items.indexOf(first);
  return items.flatMap((item, index) => {
    if (index === firstIndex) return [merged];
    return selected.has(index) ? [] : [item];
  });
}
