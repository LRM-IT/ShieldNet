import { CommonModule } from '@angular/common';
import {
  Component,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';

import {
  GuildLanguageService,
  GuildWorkspaceLanguage,
} from '../core/guild-language.service';
import { ShellComponent } from '../shared/shell.component';

@Component({
  selector: 'sn-guild-languages',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ShellComponent,
  ],
  template: `
    <sn-shell title="Server languages">
      <main class="page">
        <header>
          <div>
            <small>CORE SERVER</small>
            <h2>Server languages</h2>
            <p>
              Select languages available to Voting and other
              plugins on this Discord server.
            </p>
          </div>

          <button
            class="primary"
            type="button"
            (click)="save()"
            [disabled]="saving()"
          >
            {{ saving() ? 'Saving…' : 'Save languages' }}
          </button>
        </header>

        @if (error()) {
          <div class="notice error">{{ error() }}</div>
        }

        @if (success()) {
          <div class="notice success">{{ success() }}</div>
        }

        <section class="toolbar">
          <input
            type="search"
            [(ngModel)]="query"
            placeholder="Search language, native name or code…"
          />

          <button type="button" (click)="selectPopular()">
            Select popular
          </button>

          <button type="button" (click)="clearSelection()">
            Clear
          </button>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <small>SERVER LANGUAGE SET</small>
              <h3>Enabled for this server</h3>
            </div>
            <strong>{{ selectedLanguages().length }}</strong>
          </div>

          @for (
            language of selectedLanguages();
            track language.code;
            let index = $index
          ) {
            <article class="selected-language">
              <div class="identity">
                <span class="flag">
                  {{ language.flag || '🌐' }}
                </span>
                <div>
                  <strong>{{ language.name }}</strong>
                  <small>
                    {{ language.native_name }} ·
                    {{ language.code }}
                  </small>
                </div>
              </div>

              <label>
                <input
                  type="checkbox"
                  [(ngModel)]="language.enabled"
                />
                Enabled
              </label>

              <label>
                <input
                  type="radio"
                  name="primary-language"
                  [checked]="language.is_primary"
                  (change)="setPrimary(language)"
                />
                Primary
              </label>

              <label>
                <input
                  type="radio"
                  name="fallback-language"
                  [checked]="language.is_fallback"
                  (change)="setFallback(language)"
                />
                Fallback
              </label>

              <div class="row-actions">
                <button
                  type="button"
                  (click)="move(index, -1)"
                  [disabled]="index === 0"
                  title="Move up"
                >
                  ↑
                </button>

                <button
                  type="button"
                  (click)="move(index, 1)"
                  [disabled]="
                    index === selectedLanguages().length - 1
                  "
                  title="Move down"
                >
                  ↓
                </button>

                <button
                  class="danger"
                  type="button"
                  (click)="remove(language)"
                >
                  Remove
                </button>
              </div>
            </article>
          } @empty {
            <div class="empty">
              No server languages selected.
            </div>
          }
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <small>GLOBAL DIRECTORY</small>
              <h3>Available languages</h3>
            </div>
          </div>

          <div class="catalogue">
            @for (
              language of filteredCatalogue();
              track language.code
            ) {
              <button
                class="catalogue-item"
                type="button"
                (click)="add(language)"
                [disabled]="language.selected"
              >
                <span class="flag">
                  {{ language.flag || '🌐' }}
                </span>

                <span class="catalogue-name">
                  <strong>{{ language.name }}</strong>
                  <small>
                    {{ language.native_name }} ·
                    {{ language.code }}
                  </small>
                </span>

                <b>
                  {{ language.selected ? 'Added' : '+ Add' }}
                </b>
              </button>
            }
          </div>
        </section>
      </main>
    </sn-shell>
  `,
  styles: [`
    .page{
      display:grid;
      gap:1rem;
      padding:1rem
    }

    header,
    .toolbar,
    .panel-head,
    .selected-language,
    .identity,
    .row-actions{
      display:flex;
      align-items:center;
      gap:.75rem
    }

    header,
    .panel-head{
      justify-content:space-between
    }

    h2,h3,p{
      margin:0
    }

    small{
      color:var(--muted)
    }

    input,
    button{
      font:inherit;
      border:1px solid var(--line);
      border-radius:8px;
      background:#081019;
      color:var(--text);
      padding:.7rem
    }

    input[type=search]{
      min-width:320px;
      flex:1
    }

    .toolbar{
      flex-wrap:wrap
    }

    .panel,
    .notice{
      border:1px solid var(--line);
      border-radius:12px;
      background:var(--surface);
      padding:1rem
    }

    .panel{
      display:grid;
      gap:.65rem
    }

    .selected-language{
      justify-content:space-between;
      border:1px solid var(--line);
      border-radius:10px;
      padding:.75rem
    }

    .identity{
      min-width:280px
    }

    .identity div,
    .catalogue-name{
      display:grid
    }

    .flag{
      font-size:1.35rem
    }

    .catalogue{
      display:grid;
      grid-template-columns:repeat(
        3,
        minmax(0,1fr)
      );
      gap:.55rem
    }

    .catalogue-item{
      display:grid;
      grid-template-columns:34px 1fr auto;
      align-items:center;
      text-align:left
    }

    .primary{
      background:var(--primary);
      color:#03130e
    }

    .danger,
    .error{
      color:#ff8290
    }

    .success{
      color:var(--success)
    }

    .empty{
      padding:1.5rem;
      color:var(--muted);
      text-align:center
    }

    @media(max-width:900px){
      header,
      .selected-language{
        align-items:flex-start;
        flex-direction:column
      }

      .catalogue{
        grid-template-columns:1fr
      }
    }
  `],
})
export class GuildLanguagesComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(GuildLanguageService);

  readonly guildId =
    this.route.snapshot.paramMap.get('guildId') || '';

  readonly languages =
    signal<GuildWorkspaceLanguage[]>([]);

  readonly saving = signal(false);
  readonly error = signal('');
  readonly success = signal('');

  query = '';

  ngOnInit(): void {
    void this.load();
  }

  selectedLanguages(): GuildWorkspaceLanguage[] {
    return this.languages()
      .filter((item) => item.selected)
      .sort(
        (left, right) =>
          left.sort_order - right.sort_order,
      );
  }

  filteredCatalogue(): GuildWorkspaceLanguage[] {
    const query = this.query
      .trim()
      .toLowerCase();

    return this.languages().filter(
      (item) =>
        !query ||
        item.code.toLowerCase().includes(query) ||
        item.name.toLowerCase().includes(query) ||
        item.native_name.toLowerCase().includes(query),
    );
  }

  add(language: GuildWorkspaceLanguage): void {
    language.selected = true;
    language.enabled = true;
    language.sort_order =
      this.selectedLanguages().length * 10;

    const selected = this.selectedLanguages();

    if (selected.length === 1) {
      language.is_primary = true;
      language.is_fallback = true;
    }

    this.touch();
  }

  remove(language: GuildWorkspaceLanguage): void {
    const wasPrimary = language.is_primary;
    const wasFallback = language.is_fallback;

    Object.assign(language, {
      selected: false,
      enabled: false,
      is_primary: false,
      is_fallback: false,
    });

    const remaining = this.selectedLanguages();

    if (wasPrimary && remaining[0]) {
      remaining[0].is_primary = true;
    }

    if (wasFallback && remaining[0]) {
      remaining[0].is_fallback = true;
    }

    this.reindex();
  }

  setPrimary(
    language: GuildWorkspaceLanguage,
  ): void {
    for (const item of this.languages()) {
      item.is_primary =
        item.code === language.code;
    }

    language.enabled = true;
    this.touch();
  }

  setFallback(
    language: GuildWorkspaceLanguage,
  ): void {
    for (const item of this.languages()) {
      item.is_fallback =
        item.code === language.code;
    }

    language.enabled = true;
    this.touch();
  }

  move(index: number, delta: number): void {
    const selected = this.selectedLanguages();
    const target = index + delta;

    if (
      target < 0 ||
      target >= selected.length
    ) {
      return;
    }

    [
      selected[index],
      selected[target],
    ] = [
      selected[target],
      selected[index],
    ];

    selected.forEach((item, position) => {
      item.sort_order = position * 10;
    });

    this.touch();
  }

  selectPopular(): void {
    const popular = new Set([
      'en',
      'uk',
      'ru',
      'de',
      'fr',
      'es',
      'it',
      'pl',
    ]);

    for (const item of this.languages()) {
      if (popular.has(item.code)) {
        item.selected = true;
        item.enabled = true;
      }
    }

    const selected = this.selectedLanguages();

    if (
      !selected.some((item) => item.is_primary) &&
      selected[0]
    ) {
      selected[0].is_primary = true;
    }

    if (
      !selected.some((item) => item.is_fallback) &&
      selected[0]
    ) {
      selected[0].is_fallback = true;
    }

    this.reindex();
  }

  clearSelection(): void {
    for (const item of this.languages()) {
      Object.assign(item, {
        selected: false,
        enabled: false,
        is_primary: false,
        is_fallback: false,
      });
    }

    this.touch();
  }

  async save(): Promise<void> {
    const selected = this.selectedLanguages();

    if (!selected.length) {
      this.error.set(
        'Select at least one language.',
      );
      return;
    }

    if (
      !selected.some(
        (item) =>
          item.enabled && item.is_primary,
      )
    ) {
      this.error.set(
        'Select a primary enabled language.',
      );
      return;
    }

    if (
      !selected.some(
        (item) =>
          item.enabled && item.is_fallback,
      )
    ) {
      this.error.set(
        'Select a fallback enabled language.',
      );
      return;
    }

    this.saving.set(true);
    this.error.set('');
    this.success.set('');

    try {
      const result = await this.api.save(
        this.guildId,
        selected.map((item, index) => ({
          code: item.code,
          enabled: item.enabled,
          is_primary: item.is_primary,
          is_fallback: item.is_fallback,
          sort_order: index * 10,
        })),
      );

      this.languages.set(result);
      this.success.set(
        'Server languages saved.',
      );
    } catch (error: any) {
      this.error.set(
        error?.error?.detail ||
          'Unable to save server languages.',
      );
    } finally {
      this.saving.set(false);
    }
  }

  private async load(): Promise<void> {
    try {
      this.languages.set(
        await this.api.list(this.guildId),
      );
    } catch (error: any) {
      this.error.set(
        error?.error?.detail ||
          'Unable to load server languages.',
      );
    }
  }

  private reindex(): void {
    this.selectedLanguages().forEach(
      (item, index) => {
        item.sort_order = index * 10;
      },
    );

    this.touch();
  }

  private touch(): void {
    this.languages.set([
      ...this.languages(),
    ]);
  }
}
