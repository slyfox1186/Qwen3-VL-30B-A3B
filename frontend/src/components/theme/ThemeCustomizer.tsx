'use client';

import { useThemeStore, ThemeColor } from '@/stores/theme-store';
import { Button } from '@/components/ui/button';
import { Check } from 'lucide-react';
import { cn } from '@/lib/utils';

const themes: { name: string; value: ThemeColor; color: string }[] = [
  { name: 'Zinc', value: 'zinc', color: '#52525b' },
  { name: 'Slate', value: 'slate', color: '#475569' },
  { name: 'Stone', value: 'stone', color: '#57534e' },
  { name: 'Red', value: 'red', color: '#dc2626' },
  { name: 'Rose', value: 'rose', color: '#e11d48' },
  { name: 'Orange', value: 'orange', color: '#f97316' },
  { name: 'Green', value: 'green', color: '#16a34a' },
  { name: 'Blue', value: 'blue', color: '#2563eb' },
  { name: 'Yellow', value: 'yellow', color: '#ca8a04' },
  { name: 'Violet', value: 'violet', color: '#7c3aed' },
];

export function ThemeCustomizer() {
  const { colorTheme, setColorTheme } = useThemeStore();

  return (
    <div className="p-4 space-y-4">
      <div className="space-y-1.5">
        <h4 className="font-medium leading-none tracking-tight text-sm text-muted-foreground">Theme Color</h4>
        <div className="grid grid-cols-5 gap-2">
          {themes.map((theme) => (
            <Button
              key={theme.value}
              variant="outline"
              size="icon"
              className={cn(
                "h-8 w-8 rounded-full border-2 shadow-sm transition-all hover:scale-110",
                colorTheme === theme.value ? "border-foreground/50 ring-2 ring-offset-2 ring-offset-background ring-foreground/20" : "border-transparent"
              )}
              style={{ backgroundColor: theme.color }}
              onClick={() => setColorTheme(theme.value)}
              title={theme.name}
            >
              {colorTheme === theme.value && (
                <Check className="w-3.5 h-3.5 text-white drop-shadow-md" />
              )}
              <span className="sr-only">{theme.name}</span>
            </Button>
          ))}
        </div>
      </div>
    </div>
  );
}
