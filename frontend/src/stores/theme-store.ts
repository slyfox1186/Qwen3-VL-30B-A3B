import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type Theme = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';
export type ThemeColor = 'zinc' | 'slate' | 'stone' | 'gray' | 'neutral' | 'red' | 'rose' | 'orange' | 'green' | 'blue' | 'yellow' | 'violet';

interface ThemeState {
  theme: Theme;
  resolvedTheme: ResolvedTheme;
  colorTheme: ThemeColor;
  hasHydrated: boolean;
  setTheme: (theme: Theme) => void;
  setColorTheme: (color: ThemeColor) => void;
  setResolvedTheme: (resolved: ResolvedTheme) => void;
  setHasHydrated: (state: boolean) => void;
}

const getSystemTheme = (): ResolvedTheme => {
  if (typeof window === 'undefined') return 'dark';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
};

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      theme: 'system',
      resolvedTheme: 'dark',
      colorTheme: 'zinc',
      hasHydrated: false,

      setTheme: (theme) => {
        const resolved = theme === 'system' ? getSystemTheme() : theme;
        set({ theme, resolvedTheme: resolved });
      },

      setColorTheme: (colorTheme) => {
        set({ colorTheme });
      },

      setResolvedTheme: (resolved) => set({ resolvedTheme: resolved }),

      setHasHydrated: (state) => {
        const { theme } = get();
        const resolved = theme === 'system' ? getSystemTheme() : theme;
        set({ hasHydrated: state, resolvedTheme: resolved });
      },
    }),
    {
      name: 'theme-storage',
      onRehydrateStorage: () => (state) => {
        // Ensure hydration completes even if state is undefined
        if (state) {
          state.setHasHydrated(true);
        }
      },
    }
  )
);

