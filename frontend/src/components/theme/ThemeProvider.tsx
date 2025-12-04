'use client';

import { Toaster } from 'sonner';
import { useEffect, useLayoutEffect } from 'react';
import { useThemeStore } from '@/stores/theme-store';

const useIsomorphicLayoutEffect = typeof window !== 'undefined' ? useLayoutEffect : useEffect;

interface ThemeProviderProps {
  children: React.ReactNode;
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const { theme, resolvedTheme, colorTheme, setResolvedTheme, hasHydrated } = useThemeStore();

  // Apply theme class to document
  useIsomorphicLayoutEffect(() => {
    const root = document.documentElement;
    root.classList.add('theme-transition');

    // Handle Dark Mode
    if (resolvedTheme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }

    // Handle Color Theme
    // Remove all existing theme color classes
    root.classList.forEach((cls) => {
      if (cls.startsWith('theme-') && cls !== 'theme-transition') {
        root.classList.remove(cls);
      }
    });
    // Add new color theme
    root.classList.add(`theme-${colorTheme}`);

    const timeout = setTimeout(() => {
      root.classList.remove('theme-transition');
    }, 300);

    return () => clearTimeout(timeout);
  }, [resolvedTheme, colorTheme]);

  // Listen for system preference changes
  useEffect(() => {
    if (theme !== 'system') return;

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

    const handleChange = (e: MediaQueryListEvent) => {
      setResolvedTheme(e.matches ? 'dark' : 'light');
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [theme, setResolvedTheme]);

  // Update resolved theme when theme preference changes
  useEffect(() => {
    if (!hasHydrated) return;

    if (theme === 'system') {
      const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      setResolvedTheme(systemTheme);
    } else {
      setResolvedTheme(theme);
    }
  }, [theme, hasHydrated, setResolvedTheme]);

  return (
    <>
      {children}
      <Toaster position="top-center" theme={resolvedTheme as 'light' | 'dark' | 'system'} />
    </>
  );
}
