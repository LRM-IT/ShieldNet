import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, OnChanges, OnInit, Output, SimpleChanges, computed, inject, signal } from '@angular/core';
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
  category: string | null;
  position: number;
}

@Component({
  selector: 'sn-discord-channel-picker',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="picker" data-no-auto-translate>
      <div class="control">
        <span class="channel-icon">{{ selectedIcon() }}</span>
        <select
          [ngModel]="normalizedValue()"
          (ngModelChange)="chooseId($event)"
          [disabled]="loading() || refreshing()"
          [attr.aria-label]="t('channel_picker.select','Select Discord channel')"
        >
          <option value="">{{t('channel_picker.none','No channel selected')}}</option>
          @for (group of groupedOptions(); track group.category) {
            <optgroup [label]="group.category">
              @for (channel of group.items; track channel.id) {
                <option [value]="channel.id">{{ iconFor(channel.type) }} {{ channel.name }}</option>
              }
            </optgroup>
          }
        </select>
        <button type="button" class="refresh" (click)="refreshFromDiscord()" [disabled]="refreshing() || loading()" [attr.aria-label]="t('channel_picker.refresh','Refresh Discord channels')">
          {{ refreshing() ? '…' : '↻' }}
        </button>
      </div>
      <small>{{ selectedHint() }}</small>
      @if (error()) { <div class="error">{{ error() }}</div> }
    </div>
  `,
  styles: [`
    :host{display:block}
    .picker{display:grid;gap:.35rem}
    .control{display:grid;grid-template-columns:38px minmax(0,1fr) 44px;align-items:stretch;border:1px solid var(--line);border-radius:10px;background:var(--panel-2);overflow:hidden}
    .channel-icon{display:grid;place-items:center;color:var(--primary);font-weight:900}
    select,button{min-width:0;font:inherit;border:0;background:transparent;color:var(--text)}
    select{width:100%;min-height:50px;padding:.7rem .45rem;cursor:pointer;color-scheme:dark}
    select:disabled{cursor:wait;opacity:.65}
    option,optgroup{background:var(--panel);color:var(--text)}
    .refresh{border-inline-start:1px solid var(--line);cursor:pointer;font-size:1.1rem}
    .refresh:hover{background:rgba(52,215,174,.08);color:var(--primary)}
    small{color:var(--muted);font-size:.72rem;padding-inline:.2rem}
    .error{padding:.45rem .2rem;color:#ff8290}
    .error{color:#ff8290}
  `],
})
export class DiscordChannelPickerComponent implements OnInit, OnChanges {
  private static readonly cache = new Map<string, { expires: number; data: ExplorerResponse }>();
  private readonly http = inject(HttpClient);
  private readonly i18n = inject(TranslationService);

  @Input({ required: true }) guildId = '';
  @Input() value: string | number | null = null;
  @Output() valueChange = new EventEmitter<string | null>();

  readonly loading = signal(false);
  readonly refreshing = signal(false);
  readonly error = signal('');
  readonly channels = signal<ChannelOption[]>([]);

  normalizedValue(): string {
    return this.value === null || this.value === undefined || this.value === ''
      ? ''
      : String(this.value);
  }

  selected(): ChannelOption | null {
    return this.channels().find((item) => item.id === this.normalizedValue()) || null;
  }

  readonly groupedOptions = computed(() => {
    this.i18n.locale();
    const filtered = this.channels();

    const groups = new Map<string, ChannelOption[]>();
    for (const channel of filtered) {
      const category = this.categoryLabel(channel);
      const items = groups.get(category) || [];
      items.push(channel);
      groups.set(category, items);
    }

    const collator = new Intl.Collator(this.i18n.locale(), { sensitivity: 'base', numeric: true });
    return [...groups.entries()].sort(([a], [b]) => collator.compare(a, b)).map(([category, items]) => ({
      category,
      items: items.sort((a, b) => a.position - b.position || collator.compare(a.name, b.name)),
    }));
  });

  ngOnInit(): void { void this.load(); }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['guildId'] && !changes['guildId'].firstChange) void this.load();
  }

  chooseId(value: string | number | null): void {
    const selectedId = value === null || value === undefined || value === '' ? null : String(value);
    this.value = selectedId;
    this.valueChange.emit(selectedId);
  }

  selectedLabel(): string {
    const item = this.selected();
    if (item) return `# ${item.name}`;
    if (this.normalizedValue()) return this.t('channel_picker.unknown','Unknown or removed channel');
    return this.t('channel_picker.select','Select Discord channel');
  }

  selectedHint(): string {
    const item = this.selected();
    if (item) return this.categoryLabel(item);
    if (this.normalizedValue()) return `ID ${this.normalizedValue()}`;
    return this.t('channel_picker.hint','Search synchronized channels');
  }

  selectedIcon(): string {
    const item = this.selected();
    return item ? this.iconFor(item.type) : '#';
  }

  iconFor(type: string): string {
    const value = this.normalizeType(type);
    if (value.includes('forum') || value === '15') return '▤';
    if (value.includes('news') || value.includes('announcement') || value === '5') return '◉';
    return '#';
  }

  typeLabel(type: string): string {
    const value = this.normalizeType(type);
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
      DiscordChannelPickerComponent.cache.delete(this.guildId);
      await this.load(true);
    } catch (error: any) {
      this.error.set(error?.error?.detail || this.t('channel_picker.refresh_error','Unable to refresh channels.'));
    } finally {
      this.refreshing.set(false);
    }
  }

  private async load(force = false): Promise<void> {
    if (!this.guildId) return;
    this.loading.set(true);
    this.error.set('');

    try {
      const cached = DiscordChannelPickerComponent.cache.get(this.guildId);
      const data = !force && cached && cached.expires > Date.now()
        ? cached.data
        : await firstValueFrom(this.http.get<ExplorerResponse>(`/api/v1/discord/guilds/${this.guildId}/explorer`));
      DiscordChannelPickerComponent.cache.set(this.guildId, { expires: Date.now() + 30_000, data });

      const raw = data.channels || [];
      const categories = new Map<string, string>();
      const byId = new Map(raw.map((channel) => [String(channel.id), channel]));

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
            category: this.resolveCategory(channel, byId, categories),
            position: Number(channel.position || 0),
          }))
          .sort((a, b) => a.position - b.position)
      );
    } catch (error: any) {
      this.error.set(error?.error?.detail || this.t('channel_picker.load_error','Unable to load Discord channels.'));
      this.channels.set([]);
    } finally {
      this.loading.set(false);
    }
  }

  private isCategory(type: string): boolean {
    const value = this.normalizeType(type);
    return value === 'category' || value === '4';
  }

  private isAllowed(type: string): boolean {
    return [
      'text','guild_text','0',
      'news','announcement','guild_announcement','5',
      'forum','guild_forum','15',
      'public_thread','private_thread','news_thread','10','11','12',
    ].includes(this.normalizeType(type));
  }

  private normalizeType(type: string): string {
    return String(type ?? '').trim().toLowerCase().replace(/^channeltype\./, '').replace(/[\s-]+/g, '_');
  }

  private resolveCategory(channel: ExplorerChannel, byId: Map<string, ExplorerChannel>, categories: Map<string, string>): string | null {
    let parentId = channel.parent_id == null ? '' : String(channel.parent_id);
    const visited = new Set<string>();
    while (parentId && !visited.has(parentId)) {
      visited.add(parentId);
      const category = categories.get(parentId);
      if (category) return category;
      const parent = byId.get(parentId);
      parentId = parent?.parent_id == null ? '' : String(parent.parent_id);
    }
    return null;
  }

  private categoryLabel(channel: ChannelOption): string {
    return channel.category || this.t('channel_picker.uncategorized', 'Uncategorized');
  }

  t(key: string, fallback: string): string { return this.i18n.t(key, fallback); }
}
