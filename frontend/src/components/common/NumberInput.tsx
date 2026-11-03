import { useEffect, useRef, type ComponentProps } from 'react';

import { Input } from '@/components/ui/input';

/**
 * A `type="number"` input the mouse wheel steps only while it is both focused
 * and hovered, so scrolling the page never changes the value by accident.
 * Stepping uses the native `step` clamped to min/max (`deltaY < 0` → stepUp,
 * `deltaY > 0` → stepDown) and suppresses the page scroll only while it
 * actually steps; `deltaY = 0`, disabled and readOnly inputs scroll the page
 * untouched.
 */
export function NumberInput({ ref, ...props }: Omit<ComponentProps<typeof Input>, 'type'>) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const input = inputRef.current;
    if (!input) return;
    // React attaches onWheel as a passive listener at the root, so suppressing
    // the page scroll needs a native non-passive listener on the input itself.
    const onWheel = (event: WheelEvent) => {
      if (event.deltaY === 0) return;
      if (input.disabled || input.readOnly) return;
      if (document.activeElement !== input || !input.matches(':hover')) return;
      event.preventDefault();
      if (event.deltaY < 0) input.stepUp();
      else input.stepDown();
    };
    input.addEventListener('wheel', onWheel, { passive: false });
    return () => input.removeEventListener('wheel', onWheel);
  }, []);

  return (
    <Input
      {...props}
      type="number"
      ref={(node: HTMLInputElement | null) => {
        inputRef.current = node;
        if (typeof ref === 'function') ref(node);
        else if (ref) ref.current = node;
      }}
    />
  );
}
