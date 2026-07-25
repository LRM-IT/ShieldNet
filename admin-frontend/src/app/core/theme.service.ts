import { Injectable, signal } from '@angular/core';

export interface ThemeDefinition {
  id: string;
  name: string;
  description: string;
  icon: string;
  preview: string[];
  dark: boolean;
}

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly storageKey = 'shieldnet_theme';
  private readonly appearanceKey = 'shieldnet_appearance';
  private mediaQuery: MediaQueryList | null = null;

  readonly themes: ThemeDefinition[] = [
    {
      id: 'shieldnet',
      name: 'ShieldNet',
      description: 'Фірмова бірюзова тема з технологічною сіткою.',
      icon: '⬡',
      preview: ['#05080d', '#0d141d', '#35e2b2'],
      dark: true,
    },
    {
      id: 'midnight',
      name: 'Midnight',
      description: 'Темно-синя тема для тривалої роботи ввечері.',
      icon: '◐',
      preview: ['#060914', '#10172a', '#6c8cff'],
      dark: true,
    },
    {
      id: 'carbon',
      name: 'Carbon',
      description: 'Стримана графітова тема без яскравих акцентів.',
      icon: '◆',
      preview: ['#090909', '#171717', '#c7c7c7'],
      dark: true,
    },
    {
      id: 'oled',
      name: 'OLED',
      description: 'Максимально чорний фон для OLED-дисплеїв.',
      icon: '●',
      preview: ['#000000', '#090909', '#2df0ae'],
      dark: true,
    },
    {
      id: 'aurora',
      name: 'Aurora',
      description: 'Фіолетово-блакитний градієнтний стиль.',
      icon: '✦',
      preview: ['#090714', '#171126', '#aa78ff'],
      dark: true,
    },
    {
      id: 'arctic',
      name: 'Arctic',
      description: 'Світла корпоративна тема з холодними акцентами.',
      icon: '❄',
      preview: ['#eef4f8', '#ffffff', '#1976d2'],
      dark: false,
    },
  ];

  readonly activeTheme = signal(this.readStoredTheme());
  readonly theme = this.activeTheme;
  readonly appearanceMode = signal<'auto' | 'dark' | 'light'>(this.readAppearanceMode());

  constructor() {
    this.mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    this.mediaQuery.addEventListener('change', () => {
      if (this.appearanceMode() === 'auto') this.applyAppearance();
    });
    this.applyAppearance();
  }

  setTheme(themeId: string): void {
    const valid = this.themes.some((item) => item.id === themeId)
      ? themeId
      : 'shieldnet';
    this.activeTheme.set(valid);
    localStorage.setItem(this.storageKey, valid);
    this.applyAppearance();
  }

  setAppearanceMode(mode: 'auto' | 'dark' | 'light'): void {
    this.appearanceMode.set(mode);
    localStorage.setItem(this.appearanceKey, mode);
    this.applyAppearance();
  }

  cycleAppearanceMode(): void {
    const order: Array<'auto' | 'dark' | 'light'> = ['auto', 'dark', 'light'];
    const index = order.indexOf(this.appearanceMode());
    this.setAppearanceMode(order[(index + 1) % order.length]);
  }

  private readAppearanceMode(): 'auto' | 'dark' | 'light' {
    const stored = localStorage.getItem(this.appearanceKey);
    return stored === 'dark' || stored === 'light' || stored === 'auto' ? stored : 'auto';
  }

  private applyAppearance(): void {
    const mode = this.appearanceMode();
    const wantsDark = mode === 'dark' || (mode === 'auto' && (this.mediaQuery?.matches ?? true));
    const selected = this.themes.find((item) => item.id === this.activeTheme());
    const themeId = wantsDark
      ? (selected?.dark === false ? 'shieldnet' : this.activeTheme())
      : 'arctic';
    document.documentElement.dataset['appearance'] = mode;
    this.apply(themeId);
  }

  private readStoredTheme(): string {
    const stored = localStorage.getItem(this.storageKey);
    return this.themes.some((item) => item.id === stored) ? stored! : 'shieldnet';
  }

  apply(themeId: string): void {
    document.documentElement.dataset['theme'] = themeId;
    const definition = this.themes.find((item) => item.id === themeId);
    document.documentElement.style.colorScheme = definition?.dark === false ? 'light' : 'dark';
  }
}
