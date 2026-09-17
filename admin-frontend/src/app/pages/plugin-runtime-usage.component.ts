import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnInit, computed, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import {
  GuildPluginInstallation,
  GuildPluginMarketplaceItem,
  GuildPluginService,
} from '../core/guild-plugin.service';
import { PluginRuntimeInstance, PluginRuntimeService } from '../core/plugin-runtime.service';
import { TranslationService } from '../core/translation.service';
import { ShellComponent } from '../shared/shell.component';
import { TranslatePipe } from '../core/translate.pipe';
import { firstValueFrom } from 'rxjs';

interface PluginDocumentation {
  plugins?: Record<string, { purpose?: string }>;
}

@Component({
  selector: 'sn-plugin-runtime-usage',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, ShellComponent, TranslatePipe],
  template: `
    <sn-shell [title]="'runtime_usage.title' | snT:'Plugin Runtime'">
      <section class="head">
        <div>
          <div class="eyebrow">GUILDCONSOLE ADMIN V4 · STAGE 14.11</div>
          <h2>{{ 'runtime_usage.heading' | snT:'Plugin store' }}</h2>
          <p>{{ 'runtime_usage.description' | snT:'Install and manage plugins available for this Discord server.' }}</p>
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
        <article><span>{{ 'runtime_usage.available_plugins' | snT:'Available' }}</span><strong>{{ availablePlugins().length }}</strong></article>
        <article><span>{{ 'plugins.installed' | snT:'Installed' }}</span><strong>{{ installations().length }}</strong></article>
        <article><span>{{ 'plugins.enabled' | snT:'Enabled' }}</span><strong>{{ enabledCount() }}</strong></article>
        <article><span>{{ 'plugins.errors' | snT:'Errors' }}</span><strong [class.danger]="errorCount() > 0">{{ errorCount() }}</strong></article>
      </section>

      @if (loading() && availablePlugins().length === 0) {
        <div class="notice">{{ 'runtime_usage.loading' | snT:'Loading plugin store…' }}</div>
      }

      <section class="store-grid">
        @for (plugin of availablePlugins(); track plugin.plugin_key) {
          <article class="store-card" [class.installed]="plugin.installed" [class.enabled]="plugin.enabled">
            <div class="store-top">
              <div class="plugin-icon">{{ plugin.plugin_key.slice(0, 1).toUpperCase() }}</div>
              <div class="plugin-title"><h3>{{ localizedName(plugin) }}</h3><small>{{ plugin.plugin_key }}</small></div>
              <span class="state" [class.good]="plugin.enabled">{{ plugin.enabled ? ('plugins.enabled' | snT:'Enabled') : plugin.installed ? ('plugins.disabled' | snT:'Disabled') : ('runtime_usage.not_installed' | snT:'Not installed') }}</span>
            </div>
            <p class="summary">{{ localizedSummary(plugin) }}</p>
            <div class="store-meta"><span>v{{ plugin.version || '—' }}</span><span>{{ plugin.category }}</span>@if(plugin.verified){<span>✓ {{ 'runtime_usage.verified' | snT:'Verified' }}</span>}</div>
            @if (installation(plugin.plugin_key)?.last_error) { <div class="plugin-error">{{ displayPluginError(installation(plugin.plugin_key)?.last_error) }}</div> }
            <div class="store-actions">
              <a class="docs" [routerLink]="['/guild',guildId,'plugins',plugin.plugin_key,'documentation']">{{ 'documentation.read_more' | snT:'Documentation' }}</a>
              @if (!plugin.installed) {
                <button type="button" class="install" [disabled]="busy(plugin.plugin_key)" (click)="install(plugin)">{{ busy(plugin.plugin_key) ? ('runtime_usage.installing' | snT:'Installing…') : ('runtime_usage.install' | snT:'Install') }}</button>
              } @else if (plugin.enabled) {
                <button type="button" class="disable" [disabled]="busy(plugin.plugin_key)" (click)="toggleEnabled(installation(plugin.plugin_key)!)">{{ 'plugins.disable' | snT:'Disable' }}</button>
              } @else {
                <button type="button" class="enable" [disabled]="busy(plugin.plugin_key)" (click)="toggleEnabled(installation(plugin.plugin_key)!)">{{ 'plugins.enable' | snT:'Enable' }}</button>
                <button type="button" class="uninstall" [disabled]="busy(plugin.plugin_key)" (click)="uninstall(installation(plugin.plugin_key)!)">{{ busy(plugin.plugin_key) ? ('runtime_usage.removing' | snT:'Removing…') : ('runtime_usage.uninstall' | snT:'Uninstall') }}</button>
              }
            </div>

            @if (editingKey() === plugin.plugin_key) {
              <div class="settings-editor">
                <label>{{ 'plugins.configuration_json' | snT:'Configuration JSON' }}</label>
                <textarea [(ngModel)]="settingsText" rows="8" spellcheck="false"></textarea>
                <div class="editor-actions"><button type="button" (click)="cancelSettings()">{{ 'common.cancel' | snT:'Cancel' }}</button><button type="button" class="save" [disabled]="busy(plugin.plugin_key)" (click)="saveSettings(installation(plugin.plugin_key)!)">{{ 'common.save' | snT:'Save' }}</button></div>
              </div>
            }
          </article>
        } @empty {
          @if (!loading()) { <div class="notice">{{ 'runtime_usage.no_available_plugins' | snT:'No available plugins were found.' }}</div> }
        }
      </section>
    </sn-shell>
  `,
  styles: [`
    :host{display:block}.head{display:flex;justify-content:space-between;align-items:flex-end;gap:1rem;margin-bottom:1rem}.eyebrow{font-size:.68rem;font-weight:900;letter-spacing:.14em;color:var(--accent)}.head h2{margin:.3rem 0}.head p{margin:0;color:var(--muted)}.head-actions{display:flex;gap:.55rem}.head-actions a,.head-actions button,.editor-actions button{border:1px solid var(--line);background:var(--panel-2);color:var(--text);border-radius:9px;padding:.62rem .78rem;text-decoration:none;cursor:pointer}.head-actions button{background:var(--accent);color:#07110e;font-weight:800}.notice{padding:1rem;border:1px solid var(--line);background:var(--panel);border-radius:12px}.error,.plugin-error{color:#ff8e98;border-color:rgba(255,80,95,.4)}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:.8rem;margin-bottom:1rem}.metrics article{padding:1rem;border:1px solid var(--line);border-radius:13px;background:var(--panel);display:grid;gap:.35rem}.metrics span{font-size:.7rem;text-transform:uppercase;color:var(--muted)}.metrics strong{font-size:1.5rem}.danger{color:#ff6874}.store-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem}.store-card{display:flex;flex-direction:column;gap:1rem;min-height:245px;padding:1.1rem;border:1px solid var(--line);border-radius:16px;background:var(--panel)}.store-card.installed{border-color:rgba(53,226,178,.3)}.store-top{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:.75rem}.plugin-icon{width:44px;height:44px;border-radius:12px;display:grid;place-items:center;background:rgba(53,226,178,.12);color:var(--accent);font-weight:900}.plugin-title h3{margin:0 0 .2rem}.plugin-title small,.summary{color:var(--muted)}.state{font-size:.68rem;padding:.32rem .55rem;border:1px solid var(--line);border-radius:999px;color:var(--muted)}.state.good{color:#35e2b2;border-color:rgba(53,226,178,.4)}.summary{margin:0;flex:1}.store-meta{display:flex;gap:.45rem;flex-wrap:wrap}.store-meta span{font-size:.7rem;padding:.25rem .45rem;border-radius:7px;background:var(--panel-2);color:var(--muted)}.plugin-error{padding:.7rem;border:1px solid rgba(255,80,95,.25);border-radius:9px}.store-actions{display:flex;gap:.5rem;flex-wrap:wrap}.store-actions button,.store-actions .docs{padding:.68rem .9rem;border-radius:9px;border:1px solid var(--line);background:var(--panel-2);color:var(--text);font-weight:800;cursor:pointer;text-decoration:none}.store-actions .docs{margin-right:auto}.store-actions .install,.store-actions .enable{background:var(--accent);color:#07110e;border-color:var(--accent)}.store-actions .disable{border-color:rgba(53,226,178,.45)}.store-actions .uninstall{color:#ff7c85;border-color:rgba(255,80,95,.35)}.store-actions button:disabled,.head-actions button:disabled{opacity:.45;cursor:not-allowed}.settings-editor{margin-top:.2rem;padding-top:1rem;border-top:1px solid var(--line);display:grid;gap:.55rem}.settings-editor label{font-size:.75rem;color:var(--muted)}.settings-editor textarea{width:100%;box-sizing:border-box;background:#090d14;color:#dce7e4;border:1px solid var(--line);border-radius:10px;padding:.8rem;font-family:monospace;resize:vertical}.editor-actions{display:flex;justify-content:flex-end;gap:.5rem}.editor-actions .save{background:var(--accent);color:#07110e;font-weight:800}@media(max-width:1000px){.store-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:620px){.head{align-items:stretch;flex-direction:column}.metrics,.store-grid{grid-template-columns:1fr}.store-top{grid-template-columns:auto 1fr}.state{grid-column:1/-1}.head-actions{flex-wrap:wrap}}
  `],
})
export class PluginRuntimeUsageComponent implements OnInit {
  readonly guildId = this.route.snapshot.paramMap.get('guildId') ?? '';
  readonly installations = signal<GuildPluginInstallation[]>([]);
  readonly availablePlugins = signal<GuildPluginMarketplaceItem[]>([]);
  readonly runtimes = signal<PluginRuntimeInstance[]>([]);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly busyKey = signal('');
  readonly editingKey = signal('');
  readonly documentation = signal<PluginDocumentation>({});
  settingsText = '{}';

  readonly enabledCount = computed(() => this.installations().filter(item => item.enabled).length);
  readonly runningCount = computed(() => this.runtimes().filter(item => item.state === 'running').length);
  readonly errorCount = computed(() => this.installations().filter(item => item.status === 'error' || item.last_error).length + this.runtimes().filter(item => item.last_error).length);

  constructor(
    private readonly route: ActivatedRoute,
    private readonly router: Router,
    private readonly guildPlugins: GuildPluginService,
    private readonly runtimeService: PluginRuntimeService,
    private readonly i18n: TranslationService,
    private readonly http: HttpClient,
  ) {}

  ngOnInit(): void { void this.load(); }

  async load(): Promise<void> {
    if (this.loading()) return;
    this.loading.set(true); this.error.set('');
    const [plugins, marketplace, runtimes, documentation] = await Promise.allSettled([
      this.guildPlugins.listInstalled(this.guildId),
      this.guildPlugins.marketplace(this.guildId),
      this.runtimeService.list(this.guildId),
      firstValueFrom(this.http.get<PluginDocumentation>(`/plugin-docs/${this.i18n.locale()}.json?v=16.1`)),
    ]);
    if (plugins.status === 'fulfilled') this.installations.set(plugins.value);
    else this.error.set(this.i18n.t('runtime_usage.load_plugins_error', 'Unable to load installed plugins.'));
    this.availablePlugins.set(marketplace.status === 'fulfilled' ? marketplace.value : []);
    this.runtimes.set(runtimes.status === 'fulfilled' ? runtimes.value : []);
    this.documentation.set(documentation.status === 'fulfilled' ? documentation.value : {});
    this.loading.set(false);
  }

  async install(plugin: GuildPluginMarketplaceItem): Promise<void> {
    if (plugin.installed || this.busy(plugin.plugin_key)) return;
    this.busyKey.set(plugin.plugin_key);
    this.error.set('');
    try {
      await this.guildPlugins.install(this.guildId, plugin.plugin_key);
      await this.load();
    } catch {
      this.error.set(
        this.i18n.t(
          'runtime_usage.install_error',
          'Unable to install plugin on this server.',
        ),
      );
    } finally {
      this.busyKey.set('');
    }
  }

  installation(pluginKey: string): GuildPluginInstallation | null { return this.installations().find(item => item.plugin_key === pluginKey) || null; }
  runtime(pluginKey: string): PluginRuntimeInstance | null { return this.runtimes().find(item => item.plugin_key === pluginKey) || null; }
  busy(pluginKey: string): boolean { return this.busyKey() === pluginKey; }
  localizedName(plugin: GuildPluginMarketplaceItem): string {
    return this.i18n.t(`plugin_names.${plugin.plugin_key}`, plugin.name);
  }
  localizedSummary(plugin: GuildPluginMarketplaceItem): string {
    return this.documentation().plugins?.[plugin.plugin_key]?.purpose
      || plugin.summary
      || this.i18n.t('plugins.no_description', 'No description supplied.');
  }
  displayPluginError(value: string | null | undefined): string {
    if (!value) return '';
    if (value.includes('Unknown capabilities')) {
      return this.i18n.t('runtime_usage.capability_error', 'The plugin requested capabilities that are not registered in the core.');
    }
    return value;
  }
  displayName(plugin: GuildPluginInstallation): string {
    const manifest = this.runtime(plugin.plugin_key)?.manifest_json || {};
    return String(this.availablePlugins().find(item => item.plugin_key === plugin.plugin_key)?.name || manifest['name'] || plugin.plugin_key);
  }
  catalogVersion(pluginKey: string): string | null {
    return this.availablePlugins().find(item => item.plugin_key === pluginKey)?.version || null;
  }
  formatDate(value: string | null | undefined): string {
    if (!value) return '—'; const date = new Date(value); return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: 'short', timeStyle: 'short' }).format(date);
  }

  async toggleEnabled(plugin: GuildPluginInstallation): Promise<void> {
    this.busyKey.set(plugin.plugin_key); this.error.set('');
    try {
      const updated = plugin.enabled ? await this.guildPlugins.disable(this.guildId, plugin.plugin_key) : await this.guildPlugins.enable(this.guildId, plugin.plugin_key);
      this.installations.update(items => items.map(item => item.plugin_key === updated.plugin_key ? updated : item));
      this.availablePlugins.update(items => items.map(item => item.plugin_key === updated.plugin_key ? {...item, installed: true, enabled: updated.enabled, installation_status: updated.status} : item));
    } catch (error: any) {
      await this.load();
      const detail = String(error?.error?.detail || '');
      this.error.set(detail.includes('active subscription')
        ? this.i18n.t('runtime_usage.subscription_required', 'An active subscription is required to enable this plugin.')
        : detail || this.i18n.t('runtime_usage.toggle_error', 'Unable to change plugin state.'));
    }
    finally { this.busyKey.set(''); }
  }

  async uninstall(plugin: GuildPluginInstallation): Promise<void> {
    if (this.busy(plugin.plugin_key)) return;

    const confirmed = window.confirm(
      this.i18n.t(
        'runtime_usage.uninstall_confirm',
        `Remove ${this.displayName(plugin)} from this server?`,
      ),
    );
    if (!confirmed) return;

    this.busyKey.set(plugin.plugin_key);
    this.error.set('');
    try {
      await this.guildPlugins.uninstall(
        this.guildId,
        plugin.plugin_key,
      );
      this.editingKey.set('');
      await this.load();
    } catch {
      this.error.set(
        this.i18n.t(
          'runtime_usage.uninstall_error',
          'Unable to remove plugin from this server.',
        ),
      );
    } finally {
      this.busyKey.set('');
    }
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
    const page = plugin.plugin_key === 'translator_groups' ? 'translator-groups'
      : plugin.plugin_key === 'first_introduction' ? 'language-selection'
      : plugin.plugin_key === 'verification_level1' ? 'verification' : null;
    if (page) {
      void this.router.navigate(page === 'verification'
        ? ['/guild', this.guildId, page]
        : ['/guild', this.guildId, 'plugins', page]);
      return;
    }
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
