import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, OnChanges, OnInit, Output, SimpleChanges, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

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
      <button type="button" class="trigger" (click)="toggle()" [disabled]="loading()">
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
        <div class="menu">
          <div class="search">
            <input type="search" [(ngModel)]="query" placeholder="Search channel or category…" />
            <button type="button" (click)="refreshFromDiscord()" [disabled]="refreshing()">
              {{ refreshing() ? '…' : '↻' }}
            </button>
          </div>

          @if (error()) { <div class="error">{{ error() }}</div> }

          <button type="button" class="clear" (click)="choose(null)">
            <span>×</span>
            <span class="copy">
              <strong>No channel selected</strong>
              <small>Choose before publishing</small>
            </span>
          </button>

          <div class="options">
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
              <div class="empty">No matching text channels.</div>
            }
          </div>
        </div>
      }
    </div>
  `,
  styles: [`
    :host{display:block;position:relative}
    .picker{position:relative}
    .trigger{width:100%;min-height:42px;display:flex;align-items:center;justify-content:space-between;gap:.8rem;text-align:left}
    .trigger-main,.clear{display:flex;align-items:center;gap:.6rem}
    .copy{display:grid;min-width:0}
    .copy strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    small{color:var(--muted);font-size:.72rem}
    .menu{position:absolute;z-index:100;top:calc(100% + .4rem);left:0;right:0;min-width:340px;max-height:430px;padding:.6rem;border:1px solid var(--line);border-radius:12px;background:#071019;box-shadow:0 18px 50px rgba(0,0,0,.45)}
    .search{display:grid;grid-template-columns:1fr 42px;gap:.4rem;margin-bottom:.45rem}
    input,button{font:inherit;border:1px solid var(--line);border-radius:8px;background:#08131d;color:var(--text);padding:.65rem}
    button{cursor:pointer}
    .clear{width:100%;color:var(--muted);text-align:left}
    .options{overflow:auto;max-height:315px}
    section header{position:sticky;top:0;padding:.55rem .45rem;background:#071019;color:var(--muted);font-size:.69rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase}
    .option{width:100%;display:grid;grid-template-columns:28px minmax(0,1fr) 22px;align-items:center;gap:.6rem;text-align:left;border-color:transparent;background:transparent}
    .option:hover,.option.selected{border-color:var(--primary);background:rgba(52,215,174,.08)}
    .empty,.error{padding:.8rem;color:var(--muted)}
    .error{color:#ff8290}
    @media(max-width:700px){.menu{position:fixed;left:1rem;right:1rem;top:18vh;max-height:64vh}}
  `],
})
export class DiscordChannelPickerComponent implements OnInit, OnChanges {
  private readonly http = inject(HttpClient);

  @Input({ required: true }) guildId = '';
  @Input() value: string | number | null = null;
  @Output() valueChange = new EventEmitter<string | null>();

  readonly open = signal(false);
  readonly loading = signal(false);
  readonly refreshing = signal(false);
  readonly error = signal('');
  readonly channels = signal<ChannelOption[]>([]);
  query = '';

  readonly normalizedValue = computed(() =>
    this.value === null || this.value === undefined || this.value === '' ? '' : String(this.value)
  );

  readonly selected = computed(() =>
    this.channels().find((item) => item.id === this.normalizedValue()) || null
  );

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

  toggle(): void { this.open.update((value) => !value); }

  choose(channel: ChannelOption | null): void {
    this.value = channel?.id || null;
    this.valueChange.emit(channel?.id || null);
    this.open.set(false);
    this.query = '';
  }

  selectedLabel(): string {
    const item = this.selected();
    if (item) return `# ${item.name}`;
    if (this.normalizedValue()) return 'Unknown or removed channel';
    return 'Select Discord channel';
  }

  selectedHint(): string {
    const item = this.selected();
    if (item) return item.category;
    if (this.normalizedValue()) return `ID ${this.normalizedValue()}`;
    return 'Search synchronized channels';
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
    if (value.includes('forum') || value === '15') return 'Forum';
    if (value.includes('news') || value.includes('announcement') || value === '5') return 'Announcement';
    return 'Text channel';
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
      this.error.set(error?.error?.detail || 'Unable to refresh channels.');
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
              ? categories.get(String(channel.parent_id)) || 'Uncategorized'
              : 'Uncategorized',
            position: Number(channel.position || 0),
          }))
          .sort((a, b) =>
            a.category.localeCompare(b.category) ||
            a.position - b.position ||
            a.name.localeCompare(b.name)
          )
      );
    } catch (error: any) {
      this.error.set(error?.error?.detail || 'Unable to load Discord channels.');
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
    ].includes(String(type).toLowerCase());
  }
}
