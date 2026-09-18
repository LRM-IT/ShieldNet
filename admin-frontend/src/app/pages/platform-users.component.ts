import { CommonModule } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';

import { PlatformOwner, PlatformUsersService } from '../core/platform-users.service';
import { TranslatePipe } from '../core/translate.pipe';
import { TranslationService } from '../core/translation.service';
import { ShellComponent } from '../shared/shell.component';

@Component({
  selector: 'sn-platform-users',
  standalone: true,
  imports: [CommonModule, FormsModule, ShellComponent, TranslatePipe],
  template: `
    <sn-shell [title]="'platform_users.title' | snT:'Server owners'">
      <section class="toolbar">
        <div><div class="eyebrow">{{ 'platform_users.eyebrow' | snT:'PANEL USERS' }}</div><h2>{{ 'platform_users.heading' | snT:'Discord server owners' }}</h2><p>{{ 'platform_users.intro' | snT:'View panel accounts, their servers and contact an owner through Discord.' }}</p></div>
        <form (ngSubmit)="load()"><input name="search" [(ngModel)]="search" [placeholder]="'platform_users.search' | snT:'Search by name, email or Discord ID'"><button type="submit">{{ 'platform_users.search_button' | snT:'Search' }}</button></form>
      </section>

      @if (error()) { <div class="notice error">{{ error() }}</div> }
      @if (success()) { <div class="notice success">{{ success() }}</div> }
      @if (loading()) { <div class="notice">{{ 'platform_users.loading' | snT:'Loading server owners…' }}</div> }
      @if (!loading() && !owners().length) { <div class="notice">{{ 'platform_users.empty' | snT:'No server owners found.' }}</div> }

      <div class="owners">
        @for (owner of owners(); track owner.id) {
          <article>
            <header>
              @if (owner.avatar_url) { <img [src]="owner.avatar_url" alt=""> } @else { <span class="avatar">{{ initial(owner) }}</span> }
              <div class="identity"><h3>{{ owner.display_name || owner.login }}</h3><span>{{ owner.email }}</span><small>Discord ID: {{ owner.discord_user_id || '—' }}</small></div>
              <span class="state" [class.active]="owner.status === 'active'">{{ owner.status }}</span>
            </header>
            <div class="meta"><span>{{ 'platform_users.last_login' | snT:'Last login' }}: <b>{{ owner.last_login_at ? (owner.last_login_at | date:'medium') : ('platform_users.never' | snT:'never') }}</b></span><span>{{ 'platform_users.email' | snT:'Email' }}: <b>{{ owner.email_verified ? ('platform_users.verified' | snT:'verified') : ('platform_users.unverified' | snT:'not verified') }}</b></span></div>
            <div class="guilds">
              @for (guild of owner.guilds; track guild.guild_id) { <div><strong>{{ guild.name }}</strong><small>{{ guild.guild_id }} · {{ guild.status }} · bot {{ guild.bot_status }}</small></div> }
            </div>
            <div class="actions"><button type="button" class="primary" (click)="toggleComposer(owner)">{{ 'platform_users.send_dm' | snT:'Send Discord DM' }}</button></div>
            @if (selectedId() === owner.id) {
              <form class="composer" (ngSubmit)="send(owner)">
                <label>{{ 'platform_users.message' | snT:'Message' }}<textarea name="message" [(ngModel)]="message" maxlength="2000" rows="5" required [placeholder]="'platform_users.message_placeholder' | snT:'Write a message to the server owner…'"></textarea></label>
                <div><small>{{ message.length }}/2000</small><button type="button" (click)="selectedId.set(null)">{{ 'platform_users.cancel' | snT:'Cancel' }}</button><button class="primary" type="submit" [disabled]="sending() || !message.trim()">{{ sending() ? ('platform_users.sending' | snT:'Sending…') : ('platform_users.queue' | snT:'Send message') }}</button></div>
              </form>
            }
          </article>
        }
      </div>
    </sn-shell>
  `,
  styles: [`
    .toolbar,.notice,.owners article{border:1px solid var(--line);border-radius:18px;background:rgba(16,22,38,.72)}.toolbar{padding:1.3rem;display:flex;align-items:end;justify-content:space-between;gap:1rem}.toolbar h2{margin:.3rem 0}.toolbar p,.identity span,.identity small,.meta,small{color:var(--muted)}.eyebrow{color:var(--primary);font-size:.7rem;font-weight:900;letter-spacing:.14em}.toolbar form{display:flex;gap:.5rem;width:min(520px,100%)}input,textarea,button{font:inherit}input,textarea{box-sizing:border-box;width:100%;padding:.75rem;border:1px solid var(--line);border-radius:10px;background:rgba(5,9,15,.75);color:var(--text)}button{padding:.72rem 1rem;border:1px solid var(--line);border-radius:10px;background:rgba(255,255,255,.03);color:var(--text);cursor:pointer;font-weight:800}.primary{border-color:rgba(53,226,178,.4);background:var(--primary-soft);color:var(--primary)}button:disabled{opacity:.55;cursor:wait}.notice{padding:1rem;margin-top:1rem}.error{color:#ff9baa;border-color:rgba(255,80,100,.45)}.success{color:var(--primary)}.owners{display:grid;gap:1rem;margin-top:1rem}.owners article{padding:1.2rem}.owners header{display:flex;align-items:center;gap:1rem}.avatar,.owners img{width:52px;height:52px;border-radius:14px}.owners img{object-fit:cover}.avatar{display:grid;place-items:center;background:var(--primary-soft);color:var(--primary);font-weight:900;font-size:1.25rem}.identity{display:grid;gap:.15rem;min-width:0;flex:1}.identity h3{margin:0}.state{padding:.4rem .65rem;border:1px solid var(--line);border-radius:999px;color:var(--muted);font-size:.7rem;text-transform:uppercase}.state.active{color:var(--primary)}.meta{display:flex;gap:1.5rem;flex-wrap:wrap;padding:1rem 0}.guilds{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:.6rem}.guilds div{display:grid;gap:.2rem;padding:.7rem;border:1px solid var(--line);border-radius:10px;background:rgba(0,0,0,.12)}.actions{display:flex;justify-content:flex-end;margin-top:1rem}.composer{margin-top:1rem;padding-top:1rem;border-top:1px solid var(--line)}.composer label{display:grid;gap:.45rem;font-size:.75rem;font-weight:800}.composer>div{display:flex;justify-content:flex-end;align-items:center;gap:.55rem;margin-top:.6rem}.composer>div small{margin-right:auto}@media(max-width:760px){.toolbar{align-items:stretch;flex-direction:column}.toolbar form{width:100%}.owners header{align-items:flex-start;flex-wrap:wrap}.state{margin-left:68px}.meta{display:grid;gap:.4rem}}
  `],
})
export class PlatformUsersComponent implements OnInit {
  readonly owners = signal<PlatformOwner[]>([]);
  readonly loading = signal(false);
  readonly sending = signal(false);
  readonly selectedId = signal<string | null>(null);
  readonly error = signal('');
  readonly success = signal('');
  search = '';
  message = '';

  constructor(private readonly users: PlatformUsersService, private readonly i18n: TranslationService) {}
  ngOnInit(): void { void this.load(); }

  async load(): Promise<void> {
    this.loading.set(true); this.error.set('');
    try { this.owners.set((await firstValueFrom(this.users.list(this.search.trim()))).items); }
    catch (error: any) { this.error.set(error?.error?.detail || error?.message || this.i18n.t('platform_users.load_error', 'Unable to load users.')); }
    finally { this.loading.set(false); }
  }

  initial(owner: PlatformOwner): string { return (owner.display_name || owner.login || '?').charAt(0).toUpperCase(); }
  toggleComposer(owner: PlatformOwner): void { this.selectedId.set(this.selectedId() === owner.id ? null : owner.id); this.message = ''; this.error.set(''); this.success.set(''); }

  async send(owner: PlatformOwner): Promise<void> {
    const message = this.message.trim(); if (!message) return;
    this.sending.set(true); this.error.set(''); this.success.set('');
    try { await firstValueFrom(this.users.sendDm(owner.id, message)); this.success.set(this.i18n.t('platform_users.queued', 'Message queued for delivery through Discord.')); this.selectedId.set(null); this.message = ''; }
    catch (error: any) { this.error.set(error?.error?.detail || error?.message || this.i18n.t('platform_users.send_error', 'Unable to send the message.')); }
    finally { this.sending.set(false); }
  }
}
