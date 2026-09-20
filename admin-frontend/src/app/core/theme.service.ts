import { Injectable, signal } from '@angular/core';

export interface ThemeDefinition {
  id: 'dark' | 'light';
  name: string;
  description: string;
  icon: string;
  preview: string[];
  dark: boolean;
}

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly storageKey = 'shieldnet_theme';

  readonly themes: ThemeDefinition[] = [
    {
      id: 'dark',
      name: 'Dark',
      description: 'Темна корпоративна тема для комфортної роботи.',
      icon: '●',
      preview: ['#071018', '#0d1823', '#2dd4bf'],
      dark: true,
    },
    {
      id: 'light',
      name: 'Light',
      description: 'Світла корпоративна тема з високою читабельністю.',
      icon: '○',
      preview: ['#f3f7fa', '#ffffff', '#0f8f83'],
      dark: false,
    },
  ];

  readonly activeTheme = signal<'dark' | 'light'>(this.readStoredTheme());
  readonly theme = this.activeTheme;
  readonly appearanceMode = signal<'dark' | 'light'>(this.activeTheme());

  constructor() {
    this.apply(this.activeTheme());
  }

  setTheme(themeId: string): void {
    const theme: 'dark' | 'light' = themeId === 'light' ? 'light' : 'dark';
    this.activeTheme.set(theme);
    this.appearanceMode.set(theme);
    localStorage.setItem(this.storageKey, theme);
    localStorage.removeItem('shieldnet_appearance');
    this.apply(theme);
  }

  setAppearanceMode(mode: 'auto' | 'dark' | 'light'): void {
    this.setTheme(mode === 'light' ? 'light' : 'dark');
  }

  cycleAppearanceMode(): void {
    this.setTheme(this.activeTheme() === 'dark' ? 'light' : 'dark');
  }

  private readStoredTheme(): 'dark' | 'light' {
    const stored = localStorage.getItem(this.storageKey);
    if (stored === 'light' || stored === 'arctic') return 'light';
    return 'dark';
  }

  apply(themeId: string): void {
    const theme: 'dark' | 'light' = themeId === 'light' ? 'light' : 'dark';
    document.documentElement.dataset['theme'] = theme;
    document.documentElement.dataset['appearance'] = theme;
    document.documentElement.style.colorScheme = theme;
  }
}
