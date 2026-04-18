'use client';

import { createContext, useContext, useEffect, useMemo, useState } from 'react';

export type ThemePreference = 'light' | 'dark' | 'system';
type AppliedTheme = 'light' | 'dark';

type ThemeContextValue = {
  preference: ThemePreference;
  appliedTheme: AppliedTheme;
  setPreference: (preference: ThemePreference) => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);
const STORAGE_KEY = 'easyecom-theme-preference';
const VALID_PREFERENCES: ThemePreference[] = ['light', 'dark', 'system'];

function normalizePreference(value: string | null | undefined): ThemePreference | null {
  if (value && VALID_PREFERENCES.includes(value as ThemePreference)) {
    return value as ThemePreference;
  }
  return null;
}

function readPersistedPreference(): ThemePreference {
  try {
    const stored = normalizePreference(window.localStorage.getItem(STORAGE_KEY));
    if (stored) {
      return stored;
    }
  } catch {
    // Ignore storage read issues (private mode/restricted environments).
  }
  const datasetValue = normalizePreference(document.documentElement.dataset.themePreference);
  return datasetValue ?? 'system';
}

function resolveTheme(preference: ThemePreference): AppliedTheme {
  if (preference === 'system') {
    if (typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
    return 'light';
  }
  return preference;
}

function applyTheme(preference: ThemePreference) {
  const resolved = resolveTheme(preference);
  document.documentElement.dataset.theme = resolved;
  document.documentElement.dataset.themePreference = preference;
  return resolved;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePreference>('system');
  const [appliedTheme, setAppliedTheme] = useState<AppliedTheme>('light');

  useEffect(() => {
    const initialPreference = readPersistedPreference();
    setPreferenceState(initialPreference);
    setAppliedTheme(applyTheme(initialPreference));
  }, []);

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const syncSystemTheme = () => {
      setAppliedTheme(applyTheme(preference));
    };

    if (typeof media.addEventListener === 'function') {
      media.addEventListener('change', syncSystemTheme);
      return () => media.removeEventListener('change', syncSystemTheme);
    }

    // Safari fallback for older MediaQueryList implementations.
    media.addListener(syncSystemTheme);
    return () => media.removeListener(syncSystemTheme);
  }, [preference]);

  const setPreference = (nextPreference: ThemePreference) => {
    setPreferenceState(nextPreference);
    try {
      window.localStorage.setItem(STORAGE_KEY, nextPreference);
    } catch {
      // Ignore storage write issues while keeping in-memory + DOM state updated.
    }
    setAppliedTheme(applyTheme(nextPreference));
  };

  const value = useMemo(
    () => ({
      preference,
      appliedTheme,
      setPreference,
    }),
    [appliedTheme, preference]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useThemePreference() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useThemePreference must be used inside ThemeProvider');
  }
  return context;
}
