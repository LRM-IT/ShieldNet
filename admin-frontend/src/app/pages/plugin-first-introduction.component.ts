import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ShellComponent } from '../shared/shell.component';
import { GuildPluginService } from '../core/guild-plugin.service';
import { DiscordChannelPickerComponent } from '../shared/discord-channel-picker.component';

interface Language { code: string; name: string; flag: string | null; }
interface DiscordRole { id: string; name: string; managed?: boolean; assignable?: boolean; }
interface Settings {
  installed: boolean;
  enabled: boolean;
  languages: Language[];
  language_roles: Record<string, string>;
  channel_id: string | null;
  message_id: string | null;
  role_name_mask: string;
}

@Component({
  standalone: true,
  imports: [FormsModule, ShellComponent, DiscordChannelPickerComponent],
  template: `
    <sn-shell title="Language Selection">
      <main class="page">
        <header><span>GUILD PLUGIN</span><h2>Language Selection</h2>
          <p>Members select a language by reacting to its flag in one server thread.</p></header>
        @if (error()) { <div class="panel error">{{ error() }}</div> }
        @if (success()) { <div class="panel success">{{ success() }}</div> }
        @if (!settings.installed) {
          <section class="panel"><p>Install this plugin to configure language roles.</p>
            <button type="button" (click)="install()" [disabled]="busy()">Install plugin</button></section>
        } @else {
          <section class="panel">
            <div class="heading"><div><h3>Flag reactions</h3><p>Assign one distinct Discord role per language.</p></div>
              <button type="button" (click)="toggle()" [disabled]="busy()">{{ settings.enabled ? 'Disable plugin' : 'Enable plugin' }}</button></div>
            <label>Discord thread or text channel
              <sn-discord-channel-picker [guildId]="guildId" [value]="settings.channel_id" (valueChange)="settings.channel_id=$event" />
            </label>
            <div class="role-builder">
              <h3>Створення мовних ролей</h3>
              <p>Маска назви: &#123;flag&#125;, &#123;name&#125;, &#123;code&#125;. Наявні ролі з відповідними назвами будуть використані повторно.</p>
              <label>Маска ролі<input [(ngModel)]="settings.role_name_mask" maxlength="100" placeholder="{flag} {name}"></label>
              <div class="role-preview">
                @for (language of settings.languages; track language.code) {
                  <small>{{ language.code }} → {{ rolePreview(language) }}</small>
                }
              </div>
              <button type="button" (click)="ensureRoles()" [disabled]="busy() || !settings.languages.length">{{ provisioning() ? 'Створюємо ролі…' : 'Знайти або створити відсутні ролі' }}</button>
            </div>
            @for (language of settings.languages; track language.code) {
              <label>{{ language.flag || 'No flag' }} {{ language.name }} ({{ language.code }})
                <select [(ngModel)]="settings.language_roles[language.code]">
                  <option value="">Select role</option>
                  @for (role of roles(); track role.id) { <option [value]="role.id">{{ role.name }}</option> }
                </select>
              </label>
            } @empty { <p>Configure server languages before enabling this plugin.</p> }
            <button type="button" (click)="save()" [disabled]="busy()">Save settings</button>
          </section>
          <section class="panel"><h3>Publish the flag panel</h3>
            <p>After saving and enabling the plugin, a server administrator runs <strong>/language_panel</strong>. The bot publishes the flag message in the configured thread and adds the reactions.</p>
            <p>Members react to choose a language. Changing flags replaces the prior language role; removing the active flag removes that role. The bot role must be above all configured language roles.</p>
            @if (settings.message_id) { <p>Active panel message ID: {{ settings.message_id }}</p> }
            <p>The bot needs View Channel, Send Messages, Add Reactions, Read Message History and Manage Messages in that thread.</p>
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
    .heading{display:flex;justify-content:space-between;align-items:start;gap:1rem}.role-builder{margin:1rem 0;padding:1rem;border:1px solid var(--line);border-radius:12px}.role-preview{display:flex;flex-wrap:wrap;gap:.4rem;margin:.6rem 0 1rem}.role-preview small{padding:.35rem .6rem;border:1px solid var(--line);border-radius:7px;color:var(--muted)}
    label{display:grid;gap:.4rem;margin:.85rem 0;color:var(--text);font-weight:650}
    select,input{width:100%;padding:.72rem;border:1px solid var(--line);border-radius:9px;background:#111922;color:var(--text);font:inherit}
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
  readonly provisioning = signal(false);
  readonly error = signal('');
  readonly success = signal('');
  settings: Settings = { installed: false, enabled: false, languages: [], language_roles: {}, channel_id: null, message_id: null, role_name_mask: '{flag} {name}' };
  private get url(): string { return `/api/v1/discord/guilds/${this.guildId}/plugins/first-introduction/settings`; }

  async ngOnInit(): Promise<void> {
    try {
      const [settings, structure] = await Promise.all([
        firstValueFrom(this.http.get<Settings>(this.url)),
        firstValueFrom(this.http.get<{roles: DiscordRole[]}>(`/api/v1/discord/guilds/${this.guildId}/structure`)),
      ]);
      this.settings = settings;
      this.roles.set((structure.roles || []).filter(role => !role.managed && role.assignable && role.name !== '@everyone'));
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
    const payload = {
      language_roles: Object.fromEntries(Object.entries(this.settings.language_roles).filter(([, value]) => value)),
      channel_id: this.settings.channel_id?.trim() || null,
      role_name_mask: this.settings.role_name_mask,
    };
    try {
      this.settings = await firstValueFrom(this.http.put<Settings>(this.url, payload));
      this.success.set('Language settings saved. Run /language_panel after enabling.');
    } catch (error: any) { this.error.set(error?.error?.detail || 'Could not save language settings.'); }
    finally { this.busy.set(false); }
  }

  rolePreview(language: Language): string {
    return (this.settings.role_name_mask || '').replace(/\{flag\}/g, language.flag || '')
      .replace(/\{name\}/g, language.name).replace(/\{code\}/g, language.code).trim();
  }

  async ensureRoles(): Promise<void> {
    if (this.busy()) return;
    this.busy.set(true); this.provisioning.set(true); this.error.set(''); this.success.set('');
    const base = `/api/v1/discord/guilds/${this.guildId}/plugins/first-introduction/roles`;
    try {
      const result = await firstValueFrom(this.http.post<{jobs:string[];language_roles:Record<string,string>;role_names:Record<string,string>}>(
        `${base}/ensure`, {role_name_mask:this.settings.role_name_mask}));
      this.settings.language_roles = {...this.settings.language_roles, ...result.language_roles};
      if (result.jobs.length) {
        let completed = false;
        for (let attempt = 0; attempt < 40; attempt++) {
          await new Promise(resolve => setTimeout(resolve, 1500));
          const status = await firstValueFrom(this.http.post<{complete:boolean;items:{id:string;language_code:string;name:string;status:string;role_id:string;error:string|null}[]}>(
            `${base}/status`, result.jobs));
          if (!status.complete) continue;
          const failed = status.items.filter(item => item.status !== 'completed');
          for (const item of status.items.filter(item => item.status === 'completed' && item.role_id)) {
            this.settings.language_roles[item.language_code] = item.role_id;
            if (!this.roles().some(role => role.id === item.role_id)) this.roles.update(roles => [...roles, {id:item.role_id,name:item.name,assignable:true}]);
          }
          if (failed.length) this.error.set(failed.map(item => `${item.name}: ${item.error || 'Discord role creation failed'}`).join('; '));
          completed = true;
          break;
        }
        if (!completed) throw new Error('Час очікування Discord вичерпано. Оновіть сторінку, щоб перевірити ролі.');
      }
      const saved = await firstValueFrom(this.http.get<Settings>(this.url));
      this.settings = saved;
      if (!this.error()) this.success.set('Мовні ролі готові. Виберіть канал і збережіть налаштування.');
    } catch (error: any) { this.error.set(error?.error?.detail || error?.message || 'Не вдалося створити мовні ролі.'); }
    finally { this.busy.set(false); this.provisioning.set(false); }
  }
}
