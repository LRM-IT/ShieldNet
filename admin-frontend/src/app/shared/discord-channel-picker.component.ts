import { CommonModule } from '@angular/common';
import { Component, ElementRef, EventEmitter, HostListener, Input, OnChanges, OnInit, Output, SimpleChanges, ViewChild, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { TranslationService } from '../core/translation.service';

interface ExplorerChannel {
  id: string | number;
  parent_id?: string | number | null;
  name: string;
  type: string;
  position?: number;
}

interface ExplorerResponse { channels?: ExplorerChannel[]; }

interface ChannelOption {
  id: string;
  name: string;
  type: string;
  category: string;
  position: number;
}

@Component({
  selector: 'sn-discord-channel-picker',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="picker">
      <button #trigger type="button" class="trigger" (click)="toggle()" [disabled]="loading()">
        <span class="trigger-main">
          <b>{{ selectedIcon() }}</b>
          <span class="copy">
            <strong>{{ selectedLabel() }}</strong>
            <small>{{ selectedHint() }}</small>
          </span>
        </span>
        <span>⌄</span>
      </button>

      @if (open()) {
        <div class="menu" [style.top.px]="menuPosition().top" [style.left.px]="menuPosition().left" [style.width.px]="menuPosition().width" [style.height.px]="menuPosition().height">
          <div class="search">
            <input type="search" [(ngModel)]="query" [placeholder]="t('channel_picker.search','Search channel or category…')" />
            <button type="button" (click)="refreshFromDiscord()" [disabled]="refreshing()">
              {{ refreshing() ? '…' : '↻' }}
            </button>
          </div>

          @if (error()) { <div class="error">{{ error() }}</div> }

          <button type="button" class="clear" (click)="choose(null)">
            <span>×</span>
            <span class="copy">
              <strong>{{t('channel_picker.none','No channel selected')}}</strong>
              <small>{{t('channel_picker.choose_before_publish','Choose before publishing')}}</small>
            </span>
          </button>

          <div class="options" tabindex="0" (wheel)="$event.stopPropagation()">
            @for (group of groupedOptions(); track group.category) {
              <section>
                <header>{{ group.category }}</header>
                @for (channel of group.items; track channel.id) {
                  <button
                    type="button"
                    class="option"
                    [class.selected]="channel.id === normalizedValue()"
                    (click)="choose(channel)"
                  >
                    <span>{{ iconFor(channel.type) }}</span>
                    <span class="copy">
                      <strong># {{ channel.name }}</strong>
                      <small>{{ typeLabel(channel.type) }}</small>
                    </span>
                    @if (channel.id === normalizedValue()) { <span>✓</span> }
                  </button>
                }
              </section>
            } @empty {
              <div class="empty">{{t('channel_picker.no_matches','No matching text channels.')}}</div>
            }
          </div>
        </div>
      }
    </div>
  `,
  styles: [`
    :host{display:block;position:relative;isolation:isolate}
    :host:has(.menu){z-index:1000}
    .picker{position:relative;z-index:1}
    .trigger{box-sizing:border-box;width:100%;min-height:48px;display:flex;align-items:center;justify-content:space-between;gap:.8rem;text-align:left}
    .trigger-main,.clear{display:flex;align-items:center;gap:.6rem}
    .copy{display:grid;min-width:0}
    .copy strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    small{color:var(--muted);font-size:.72rem}
    .menu{position:fixed;z-index:10000;min-width:300px;max-height:430px;display:flex;flex-direction:column;overflow:hidden;padding:.6rem;border:1px solid var(--line);border-radius:12px;background:var(--panel);box-shadow:var(--shadow)}
    .search{display:grid;grid-template-columns:1fr 42px;gap:.4rem;margin-bottom:.45rem}
    input,button{font:inherit;border:1px solid var(--line);border-radius:8px;background:var(--panel-2);color:var(--text);padding:.65rem}
    button{cursor:pointer}
    .clear{width:100%;color:var(--muted);text-align:left}
    .options{flex:1;min-height:0;overflow-x:hidden;overflow-y:auto;overscroll-behavior:contain;scrollbar-gutter:stable;padding-right:.2rem;touch-action:pan-y}
    .options::-webkit-scrollbar{width:9px}.options::-webkit-scrollbar-track{background:var(--panel-2);border-radius:9px}.options::-webkit-scrollbar-thumb{background:var(--line-strong);border-radius:9px}.options::-webkit-scrollbar-thumb:hover{background:var(--primary)}
    section header{position:sticky;top:0;padding:.55rem .45rem;background:var(--panel);color:var(--muted);font-size:.69rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase}
    .option{width:100%;display:grid;grid-template-columns:28px minmax(0,1fr) 22px;align-items:center;gap:.6rem;text-align:left;border-color:transparent;background:transparent}
    .option:hover,.option.selected{border-color:var(--primary);background:rgba(52,215,174,.08)}
    .empty,.error{padding:.8rem;color:var(--muted)}
    .error{color:#ff8290}
    @media(max-width:700px){.menu{min-width:0;max-height:calc(100vh - 2rem)}}
  `],
})
export class DiscordChannelPickerComponent implements OnInit, OnChanges {
  private readonly http = inject(HttpClient);
  private readonly i18n = inject(TranslationService);
  @ViewChild('trigger') trigger?: ElementRef<HTMLButtonElement>;

  @Input({ required: true }) guildId = '';
  @Input() value: string | number | null = null;
  @Output() valueChange = new EventEmitter<string | null>();

  readonly open = signal(false);
  readonly loading = signal(false);
  readonly refreshing = signal(false);
  readonly error = signal('');
  readonly channels = signal<ChannelOption[]>([]);
  readonly menuPosition = signal({ top: 0, left: 0, width: 340, height: 430 });
  query = '';

  normalizedValue(): string {
    return this.value === null || this.value === undefined || this.value === ''
      ? ''
      : String(this.value);
  }

  selected(): ChannelOption | null {
    return this.channels().find((item) => item.id === this.normalizedValue()) || null;
  }

  readonly groupedOptions = computed(() => {
    const query = this.query.trim().toLowerCase();
    const filtered = this.channels().filter((item) =>
      !query ||
      item.name.toLowerCase().includes(query) ||
      item.category.toLowerCase().includes(query) ||
      item.type.toLowerCase().includes(query)
    );

    const groups = new Map<string, ChannelOption[]>();
    for (const channel of filtered) {
      const items = groups.get(channel.category) || [];
      items.push(channel);
      groups.set(channel.category, items);
    }

    return [...groups.entries()].map(([category, items]) => ({
      category,
      items: items.sort((a, b) => a.position - b.position),
    }));
  });

  ngOnInit(): void { void this.load(); }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['guildId'] && !changes['guildId'].firstChange) void this.load();
  }

  toggle(): void {
    if (this.open()) {
      this.open.set(false);
      return;
    }
    this.updateMenuPosition();
    this.open.set(true);
  }

  @HostListener('window:resize')
  onViewportResize(): void {
    if (this.open()) this.updateMenuPosition();
  }

  private updateMenuPosition(): void {
    const rect = this.trigger?.nativeElement.getBoundingClientRect();
    if (!rect) return;
    const margin = 16;
    const gap = 7;
    const width = Math.min(Math.max(rect.width, 300), window.innerWidth - margin * 2);
    const left = Math.min(Math.max(rect.left, margin), window.innerWidth - width - margin);
    const roomBelow = window.innerHeight - rect.bottom - gap - margin;
    const roomAbove = rect.top - gap - margin;
    const height = Math.min(430, Math.max(220, roomBelow >= 220 ? roomBelow : roomAbove));
    const top = roomBelow >= 220
      ? rect.bottom + gap
      : Math.max(margin, rect.top - gap - height);
    this.menuPosition.set({ top, left, width, height });
  }

  choose(channel: ChannelOption | null): void {
    const selectedId = channel?.id ?? null;
    this.value = selectedId;
    this.valueChange.emit(selectedId);
    this.open.set(false);
    this.query = '';
  }

  selectedLabel(): string {
    const item = this.selected();
    if (item) return `# ${item.name}`;
    if (this.normalizedValue()) return this.t('channel_picker.unknown','Unknown or removed channel');
    return this.t('channel_picker.select','Select Discord channel');
  }

  selectedHint(): string {
    const item = this.selected();
    if (item) return item.category;
    if (this.normalizedValue()) return `ID ${this.normalizedValue()}`;
    return this.t('channel_picker.hint','Search synchronized channels');
  }

  selectedIcon(): string {
    const item = this.selected();
    return item ? this.iconFor(item.type) : '#';
  }

  iconFor(type: string): string {
    const value = String(type).toLowerCase();
    if (value.includes('forum') || value === '15') return '▤';
    if (value.includes('news') || value.includes('announcement') || value === '5') return '◉';
    return '#';
  }

  typeLabel(type: string): string {
    const value = String(type).toLowerCase();
    if (value.includes('thread') || ['10','11','12'].includes(value)) return this.t('channel_picker.thread','Thread');
    if (value.includes('forum') || value === '15') return this.t('channel_picker.forum','Forum');
    if (value.includes('news') || value.includes('announcement') || value === '5') return this.t('channel_picker.announcement','Announcement');
    return this.t('channel_picker.text_channel','Text channel');
  }

  async refreshFromDiscord(): Promise<void> {
    if (!this.guildId || this.refreshing()) return;
    this.refreshing.set(true);
    this.error.set('');

    try {
      await firstValueFrom(
        this.http.post(`/api/v1/discord/guilds/${this.guildId}/structure/refresh`, {})
      );
      await new Promise((resolve) => setTimeout(resolve, 1800));
      await this.load();
    } catch (error: any) {
      this.error.set(error?.error?.detail || this.t('channel_picker.refresh_error','Unable to refresh channels.'));
    } finally {
      this.refreshing.set(false);
    }
  }

  private async load(): Promise<void> {
    if (!this.guildId) return;
    this.loading.set(true);
    this.error.set('');

    try {
      const data = await firstValueFrom(
        this.http.get<ExplorerResponse>(`/api/v1/discord/guilds/${this.guildId}/explorer`)
      );

      const raw = data.channels || [];
      const categories = new Map<string, string>();

      for (const channel of raw) {
        if (this.isCategory(channel.type)) categories.set(String(channel.id), channel.name);
      }

      this.channels.set(
        raw
          .filter((channel) => this.isAllowed(channel.type))
          .map((channel) => ({
            id: String(channel.id),
            name: channel.name,
            type: String(channel.type),
            category: channel.parent_id
              ? categories.get(String(channel.parent_id)) || this.t('channel_picker.uncategorized','Uncategorized')
              : this.t('channel_picker.uncategorized','Uncategorized'),
            position: Number(channel.position || 0),
          }))
          .sort((a, b) =>
            a.category.localeCompare(b.category) ||
            a.position - b.position ||
            a.name.localeCompare(b.name)
          )
      );
    } catch (error: any) {
      this.error.set(error?.error?.detail || this.t('channel_picker.load_error','Unable to load Discord channels.'));
      this.channels.set([]);
    } finally {
      this.loading.set(false);
    }
  }

  private isCategory(type: string): boolean {
    const value = String(type).toLowerCase();
    return value === 'category' || value === '4';
  }

  private isAllowed(type: string): boolean {
    return [
      'text','guild_text','0',
      'news','announcement','guild_announcement','5',
      'forum','guild_forum','15',
      'public_thread','private_thread','news_thread','10','11','12',
    ].includes(String(type).toLowerCase());
  }

  t(key: string, fallback: string): string { return this.i18n.t(key, fallback); }
}
