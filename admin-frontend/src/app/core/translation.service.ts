import { HttpClient } from '@angular/common/http';
import { Injectable, computed, signal } from '@angular/core';
import { firstValueFrom, timeout } from 'rxjs';

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
  private readonly supportedLocales = ['en', 'uk', 'ru', 'de', 'ar', 'fr', 'it', 'pl'];
  private englishDictionary: Dictionary = {};
  private readonly phraseDictionary = signal<Record<string, string>>({});
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
      this.supportedLocales.map((code) =>
        firstValueFrom(this.http.get<Dictionary>(`/locales/${code}.json?v=16.62`)),
      ),
    );
    this.englishDictionary = docs[0];
    this.languages.set(
      docs.map((doc) => doc['_language'] as LanguageEntity),
    );

    const stored = localStorage.getItem(this.storageKey);
    const selected = preferred || stored || await this.detectInitialLocale();

    await this.setLocale(selected, false);
    this.ready.set(true);
  }

  async setLocale(code: string, persist = true): Promise<void> {
    const selected = this.languages().some((item) => item.code === code) ? code : 'en';
    const dictionary = await firstValueFrom(
      this.http.get<Dictionary>(`/locales/${selected}.json?v=16.62`),
    );
    this.dictionary.set(dictionary);
    this.phraseDictionary.set(this.buildPhraseDictionary(this.englishDictionary, dictionary));
    this.locale.set(selected);
    localStorage.setItem(this.storageKey, selected);
    document.documentElement.lang = selected;
    document.documentElement.dir =
      (dictionary['_language'] as LanguageEntity)?.rtl ? 'rtl' : 'ltr';
    window.dispatchEvent(new CustomEvent('guildconsole-locale-changed', { detail: selected }));

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
    const lookup = (document: Dictionary): unknown => key.split('.').reduce<unknown>((current, part) => {
      if (!current || typeof current !== 'object') return undefined;
      return (current as Dictionary)[part];
    }, document);
    const value = lookup(this.dictionary());
    if (typeof value === 'string') return value;
    const english = lookup(this.englishDictionary);
    return typeof english === 'string' ? english : fallback || key;
  }

  private async detectInitialLocale(): Promise<string> {
    const browserLanguages = [navigator.language, ...(navigator.languages ?? [])]
      .filter(Boolean)
      .map((value) => value.toLowerCase().replace('_', '-'));
    if (browserLanguages.some((value) => value === 'uk' || value.startsWith('uk-'))) {
      return 'uk';
    }
    try {
      const detected = await firstValueFrom(
        this.http.get<{ recommended_locale?: string }>('/api/v1/public/locale').pipe(timeout(1800)),
      );
      if (detected.recommended_locale === 'uk') return 'uk';
    } catch {
      // Locale detection must never prevent the application from opening.
    }
    return 'en';
  }

  hasPhrase(source: string): boolean {
    return source in this.phraseDictionary();
  }

  phrase(source: string): string {
    return this.phraseDictionary()[source] ?? source;
  }

  private buildPhraseDictionary(english: Dictionary, localized: Dictionary): Record<string, string> {
    const result: Record<string, string> = {};
    const visit = (left: unknown, right: unknown): void => {
      if (typeof left === 'string' && typeof right === 'string') {
        result[left] = right;
        return;
      }
      if (!left || !right || typeof left !== 'object' || typeof right !== 'object' || Array.isArray(left) || Array.isArray(right)) return;
      for (const key of Object.keys(left as Dictionary)) {
        if (key === '_language' || key === '_phrases') continue;
        visit((left as Dictionary)[key], (right as Dictionary)[key]);
      }
    };
    visit(english, localized);
    const phrases = localized['_phrases'];
    if (phrases && typeof phrases === 'object' && !Array.isArray(phrases)) {
      for (const [source, value] of Object.entries(phrases as Dictionary)) {
        if (typeof value === 'string') result[source] = value;
      }
    }
    return result;
  }
}
