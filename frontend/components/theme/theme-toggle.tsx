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
  { value: 'system', label: 'Auto', icon: LaptopMinimal },
];

export function ThemeToggle() {
  const { preference, appliedTheme, setPreference } = useThemePreference();

  return (
    <div className="theme-toggle" role="group" aria-label="Display mode" data-applied-theme={appliedTheme}>
      {OPTIONS.map((option) => {
        const Icon = option.icon;
        const active = preference === option.value;
        const applied =
          option.value === 'system'
            ? false
            : (option.value === 'light' && appliedTheme === 'light') || (option.value === 'dark' && appliedTheme === 'dark');
        const className = [
          'theme-toggle-option',
          active ? 'active' : '',
          applied ? 'is-applied' : '',
        ]
          .filter(Boolean)
          .join(' ');
        return (
          <button
            key={option.value}
            type="button"
            className={className}
            aria-pressed={active}
            aria-label={`${option.label} theme`}
            title={option.label}
            onClick={() => setPreference(option.value)}
          >
            <Icon size={14} aria-hidden="true" />
            <span>{option.label}</span>
          </button>
        );
      })}
      <span className="theme-toggle-applied" aria-live="polite">
        Active: {appliedTheme === 'dark' ? 'Dark' : 'Light'}
      </span>
    </div>
  );
}
