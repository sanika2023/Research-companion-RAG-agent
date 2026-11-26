/**
 * A small preference kept in localStorage that components can subscribe to
 * (via useSyncExternalStore), so every reader updates when it changes.
 */
export interface StoredValue<T> {
  read: () => T;
  write: (value: T) => void;
  subscribe: (listener: () => void) => () => void;
  /** What the server renders, before the browser's saved value is known. */
  fallback: () => T;
}

export function storedValue<T extends string | number>(
  key: string,
  parse: (raw: string | null) => T,
): StoredValue<T> {
  const listeners = new Set<() => void>();
  // Storage can throw (private windows, blocked site data); the app must still work.
  const read = () => {
    try {
      return parse(localStorage.getItem(key));
    } catch {
      return parse(null);
    }
  };
  return {
    read,
    write: (value) => {
      try {
        localStorage.setItem(key, String(value));
      } catch {
        // Not saved; the value still applies until the page is reloaded.
      }
      listeners.forEach((listener) => listener());
    },
    subscribe: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    fallback: () => parse(null),
  };
}
