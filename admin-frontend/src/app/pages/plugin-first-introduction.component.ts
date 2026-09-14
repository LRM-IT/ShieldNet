import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ShellComponent } from '../shared/shell.component';
import { GuildPluginService } from '../core/guild-plugin.service';

interface Language { code: string; name: string; }
interface DiscordRole { id: string; name: string; managed?: boolean; }
interface Settings {
  installed: boolean;
  enabled: boolean;
  languages: Language[];
  language_roles: Record<string, string>;
}

@Component({
  standalone: true,
  imports: [FormsModule, ShellComponent],
  template: `
    <sn-shell title="Language Selection">
      <main class="page">
        <header><span>GUILD PLUGIN</span><h2>Language Selection</h2>
          <p>Members choose a server language and receive its Discord role. They can change their choice later.</p></header>
        @if (error()) { <div class="panel error">{{ error() }}</div> }
        @if (success()) { <div class="panel success">{{ success() }}</div> }
        @if (!settings.installed) {
          <section class="panel"><p>Install this plugin to configure language roles.</p>
            <button type="button" (click)="install()" [disabled]="busy()">Install plugin</button></section>
        } @else {
          <section class="panel">
            <div class="heading"><div><h3>Language roles</h3><p>Languages come from Server Languages. Assign one distinct Discord role per language.</p></div>
              <button type="button" (click)="toggle()" [disabled]="busy()">{{ settings.enabled ? 'Disable plugin' : 'Enable plugin' }}</button></div>
            @for (language of settings.languages; track language.code) {
              <label>{{ language.name }} ({{ language.code }})
                <select [(ngModel)]="settings.language_roles[language.code]">
                  <option value="">Select role</option>
                  @for (role of roles(); track role.id) { <option [value]="role.id">{{ role.name }}</option> }
                </select>
              </label>
            } @empty { <p>Configure server languages before enabling this plugin.</p> }
            <button type="button" (click)="save()" [disabled]="busy()">Save roles</button>
          </section>
          <section class="panel"><h3>Member access</h3>
            <p>Members use <strong>/language</strong> to choose or change their role. A server administrator can run <strong>/language_panel</strong> in a channel to post a permanent selection button.</p>
            <p>The bot role must be above all configured language roles.</p>
          </section>
        }
      </main>
    </sn-shell>
  `,
  styles: [`
    .page{max-width:960px;margin:auto;display:grid;gap:1rem;padding-bottom:3rem}
    header span{color:var(--primary);font-size:.7rem;font-weight:800;letter-spacing:.12em}
    h2{margin:.3rem 0;font-size:1.8rem}h3{margin:0 0 .6rem}p{color:var(--muted);margin:.3rem 0 1rem}
    .panel{padding:1.25rem;border:1px solid var(--line);border-radius:16px;background:var(--panel)}
    .heading{display:flex;justify-content:space-between;align-items:start;gap:1rem}
    label{display:grid;gap:.4rem;margin:.85rem 0;color:var(--text);font-weight:650}
    select{width:100%;padding:.72rem;border:1px solid var(--line);border-radius:9px;background:#111922;color:var(--text);font:inherit}
    button{padding:.7rem 1rem;border:0;border-radius:9px;background:var(--primary);color:#07120f;font-weight:800;cursor:pointer}
    button:disabled{opacity:.55;cursor:not-allowed}.error{color:#ff9ea3}.success{color:#76e8b8}
  `],
})
export class PluginFirstIntroductionComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly route = inject(ActivatedRoute);
  private readonly plugins = inject(GuildPluginService);
  readonly guildId = this.route.snapshot.paramMap.get('guildId') || '';
  readonly roles = signal<DiscordRole[]>([]);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly success = signal('');
  settings: Settings = { installed: false, enabled: false, languages: [], language_roles: {} };
  private get url(): string { return `/api/v1/discord/guilds/${this.guildId}/plugins/first-introduction/settings`; }

  async ngOnInit(): Promise<void> {
    try {
      const [settings, structure] = await Promise.all([
        firstValueFrom(this.http.get<Settings>(this.url)),
        firstValueFrom(this.http.get<{roles: DiscordRole[]}>(`/api/v1/discord/guilds/${this.guildId}/structure`)),
      ]);
      this.settings = settings;
      this.roles.set((structure.roles || []).filter(role => !role.managed && role.name !== '@everyone'));
    } catch { this.error.set('Could not load language settings or Discord roles.'); }
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
    } catch (error: any) { this.error.set(error?.error?.detail || 'Could not change plugin state. Save roles first.'); }
    finally { this.busy.set(false); }
  }

  async save(): Promise<void> {
    this.busy.set(true); this.error.set(''); this.success.set('');
    const payload = { language_roles: Object.fromEntries(Object.entries(this.settings.language_roles).filter(([, value]) => value)) };
    try {
      this.settings = await firstValueFrom(this.http.put<Settings>(this.url, payload));
      this.success.set('Language roles saved.');
    } catch (error: any) { this.error.set(error?.error?.detail || 'Could not save language roles.'); }
    finally { this.busy.set(false); }
  }
}
