import { Injectable, computed, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

export interface LanguageEntity {
  code: string;
  icon: string;
  name: string;
  english_name: string;
  discord_locale: string[];
  rtl: boolean;
  version: number;
}

@Injectable({ providedIn: 'root' })
export class TranslationService {
  readonly languages = signal<LanguageEntity[]>([]);
  readonly locale = signal('en');
  readonly currentLanguage = computed(
    () => this.languages().find((item) => item.code === this.locale()) ?? null,
  );

  constructor(private readonly http: HttpClient) {}

  async initialize(preferred?: string | null): Promise<void> {
    const languages = await firstValueFrom(
      this.http.get<LanguageEntity[]>('/api/v1/locales'),
    );
    this.languages.set(languages);

    const browser = navigator.language;
    const selected =
      preferred ||
      localStorage.getItem('shieldnet_locale') ||
      languages.find((item) => item.discord_locale.includes(browser))?.code ||
      languages.find((item) => browser.startsWith(item.code))?.code ||
      'en';

    this.locale.set(selected);
    localStorage.setItem('shieldnet_locale', selected);
  }
}
