import { Component, HostListener, Input, OnDestroy, OnInit, computed, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink, RouterLinkActive } from '@angular/router';
import { TranslatePipe } from '../core/translate.pipe';
import { EventBusService } from '../core/event-bus.service';
import { ThemeService } from '../core/theme.service';

import { AuthService } from '../core/auth.service';
import {
  GuildPluginInstallation,
  GuildPluginService,
} from '../core/guild-plugin.service';

interface NavItem {
  label: string;
  icon: string;
  path: string | any[];
  exact?: boolean;
}


interface PaletteCommand {
  id: string;
  label: string;
  fallback: string;
  icon: string;
  path: string | any[];
  guildOnly?: boolean;
}

interface PluginNavDefinition {
  keys: string[];
  label: string;
  icon: string;
  path: string;
}

@Component({
  selector: 'sn-shell',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, TranslatePipe],
  template: `
    <div class="workspace" [class.menu-open]="mobileMenu()" [class.menu-collapsed]="menuCollapsed()">
      <aside class="rail">
        <a [routerLink]="homeLink()" class="brand" aria-label="ShieldNet home">
          <span class="brand-symbol"><span></span><span></span><span></span></span>
          <span class="brand-copy">
            <strong>SHIELDNET</strong>
            <small>{{ 'shell.control_fabric' | snT:'CONTROL FABRIC' }}</small>
          </span>
        </a>

        <div class="rail-state">
          <span class="pulse"></span>
          <div>
            <strong>{{ 'shell.control_plane' | snT:'CONTROL PLANE' }}</strong>
            <small>{{ 'shell.encrypted_session' | snT:'Encrypted session active' }}</small>
          </div>
        </div>

        <nav aria-label="Main navigation">
          <div class="nav-group">
            <div class="nav-label">{{ "shell.workspace" | snT:"Workspace" }}</div>
            @if (isPlatformContext()) {
              <a routerLink="/platform" routerLinkActive="active" [routerLinkActiveOptions]="{ exact: true }">
                <span class="nav-icon">⌂</span><span>Platform overview</span>
              </a>
              <a routerLink="/servers" routerLinkActive="active">
                <span class="nav-icon">◫</span><span>Guild Control Centers</span>
              </a>
              <a routerLink="/platform/plugins" routerLinkActive="active">
                <span class="nav-icon">⬡</span><span>{{ 'shell.plugin_fabric' | snT:'Plugin fabric' }}</span>
              </a>
              <a routerLink="/platform/jobs" routerLinkActive="active">
                <span class="nav-icon">⌁</span><span>{{ 'shell.jobs_center' | snT:'Jobs center' }}</span>
              </a>
              <a routerLink="/platform/operations" routerLinkActive="active">
                <span class="nav-icon">◎</span><span>{{ 'shell.operations' | snT:'Operations' }}</span>
              </a>
              <a routerLink="/platform/health" routerLinkActive="active">
                <span class="nav-icon">✚</span><span>Health monitor</span>
              </a>
              <a routerLink="/platform/logs" routerLinkActive="active">
                <span class="nav-icon">≡</span><span>Live logs</span>
              </a>
              <a routerLink="/platform/notifications" routerLinkActive="active">
                <span class="nav-icon">◌</span><span>Notifications</span>
              </a>
              <a routerLink="/platform/access" routerLinkActive="active">
                <span class="nav-icon">⚿</span><span>Platform access</span>
              </a>
            } @else {
              <a routerLink="/servers" routerLinkActive="active">
                <span class="nav-icon">⌂</span><span>{{ 'shell.servers' | snT:'Servers' }}</span>
              </a>
            }
          </div>

          @if (guildId()) {
            <div class="nav-group">
              <div class="nav-label">{{ "shell.core_server" | snT:"Core server" }}</div>
              @for (item of coreNavigation(); track item.label) {
                <a [routerLink]="item.path" routerLinkActive="active"
                   [routerLinkActiveOptions]="{ exact: !!item.exact }">
                  <span class="nav-icon">{{ item.icon }}</span>
                  <span>{{ item.label | snT:item.label }}</span>
                </a>
              }
            </div>

            @if (pluginNavigation().length > 0) {
              <div class="nav-group">
                <div class="nav-label">{{ "shell.installed_plugins" | snT:"Installed plugins" }}</div>
                @for (item of pluginNavigation(); track item.label) {
                  <a [routerLink]="item.path" routerLinkActive="active">
                    <span class="nav-icon">{{ item.icon }}</span>
                    <span>{{ item.label | snT:item.label }}</span>
                  </a>
                }
              </div>
            }
          }
        </nav>

        <a routerLink="/profile" class="operator" aria-label="Open profile">
          @if (auth.profile()?.avatar_url) {
            <img [src]="auth.profile()?.avatar_url" alt="" />
          } @else {
            <span class="avatar-fallback">{{ initial() }}</span>
          }
          <div class="operator-copy">
            <strong>{{ auth.profile()?.display_name || auth.profile()?.login || 'Operator' }}</strong>
            <small>{{ authSourceLabel() }}</small>
          </div>
          <span class="profile-arrow">→</span>
        </a>
      </aside>

      <section class="stage">
        <header class="topbar">
          <div class="title-block">
            <button type="button" class="menu-button"
                    (click)="mobileMenu.set(!mobileMenu())"
                    aria-label="Open navigation">☰</button>
            <div>
              <div class="breadcrumb"><span>SHIELDNET</span><b>/</b><span>COMMAND</span></div>
              <h1>{{ title }}</h1>
            </div>
          </div>

          <div class="top-actions">
            <button type="button" class="icon-action desktop-collapse"
                    (click)="toggleMenuCollapsed()"
                    [attr.aria-label]="menuCollapsed() ? 'Expand navigation' : 'Collapse navigation'">
              {{ menuCollapsed() ? '»' : '«' }}
            </button>
            <button type="button" class="appearance-button"
                    (click)="themes.cycleAppearanceMode()"
                    [attr.aria-label]="'Appearance: ' + themes.appearanceMode()">
              <span>{{ appearanceIcon() }}</span><b>{{ themes.appearanceMode().toUpperCase() }}</b>
            </button>
            <button type="button" class="command-button"
                    (click)="openPalette()"
                    [attr.aria-label]="'palette.open' | snT:'Open command palette'">
              <span>⌘</span><b>Ctrl K</b>
            </button>
            <div class="health-chip" [class.offline]="eventBus.state() === 'offline'"><span></span>{{ eventBus.state() === 'online' ? ("shell.system_nominal" | snT:"SYSTEM NOMINAL") : ("shell.connecting" | snT:"CONNECTING") }}</div>
            <div class="clock"><small>{{ "shell.secure_console" | snT:"SECURE CONSOLE" }}</small><strong>{{ currentTime() }}</strong></div>
          </div>
        </header>

        <main class="viewport"><ng-content /></main>
      </section>


      @if (paletteOpen()) {
        <div class="palette-layer" (click)="closePalette()">
          <section class="command-palette" role="dialog" aria-modal="true"
                   [attr.aria-label]="'palette.title' | snT:'Command Palette'"
                   (click)="$event.stopPropagation()">
            <header>
              <div>
                <strong>{{ "palette.title" | snT:"Command Palette" }}</strong>
                <small>{{ "palette.hint" | snT:"Press Ctrl+K anywhere" }}</small>
              </div>
              <button type="button" (click)="closePalette()"
                      [attr.aria-label]="'palette.close' | snT:'Close'">Esc</button>
            </header>

            <label class="palette-search">
              <span>⌕</span>
              <input #paletteInput
                     [value]="paletteQuery()"
                     (input)="paletteQuery.set($any($event.target).value)"
                     (keydown.enter)="runFirstCommand()"
                     [placeholder]="'palette.placeholder' | snT:'Search commands, pages and actions…'" />
            </label>

            <div class="command-list">
              @for (command of filteredCommands(); track command.id) {
                <button type="button" (click)="runCommand(command)">
                  <span class="command-icon">{{ command.icon }}</span>
                  <span>
                    <strong>{{ command.label | snT:command.fallback }}</strong>
                    <small>{{ "palette.navigate" | snT:"Navigate" }}</small>
                  </span>
                  <kbd>↵</kbd>
                </button>
              } @empty {
                <div class="palette-empty">{{ "palette.empty" | snT:"No matching commands" }}</div>
              }
            </div>
          </section>
        </div>
      }

      @if (mobileMenu()) {
        <button type="button" class="scrim" aria-label="Close navigation"
                (click)="mobileMenu.set(false)"></button>
      }
    </div>
  `,
  styles: [`
    .workspace{min-height:100vh;display:grid;grid-template-columns:276px minmax(0,1fr);transition:grid-template-columns .2s ease}
    .workspace.menu-collapsed{grid-template-columns:86px minmax(0,1fr)}
    .rail{position:sticky;top:0;height:100vh;z-index:30;display:flex;flex-direction:column;padding:1rem;overflow:auto;background:linear-gradient(180deg,rgba(16,29,38,.96),rgba(6,10,16,.98)),#080d14;border-right:1px solid var(--line)}
    .brand{min-height:68px;display:flex;align-items:center;gap:.85rem;padding:.7rem .75rem;border-bottom:1px solid var(--line)}
    .brand-symbol{position:relative;width:38px;height:38px;display:grid;place-items:center;border:1px solid rgba(53,226,178,.34);border-radius:10px;transform:rotate(45deg);background:rgba(53,226,178,.07)}
    .brand-symbol span{position:absolute;height:2px;border-radius:9px;background:var(--primary);box-shadow:0 0 8px rgba(53,226,178,.65);transform:rotate(-45deg)}
    .brand-symbol span:nth-child(1){width:18px;transform:translateY(-6px) rotate(-45deg)}
    .brand-symbol span:nth-child(2){width:24px}.brand-symbol span:nth-child(3){width:12px;transform:translateY(6px) rotate(-45deg)}
    .brand-copy{display:grid;gap:.1rem}.brand-copy strong{font-size:.92rem;letter-spacing:.14em}.brand-copy small{font-size:.58rem;letter-spacing:.18em;color:var(--muted)}
    .rail-state{margin:1rem .35rem .5rem;padding:.75rem;display:grid;grid-template-columns:auto 1fr;align-items:center;gap:.65rem;border:1px solid rgba(53,226,178,.14);border-radius:10px;background:rgba(53,226,178,.035)}
    .pulse{width:.52rem;height:.52rem;border-radius:50%;background:var(--primary);box-shadow:0 0 0 5px rgba(53,226,178,.07),0 0 14px rgba(53,226,178,.7)}
    .rail-state div{display:grid;gap:.15rem}.rail-state strong{font-size:.65rem;letter-spacing:.12em}.rail-state small{font-size:.62rem;color:var(--muted)}
    nav{display:grid;gap:1.15rem;margin-top:.65rem}.nav-group{display:grid;gap:.25rem}
    .nav-label{margin:.6rem .75rem .35rem;color:#577083;font-size:.59rem;font-weight:900;letter-spacing:.16em;text-transform:uppercase}
    nav a{min-height:43px;display:grid;grid-template-columns:28px 1fr;align-items:center;gap:.6rem;padding:.55rem .75rem;color:#8496a4;border:1px solid transparent;border-radius:9px;font-size:.82rem;font-weight:650}
    nav a:hover{color:var(--text);background:rgba(255,255,255,.025)}
    nav a.active{color:#dffff5;background:linear-gradient(90deg,rgba(53,226,178,.11),rgba(53,226,178,.025));border-color:rgba(53,226,178,.16);box-shadow:inset 3px 0 var(--primary)}
    .nav-icon{width:28px;height:28px;display:grid;place-items:center;color:#75a99d;border:1px solid rgba(126,160,166,.13);border-radius:7px;font-size:.78rem}
    nav a.active .nav-icon{color:var(--primary);border-color:rgba(53,226,178,.22);background:rgba(53,226,178,.06)}
    .operator{margin-top:auto;display:grid;grid-template-columns:auto 1fr auto;gap:.65rem;align-items:center;padding:.75rem;border-top:1px solid var(--line)}
    .operator img,.avatar-fallback{width:34px;height:34px;border-radius:9px;object-fit:cover}.avatar-fallback{display:grid;place-items:center;color:#04130f;background:var(--primary);font-weight:900}
    .operator-copy{min-width:0;display:grid;gap:.12rem}.operator-copy strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.76rem}.operator-copy small{color:var(--muted);font-size:.59rem}
    .profile-arrow{width:32px;height:32px;display:grid;place-items:center;color:var(--muted);background:transparent;border:1px solid var(--line);border-radius:8px}.operator:hover .profile-arrow{color:var(--primary);border-color:var(--line-strong)}
    .stage{min-width:0}.topbar{min-height:86px;position:sticky;top:0;z-index:20;display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:1rem 1.5rem;background:rgba(5,8,13,.78);border-bottom:1px solid var(--line);backdrop-filter:blur(22px)}
    .title-block{display:flex;align-items:center;gap:.75rem}.breadcrumb{display:flex;gap:.4rem;color:#557083;font-size:.58rem;font-weight:850;letter-spacing:.16em}.breadcrumb b{color:var(--primary)}h1{margin:.28rem 0 0;font-size:1.28rem}
    .menu-button{display:none;width:40px;height:40px;color:var(--text);background:var(--panel);border:1px solid var(--line);border-radius:9px}
    .top-actions{display:flex;align-items:center;gap:.75rem}
    .command-button{height:35px;display:flex;align-items:center;gap:.45rem;padding:0 .65rem;color:#9fb3c1;background:rgba(255,255,255,.025);border:1px solid var(--line);border-radius:9px;cursor:pointer}
    .command-button:hover{color:var(--primary);border-color:rgba(53,226,178,.28)}
    .command-button span{font-size:.78rem}.command-button b{font-size:.58rem;letter-spacing:.08em}.health-chip{min-height:35px;display:flex;align-items:center;gap:.5rem;padding:0 .75rem;color:#a7c8bd;border:1px solid rgba(53,226,178,.18);border-radius:999px;background:rgba(53,226,178,.045);font-size:.62rem;font-weight:850;letter-spacing:.1em}
    .health-chip span{width:.45rem;height:.45rem;border-radius:50%;background:var(--success);box-shadow:0 0 12px rgba(57,221,161,.75)}
    .clock{min-width:118px;display:grid;justify-items:end;gap:.1rem}.clock small{color:#587081;font-size:.55rem;letter-spacing:.12em}.clock strong{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.78rem}
    .viewport{min-width:0;padding:1.35rem 1.5rem 2.5rem}.scrim{display:none}
    .palette-layer{position:fixed;inset:0;z-index:100;display:grid;place-items:start center;padding-top:min(16vh,9rem);background:rgba(1,4,8,.76);backdrop-filter:blur(12px)}
    .command-palette{width:min(680px,calc(100vw - 2rem));max-height:min(70vh,620px);overflow:hidden;background:linear-gradient(180deg,rgba(18,29,39,.98),rgba(7,11,18,.99));border:1px solid rgba(53,226,178,.24);border-radius:18px;box-shadow:0 28px 90px rgba(0,0,0,.55)}
    .command-palette header{display:flex;align-items:center;justify-content:space-between;padding:1rem 1.1rem;border-bottom:1px solid var(--line)}
    .command-palette header div{display:grid;gap:.15rem}.command-palette header strong{font-size:.95rem}.command-palette header small{color:var(--muted);font-size:.65rem}
    .command-palette header button{padding:.35rem .5rem;color:var(--muted);background:rgba(255,255,255,.04);border:1px solid var(--line);border-radius:7px;cursor:pointer}
    .palette-search{display:grid;grid-template-columns:auto 1fr;align-items:center;gap:.65rem;margin:1rem;padding:.8rem 1rem;border:1px solid var(--line);border-radius:11px;background:rgba(0,0,0,.22)}
    .palette-search span{color:var(--primary)}.palette-search input{width:100%;color:var(--text);background:transparent;border:0;outline:0;font:inherit}
    .command-list{max-height:430px;overflow:auto;padding:0 .7rem .8rem}
    .command-list>button{width:100%;display:grid;grid-template-columns:36px 1fr auto;align-items:center;gap:.7rem;padding:.7rem;color:var(--text);background:transparent;border:1px solid transparent;border-radius:10px;text-align:left;cursor:pointer}
    .command-list>button:hover{background:rgba(53,226,178,.07);border-color:rgba(53,226,178,.14)}
    .command-icon{width:34px;height:34px;display:grid;place-items:center;color:var(--primary);background:rgba(53,226,178,.07);border:1px solid rgba(53,226,178,.14);border-radius:8px}
    .command-list>button>span:nth-child(2){display:grid;gap:.12rem}.command-list strong{font-size:.78rem}.command-list small{color:var(--muted);font-size:.61rem}
    .command-list kbd{color:#738895;background:rgba(255,255,255,.04);border:1px solid var(--line);border-radius:6px;padding:.18rem .35rem}
    .palette-empty{padding:2rem;text-align:center;color:var(--muted)}
    @media(max-width:1000px){.workspace,.workspace.menu-collapsed{grid-template-columns:1fr}.desktop-collapse{display:none}.rail{position:fixed;left:0;transform:translateX(-102%);width:min(290px,88vw);transition:transform .22s ease}.menu-open .rail{transform:translateX(0)}.menu-button{display:grid;place-items:center}.scrim{display:block;position:fixed;inset:0;z-index:25;background:rgba(0,0,0,.6);backdrop-filter:blur(3px)}}
    @media(max-width:680px){.topbar{min-height:74px;padding:.8rem 1rem}.viewport{padding:1rem}.health-chip,.clock small,.command-button b{display:none}.clock{min-width:auto}.breadcrumb{display:none}h1{margin:0;font-size:1.05rem}}
  `],
})
export class ShellComponent implements OnInit, OnDestroy {
  @Input({ required: true }) title = '';

  readonly mobileMenu = signal(false);
  readonly menuCollapsed = signal(localStorage.getItem('shieldnet_menu_collapsed') === '1');
  readonly paletteOpen = signal(false);
  readonly paletteQuery = signal('');
  readonly installedPlugins = signal<GuildPluginInstallation[]>([]);
  readonly currentTime = signal('');
  readonly appearanceIcon = computed(() => ({ auto: '◐', dark: '●', light: '○' }[this.themes.appearanceMode()]));
  readonly isPlatformContext = computed(() => Boolean(this.auth.profile()?.platform_context));
  readonly hasPlatformOperations = this.isPlatformContext;
  readonly homeLink = computed(() => this.isPlatformContext() ? '/platform' : (this.guildId() ? `/guild/${this.guildId()}` : '/servers'));
  readonly authSourceLabel = computed(() => {
    const source = this.auth.profile()?.auth_source;
    if (source === 'local_platform') return 'Local platform';
    if (source === 'discord_platform') return 'Discord platform';
    if (source === 'discord_guild') return 'Discord guild';
    return 'Authenticated operator';
  });
  private timerId: ReturnType<typeof setInterval> | null = null;


  readonly paletteCommands = computed<PaletteCommand[]>(() => {
    const id = this.guildId();
    const commands: PaletteCommand[] = [
      { id: 'home', label: 'palette.dashboard', fallback: 'Open Control Center', icon: '⌂', path: this.homeLink() },
      { id: 'servers', label: 'shell.servers', fallback: 'Open Server Selector', icon: '◫', path: '/servers' },
      { id: 'profile', label: 'palette.profile', fallback: 'Open Profile', icon: '◉', path: '/profile' },
    ];

    if (this.isPlatformContext()) {
      commands.push(
        { id: 'plugins', label: 'palette.plugins', fallback: 'Open Plugin Platform', icon: '⬡', path: '/platform/plugins' },
        { id: 'jobs', label: 'palette.jobs', fallback: 'Open Jobs Center', icon: '⌁', path: '/platform/jobs' },
        { id: 'doctor', label: 'palette.doctor', fallback: 'Run Platform Doctor', icon: '✚', path: '/platform/doctor' },
      );
      commands.push(
        { id: 'operations', label: 'palette.operations', fallback: 'Open Live Operations', icon: '◎', path: '/platform/operations' },
        { id: 'health', label: 'palette.health', fallback: 'Open Health Monitor', icon: '✚', path: '/platform/health' },
        { id: 'logs', label: 'palette.logs', fallback: 'Open Live Logs', icon: '≡', path: '/platform/logs' },
        { id: 'notifications', label: 'palette.notifications', fallback: 'Open Notification Center', icon: '◌', path: '/platform/notifications' },
      );
    }

    if (id) {
      commands.push(
        { id: 'members', label: 'palette.members', fallback: 'Open Members', icon: '◉', path: ['/guild', id, 'members'], guildOnly: true },
        { id: 'security', label: 'palette.security', fallback: 'Open Security Center', icon: '◇', path: ['/guild', id, 'security'], guildOnly: true },
        { id: 'runtime', label: 'palette.runtime', fallback: 'Open Plugin Runtime', icon: '⬢', path: ['/guild', id, 'plugin-runtime'], guildOnly: true },
        { id: 'audit', label: 'palette.audit', fallback: 'Open Audit Trail', icon: '≡', path: ['/guild', id, 'audit'], guildOnly: true },
        { id: 'control', label: 'palette.control', fallback: 'Open Server Control', icon: '⌬', path: ['/guild', id, 'control'], guildOnly: true },
        { id: 'backups', label: 'palette.backups', fallback: 'Open Backup Center', icon: '▣', path: ['/guild', id, 'backups'], guildOnly: true },
        { id: 'automations', label: 'palette.automations', fallback: 'Open Automations', icon: '⌘', path: ['/guild', id, 'automations'], guildOnly: true },
        { id: 'scheduler', label: 'palette.scheduler', fallback: 'Open Workflow Scheduler', icon: '◷', path: ['/guild', id, 'workflow-scheduler'], guildOnly: true },
        { id: 'monitor', label: 'palette.monitor', fallback: 'Open Automation Monitor', icon: '◈', path: ['/guild', id, 'automation-monitor'], guildOnly: true },
        { id: 'explorer', label: 'palette.explorer', fallback: 'Open Discord Explorer', icon: '⌕', path: ['/guild', id, 'explorer'], guildOnly: true },
        { id: 'permissions', label: 'palette.permissions', fallback: 'Open Permission Simulator', icon: '⚿', path: ['/guild', id, 'permission-simulator'], guildOnly: true },
      );
    }

    return commands;
  });

  readonly filteredCommands = computed(() => {
    const query = this.paletteQuery().trim().toLowerCase();
    if (!query) return this.paletteCommands();
    return this.paletteCommands().filter((command) =>
      `${command.id} ${command.label} ${command.fallback}`.toLowerCase().includes(query),
    );
  });

  readonly guildId = computed(() => {
    let route: ActivatedRoute | null = this.route;
    while (route) {
      const value = route.snapshot.paramMap.get('guildId');
      if (value) return value;
      route = route.parent;
    }
    return null;
  });

  readonly coreNavigation = computed<NavItem[]>(() => {
    const id = this.guildId();
    if (!id) return [];
    return [
      { label: 'shell.overview', icon: '◫', path: ['/guild', id], exact: true },
      { label: 'shell.members', icon: '◉', path: ['/guild', id, 'members'] },
      { label: 'shell.security', icon: '◇', path: ['/guild', id, 'security'] },
      { label: 'shell.plugin_runtime', icon: '⬢', path: ['/guild', id, 'plugin-runtime'] },
      { label: 'shell.audit_trail', icon: '≡', path: ['/guild', id, 'audit'] },
      { label: 'shell.server_control', icon: '⌬', path: ['/guild', id, 'control'] },
    ];
  });

  private readonly pluginNavDefinitions: PluginNavDefinition[] = [
    { keys: ['welcome'], label: 'Welcome', icon: '👋', path: 'welcome' },
    { keys: ['verification'], label: 'Verification', icon: '✓', path: 'verification' },
    { keys: ['leadership', 'r5_r4', 'r5-r4'], label: 'Leadership', icon: '★', path: 'leadership' },
    { keys: ['moderation'], label: 'Moderation', icon: '⚖', path: 'moderation' },
    { keys: ['translator', 'translation'], label: 'Translator', icon: '◎', path: 'translator' },
    { keys: ['automations', 'automation'], label: 'Automations', icon: '⌘', path: 'automations' },
    { keys: ['reaction_roles', 'reaction-roles', 'reactionroles'], label: 'Reaction Roles', icon: '◈', path: 'reaction-roles' },
    { keys: ['tickets', 'ticketing'], label: 'Tickets', icon: '▣', path: 'tickets' },
    { keys: ['logging', 'logs'], label: 'Logging', icon: '≡', path: 'logging' },
  ];

  readonly pluginNavigation = computed<NavItem[]>(() => {
    const id = this.guildId();
    if (!id) return [];

    const installedKeys = new Set(
      this.installedPlugins().map((plugin) => this.normalize(plugin.plugin_key)),
    );

    return this.pluginNavDefinitions
      .filter((definition) =>
        definition.keys.some((key) => installedKeys.has(this.normalize(key))),
      )
      .map((definition) => ({
        label: definition.label,
        icon: definition.icon,
        path: ['/guild', id, definition.path],
      }));
  });

  readonly initial = computed(
    () => (this.auth.profile()?.display_name || this.auth.profile()?.login || 'O')
      .slice(0, 1).toUpperCase(),
  );

  constructor(
    public readonly auth: AuthService,
    private readonly route: ActivatedRoute,
    private readonly guildPluginService: GuildPluginService,
    private readonly router: Router,
    public readonly themes: ThemeService,
    public readonly eventBus: EventBusService,
  ) {}


  @HostListener('document:keydown', ['$event'])
  handleKeyboard(event: KeyboardEvent): void {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      this.paletteOpen() ? this.closePalette() : this.openPalette();
      return;
    }
    if (event.key === 'Escape' && this.paletteOpen()) {
      event.preventDefault();
      this.closePalette();
    }
  }

  toggleMenuCollapsed(): void {
    const next = !this.menuCollapsed();
    this.menuCollapsed.set(next);
    localStorage.setItem('shieldnet_menu_collapsed', next ? '1' : '0');
  }

  openPalette(): void {
    this.paletteQuery.set('');
    this.paletteOpen.set(true);
    setTimeout(() => {
      const input = document.querySelector<HTMLInputElement>('.palette-search input');
      input?.focus();
    });
  }

  closePalette(): void {
    this.paletteOpen.set(false);
    this.paletteQuery.set('');
  }

  runCommand(command: PaletteCommand): void {
    this.closePalette();
    void this.router.navigate(Array.isArray(command.path) ? command.path : [command.path]);
  }

  runFirstCommand(): void {
    const command = this.filteredCommands()[0];
    if (command) this.runCommand(command);
  }

  ngOnInit(): void {
    this.eventBus.connect();
    this.updateTime();
    this.timerId = setInterval(() => this.updateTime(), 1000);

    const id = this.guildId();
    if (id) {
      void this.guildPluginService.listInstalled(id)
        .then((items) => this.installedPlugins.set(items))
        .catch(() => this.installedPlugins.set([]));
    }
  }

  ngOnDestroy(): void {
    if (this.timerId) clearInterval(this.timerId);
  }

  private updateTime(): void {
    this.currentTime.set(
      new Intl.DateTimeFormat(undefined, {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      }).format(new Date()),
    );
  }

  private normalize(value: string): string {
    return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_');
  }
}
