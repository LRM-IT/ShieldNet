import { HttpClient } from '@angular/common/http';
import { Injectable, computed, signal } from '@angular/core';
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

type Dictionary = Record<string, unknown>;

@Injectable({ providedIn: 'root' })
export class TranslationService {
  private readonly storageKey = 'shieldnet_locale';
  readonly locale = signal('en');
  readonly dictionary = signal<Dictionary>({});
  readonly languages = signal<LanguageEntity[]>([]);
  readonly ready = signal(false);
  readonly currentLanguage = computed(
    () => this.languages().find((item) => item.code === this.locale()) ?? null,
  );

  constructor(private readonly http: HttpClient) {}

  async initialize(preferred?: string | null): Promise<void> {
    const docs = await Promise.all(
      ['en', 'uk', 'ru'].map((code) =>
        firstValueFrom(this.http.get<Dictionary>(`/locales/${code}.json?v=14.27`)),
      ),
    );
    this.languages.set(
      docs.map((doc) => doc['_language'] as LanguageEntity),
    );

    const browser = navigator.language || 'en';
    const stored = localStorage.getItem(this.storageKey);
    const selected =
      preferred ||
      stored ||
      this.languages().find((item) => item.discord_locale.includes(browser))?.code ||
      this.languages().find((item) => browser.startsWith(item.code))?.code ||
      'en';

    await this.setLocale(selected, false);
    this.ready.set(true);
  }

  async setLocale(code: string, persist = true): Promise<void> {
    const selected = this.languages().some((item) => item.code === code) ? code : 'en';
    const dictionary = await firstValueFrom(
      this.http.get<Dictionary>(`/locales/${selected}.json?v=14.27`),
    );
    this.dictionary.set(dictionary);
    this.locale.set(selected);
    localStorage.setItem(this.storageKey, selected);
    document.documentElement.lang = selected;
    document.documentElement.dir =
      (dictionary['_language'] as LanguageEntity)?.rtl ? 'rtl' : 'ltr';

    if (persist) {
      // Local persistence is immediate. Backend profile persistence is optional
      // until the preferences endpoint is deployed.
      try {
        await firstValueFrom(
          this.http.patch('/api/v1/auth/me/preferences', {
            preferred_locale: selected,
            use_discord_locale: false,
          }),
        );
      } catch {
        // Keep the browser preference even on older backend versions.
      }
    }
  }

  t(key: string, fallback = ''): string {
    const value = key.split('.').reduce<unknown>((current, part) => {
      if (!current || typeof current !== 'object') return undefined;
      return (current as Dictionary)[part];
    }, this.dictionary());
    return typeof value === 'string' ? value : fallback || key;
  }
}
