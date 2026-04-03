'use client';

import { LaptopMinimal, MoonStar, SunMedium } from 'lucide-react';
import { useThemePreference, type ThemePreference } from '@/components/theme/theme-provider';

const OPTIONS: Array<{
  value: ThemePreference;
  label: string;
  icon: typeof SunMedium;
}> = [
  { value: 'light', label: 'Light', icon: SunMedium },
  { value: 'dark', label: 'Dark', icon: MoonStar },
  { value: 'system', label: 'System', icon: LaptopMinimal },
];

export function ThemeToggle() {
  const { preference, setPreference } = useThemePreference();

  return (
    <div className="theme-toggle" role="group" aria-label="Theme mode">
      {OPTIONS.map((option) => {
        const Icon = option.icon;
        const active = preference === option.value;
        return (
          <button
            key={option.value}
            type="button"
            className={active ? 'theme-toggle-option active' : 'theme-toggle-option'}
            aria-pressed={active}
            aria-label={`${option.label} theme`}
            title={option.label}
            onClick={() => setPreference(option.value)}
          >
            <Icon size={14} aria-hidden="true" />
          </button>
        );
      })}
    </div>
  );
}
