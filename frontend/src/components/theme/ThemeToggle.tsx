'use client';

import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider,
} from '@/components/ui/tooltip';
import { useThemeStore, type Theme } from '@/stores/theme-store';
import { Sun, Moon, Monitor } from 'lucide-react';

const themeConfig: Record<Theme, { icon: typeof Sun; label: string; next: Theme }> = {
  light: { icon: Sun, label: 'Light', next: 'dark' },
  dark: { icon: Moon, label: 'Dark', next: 'system' },
  system: { icon: Monitor, label: 'System', next: 'light' },
};

export function ThemeToggle() {
  const { theme, setTheme, hasHydrated } = useThemeStore();

  // Prevent hydration mismatch - show placeholder during SSR
  if (!hasHydrated) {
    return (
      <Button variant="ghost" size="icon" className="text-muted-foreground" disabled>
        <Moon className="h-5 w-5" />
      </Button>
    );
  }

  const config = themeConfig[theme];
  const Icon = config.icon;

  const handleToggle = () => {
    setTheme(config.next);
  };

  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleToggle}
            className="text-muted-foreground hover:text-foreground"
          >
            <Icon className="h-5 w-5" />
            <span className="sr-only">Toggle theme</span>
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          <p>{config.label} mode</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
