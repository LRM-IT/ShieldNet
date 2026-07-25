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

  constructor() {
    this.apply(this.activeTheme());
  }

  setTheme(themeId: string): void {
    const valid = this.themes.some((item) => item.id === themeId)
      ? themeId
      : 'shieldnet';
    this.activeTheme.set(valid);
    localStorage.setItem(this.storageKey, valid);
    this.apply(valid);
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
