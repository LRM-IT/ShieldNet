import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { GuildPluginInstallation, GuildPluginService } from '../core/guild-plugin.service';
import { PluginRuntimeInstance, PluginRuntimeService } from '../core/plugin-runtime.service';
import { TranslationService } from '../core/translation.service';
import { ShellComponent } from '../shared/shell.component';
import { TranslatePipe } from '../core/translate.pipe';

@Component({
  selector: 'sn-plugin-runtime-usage',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, ShellComponent, TranslatePipe],
  template: `
    <sn-shell [title]="'runtime_usage.title' | snT:'Plugin Runtime'">
      <section class="head">
        <div>
          <div class="eyebrow">SHIELDNET ADMIN V4 · STAGE 14.11</div>
          <h2>{{ 'runtime_usage.heading' | snT:'Server plugin runtime' }}</h2>
          <p>{{ 'runtime_usage.description' | snT:'Manage installed plugins, runtime processes and server-specific settings.' }}</p>
        </div>
        <div class="head-actions">
          <a [routerLink]="['/guild', guildId]">{{ 'common.back' | snT:'Back to server' }}</a>
          <button type="button" (click)="load()" [disabled]="loading()">
            {{ loading() ? ('runtime_usage.refreshing' | snT:'Refreshing…') : ('runtime_usage.refresh' | snT:'Refresh') }}
          </button>
        </div>
      </section>

      @if (error()) { <div class="notice error">{{ error() }}</div> }

      <section class="metrics">
        <article><span>{{ 'plugins.installed' | snT:'Installed' }}</span><strong>{{ installations().length }}</strong></article>
        <article><span>{{ 'plugins.enabled' | snT:'Enabled' }}</span><strong>{{ enabledCount() }}</strong></article>
        <article><span>{{ 'plugins.running' | snT:'Running' }}</span><strong>{{ runningCount() }}</strong></article>
        <article><span>{{ 'plugins.errors' | snT:'Errors' }}</span><strong [class.danger]="errorCount() > 0">{{ errorCount() }}</strong></article>
      </section>

      @if (loading() && installations().length === 0) {
        <div class="notice">{{ 'runtime_usage.loading' | snT:'Loading server plugins…' }}</div>
      }

      <section class="plugin-grid">
        @for (plugin of installations(); track plugin.plugin_key) {
          <article class="plugin-card">
            <div class="plugin-head">
              <div class="plugin-icon">{{ plugin.plugin_key.slice(0, 1).toUpperCase() }}</div>
              <div class="plugin-title">
                <h3>{{ displayName(plugin) }}</h3>
                <small>{{ plugin.plugin_key }}</small>
              </div>
              <div class="badges">
                <span [class.good]="plugin.enabled" [class.muted-badge]="!plugin.enabled">{{ plugin.enabled ? 'ENABLED' : 'DISABLED' }}</span>
                <span [class.good]="runtime(plugin.plugin_key)?.state === 'running'" [class.warn]="runtime(plugin.plugin_key)?.state !== 'running'">
                  {{ (runtime(plugin.plugin_key)?.state || 'not started') | uppercase }}
                </span>
              </div>
            </div>

            <div class="details">
              <div><span>{{ 'plugins.version' | snT:'Version' }}</span><strong>{{ runtime(plugin.plugin_key)?.package_version || '—' }}</strong></div>
              <div><span>{{ 'runtime_usage.generation' | snT:'Generation' }}</span><strong>{{ runtime(plugin.plugin_key)?.generation ?? 0 }}</strong></div>
              <div><span>{{ 'runtime_usage.last_heartbeat' | snT:'Last heartbeat' }}</span><strong>{{ formatDate(runtime(plugin.plugin_key)?.last_heartbeat_at) }}</strong></div>
              <div><span>{{ 'runtime_usage.updated' | snT:'Updated' }}</span><strong>{{ formatDate(plugin.updated_at) }}</strong></div>
            </div>

            @if (plugin.last_error || runtime(plugin.plugin_key)?.last_error) {
              <div class="plugin-error">{{ runtime(plugin.plugin_key)?.last_error || plugin.last_error }}</div>
            }

            <div class="actions">
              <button type="button" class="toggle" [class.on]="plugin.enabled" [disabled]="busy(plugin.plugin_key)" (click)="toggleEnabled(plugin)">
                {{ plugin.enabled ? ('plugins.disable' | snT:'Disable') : ('plugins.enable' | snT:'Enable') }}
              </button>
              <button type="button" class="start" [disabled]="busy(plugin.plugin_key) || !plugin.enabled || runtime(plugin.plugin_key)?.state === 'running'" (click)="start(plugin)">
                {{ 'plugins.start' | snT:'Start' }}
              </button>
              <button type="button" class="stop" [disabled]="busy(plugin.plugin_key) || runtime(plugin.plugin_key)?.state !== 'running'" (click)="stop(plugin)">
                {{ 'plugins.stop' | snT:'Stop' }}
              </button>
              <button type="button" class="settings" [disabled]="busy(plugin.plugin_key)" (click)="openSettings(plugin)">
                {{ 'plugins.settings' | snT:'Settings' }}
              </button>
            </div>

            @if (editingKey() === plugin.plugin_key) {
              <div class="settings-editor">
                <label>{{ 'plugins.configuration_json' | snT:'Configuration JSON' }}</label>
                <textarea [(ngModel)]="settingsText" rows="8" spellcheck="false"></textarea>
                <div class="editor-actions">
                  <button type="button" (click)="cancelSettings()">{{ 'common.cancel' | snT:'Cancel' }}</button>
                  <button type="button" class="save" [disabled]="busy(plugin.plugin_key)" (click)="saveSettings(plugin)">{{ 'common.save' | snT:'Save' }}</button>
                </div>
              </div>
            }
          </article>
        } @empty {
          @if (!loading()) { <div class="notice">{{ 'runtime_usage.no_plugins' | snT:'No plugins are installed for this server.' }}</div> }
        }
      </section>
    </sn-shell>
  `,
  styles: [`
    :host{display:block}.head{display:flex;justify-content:space-between;align-items:flex-end;gap:1rem;margin-bottom:1rem}.eyebrow{font-size:.68rem;font-weight:900;letter-spacing:.14em;color:var(--accent)}.head h2{margin:.3rem 0}.head p{margin:0;color:var(--muted)}.head-actions{display:flex;gap:.55rem}.head-actions a,.head-actions button,.actions button,.editor-actions button{border:1px solid var(--line);background:var(--panel-2);color:var(--text);border-radius:9px;padding:.62rem .78rem;text-decoration:none;cursor:pointer}.head-actions button{background:var(--accent);color:#07110e;font-weight:800}.notice{padding:1rem;border:1px solid var(--line);background:var(--panel);border-radius:12px}.error,.plugin-error{color:#ff8e98;border-color:rgba(255,80,95,.4)}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:.8rem;margin-bottom:1rem}.metrics article{padding:1rem;border:1px solid var(--line);border-radius:13px;background:var(--panel);display:grid;gap:.35rem}.metrics span,.details span{font-size:.7rem;text-transform:uppercase;color:var(--muted)}.metrics strong{font-size:1.5rem}.danger{color:#ff6874}.plugin-grid{display:grid;gap:1rem}.plugin-card{border:1px solid var(--line);background:var(--panel);border-radius:16px;padding:1.1rem}.plugin-head{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:.75rem}.plugin-icon{width:44px;height:44px;border-radius:12px;display:grid;place-items:center;background:rgba(53,226,178,.12);color:var(--accent);font-weight:900}.plugin-title h3{margin:0 0 .2rem}.plugin-title small{color:var(--muted)}.badges{display:flex;gap:.4rem;flex-wrap:wrap}.badges span{font-size:.65rem;padding:.3rem .5rem;border:1px solid var(--line);border-radius:999px}.badges .good{color:#35e2b2}.badges .warn{color:#f2b15a}.muted-badge{color:var(--muted)}.details{display:grid;grid-template-columns:repeat(4,1fr);gap:.6rem;margin:1rem 0}.details div{padding:.75rem;border:1px solid var(--line);border-radius:10px;display:grid;gap:.25rem}.details strong{font-size:.86rem;overflow:hidden;text-overflow:ellipsis}.plugin-error{padding:.7rem;border:1px solid rgba(255,80,95,.25);border-radius:9px;margin-bottom:.8rem}.actions{display:flex;gap:.5rem;flex-wrap:wrap}.actions button:disabled,.head-actions button:disabled{opacity:.45;cursor:not-allowed}.actions .start{color:#35e2b2}.actions .stop{color:#ff7c85}.actions .toggle.on{border-color:rgba(53,226,178,.45)}.settings-editor{margin-top:1rem;padding-top:1rem;border-top:1px solid var(--line);display:grid;gap:.55rem}.settings-editor label{font-size:.75rem;color:var(--muted)}.settings-editor textarea{width:100%;box-sizing:border-box;background:#090d14;color:#dce7e4;border:1px solid var(--line);border-radius:10px;padding:.8rem;font-family:monospace;resize:vertical}.editor-actions{display:flex;justify-content:flex-end;gap:.5rem}.editor-actions .save{background:var(--accent);color:#07110e;font-weight:800}@media(max-width:900px){.metrics,.details{grid-template-columns:repeat(2,1fr)}}@media(max-width:620px){.head{align-items:stretch;flex-direction:column}.metrics,.details{grid-template-columns:1fr}.plugin-head{grid-template-columns:auto 1fr}.badges{grid-column:1/-1}.head-actions{flex-wrap:wrap}}
  `],
})
export class PluginRuntimeUsageComponent implements OnInit {
  readonly guildId = this.route.snapshot.paramMap.get('guildId') ?? '';
  readonly installations = signal<GuildPluginInstallation[]>([]);
  readonly runtimes = signal<PluginRuntimeInstance[]>([]);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly busyKey = signal('');
  readonly editingKey = signal('');
  settingsText = '{}';

  readonly enabledCount = computed(() => this.installations().filter(item => item.enabled).length);
  readonly runningCount = computed(() => this.runtimes().filter(item => item.state === 'running').length);
  readonly errorCount = computed(() => this.installations().filter(item => item.status === 'error' || item.last_error).length + this.runtimes().filter(item => item.last_error).length);

  constructor(
    private readonly route: ActivatedRoute,
    private readonly guildPlugins: GuildPluginService,
    private readonly runtimeService: PluginRuntimeService,
    private readonly i18n: TranslationService,
  ) {}

  ngOnInit(): void { void this.load(); }

  async load(): Promise<void> {
    if (this.loading()) return;
    this.loading.set(true); this.error.set('');
    const [plugins, runtimes] = await Promise.allSettled([
      this.guildPlugins.listInstalled(this.guildId),
      this.runtimeService.list(this.guildId),
    ]);
    if (plugins.status === 'fulfilled') this.installations.set(plugins.value);
    else this.error.set(this.i18n.t('runtime_usage.load_plugins_error', 'Unable to load installed plugins.'));
    this.runtimes.set(runtimes.status === 'fulfilled' ? runtimes.value : []);
    this.loading.set(false);
  }

  runtime(pluginKey: string): PluginRuntimeInstance | null { return this.runtimes().find(item => item.plugin_key === pluginKey) || null; }
  busy(pluginKey: string): boolean { return this.busyKey() === pluginKey; }
  displayName(plugin: GuildPluginInstallation): string {
    const manifest = this.runtime(plugin.plugin_key)?.manifest_json || {};
    return String(manifest['name'] || plugin.plugin_key);
  }
  formatDate(value: string | null | undefined): string {
    if (!value) return '—'; const date = new Date(value); return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: 'short', timeStyle: 'short' }).format(date);
  }

  async toggleEnabled(plugin: GuildPluginInstallation): Promise<void> {
    this.busyKey.set(plugin.plugin_key); this.error.set('');
    try {
      const updated = plugin.enabled ? await this.guildPlugins.disable(this.guildId, plugin.plugin_key) : await this.guildPlugins.enable(this.guildId, plugin.plugin_key);
      this.installations.update(items => items.map(item => item.plugin_key === updated.plugin_key ? updated : item));
    } catch { this.error.set(this.i18n.t('runtime_usage.toggle_error', 'Unable to change plugin state.')); }
    finally { this.busyKey.set(''); }
  }

  async start(plugin: GuildPluginInstallation): Promise<void> {
    this.busyKey.set(plugin.plugin_key); this.error.set('');
    try { this.upsertRuntime(await this.runtimeService.start(this.guildId, plugin.plugin_key)); }
    catch { this.error.set(this.i18n.t('runtime_usage.start_error', 'Unable to start plugin runtime.')); }
    finally { this.busyKey.set(''); }
  }

  async stop(plugin: GuildPluginInstallation): Promise<void> {
    this.busyKey.set(plugin.plugin_key); this.error.set('');
    try { this.upsertRuntime(await this.runtimeService.stop(this.guildId, plugin.plugin_key)); }
    catch { this.error.set(this.i18n.t('runtime_usage.stop_error', 'Unable to stop plugin runtime.')); }
    finally { this.busyKey.set(''); }
  }

  openSettings(plugin: GuildPluginInstallation): void {
    this.editingKey.set(plugin.plugin_key);
    this.settingsText = JSON.stringify(plugin.configuration || {}, null, 2);
  }
  cancelSettings(): void { this.editingKey.set(''); this.settingsText = '{}'; }

  async saveSettings(plugin: GuildPluginInstallation): Promise<void> {
    let configuration: Record<string, unknown>;
    try { configuration = JSON.parse(this.settingsText) as Record<string, unknown>; }
    catch { this.error.set(this.i18n.t('runtime_usage.invalid_json', 'Configuration must be valid JSON.')); return; }
    this.busyKey.set(plugin.plugin_key); this.error.set('');
    try {
      const updated = await this.guildPlugins.updateSettings(this.guildId, plugin.plugin_key, configuration);
      this.installations.update(items => items.map(item => item.plugin_key === updated.plugin_key ? updated : item));
      this.cancelSettings();
    } catch { this.error.set(this.i18n.t('runtime_usage.settings_error', 'Unable to save plugin settings.')); }
    finally { this.busyKey.set(''); }
  }

  private upsertRuntime(updated: PluginRuntimeInstance): void {
    this.runtimes.update(items => {
      const exists = items.some(item => item.plugin_key === updated.plugin_key);
      return exists ? items.map(item => item.plugin_key === updated.plugin_key ? updated : item) : [...items, updated];
    });
  }
}
