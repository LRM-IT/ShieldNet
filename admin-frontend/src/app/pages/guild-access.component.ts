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
  is_guild_owner: boolean;
}

interface AccessResponse {
  owner_discord_id: string;
  allowed_permissions: string[];
  items: AccessItem[];
}

@Component({
  selector: 'sn-guild-access',
  standalone: true,
  imports: [CommonModule, FormsModule, ShellComponent],
  template: `
    <sn-shell title="Guild Access">
      <section class="hero">
        <div><span>DELEGATED ADMINISTRATION</span><h2>Guild access</h2><p>Grant limited or temporary access to this Discord server.</p></div>
        <button (click)="load()" [disabled]="loading()">Refresh</button>
      </section>

      <section class="panel create">
        <h3>Add trusted administrator</h3>
        <div class="form-grid">
          <label>Discord User ID<input [(ngModel)]="form.discord_user_id" placeholder="123456789012345678" /></label>
          <label>Role<select [(ngModel)]="form.role"><option value="moderator">Moderator</option><option value="admin">Administrator</option></select></label>
          <label>Expires at<input type="datetime-local" [(ngModel)]="form.expires_at" /></label>
        </div>
        <div class="permissions">
          @for (permission of allowedPermissions(); track permission) {
            <label><input type="checkbox" [checked]="form.permissions.includes(permission)" (change)="toggle(permission, $any($event.target).checked)" />{{ permission }}</label>
          }
        </div>
        <button class="primary" (click)="create()" [disabled]="saving() || !form.discord_user_id">Add access</button>
      </section>

      @if (error()) { <div class="error">{{ error() }}</div> }

      <section class="panel list">
        @for (item of items(); track item.id) {
          <article [class.expired]="item.is_expired">
            <div class="identity"><strong>{{ item.discord_user_id }}</strong><small>{{ item.is_guild_owner ? 'Guild owner' : item.role }}</small></div>
            <select [(ngModel)]="item.role" [disabled]="item.is_guild_owner"><option value="moderator">Moderator</option><option value="admin">Administrator</option></select>
            <select [(ngModel)]="item.status" [disabled]="item.is_guild_owner"><option value="active">Active</option><option value="revoked">Revoked</option></select>
            <div class="permissions compact">
              @for (permission of allowedPermissions(); track permission) {
                <label><input type="checkbox" [checked]="item.permissions.includes(permission)" [disabled]="item.is_guild_owner" (change)="toggleItem(item, permission, $any($event.target).checked)" />{{ permission }}</label>
              }
            </div>
            <input type="datetime-local" [ngModel]="toLocal(item.expires_at)" (ngModelChange)="item.expires_at = fromLocal($event)" [disabled]="item.is_guild_owner" />
            <div class="actions">
              <button (click)="save(item)" [disabled]="item.is_guild_owner">Save</button>
              <button (click)="revokeSessions(item)" [disabled]="item.is_guild_owner">Revoke sessions</button>
              <button class="danger" (click)="remove(item)" [disabled]="item.is_guild_owner">Delete</button>
            </div>
          </article>
        } @empty { <div class="empty">No delegated administrators.</div> }
      </section>
    </sn-shell>
  `,
  styles: [`
    .hero,.panel,.error{border:1px solid var(--line);border-radius:16px;background:rgba(16,22,38,.72)}
    .hero{display:flex;justify-content:space-between;align-items:center;padding:1.25rem;margin-bottom:1rem}.hero span{color:var(--primary);font-size:.7rem;letter-spacing:.14em}.hero h2{margin:.25rem 0}.hero p{margin:0;color:var(--muted)}
    .panel{padding:1rem;margin-bottom:1rem}.form-grid{display:grid;grid-template-columns:2fr 1fr 1fr;gap:.8rem}.form-grid label{display:grid;gap:.35rem;color:var(--muted)}
    input,select,button{border:1px solid var(--line);border-radius:9px;background:rgba(6,10,16,.9);color:var(--text);padding:.65rem}.permissions{display:flex;flex-wrap:wrap;gap:.55rem;margin:1rem 0}.permissions label{display:flex;gap:.35rem;align-items:center;padding:.4rem .55rem;border:1px solid var(--line);border-radius:8px;color:var(--muted)}
    .primary{background:var(--primary);color:#04130f;font-weight:800}.error{padding:.8rem;color:#ff91a5;margin-bottom:1rem}.list{display:grid;gap:.75rem}.list article{display:grid;grid-template-columns:1.2fr .8fr .8fr 2fr 1fr auto;gap:.7rem;align-items:center;padding:.85rem;border:1px solid var(--line);border-radius:12px}.identity{display:grid}.identity small{color:var(--muted)}.compact{margin:0}.compact label{font-size:.7rem}.actions{display:flex;gap:.4rem}.danger{color:#ff91a5}.expired{opacity:.65}.empty{text-align:center;color:var(--muted);padding:2rem}
    @media(max-width:1100px){.form-grid,.list article{grid-template-columns:1fr}.actions{flex-wrap:wrap}}
  `],
})
export class GuildAccessComponent implements OnInit {
  readonly guildId = this.route.snapshot.paramMap.get('guildId')!;
  readonly items = signal<AccessItem[]>([]);
  readonly allowedPermissions = signal<string[]>([]);
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly error = signal('');
  form = { discord_user_id: '', role: 'moderator', permissions: [] as string[], expires_at: '' };

  constructor(private readonly http: HttpClient, private readonly route: ActivatedRoute) {}
  ngOnInit(): void { void this.load(); }

  async load(): Promise<void> {
    this.loading.set(true); this.error.set('');
    try {
      const data = await firstValueFrom(this.http.get<AccessResponse>(`/api/v1/guilds/${this.guildId}/access`));
      this.items.set(data.items); this.allowedPermissions.set(data.allowed_permissions);
    } catch (e: any) { this.error.set(e?.error?.detail || 'Unable to load guild access.'); }
    finally { this.loading.set(false); }
  }

  toggle(permission: string, checked: boolean): void {
    this.form.permissions = checked ? [...new Set([...this.form.permissions, permission])] : this.form.permissions.filter(x => x !== permission);
  }
  toggleItem(item: AccessItem, permission: string, checked: boolean): void {
    item.permissions = checked ? [...new Set([...item.permissions, permission])] : item.permissions.filter(x => x !== permission);
  }
  async create(): Promise<void> {
    this.saving.set(true); this.error.set('');
    try {
      await firstValueFrom(this.http.post(`/api/v1/guilds/${this.guildId}/access`, {
        discord_user_id: this.form.discord_user_id,
        role: this.form.role,
        permissions: this.form.permissions,
        expires_at: this.form.expires_at ? new Date(this.form.expires_at).toISOString() : null,
      }));
      this.form = { discord_user_id: '', role: 'moderator', permissions: [], expires_at: '' };
      await this.load();
    } catch (e: any) { this.error.set(e?.error?.detail || 'Unable to add guild access.'); }
    finally { this.saving.set(false); }
  }
  async save(item: AccessItem): Promise<void> {
    await firstValueFrom(this.http.patch(`/api/v1/guilds/${this.guildId}/access/${item.id}`, { role:item.role, status:item.status, permissions:item.permissions, expires_at:item.expires_at }));
    await this.load();
  }
  async revokeSessions(item: AccessItem): Promise<void> {
    await firstValueFrom(this.http.post(`/api/v1/guilds/${this.guildId}/access/${item.id}/revoke-sessions`, {}));
  }
  async remove(item: AccessItem): Promise<void> {
    if (!confirm(`Delete access for ${item.discord_user_id}?`)) return;
    await firstValueFrom(this.http.delete(`/api/v1/guilds/${this.guildId}/access/${item.id}`));
    await this.load();
  }
  toLocal(value: string | null): string { if (!value) return ''; const d=new Date(value); return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16); }
  fromLocal(value: string): string | null { return value ? new Date(value).toISOString() : null; }
}
