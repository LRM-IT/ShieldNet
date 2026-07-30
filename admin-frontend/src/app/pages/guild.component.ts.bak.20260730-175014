import { Component, OnInit, computed, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { GuildAccess } from '../core/api.models';
import { GuildService } from '../core/guild.service';
import { GuildPluginInstallation, GuildPluginService } from '../core/guild-plugin.service';
import { GuildModule } from '../core/module.models';
import { ModuleService } from '../core/module.service';
import { ShellComponent } from '../shared/shell.component';
import { TranslatePipe } from '../core/translate.pipe';
import { TranslationService } from '../core/translation.service';

interface QuickAction {
  title: string;
  description: string;
  icon: string;
  path: string;
  code: string;
}

@Component({
  standalone: true,
  imports: [ShellComponent, RouterLink, TranslatePipe],
  template: `
    <sn-shell [title]="guild()?.name || ('guild_node.fallback_title' | snT:'Server Node')">
      @if (error()) {
        <div class="error-panel">{{ error() }}</div>
      } @else if (guild(); as item) {
        <section class="node-hero">
          <div class="node-identity">
            <div class="node-label">{{ "guild_node.label" | snT:"DISCORD INFRASTRUCTURE NODE" }}</div>
            <h2>{{ item.name }}</h2>
            <p>
              {{ "guild_node.description" | snT:"Identity, moderation, security, automation and runtime control." }}
            </p>

            <div class="node-id">{{ "guild_node.node_id" | snT:"NODE ID" }} // {{ guildId }}</div>
          </div>

          <div class="node-status">
            <div class="status-box">
              <span>{{ "guild_node.bot_link" | snT:"BOT LINK" }}</span>
              <strong>{{ item.bot_status }}</strong>
              <i></i>
            </div>

            <div class="hero-actions">
              <a [routerLink]="['/guild', guildId, 'explorer']">{{ "guild_node.explore" | snT:"EXPLORE" }}</a>
              <a class="primary" [routerLink]="['/guild', guildId, 'control']">{{ "guild_node.control" | snT:"CONTROL" }}</a>
            </div>
          </div>
        </section>

        <section class="summary-grid">
          <article>
            <span>{{ "guild_node.members" | snT:"MEMBERS" }}</span>
            <strong>{{ item.member_count }}</strong>
            <a [routerLink]="['/guild', guildId, 'members']">{{ "guild_node.inspect_identities" | snT:"Inspect identities" }} →</a>
          </article>

          <article>
            <span>{{ "guild_node.access_profile" | snT:"ACCESS PROFILE" }}</span>
            <strong class="text-value">{{ item.access_role }}</strong>
            <a [routerLink]="['/guild', guildId, 'permissions']">{{ "guild_node.view_permissions" | snT:"View permissions" }} →</a>
          </article>

          <article>
            <span>{{ "guild_node.installed_plugins" | snT:"INSTALLED PLUGINS" }}</span>
            <strong>{{ enabledCount() }}/{{ visibleModules().length }}</strong>
            <a href="#module-fabric">{{ "guild_node.open_module_fabric" | snT:"Open module fabric" }} ↓</a>
          </article>

          <article>
            <span>{{ "guild_node.node_state" | snT:"NODE STATE" }}</span>
            <strong class="state-value">{{ "guild_node.nominal" | snT:"NOMINAL" }}</strong>
            <a [routerLink]="['/guild', guildId, 'security']">{{ "guild_node.security_overview" | snT:"Security overview" }} →</a>
          </article>
        </section>

        <section class="section-title">
          <div>
            <span>{{ "guild_node.core_operations" | snT:"CORE OPERATIONS" }}</span>
            <h3>{{ "guild_node.operational_access" | snT:"Operational access" }}</h3>
          </div>
          <small>{{ "guild_node.global_modules" | snT:"GLOBAL MODULES" }}</small>
        </section>

        <section class="quick-grid">
          @for (action of quickActions; track action.path) {
            <a class="quick-node" [routerLink]="['/guild', guildId, action.path]">
              <div class="quick-code">{{ action.code }}</div>
              <div class="quick-icon">{{ action.icon }}</div>
              <div>
                <strong>{{ action.title }}</strong>
                <span>{{ action.description }}</span>
              </div>
              <b>→</b>
            </a>
          }
        </section>

        <section id="module-fabric" class="section-title module-title">
          <div>
            <span>{{ "guild_node.installed_plugins" | snT:"INSTALLED PLUGINS" }}</span>
            <h3>{{ "guild_node.plugin_controls" | snT:"Plugin controls" }}</h3>
          </div>
          @if (savingKey()) {
            <small>{{ "guild_node.synchronizing" | snT:"SYNCHRONIZING" }} {{ savingKey() }}</small>
          } @else {
            <small>{{ enabledCount() }} {{ "guild_node.active_modules" | snT:"ACTIVE MODULES" }}</small>
          }
        </section>

        @if (loading()) {
          <div class="loading-panel">{{ "guild_node.loading_fabric" | snT:"Loading module fabric…" }}</div>
        } @else {
          <section class="module-grid">
            @for (module of visibleModules(); track module.module_key; let index = $index) {
              <article class="module-row" [class.enabled]="module.enabled">
                <div class="module-icon">{{ module.icon || '⬡' }}</div>

                <div class="module-copy">
                  <div class="module-heading">
                    <h4>{{ module.name }}</h4>
                    @if (module.is_core) {
                      <span class="badge core">{{ "guild_node.core" | snT:"CORE" }}</span>
                    } @else if (module.enabled) {
                      <span class="badge active">{{ "guild_node.enabled" | snT:"ENABLED" }}</span>
                    } @else {
                      <span class="badge">{{ "guild_node.disabled" | snT:"DISABLED" }}</span>
                    }
                  </div>
                  <p>{{ module.description }}</p>
                </div>

                <div class="module-actions">
                  @if (modulePath(module.module_key); as path) {
                    <a
                      class="open-button"
                      [class.disabled]="!module.enabled && !module.is_core"
                      [routerLink]="['/guild', guildId, path]"
                    >
                      {{ "guild_node.open" | snT:"OPEN" }}
                    </a>
                  }

                  <label class="switch-wrap">
                    <span>{{ module.enabled ? ('guild_node.on' | snT:'ON') : ('guild_node.off' | snT:'OFF') }}</span>
                    <button
                      type="button"
                      class="toggle"
                      [class.on]="module.enabled"
                      [disabled]="module.is_core || savingKey() === module.module_key"
                      (click)="toggle(module)"
                      [attr.aria-label]="('guild_node.toggle' | snT:'Toggle') + ' ' + module.name"
                    >
                      <span></span>
                    </button>
                  </label>
                </div>
              </article>
            }
          </section>
        }
      } @else if (loading()) {
        <div class="loading-panel">{{ "guild_node.establishing" | snT:"Establishing node connection…" }}</div>
      } @else {
        <div class="error-panel">{{ "guild_node.unavailable" | snT:"Node unavailable or access has been revoked." }}</div>
      }
    </sn-shell>
  `,
  styles: [`
    .node-hero{
      position:relative;
      overflow:hidden;
      min-height:245px;
      display:grid;
      grid-template-columns:1fr auto;
      align-items:center;
      gap:2rem;
      padding:1.8rem;
      background:
        radial-gradient(circle at 82% 30%,rgba(53,226,178,.1),transparent 17rem),
        linear-gradient(145deg,#0c171f,#070d13);
      border:1px solid var(--line);
      border-radius:17px
    }

    .node-hero::before{
      content:"";
      position:absolute;
      right:-90px;
      top:-120px;
      width:360px;
      height:360px;
      border:1px solid rgba(53,226,178,.1);
      border-radius:50%;
      box-shadow:0 0 0 45px rgba(53,226,178,.015),0 0 0 90px rgba(53,226,178,.01)
    }

    .node-identity,.node-status{position:relative;z-index:2}
    .node-label{
      color:#69857e;
      font-size:.58rem;
      font-weight:900;
      letter-spacing:.16em
    }

    .node-identity h2{
      margin:.65rem 0 .45rem;
      font-size:clamp(2rem,4vw,4.3rem);
      line-height:1;
      letter-spacing:-.055em
    }

    .node-identity p{margin:0;color:var(--muted)}
    .node-id{
      width:max-content;
      max-width:100%;
      margin-top:1.2rem;
      padding:.5rem .65rem;
      color:#6f8f87;
      background:rgba(53,226,178,.04);
      border-left:2px solid var(--primary);
      font-family:ui-monospace,SFMono-Regular,Consolas,monospace;
      font-size:.59rem
    }

    .node-status{display:grid;justify-items:end;gap:1rem}
    .status-box{
      min-width:170px;
      display:grid;
      grid-template-columns:1fr auto;
      gap:.25rem .75rem;
      padding:1rem;
      background:#091018;
      border:1px solid var(--line);
      border-radius:11px
    }
    .status-box span{color:#5a737e;font-size:.55rem;letter-spacing:.14em}
    .status-box strong{
      grid-row:2;
      color:var(--success);
      text-transform:uppercase;
      font-size:.73rem;
      letter-spacing:.1em
    }
    .status-box i{
      grid-row:1/3;
      grid-column:2;
      align-self:center;
      width:.55rem;
      height:.55rem;
      border-radius:50%;
      background:var(--success);
      box-shadow:0 0 12px rgba(57,221,161,.78)
    }

    .hero-actions{display:flex;gap:.55rem}
    .hero-actions a{
      min-height:40px;
      display:flex;
      align-items:center;
      justify-content:center;
      padding:.65rem .8rem;
      color:#91a8a1;
      background:#0b131b;
      border:1px solid var(--line);
      border-radius:8px;
      font-size:.6rem;
      font-weight:900;
      letter-spacing:.09em
    }
    .hero-actions a.primary{color:#03130e;background:var(--primary)}

    .summary-grid{
      display:grid;
      grid-template-columns:repeat(4,minmax(0,1fr));
      gap:.7rem;
      margin-top:.8rem
    }

    .summary-grid article{
      min-height:138px;
      display:flex;
      flex-direction:column;
      justify-content:flex-end;
      gap:.35rem;
      padding:1rem;
      background:
        linear-gradient(145deg,rgba(255,255,255,.02),transparent 45%),
        #0a1119;
      border:1px solid var(--line);
      border-radius:11px
    }

    .summary-grid span{
      color:#5e7580;
      font-size:.55rem;
      font-weight:850;
      letter-spacing:.13em
    }
    .summary-grid strong{font-size:2rem}
    .summary-grid strong.text-value{font-size:1.05rem;text-transform:uppercase}
    .summary-grid strong.state-value{color:var(--success);font-size:1.1rem}
    .summary-grid a{margin-top:.2rem;color:#718d86;font-size:.63rem}

    .section-title{
      display:flex;
      justify-content:space-between;
      align-items:end;
      gap:1rem;
      margin:1.5rem 0 .75rem
    }
    .section-title span{
      color:#607982;
      font-size:.56rem;
      font-weight:900;
      letter-spacing:.15em
    }
    .section-title h3{margin:.24rem 0 0}
    .section-title small{color:#49616c;font-size:.55rem;letter-spacing:.11em}

    .quick-grid{
      display:grid;
      grid-template-columns:repeat(3,minmax(0,1fr));
      gap:.55rem
    }

    .quick-node{
      min-height:78px;
      display:grid;
      grid-template-columns:34px 1fr auto;
      align-items:center;
      gap:.7rem;
      padding:.75rem .85rem;
      background:#0a1119;
      border:1px solid var(--line);
      border-radius:9px
    }

    .quick-node:hover{
      background:rgba(53,226,178,.025);
      border-color:rgba(53,226,178,.18)
    }

    .quick-code{display:none}

    .quick-icon{
      width:34px;
      height:34px;
      display:grid;
      place-items:center;
      color:var(--primary);
      background:rgba(53,226,178,.045);
      border:1px solid rgba(53,226,178,.12);
      border-radius:8px
    }

    .quick-node>div:nth-child(3){display:grid;gap:.15rem}
    .quick-node strong{font-size:.76rem}
    .quick-node span{color:var(--muted);font-size:.61rem;line-height:1.25}
    .quick-node b{color:#58756d;font-size:.72rem}

    .module-title{margin-top:1.4rem}
    .module-grid{display:grid;gap:.45rem}

    .module-row{
      display:grid;
      grid-template-columns:38px minmax(0,1fr) auto;
      gap:.75rem;
      align-items:center;
      padding:.7rem .8rem;
      background:#0a1119;
      border:1px solid var(--line);
      border-radius:9px
    }

    .module-row.enabled{
      border-color:rgba(53,226,178,.16);
      background:linear-gradient(90deg,rgba(53,226,178,.025),transparent 24%),#0a1119
    }

    .module-icon{
      width:38px;
      height:38px;
      display:grid;
      place-items:center;
      color:#6f9187;
      background:#0d1720;
      border:1px solid var(--line);
      border-radius:8px;
      font-size:.95rem
    }

    .module-row.enabled .module-icon{color:var(--primary)}

    .module-heading{display:flex;align-items:center;gap:.45rem;flex-wrap:wrap}
    .module-heading h4{margin:0;font-size:.78rem}
    .module-copy p{margin:.2rem 0 0;color:var(--muted);font-size:.62rem;line-height:1.3}

    .badge{
      padding:.18rem .36rem;
      color:#738791;
      border:1px solid var(--line);
      border-radius:999px;
      font-size:.46rem;
      font-weight:900;
      letter-spacing:.06em
    }
    .badge.active{color:var(--success);border-color:rgba(57,221,161,.22)}
    .badge.core{color:var(--accent);border-color:rgba(99,199,255,.22)}

    .module-actions{display:flex;align-items:center;gap:.65rem}

    .open-button{
      min-height:32px;
      display:flex;
      align-items:center;
      padding:.42rem .58rem;
      color:#9bb1ab;
      border:1px solid var(--line);
      border-radius:7px;
      font-size:.53rem;
      font-weight:900
    }
    .open-button.disabled{opacity:.3;pointer-events:none}

    .switch-wrap{
      display:flex;
      align-items:center;
      gap:.4rem;
      color:#5e737d;
      font-size:.49rem;
      font-weight:900;
      letter-spacing:.08em
    }

    .toggle{
      width:2.7rem;
      height:1.45rem;
      padding:.16rem;
      background:#23303a;
      border-radius:999px
    }
    .toggle:disabled{opacity:.45}
    .toggle span{
      display:block;
      width:1.12rem;
      height:1.12rem;
      background:#7d8b94;
      border-radius:50%;
      transition:.18s
    }
    .toggle.on{background:rgba(53,226,178,.2)}
    .toggle.on span{
      transform:translateX(1.2rem);
      background:var(--primary);
      box-shadow:0 0 8px rgba(53,226,178,.4)
    }

    .error-panel,.loading-panel{
      padding:1rem;
      color:var(--muted);
      background:#0a1119;
      border:1px solid var(--line);
      border-radius:10px
    }
    .error-panel{color:#ffd8dc;border-color:rgba(255,111,127,.24)}

    @media(max-width:1100px){
      .summary-grid{grid-template-columns:repeat(2,1fr)}
      .quick-grid{grid-template-columns:repeat(2,1fr)}
    }

    @media(max-width:700px){
      .node-hero{grid-template-columns:1fr;padding:1.2rem}
      .node-status{justify-items:start}
      .summary-grid,.quick-grid{grid-template-columns:1fr}
      .module-row{grid-template-columns:34px 1fr}
      .module-actions{grid-column:1/-1;justify-content:flex-end}
      .section-title{align-items:flex-start;flex-direction:column}
    }
  `],
})
export class GuildComponent implements OnInit {
  readonly guilds = signal<GuildAccess[]>([]);
  readonly modules = signal<GuildModule[]>([]);
  readonly installedPlugins = signal<GuildPluginInstallation[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly savingKey = signal('');

  readonly guildId = this.route.snapshot.paramMap.get('guildId') ?? '';
  readonly guild = computed(
    () => this.guilds().find((item) => item.guild_id === this.guildId) || null,
  );
  readonly visibleModules = computed(() => {
    const installed = new Set(
      this.installedPlugins().map((plugin) => this.normalize(plugin.plugin_key)),
    );

    return this.modules().filter((module) => {
      const key = this.normalize(module.module_key);
      if (key === 'welcome') return false;
      if (module.is_core) return true;
      return installed.has(key);
    });
  });

  readonly enabledCount = computed(
    () => this.visibleModules().filter((module) => module.enabled).length,
  );

  readonly quickActions: QuickAction[] = [
    { title: 'Members', description: 'Identity and member management', icon: '◉', path: 'members', code: 'CORE-01' },
    { title: 'Security', description: 'Risks and security controls', icon: '◇', path: 'security', code: 'CORE-02' },
    { title: 'Explorer', description: 'Discord roles and channels', icon: '⌁', path: 'explorer', code: 'CORE-03' },
    { title: 'Audit Trail', description: 'Administrative activity', icon: '≡', path: 'audit', code: 'CORE-04' },
    { title: 'Backup Center', description: 'Backup and restore', icon: '◫', path: 'backups', code: 'CORE-05' },
    { title: 'Server Control', description: 'Core server settings', icon: '⌬', path: 'control', code: 'CORE-06' },
  ];

  constructor(
    private readonly route: ActivatedRoute,
    private readonly guildService: GuildService,
    private readonly moduleService: ModuleService,
    private readonly guildPluginService: GuildPluginService,
    private readonly i18n: TranslationService,
  ) {}

  async ngOnInit(): Promise<void> {
    try {
      const [guilds, modules, installedPlugins] = await Promise.all([
        this.guildService.list(),
        this.moduleService.list(this.guildId),
        this.guildPluginService.listInstalled(this.guildId),
      ]);

      this.guilds.set(guilds);
      this.modules.set(modules);
      this.installedPlugins.set(installedPlugins);
    } catch {
      this.error.set(this.i18n.t('guild_node.connection_error','Unable to establish a connection to this server node.'));
    } finally {
      this.loading.set(false);
    }
  }

  async toggle(module: GuildModule): Promise<void> {
    if (module.is_core || this.savingKey()) return;

    this.savingKey.set(module.module_key);
    this.error.set('');

    try {
      const updated = await this.moduleService.update(
        this.guildId,
        module.module_key,
        !module.enabled,
        module.configuration,
      );

      this.modules.update((items) =>
        items.map((item) =>
          item.module_key === updated.module_key ? updated : item,
        ),
      );
    } catch {
      this.error.set(this.i18n.t('guild_node.module_update_error','Unable to update {name}.').replace('{name}',module.name));
    } finally {
      this.savingKey.set('');
    }
  }

  private normalize(value: string): string {
    return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_');
  }

  modulePath(key: string): string | null {
    const map: Record<string, string> = {
      core: 'control',
      verification: 'verification',
      moderation: 'moderation',
      translator: 'control',
      security: 'security',
      automations: 'automations',
      automation: 'automations',
      plugin_runtime: 'plugin-runtime',
      runtime: 'plugin-runtime',
      plugins: 'plugin-runtime',
      members: 'members',
      leadership: 'leadership',
      audit: 'audit',
      voting: 'plugins/voting',
    };

    return map[key.toLowerCase()] || null;
  }
}
