import * as React from 'react';

/** Number of requests / view mounts currently in flight. */
let pending = 0;
const listeners = new Set<() => void>();

function notify(): void {
  for (const listener of listeners) {
    listener();
  }
}

export function beginLoading(): void {
  pending += 1;
  notify();
}

export function endLoading(): void {
  pending = Math.max(0, pending - 1);
  notify();
}

export function isLoading(): boolean {
  return pending > 0;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/**
 * Whether to show the loading indicator.
 *
 * The short delay avoids flashing on instant requests; the minimum visible
 * duration avoids a one-frame blip once the indicator is shown.
 */
export function useLoading(delay = 120, minDuration = 320): boolean {
  const active = React.useSyncExternalStore(subscribe, isLoading, isLoading);
  const [visible, setVisible] = React.useState(false);
  const shownAt = React.useRef(0);

  React.useEffect(() => {
    let timer: number | undefined;

    if (active) {
      if (!visible) {
        timer = window.setTimeout(() => {
          shownAt.current = Date.now();
          setVisible(true);
        }, delay);
      }
    } else if (visible) {
      const remaining = Math.max(
        0,
        minDuration - (Date.now() - shownAt.current),
      );
      timer = window.setTimeout(() => setVisible(false), remaining);
    }

    return () => {
      if (timer !== undefined) {
        window.clearTimeout(timer);
      }
    };
  }, [active, visible, delay, minDuration]);

  return visible;
}
