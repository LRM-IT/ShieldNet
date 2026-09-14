import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ShellComponent } from '../shared/shell.component';
import { GuildPluginService } from '../core/guild-plugin.service';

interface Language { code: string; name: string; }
interface DiscordOption { id: string; name: string; type?: string; managed?: boolean; }
interface IntroSettings {
  installed: boolean;
  enabled: boolean;
  languages: Language[];
  server_numbers: string[];
  nickname_template: string;
  verified_role_id: string | null;
  language_roles: Record<string, string>;
  fallback_channel_id: string | null;
  delivery_mode: 'dm_with_fallback' | 'channel' | 'dm';
  prompt_text: string;
}

@Component({
  standalone: true,
  imports: [FormsModule, ShellComponent],
  template: `
    <sn-shell title="First Introduction">
      <main class="intro-page">
        <header><span>GUILD PLUGIN</span><h2>First Introduction</h2>
          <p>Ask new members for their language, server number, alliance and nickname before assigning roles.</p></header>
        @if (error()) { <div class="alert error">{{ error() }}</div> }
        @if (success()) { <div class="alert success">{{ success() }}</div> }
        @if (!settings.installed) {
          <section class="panel"><p>Install this plugin to configure it for this server.</p>
            <button type="button" (click)="install()" [disabled]="busy()">Install plugin</button></section>
        } @else {
          <section class="panel">
            <div class="heading"><div><h3>Introduction delivery</h3><p>The questionnaire is sent when a member joins for the first time.</p></div>
              <button type="button" (click)="toggle()" [disabled]="busy()">{{ settings.enabled ? 'Disable plugin' : 'Enable plugin' }}</button></div>
            <label>Delivery method
              <select [(ngModel)]="settings.delivery_mode">
                <option value="dm_with_fallback">Direct message, then server channel if DMs are closed</option>
                <option value="channel">Server channel only</option>
                <option value="dm">Direct message only</option>
              </select>
            </label>
            <label>Introduction channel
              <select [(ngModel)]="settings.fallback_channel_id">
                <option [ngValue]="null">Select channel</option>
                @for (channel of channels(); track channel.id) { <option [value]="channel.id">#{{ channel.name }}</option> }
              </select>
            </label>
            <label>Prompt text<textarea [(ngModel)]="settings.prompt_text" rows="3" maxlength="500"></textarea></label>
          </section>
          <section class="panel">
            <h3>Questionnaire and nickname</h3>
            <label>Server numbers, one per line<textarea [(ngModel)]="serverNumbersText" rows="5" placeholder="2279&#10;2380"></textarea></label>
            <label>Nickname format<input [(ngModel)]="settings.nickname_template" placeholder="{server} [{alliance}] {nick}"></label>
            <p class="hint">Use {{ '{server}' }}, {{ '{alliance}' }} and {{ '{nick}' }}. Discord nicknames can be at most 32 characters.</p>
            <label>Verified role
              <select [(ngModel)]="settings.verified_role_id">
                <option [ngValue]="null">Select role</option>
                @for (role of roles(); track role.id) { <option [value]="role.id">{{ role.name }}</option> }
              </select>
            </label>
          </section>
          <section class="panel">
            <h3>Language roles</h3>
            <p class="hint">Languages come from Server Languages. Assign one Discord role per enabled language.</p>
            @for (language of settings.languages; track language.code) {
              <label>{{ language.name }} ({{ language.code }})
                <select [(ngModel)]="settings.language_roles[language.code]">
                  <option value="">Select role</option>
                  @for (role of roles(); track role.id) { <option [value]="role.id">{{ role.name }}</option> }
                </select>
              </label>
            } @empty { <p>Configure server languages before enabling this plugin.</p> }
          </section>
          <button type="button" class="save" (click)="save()" [disabled]="busy()">Save settings</button>
        }
      </main>
    </sn-shell>
  `,
  styles: [`
    .intro-page{max-width:960px;margin:auto;display:grid;gap:1rem;padding-bottom:3rem}
    header span{color:var(--primary);font-size:.7rem;font-weight:800;letter-spacing:.12em}
    h2{margin:.3rem 0;font-size:1.8rem}h3{margin:0 0 .6rem}p{color:var(--muted);margin:.3rem 0 1rem}
    .panel,.alert{padding:1.25rem;border:1px solid var(--line);border-radius:16px;background:var(--panel)}
    .heading{display:flex;justify-content:space-between;align-items:start;gap:1rem}
    label{display:grid;gap:.4rem;margin:.85rem 0;color:var(--text);font-weight:650}
    input,select,textarea{width:100%;padding:.72rem;border:1px solid var(--line);border-radius:9px;background:#111922;color:var(--text);font:inherit}
    button{padding:.7rem 1rem;border:0;border-radius:9px;background:var(--primary);color:#07120f;font-weight:800;cursor:pointer}
    button:disabled{opacity:.55;cursor:not-allowed}.save{justify-self:end}.hint{font-size:.85rem}
    .error{color:#ff9ea3}.success{color:#76e8b8}
  `],
})
export class PluginFirstIntroductionComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly route = inject(ActivatedRoute);
  private readonly plugins = inject(GuildPluginService);
  readonly guildId = this.route.snapshot.paramMap.get('guildId') || '';
  readonly channels = signal<DiscordOption[]>([]);
  readonly roles = signal<DiscordOption[]>([]);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly success = signal('');
  serverNumbersText = '';
  settings: IntroSettings = {
    installed: false, enabled: false, languages: [], server_numbers: [],
    nickname_template: '[{alliance}] {nick}', verified_role_id: null,
    language_roles: {}, fallback_channel_id: null, delivery_mode: 'dm_with_fallback',
    prompt_text: 'Welcome! Confirm your membership and introduce yourself to continue.',
  };
  private get url(): string { return `/api/v1/discord/guilds/${this.guildId}/plugins/first-introduction/settings`; }

  async ngOnInit(): Promise<void> {
    try {
      const [settings, structure] = await Promise.all([
        firstValueFrom(this.http.get<IntroSettings>(this.url)),
        firstValueFrom(this.http.get<{channels: DiscordOption[]; roles: DiscordOption[]}>(`/api/v1/discord/guilds/${this.guildId}/structure`)),
      ]);
      this.settings = settings;
      this.serverNumbersText = settings.server_numbers.join('\n');
      this.channels.set((structure.channels || []).filter(item => ['text', '0', 'guild_text'].includes(String(item.type).toLowerCase())));
      this.roles.set((structure.roles || []).filter(item => !item.managed && item.name !== '@everyone'));
    } catch { this.error.set('Could not load introduction settings or Discord structure.'); }
  }

  async install(): Promise<void> {
    this.busy.set(true); this.error.set('');
    try { await this.plugins.install(this.guildId, 'first_introduction'); await this.ngOnInit(); }
    catch (error: any) { this.error.set(error?.error?.detail || 'Could not install plugin.'); }
    finally { this.busy.set(false); }
  }

  async toggle(): Promise<void> {
    this.busy.set(true); this.error.set('');
    try {
      if (this.settings.enabled) await this.plugins.disable(this.guildId, 'first_introduction');
      else await this.plugins.enable(this.guildId, 'first_introduction');
      await this.ngOnInit();
    } catch (error: any) { this.error.set(error?.error?.detail || 'Could not change plugin state. Save settings first.'); }
    finally { this.busy.set(false); }
  }

  async save(): Promise<void> {
    this.busy.set(true); this.error.set(''); this.success.set('');
    const payload = {
      server_numbers: this.serverNumbersText.split(/\r?\n/).map(value => value.trim()).filter(Boolean),
      nickname_template: this.settings.nickname_template,
      verified_role_id: this.settings.verified_role_id,
      language_roles: Object.fromEntries(Object.entries(this.settings.language_roles).filter(([, value]) => value)),
      fallback_channel_id: this.settings.fallback_channel_id,
      delivery_mode: this.settings.delivery_mode,
      prompt_text: this.settings.prompt_text,
    };
    try {
      this.settings = await firstValueFrom(this.http.put<IntroSettings>(this.url, payload));
      this.serverNumbersText = this.settings.server_numbers.join('\n');
      this.success.set('Introduction settings saved.');
    } catch (error: any) { this.error.set(error?.error?.detail || 'Could not save settings.'); }
    finally { this.busy.set(false); }
  }
}
