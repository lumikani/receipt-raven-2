import { describe, expect, test } from 'vitest';

import { normalizeName } from './classification';

describe('normalizeName (the rule engine’s normalization)', () => {
  test('lowercases and collapses whitespace', () => {
    expect(normalizeName('  Banaani   Raaka ')).toBe('banaani raaka');
  });

  test('strips price and quantity tokens', () => {
    expect(normalizeName('Thunder Sour Apple 0,5 l 1,99 €')).toBe('thunder sour apple 0 5 l');
    expect(normalizeName('Kurkku 2 kpl')).toBe('kurkku');
    expect(normalizeName('Olut 0,5 l 4,75 eur/kg')).toBe('olut 0 5 l');
    expect(normalizeName('Banaani 2,50€')).toBe('banaani');
  });

  test('turns punctuation into spaces but keeps size tokens, digits and ä/ö', () => {
    expect(normalizeName('Kauraleipä 400g')).toBe('kauraleipä 400g');
    expect(normalizeName('Kinkkupiirakka (450 g) 6,50 EUR')).toBe('kinkkupiirakka 450 g');
    expect(normalizeName('Maito 1L')).toBe('maito 1l');
  });
});
