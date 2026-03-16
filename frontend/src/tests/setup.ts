import '@testing-library/jest-dom/vitest';

// jsdom does not always provide a working localStorage.
// Provide a simple in-memory implementation so tests can call
// localStorage.getItem / setItem / removeItem / clear reliably.
if (typeof globalThis.localStorage === 'undefined' || typeof globalThis.localStorage.clear !== 'function') {
  const store: Record<string, string> = {};
  globalThis.localStorage = {
    getItem(key: string) { return store[key] ?? null; },
    setItem(key: string, value: string) { store[key] = String(value); },
    removeItem(key: string) { delete store[key]; },
    clear() { for (const k of Object.keys(store)) delete store[k]; },
    get length() { return Object.keys(store).length; },
    key(index: number) { return Object.keys(store)[index] ?? null; },
  } as Storage;
}
