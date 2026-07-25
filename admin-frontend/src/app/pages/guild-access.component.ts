import { CommonModule } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ShellComponent } from '../shared/shell.component';

interface AccessItem {
  id: string;
  discord_user_id: string;
  role: 'admin' | 'moderator';
  status: 'active' | 'pending' | 'revoked';
  permissions: string[];
  expires_at: string | null;
  is_expired: boolean;
  expires_soon: boolean;
  seconds_remaining: number | null;
  is_guild_owner: boolean;
}

interface AccessResponse {
  owner_discord_id: string;
  allowed_permissions: string[];
  expired_now: number;
  expires_soon_count: number;
  items: AccessItem[];
}

interface AccessHistoryItem {
  id: string;
  event_type: string;
  actor_user_id: string | null;
  target_id: string | null;
  payload: Record<string, unknown>;
  result: string;
  message: string | null;
  created_at: string | null;
}

interface AccessHistoryResponse {
  items: AccessHistoryItem[];
}

@Component({
  selector: 'sn-guild-access',
  standalone: true,
  imports: [CommonModule, FormsModule, ShellComponent],
  template: `
    <sn-shell title="Guild Access">
      <section class="hero">
        <div>
          <span>DELEGATED ADMINISTRATION</span>
          <h2>Guild access</h2>
          <p>Grant limited or temporary access and review every access change.</p>
        </div>
        <button (click)="reloadAll()" [disabled]="loading()">Refresh</button>
      </section>

      <section class="summary">
        <article><strong>{{ activeCount() }}</strong><span>Active</span></article>
        <article><strong>{{ expiringSoonCount() }}</strong><span>Expiring in 7 days</span></article>
        <article><strong>{{ revokedCount() }}</strong><span>Revoked</span></article>
        <article><strong>{{ history().length }}</strong><span>Recent events</span></article>
      </section>

      @if (expiredNow() > 0) {
        <div class="notice danger">
          {{ expiredNow() }} expired access record(s) were revoked automatically together with their active sessions.
        </div>
      }

      @if (expiringSoonCount() > 0) {
        <div class="notice warning">
          {{ expiringSoonCount() }} delegated access record(s) expire within seven days.
        </div>
      }

      <section class="panel create">
        <h3>Add trusted administrator</h3>
        <div class="form-grid">
          <label>Discord User ID
            <input [(ngModel)]="form.discord_user_id" placeholder="123456789012345678" />
          </label>
          <label>Role
            <select [(ngModel)]="form.role">
              <option value="moderator">Moderator</option>
              <option value="admin">Administrator</option>
            </select>
          </label>
          <label>Expires at
            <input type="datetime-local" [(ngModel)]="form.expires_at" />
          </label>
        </div>

        <div class="quick-expiry">
          <button type="button" (click)="setFormExpiry(1)">+1 day</button>
          <button type="button" (click)="setFormExpiry(7)">+7 days</button>
          <button type="button" (click)="setFormExpiry(30)">+30 days</button>
          <button type="button" (click)="form.expires_at = ''">Permanent</button>
        </div>

        <div class="permissions">
          @for (permission of allowedPermissions(); track permission) {
            <label>
              <input
                type="checkbox"
                [checked]="form.permissions.includes(permission)"
                (change)="toggle(permission, $any($event.target).checked)"
              />
              {{ permission }}
            </label>
          }
        </div>

        <button class="primary" (click)="create()" [disabled]="saving() || !form.discord_user_id">
          Add access
        </button>
      </section>

      @if (error()) {
        <div class="error">{{ error() }}</div>
      }

      <section class="panel list">
        <div class="section-head">
          <div><h3>Administrators</h3><p>Access status, permissions and expiry.</p></div>
        </div>

        @for (item of items(); track item.id) {
          <article [class.expired]="item.is_expired" [class.expiring]="item.expires_soon && !item.is_expired">
            <div class="identity">
              <strong>{{ item.discord_user_id }}</strong>
              <small>{{ item.is_guild_owner ? 'Guild owner' : item.role }}</small>
              @if (!item.is_guild_owner && item.expires_at) {
                <em>{{ expiryText(item) }}</em>
              }
            </div>

            <select [(ngModel)]="item.role" [disabled]="item.is_guild_owner">
              <option value="moderator">Moderator</option>
              <option value="admin">Administrator</option>
            </select>

            <select [(ngModel)]="item.status" [disabled]="item.is_guild_owner">
              <option value="active">Active</option>
              <option value="revoked">Revoked</option>
            </select>

            <div class="permissions compact">
              @for (permission of allowedPermissions(); track permission) {
                <label>
                  <input
                    type="checkbox"
                    [checked]="item.permissions.includes(permission)"
                    [disabled]="item.is_guild_owner"
                    (change)="toggleItem(item, permission, $any($event.target).checked)"
                  />
                  {{ permission }}
                </label>
              }
            </div>

            <div class="expiry-editor">
              <input
                type="datetime-local"
                [ngModel]="toLocal(item.expires_at)"
                (ngModelChange)="item.expires_at = fromLocal($event)"
                [disabled]="item.is_guild_owner"
              />
              @if (!item.is_guild_owner) {
                <div class="quick-expiry compact-buttons">
                  <button type="button" (click)="extend(item, 7)">+7d</button>
                  <button type="button" (click)="extend(item, 30)">+30d</button>
                  <button type="button" (click)="item.expires_at = null">∞</button>
                </div>
              }
            </div>

            <div class="actions">
              <button (click)="save(item)" [disabled]="item.is_guild_owner">Save</button>
              <button (click)="revokeSessions(item)" [disabled]="item.is_guild_owner">Revoke sessions</button>
              <button class="danger" (click)="remove(item)" [disabled]="item.is_guild_owner">Delete</button>
            </div>
          </article>
        } @empty {
          <div class="empty">No delegated administrators.</div>
        }
      </section>

      <section class="panel history">
        <div class="section-head">
          <div><h3>Access history</h3><p>Latest 100 changes and automatic expiry events.</p></div>
          <button (click)="loadHistory()" [disabled]="historyLoading()">Reload history</button>
        </div>

        <div class="timeline">
          @for (event of history(); track event.id) {
            <article>
              <div class="event-icon">{{ eventIcon(event.event_type) }}</div>
              <div>
                <strong>{{ eventLabel(event.event_type) }}</strong>
                <p>{{ event.message || eventSummary(event) }}</p>
                <small>{{ event.created_at ? (event.created_at | date:'medium') : 'Unknown time' }}</small>
              </div>
              <span [class.ok]="event.result === 'success'">{{ event.result }}</span>
            </article>
          } @empty {
            <div class="empty">No access history yet.</div>
          }
        </div>
      </section>
    </sn-shell>
  `,
  styles: [`
    .hero,.panel,.error,.notice,.summary article{border:1px solid var(--line);border-radius:16px;background:rgba(16,22,38,.72)}
    .hero{display:flex;justify-content:space-between;align-items:center;padding:1.25rem;margin-bottom:1rem}
    .hero span{color:var(--primary);font-size:.7rem;letter-spacing:.14em}.hero h2{margin:.25rem 0}.hero p{margin:0;color:var(--muted)}
    .summary{display:grid;grid-template-columns:repeat(4,1fr);gap:.75rem;margin-bottom:1rem}.summary article{padding:1rem;display:grid;gap:.2rem}.summary strong{font-size:1.55rem}.summary span{color:var(--muted);font-size:.8rem}
    .notice{padding:.85rem 1rem;margin-bottom:1rem}.warning{border-color:#a77a22;color:#ffd27a}.danger{border-color:#9e3a4d;color:#ff9bad}
    .panel{padding:1rem;margin-bottom:1rem}.form-grid{display:grid;grid-template-columns:2fr 1fr 1fr;gap:.8rem}.form-grid label{display:grid;gap:.35rem;color:var(--muted)}
    input,select,button{border:1px solid var(--line);border-radius:9px;background:rgba(6,10,16,.9);color:var(--text);padding:.65rem}
    button{cursor:pointer}.permissions{display:flex;flex-wrap:wrap;gap:.55rem;margin:1rem 0}.permissions label{display:flex;gap:.35rem;align-items:center;padding:.4rem .55rem;border:1px solid var(--line);border-radius:8px;color:var(--muted)}
    .quick-expiry{display:flex;gap:.45rem;flex-wrap:wrap;margin-top:.7rem}.quick-expiry button{padding:.4rem .55rem;font-size:.75rem}.primary{background:var(--primary);color:#04130f;font-weight:800}
    .error{padding:.8rem;color:#ff91a5;margin-bottom:1rem}.list{display:grid;gap:.75rem}.list>article{display:grid;grid-template-columns:1.15fr .7fr .7fr 2fr 1.2fr auto;gap:.7rem;align-items:center;padding:.85rem;border:1px solid var(--line);border-radius:12px}
    .identity{display:grid}.identity small{color:var(--muted)}.identity em{font-style:normal;font-size:.72rem;color:#ffd27a;margin-top:.25rem}.compact{margin:0}.compact label{font-size:.7rem}.actions{display:flex;gap:.4rem;flex-wrap:wrap}.expired{opacity:.6;border-color:#9e3a4d!important}.expiring{border-color:#a77a22!important}.empty{text-align:center;color:var(--muted);padding:2rem}
    .expiry-editor{display:grid;gap:.35rem}.compact-buttons{margin:0}.section-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:.8rem}.section-head h3{margin:0}.section-head p{margin:.2rem 0 0;color:var(--muted);font-size:.8rem}
    .timeline{display:grid;gap:.55rem}.timeline article{display:grid;grid-template-columns:auto 1fr auto;gap:.8rem;align-items:center;padding:.8rem;border:1px solid var(--line);border-radius:10px}.timeline p{margin:.25rem 0;color:var(--muted)}.timeline small{color:var(--muted)}.timeline>article>span{font-size:.72rem;text-transform:uppercase}.timeline>article>span.ok{color:var(--primary)}.event-icon{width:2rem;height:2rem;border:1px solid var(--line);border-radius:50%;display:grid;place-items:center}
    @media(max-width:1100px){.summary{grid-template-columns:repeat(2,1fr)}.form-grid,.list>article{grid-template-columns:1fr}.actions{flex-wrap:wrap}}
    @media(max-width:600px){.summary{grid-template-columns:1fr}.hero,.section-head{align-items:flex-start;gap:.8rem;flex-direction:column}}
  `],
})
export class GuildAccessComponent implements OnInit {
  readonly guildId = this.route.snapshot.paramMap.get('guildId')!;
  readonly items = signal<AccessItem[]>([]);
  readonly allowedPermissions = signal<string[]>([]);
  readonly history = signal<AccessHistoryItem[]>([]);
  readonly loading = signal(false);
  readonly historyLoading = signal(false);
  readonly saving = signal(false);
  readonly error = signal('');
  readonly expiredNow = signal(0);
  readonly expiringSoonCount = signal(0);

  form = {
    discord_user_id: '',
    role: 'moderator',
    permissions: [] as string[],
    expires_at: '',
  };

  constructor(
    private readonly http: HttpClient,
    private readonly route: ActivatedRoute,
  ) {}

  ngOnInit(): void {
    void this.reloadAll();
  }

  activeCount(): number {
    return this.items().filter(item => item.status === 'active' && !item.is_expired).length;
  }

  revokedCount(): number {
    return this.items().filter(item => item.status === 'revoked' || item.is_expired).length;
  }

  async reloadAll(): Promise<void> {
    await Promise.all([this.load(), this.loadHistory()]);
  }

  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set('');

    try {
      const data = await firstValueFrom(
        this.http.get<AccessResponse>(`/api/v1/guilds/${this.guildId}/access`),
      );

      this.items.set(data.items);
      this.allowedPermissions.set(data.allowed_permissions);
      this.expiredNow.set(data.expired_now || 0);
      this.expiringSoonCount.set(data.expires_soon_count || 0);
    } catch (e: any) {
      this.error.set(e?.error?.detail || 'Unable to load guild access.');
    } finally {
      this.loading.set(false);
    }
  }

  async loadHistory(): Promise<void> {
    this.historyLoading.set(true);

    try {
      const data = await firstValueFrom(
        this.http.get<AccessHistoryResponse>(
          `/api/v1/guilds/${this.guildId}/access/history?limit=100`,
        ),
      );
      this.history.set(data.items);
    } catch (e: any) {
      this.error.set(e?.error?.detail || 'Unable to load access history.');
    } finally {
      this.historyLoading.set(false);
    }
  }

  toggle(permission: string, checked: boolean): void {
    this.form.permissions = checked
      ? [...new Set([...this.form.permissions, permission])]
      : this.form.permissions.filter(value => value !== permission);
  }

  toggleItem(item: AccessItem, permission: string, checked: boolean): void {
    item.permissions = checked
      ? [...new Set([...item.permissions, permission])]
      : item.permissions.filter(value => value !== permission);
  }

  setFormExpiry(days: number): void {
    const date = new Date();
    date.setDate(date.getDate() + days);
    this.form.expires_at = this.toLocal(date.toISOString());
  }

  extend(item: AccessItem, days: number): void {
    const base = item.expires_at && new Date(item.expires_at) > new Date()
      ? new Date(item.expires_at)
      : new Date();
    base.setDate(base.getDate() + days);
    item.expires_at = base.toISOString();
  }

  async create(): Promise<void> {
    this.saving.set(true);
    this.error.set('');

    try {
      await firstValueFrom(
        this.http.post(`/api/v1/guilds/${this.guildId}/access`, {
          discord_user_id: this.form.discord_user_id,
          role: this.form.role,
          permissions: this.form.permissions,
          expires_at: this.form.expires_at
            ? new Date(this.form.expires_at).toISOString()
            : null,
        }),
      );

      this.form = {
        discord_user_id: '',
        role: 'moderator',
        permissions: [],
        expires_at: '',
      };

      await this.reloadAll();
    } catch (e: any) {
      this.error.set(e?.error?.detail || 'Unable to add guild access.');
    } finally {
      this.saving.set(false);
    }
  }

  async save(item: AccessItem): Promise<void> {
    this.error.set('');

    try {
      await firstValueFrom(
        this.http.patch(
          `/api/v1/guilds/${this.guildId}/access/${item.id}`,
          {
            role: item.role,
            status: item.status,
            permissions: item.permissions,
            expires_at: item.expires_at,
          },
        ),
      );

      await this.reloadAll();
    } catch (e: any) {
      this.error.set(e?.error?.detail || 'Unable to save guild access.');
    }
  }

  async revokeSessions(item: AccessItem): Promise<void> {
    this.error.set('');

    try {
      await firstValueFrom(
        this.http.post(
          `/api/v1/guilds/${this.guildId}/access/${item.id}/revoke-sessions`,
          {},
        ),
      );
      await this.loadHistory();
    } catch (e: any) {
      this.error.set(e?.error?.detail || 'Unable to revoke sessions.');
    }
  }

  async remove(item: AccessItem): Promise<void> {
    if (!confirm(`Delete access for ${item.discord_user_id}?`)) {
      return;
    }

    this.error.set('');

    try {
      await firstValueFrom(
        this.http.delete(
          `/api/v1/guilds/${this.guildId}/access/${item.id}`,
        ),
      );
      await this.reloadAll();
    } catch (e: any) {
      this.error.set(e?.error?.detail || 'Unable to delete guild access.');
    }
  }

  expiryText(item: AccessItem): string {
    if (!item.expires_at) {
      return 'Permanent';
    }

    if (item.is_expired) {
      return 'Expired';
    }

    if (item.seconds_remaining === null) {
      return new Date(item.expires_at).toLocaleString();
    }

    const days = Math.ceil(item.seconds_remaining / 86400);
    return days <= 1 ? 'Expires within 24 hours' : `Expires in ${days} days`;
  }

  eventIcon(eventType: string): string {
    if (eventType.endsWith('.created')) return '+';
    if (eventType.endsWith('.updated')) return '↻';
    if (eventType.endsWith('.expired')) return '!';
    if (eventType.endsWith('.deleted')) return '×';
    if (eventType.endsWith('.sessions_revoked')) return '⌁';
    return '•';
  }

  eventLabel(eventType: string): string {
    const labels: Record<string, string> = {
      'guild_access.created': 'Access granted',
      'guild_access.updated': 'Access updated',
      'guild_access.expired': 'Access expired',
      'guild_access.deleted': 'Access deleted',
      'guild_access.sessions_revoked': 'Sessions revoked',
    };
    return labels[eventType] || eventType;
  }

  eventSummary(event: AccessHistoryItem): string {
    const discordUserId = event.payload['discord_user_id'];
    if (discordUserId) {
      return `Discord user ${discordUserId}`;
    }

    if (event.target_id) {
      return `Membership ${event.target_id}`;
    }

    return 'Guild access event';
  }

  toLocal(value: string | null): string {
    if (!value) {
      return '';
    }

    const date = new Date(value);
    return new Date(
      date.getTime() - date.getTimezoneOffset() * 60000,
    ).toISOString().slice(0, 16);
  }

  fromLocal(value: string): string | null {
    return value ? new Date(value).toISOString() : null;
  }
}
