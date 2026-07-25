import {
  Component,
  OnInit,
  computed,
  signal,
} from '@angular/core';

import {
  PluginAction,
  PluginActivation,
  PluginManifest,
  PluginScanResult,
  PluginService,
} from '../core/plugin.service';
import { ShellComponent } from '../shared/shell.component';
import { TranslatePipe } from '../core/translate.pipe';
import { TranslationService } from '../core/translation.service';
import { ModalService } from '../core/modal.service';
import { ToastService } from '../core/toast.service';

@Component({
  selector: 'sn-plugins',
  standalone: true,
  imports: [ShellComponent, TranslatePipe],
  template: `
    <sn-shell [title]="'plugins.title' | snT:'Plugin Platform'">
      <section class="page-head">
        <div>
          <h2>{{ "plugins.installed" | snT:"Installed plugins" }}</h2>
          <p class="muted">
            {{ "plugins.description" | snT:"Manage discovered ShieldNet plugins and their runtime state." }}
          </p>
        </div>

        <div class="head-actions">
          <button
            type="button"
            class="secondary"
            (click)="load()"
            [disabled]="loading()"
          >
            {{ "plugins.refresh" | snT:"Refresh" }}
          </button>

          <button
            type="button"
            (click)="scan()"
            [disabled]="scanning()"
          >
            {{ scanning() ? ('plugins.scanning' | snT:'Scanning…') : ('plugins.scan' | snT:'Scan plugin directory') }}
          </button>
        </div>
      </section>

      <section class="metrics">
        <article class="card">
          <span class="muted">{{ "plugins.discovered" | snT:"Discovered" }}</span>
          <strong>{{ plugins().length }}</strong>
        </article>

        <article class="card">
          <span class="muted">{{ "plugins.enabled" | snT:"Enabled" }}</span>
          <strong>{{ enabledCount() }}</strong>
        </article>

        <article class="card">
          <span class="muted">{{ "plugins.healthy" | snT:"Healthy" }}</span>
          <strong>{{ healthyCount() }}</strong>
        </article>

        <article class="card">
          <span class="muted">{{ "plugins.running" | snT:"Running" }}</span>
          <strong>{{ runningCount() }}</strong>
        </article>
      </section>

      @if (scanResult()) {
        <div class="notice card">
          {{ "plugins.scan_complete" | snT:"Scan complete" }}:
          {{ scanResult()?.discovered }} {{ "plugins.scan_discovered" | snT:"discovered" }},
          {{ scanResult()?.updated }} {{ "plugins.scan_updated" | snT:"updated" }},
          {{ scanResult()?.missing }} {{ "plugins.scan_missing" | snT:"missing" }}.

          @if ((scanResult()?.errors?.length || 0) > 0) {
            <div class="scan-errors">
              @for (item of scanResult()?.errors || []; track item) {
                <div>{{ item }}</div>
              }
            </div>
          }
        </div>
      }

      @if (error()) {
        <div class="error card">{{ error() }}</div>
      }

      @if (loading()) {
        <div class="card loading">{{ "plugins.loading" | snT:"Loading plugins…" }}</div>
      }

      <section class="plugin-grid">
        @for (plugin of plugins(); track plugin.plugin_key) {
          <article
            class="plugin card"
            [class.unhealthy]="!plugin.healthy"
          >
            <div class="plugin-main">
              <div class="title-row">
                <h3>{{ plugin.name }}</h3>

                <span class="badge">v{{ plugin.version }}</span>

                <span
                  class="badge"
                  [class.good]="plugin.healthy"
                  [class.bad]="!plugin.healthy"
                >
                  {{ plugin.healthy ? ('plugins.healthy' | snT:'Healthy') : ('plugins.unhealthy' | snT:'Unhealthy') }}
                </span>

                <span
                  class="badge"
                  [class.good]="runtime(plugin.plugin_key)?.state === 'running'"
                >
                  {{ runtime(plugin.plugin_key)?.state || ('plugins.unknown' | snT:'unknown') }}
                </span>

                @if (runtime(plugin.plugin_key)?.maintenance) {
                  <span class="badge warning">{{ "plugins.maintenance" | snT:"Maintenance" }}</span>
                }

                <span class="badge">
                  {{ plugin.signature_status }}
                </span>
              </div>

              <p class="muted">
                {{ plugin.description || ('plugins.no_description' | snT:'No description supplied.') }}
              </p>

              <div class="meta">
                <span>{{ 'plugins.id' | snT:'ID' }}: {{ plugin.plugin_key }}</span>
                <span>{{ 'plugins.author' | snT:'Author' }}: {{ plugin.author || ('plugins.unknown_author' | snT:'Unknown') }}</span>
                <span>{{ 'plugins.core' | snT:'Core' }}: {{ plugin.min_core_version || ('plugins.any' | snT:'Any') }}</span>

                @if (runtime(plugin.plugin_key)?.pid) {
                  <span>{{ 'plugins.pid' | snT:'PID' }}: {{ runtime(plugin.plugin_key)?.pid }}</span>
                }

                <span>
                  {{ "plugins.restarts" | snT:"Restarts" }}:
                  {{ runtime(plugin.plugin_key)?.restart_count || 0 }}
                </span>
              </div>

              <div class="chips">
                @for (
                  capability of plugin.capabilities;
                  track capability
                ) {
                  <span>{{ capability }}</span>
                }
              </div>

              @if (
                plugin.last_error ||
                runtime(plugin.plugin_key)?.last_error
              ) {
                <div class="plugin-error">
                  {{
                    runtime(plugin.plugin_key)?.last_error ||
                    plugin.last_error
                  }}
                </div>
              }
            </div>

            <div class="plugin-actions">
              <button class="small secondary" type="button" (click)="showDetails(plugin)">
                {{ "plugins.view_details" | snT:"View details" }}
              </button>
              <button
                class="small success"
                type="button"
                [disabled]="busy(plugin.plugin_key)"
                (click)="runAction(plugin, 'start')"
              >
                {{ "plugins.start" | snT:"Start" }}
              </button>

              <button
                class="small"
                type="button"
                [disabled]="busy(plugin.plugin_key)"
                (click)="runAction(plugin, 'restart')"
              >
                {{ "plugins.restart" | snT:"Restart" }}
              </button>

              <button
                class="small danger"
                type="button"
                [disabled]="busy(plugin.plugin_key)"
                (click)="runAction(plugin, 'stop')"
              >
                {{ "plugins.stop" | snT:"Stop" }}
              </button>

              <button
                class="small secondary"
                type="button"
                [disabled]="busy(plugin.plugin_key)"
                (click)="toggleMaintenance(plugin)"
              >
                {{
                  runtime(plugin.plugin_key)?.maintenance
                    ? ('plugins.leave_maintenance' | snT:'Leave maintenance')
                    : ('plugins.maintenance' | snT:'Maintenance')
                }}
              </button>

              <label class="enabled-control">
                <span>{{ "plugins.enabled" | snT:"Enabled" }}</span>

                <button
                  class="toggle"
                  type="button"
                  [class.on]="plugin.enabled"
                  [disabled]="busy(plugin.plugin_key) || !plugin.healthy"
                  (click)="toggle(plugin)"
                  [attr.aria-label]="('plugins.toggle' | snT:'Toggle') + ' ' + plugin.name"
                >
                  <span></span>
                </button>
              </label>
            </div>
          </article>
        } @empty {
          @if (!loading()) {
            <div class="empty card">
              {{ "plugins.empty" | snT:"No plugins found. Place manifests under /opt/shieldnet/plugins/&lt;plugin&gt;/plugin.json and scan again." }}
            </div>
          }
        }
      </section>
    </sn-shell>
  `,
  styles: [`
    .page-head{
      display:flex;
      justify-content:space-between;
      align-items:end;
      gap:1rem;
      margin-bottom:1rem
    }

    .page-head h2,.page-head p{margin:0}
    .page-head p{margin-top:.35rem}

    .head-actions{
      display:flex;
      gap:.6rem;
      flex-wrap:wrap
    }

    button{
      border:0;
      cursor:pointer
    }

    .page-head button{
      padding:.75rem 1rem;
      border-radius:11px;
      background:var(--primary);
      color:#fff;
      font-weight:750
    }

    button:disabled{
      opacity:.5;
      cursor:not-allowed
    }

    .secondary{
      background:#263149!important
    }

    .metrics{
      display:grid;
      grid-template-columns:repeat(4,minmax(0,1fr));
      gap:1rem;
      margin-bottom:1rem
    }

    .metrics article{
      padding:1rem;
      display:grid;
      gap:.4rem
    }

    .metrics strong{font-size:1.45rem}

    .notice,.error,.loading,.empty{
      padding:1rem;
      margin-bottom:1rem
    }

    .error,.plugin-error{color:#ffd9de}

    .scan-errors{
      margin-top:.7rem;
      color:#ffd3a0;
      font-size:.8rem
    }

    .plugin-grid{
      display:grid;
      gap:.8rem
    }

    .plugin{
      padding:1rem;
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      gap:1.2rem;
      align-items:center
    }

    .plugin.unhealthy{
      border-color:rgba(255,107,125,.45)
    }

    .title-row{
      display:flex;
      align-items:center;
      gap:.5rem;
      flex-wrap:wrap
    }

    .title-row h3{margin:0}
    .plugin p{margin:.45rem 0}

    .meta{
      display:flex;
      gap:1rem;
      flex-wrap:wrap;
      color:var(--muted);
      font-size:.75rem
    }

    .badge,.chips span{
      padding:.22rem .5rem;
      border:1px solid var(--line);
      border-radius:999px;
      color:var(--muted);
      font-size:.7rem
    }

    .badge.good{
      color:#b9f4dc;
      border-color:rgba(75,214,155,.35)
    }

    .badge.bad{
      color:#ffd9de;
      border-color:rgba(255,107,125,.35)
    }

    .badge.warning{
      color:#ffe0a3;
      border-color:rgba(255,202,98,.4)
    }

    .chips{
      display:flex;
      gap:.4rem;
      flex-wrap:wrap;
      margin-top:.7rem
    }

    .plugin-error{
      margin-top:.7rem;
      font-size:.8rem
    }

    .plugin-actions{
      display:grid;
      grid-template-columns:repeat(2,minmax(7rem,1fr));
      gap:.5rem;
      min-width:16rem
    }

    .small{
      padding:.55rem .7rem;
      border-radius:8px;
      background:#303b54;
      color:#fff;
      font-weight:700
    }

    .small.success{
      background:rgba(75,214,155,.24)
    }

    .small.danger{
      background:rgba(255,107,125,.22)
    }

    .enabled-control{
      grid-column:1/-1;
      display:flex;
      justify-content:space-between;
      align-items:center;
      color:var(--muted);
      font-size:.8rem;
      margin-top:.2rem
    }

    .toggle{
      width:3.1rem;
      height:1.75rem;
      padding:.2rem;
      border-radius:999px;
      background:#2a344b
    }

    .toggle span{
      display:block;
      width:1.35rem;
      height:1.35rem;
      border-radius:50%;
      background:white;
      transition:.2s
    }

    .toggle.on{background:var(--success)}
    .toggle.on span{transform:translateX(1.35rem)}
    code{color:#cfd5ff}

    @media(max-width:900px){
      .plugin{
        grid-template-columns:1fr
      }

      .plugin-actions{
        min-width:0
      }
    }

    @media(max-width:760px){
      .page-head{
        align-items:stretch;
        flex-direction:column
      }

      .metrics{
        grid-template-columns:1fr 1fr
      }
    }
  `],
})
export class PluginsComponent implements OnInit {
  readonly plugins = signal<PluginManifest[]>([]);
  readonly activations = signal<Record<string, PluginActivation>>({});
  readonly loading = signal(true);
  readonly scanning = signal(false);
  readonly savingKey = signal<string | null>(null);
  readonly error = signal('');
  readonly scanResult = signal<PluginScanResult | null>(null);

  readonly enabledCount = computed(
    () => this.plugins().filter((plugin) => plugin.enabled).length,
  );

  readonly healthyCount = computed(
    () => this.plugins().filter((plugin) => plugin.healthy).length,
  );

  readonly runningCount = computed(
    () => Object.values(this.activations())
      .filter((activation) => activation.state === 'running')
      .length,
  );

  constructor(private readonly pluginService: PluginService, private readonly i18n: TranslationService, private readonly modal: ModalService, private readonly toast: ToastService) {}


  showDetails(plugin: PluginManifest): void {
    const runtime = this.runtime(plugin.plugin_key);
    const raw = JSON.stringify({ plugin, runtime }, null, 2);

    this.modal.details(
      this.i18n.t('plugins.details', 'Plugin details'),
      [
        { label: this.i18n.t('plugins.plugin_key', 'Plugin key'), value: plugin.plugin_key, code: true },
        { label: this.i18n.t('plugins.version', 'Version'), value: plugin.version },
        { label: this.i18n.t('plugins.author', 'Author'), value: plugin.author || this.i18n.t('plugins.unknown_author','Unknown') },
        { label: this.i18n.t('plugins.signature', 'Signature'), value: plugin.signature_status || '—' },
        { label: this.i18n.t('plugins.runtime_state', 'Runtime state'), value: runtime?.state || this.i18n.t('plugins.unknown','unknown') },
        { label: this.i18n.t('plugins.maintenance_mode', 'Maintenance mode'), value: runtime?.maintenance ? 'ON' : 'OFF' },
        { label: this.i18n.t('plugins.pid', 'PID'), value: runtime?.pid ? String(runtime.pid) : '—', code: true },
        { label: this.i18n.t('plugins.restart_count', 'Restart count'), value: String(runtime?.restart_count || 0) },
        { label: this.i18n.t('plugins.capabilities', 'Capabilities'), value: plugin.capabilities?.join(', ') || '—', wide: true },
        { label: this.i18n.t('plugins.description', 'Description'), value: plugin.description || '—', wide: true },
        { label: this.i18n.t('plugins.last_error', 'Last error'), value: runtime?.last_error || plugin.last_error || '—', wide: true, code: true },
      ],
      {
        message: plugin.name,
        raw,
        copyLabel: this.i18n.t('ui.copy', 'Copy'),
        closeLabel: this.i18n.t('ui.close', 'Close'),
        danger: !plugin.healthy,
      },
    );
  }

  async ngOnInit(): Promise<void> {
    await this.load();
  }

  runtime(pluginKey: string): PluginActivation | null {
    return this.activations()[pluginKey] || null;
  }

  busy(pluginKey: string): boolean {
    return this.savingKey() === pluginKey;
  }

  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set('');

    try {
      const plugins = await this.pluginService.list();
      this.plugins.set(plugins);

      const activationEntries = await Promise.all(
        plugins.map(async (plugin) => {
          try {
            const status = await this.pluginService.status(
              plugin.plugin_key,
            );

            return [plugin.plugin_key, status] as const;
          } catch {
            return null;
          }
        }),
      );

      const activations: Record<string, PluginActivation> = {};

      for (const entry of activationEntries) {
        if (entry) {
          activations[entry[0]] = entry[1];
        }
      }

      this.activations.set(activations);
    } catch {
      this.error.set(this.i18n.t('plugins.load_error','Unable to load plugins.'));
    } finally {
      this.loading.set(false);
    }
  }

  async scan(): Promise<void> {
    this.scanning.set(true);
    this.error.set('');

    try {
      this.scanResult.set(await this.pluginService.scan());
      await this.load();
      this.toast.success(this.i18n.t('ui.success','Completed'),this.i18n.t('plugins.scan_success','Plugin scan completed.'));
    } catch {
      this.error.set(
        this.i18n.t('plugins.scan_error','Plugin scan failed. Superadmin access is required.'),
      );
    } finally {
      this.scanning.set(false);
    }
  }

  async toggle(plugin: PluginManifest): Promise<void> {
    this.savingKey.set(plugin.plugin_key);
    this.error.set('');

    try {
      const updated = await this.pluginService.setEnabled(
        plugin.plugin_key,
        !plugin.enabled,
      );

      this.plugins.update((items) =>
        items.map((item) =>
          item.plugin_key === updated.plugin_key ? updated : item,
        ),
      );

      await this.refreshStatus(plugin.plugin_key);
      this.toast.success(this.i18n.t('ui.success','Completed'),this.i18n.t('plugins.enabled_success','Plugin state updated.'));
    } catch {
      this.error.set(this.i18n.t('plugins.update_error','Unable to update {name}.').replace('{name}',plugin.name));
    } finally {
      this.savingKey.set(null);
    }
  }

  async runAction(
    plugin: PluginManifest,
    action: PluginAction,
  ): Promise<void> {
    this.savingKey.set(plugin.plugin_key);
    this.error.set('');

    try {
      const activation = await this.pluginService.action(
        plugin.plugin_key,
        action,
      );

      this.setActivation(activation);
      await this.refreshManifest();
      this.toast.success(this.i18n.t('ui.success','Completed'),this.i18n.t('plugins.action_success','Plugin action completed.'));
    } catch {
      this.error.set(
        this.i18n.t('plugins.action_error','Unable to {action} {name}.').replace('{action}',action).replace('{name}',plugin.name),
      );
    } finally {
      this.savingKey.set(null);
    }
  }

  async toggleMaintenance(
    plugin: PluginManifest,
  ): Promise<void> {
    this.savingKey.set(plugin.plugin_key);
    this.error.set('');

    const current = this.runtime(plugin.plugin_key);

    try {
      const activation = await this.pluginService.setMaintenance(
        plugin.plugin_key,
        !current?.maintenance,
      );

      this.setActivation(activation);
      this.toast.success(this.i18n.t('ui.success','Completed'),this.i18n.t('plugins.maintenance_success','Maintenance mode updated.'));
    } catch {
      this.error.set(
        this.i18n.t('plugins.maintenance_error','Unable to update maintenance mode for {name}.').replace('{name}',plugin.name),
      );
    } finally {
      this.savingKey.set(null);
    }
  }

  private async refreshManifest(): Promise<void> {
    const plugins = await this.pluginService.list();
    this.plugins.set(plugins);
  }

  private async refreshStatus(pluginKey: string): Promise<void> {
    try {
      const activation = await this.pluginService.status(pluginKey);
      this.setActivation(activation);
    } catch {
      // Plugin may not yet have an activation record.
    }
  }

  private setActivation(activation: PluginActivation): void {
    this.activations.update((items) => ({
      ...items,
      [activation.plugin_key]: activation,
    }));
  }
}
