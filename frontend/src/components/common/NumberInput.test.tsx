import { expect, test } from 'vitest';
import { render } from 'vitest-browser-react';
import type { Locator } from 'vitest/browser';

import '@/index.css';

import { NumberInput } from './NumberInput';

/**
 * Runs `dispatch` while recording whether the wheel event's default action
 * (the page scroll) was prevented by the time the event reached the document.
 */
async function captureWheelDefault(dispatch: () => unknown) {
  let defaultPrevented: boolean | undefined;
  const listener = (event: WheelEvent) => {
    defaultPrevented = event.defaultPrevented;
  };
  document.addEventListener('wheel', listener);
  try {
    await dispatch();
  } finally {
    document.removeEventListener('wheel', listener);
  }
  return defaultPrevented;
}

/** Wheels over `locator` and reports whether the page scroll was prevented. */
function wheelAndReportDefault(locator: Locator, delta: { x?: number; y: number }) {
  return captureWheelDefault(() => locator.wheel({ delta }));
}

test('steps with the native step while focused and hovered, clamped to min/max', async () => {
  const screen = await render(
    <NumberInput aria-label="Flatmate share" defaultValue={10} step={5} min={0} max={20} />
  );
  const input = screen.getByRole('spinbutton', { name: 'Flatmate share' });

  await input.click(); // focuses the input and leaves the cursor on it
  expect(await wheelAndReportDefault(input, { y: -100 })).toBe(true);
  await expect.element(input).toHaveValue(15);

  expect(await wheelAndReportDefault(input, { y: 100 })).toBe(true);
  await expect.element(input).toHaveValue(10);

  // Two steps up reach the max of 20; a third stays clamped there.
  await input.wheel({ delta: { y: -100 } });
  await input.wheel({ delta: { y: -100 } });
  await expect.element(input).toHaveValue(20);
  await input.wheel({ delta: { y: -100 } });
  await expect.element(input).toHaveValue(20);
});

test('wheel over a merely hovered input scrolls the page instead of stepping', async () => {
  window.scrollTo(0, 0);
  const screen = await render(
    <div>
      <div aria-hidden style={{ height: '3000px' }} />
      <NumberInput aria-label="Flatmate share" defaultValue={10} />
    </div>
  );
  const input = screen.getByRole('spinbutton', { name: 'Flatmate share' });

  // No click: the wheel hovers the input, but nothing is focused.
  expect(await wheelAndReportDefault(input, { y: 120 })).toBe(false);
  await expect.element(input).toHaveValue(10);
  expect(window.scrollY).toBeGreaterThan(0);
});

test('a horizontal wheel (deltaY = 0) touches neither the value nor the page scroll', async () => {
  const screen = await render(<NumberInput aria-label="Flatmate share" defaultValue={10} />);
  const input = screen.getByRole('spinbutton', { name: 'Flatmate share' });

  await input.click();
  expect(await wheelAndReportDefault(input, { x: 120, y: 0 })).toBe(false);
  await expect.element(input).toHaveValue(10);
});

test('a readOnly input never steps, even while focused and hovered', async () => {
  const screen = await render(
    <NumberInput aria-label="Flatmate share" defaultValue={10} readOnly />
  );
  const input = screen.getByRole('spinbutton', { name: 'Flatmate share' });

  await input.click(); // readOnly inputs still take focus
  expect(document.activeElement).toBe(input.element());
  expect(await wheelAndReportDefault(input, { y: -100 })).toBe(false);
  await expect.element(input).toHaveValue(10);
});

test('a disabled input never steps and never blocks the page scroll', async () => {
  const screen = await render(
    <NumberInput aria-label="Flatmate share" defaultValue={10} disabled />
  );
  const input = screen.getByRole('spinbutton', { name: 'Flatmate share' });

  // Browsers do not deliver trusted mouse events to disabled controls, so
  // fire the wheel event directly at the element.
  const defaultPrevented = await captureWheelDefault(() =>
    input
      .element()
      .dispatchEvent(new WheelEvent('wheel', { deltaY: -100, bubbles: true, cancelable: true }))
  );

  expect(defaultPrevented).toBe(false);
  await expect.element(input).toHaveValue(10);
});

/**
 * Chromium does not resolve webkit pseudo-elements through getComputedStyle,
 * so the spinner-hiding rule is found among the applied stylesheet rules
 * (Tailwind keeps them inside CSS layers).
 */
function appliedSpinnerRule() {
  const styleRules: CSSStyleRule[] = [];
  const walk = (rules: CSSRuleList) => {
    for (const rule of rules) {
      if (rule instanceof CSSStyleRule) styleRules.push(rule);
      else if ('cssRules' in rule) walk((rule as CSSGroupingRule).cssRules);
    }
  };
  for (const sheet of document.styleSheets) walk(sheet.cssRules);
  return styleRules.find(
    (rule) =>
      rule.selectorText.includes('input[type=') &&
      rule.selectorText.includes('::-webkit-outer-spin-button') &&
      rule.selectorText.includes('::-webkit-inner-spin-button')
  );
}

test('the app stylesheet hides the native spinner arrows on number inputs', async () => {
  const screen = await render(<NumberInput aria-label="Flatmate share" defaultValue={1} />);
  const input = screen.getByRole('spinbutton', { name: 'Flatmate share' }).element();

  expect(getComputedStyle(input).appearance).toBe('textfield');
  expect(appliedSpinnerRule()?.style.getPropertyValue('-webkit-appearance')).toBe('none');
});
