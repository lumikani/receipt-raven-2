/**
 * The product-name normalization the backend rule engine runs on, ported to
 * TypeScript so the review screen can prefill a save-as-rule pattern with the
 * normalized row name (see `normalize_name` in the backend rule engine).
 */

// `12,50 €`, `4.75 eur/kg` — price tokens are stripped from item names.
const PRICE_TOKEN = /\d+(?:[.,]\d+)?\s*(?:€|eur\b)(?:\s*\/\s*[a-z]+)?/gi;
// `2 kpl`, `3 pcs`, `1 stk` — quantity tokens are stripped too.
const QUANTITY_TOKEN = /\d+(?:[.,]\d+)?\s*(?:kpl|pcs|stk)\b/gi;
// Punctuation becomes a space; letters (ä/ö included), digits and _ stay.
const PUNCTUATION = /[^\p{L}\p{N}_]/gu;
const WHITESPACE = /\s+/g;

export function normalizeName(name: string): string {
  let text = name.toLowerCase();
  text = text.replace(PRICE_TOKEN, ' ');
  text = text.replace(QUANTITY_TOKEN, ' ');
  text = text.replace(PUNCTUATION, ' ');
  return text.replace(WHITESPACE, ' ').trim();
}
