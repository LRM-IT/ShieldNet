import { Component, Input, OnDestroy, OnInit, computed, signal } from '@angular/core';
import { ActivatedRoute, RouterLink, RouterLinkActive } from '@angular/router';

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

interface PluginNavDefinition {
  keys: string[];
  label: string;
  icon: string;
  path: string;
}

@Component({
  selector: 'sn-shell',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  template: `
    <div class="workspace" [class.menu-open]="mobileMenu()">
      <aside class="rail">
        <a routerLink="/" class="brand" aria-label="ShieldNet home">
          <span class="brand-symbol"><span></span><span></span><span></span></span>
          <span class="brand-copy">
            <strong>SHIELDNET</strong>
            <small>CONTROL FABRIC</small>
          </span>
        </a>

        <div class="rail-state">
          <span class="pulse"></span>
          <div>
            <strong>CONTROL PLANE</strong>
            <small>Encrypted session active</small>
          </div>
        </div>

        <nav aria-label="Main navigation">
          <div class="nav-group">
            <div class="nav-label">Workspace</div>
            <a routerLink="/" routerLinkActive="active"
               [routerLinkActiveOptions]="{ exact: true }">
              <span class="nav-icon">⌂</span><span>Servers</span>
            </a>
            <a routerLink="/platform/plugins" routerLinkActive="active">
              <span class="nav-icon">⬡</span><span>Plugin fabric</span>
            </a>
            <a routerLink="/platform/jobs" routerLinkActive="active">
              <span class="nav-icon">⌁</span><span>Jobs center</span>
            </a>
            <a routerLink="/platform/operations" routerLinkActive="active">
              <span class="nav-icon">◎</span><span>Operations</span>
            </a>
          </div>

          @if (guildId()) {
            <div class="nav-group">
              <div class="nav-label">Core server</div>
              @for (item of coreNavigation(); track item.label) {
                <a [routerLink]="item.path" routerLinkActive="active"
                   [routerLinkActiveOptions]="{ exact: !!item.exact }">
                  <span class="nav-icon">{{ item.icon }}</span>
                  <span>{{ item.label }}</span>
                </a>
              }
            </div>

            @if (pluginNavigation().length > 0) {
              <div class="nav-group">
                <div class="nav-label">Installed plugins</div>
                @for (item of pluginNavigation(); track item.label) {
                  <a [routerLink]="item.path" routerLinkActive="active">
                    <span class="nav-icon">{{ item.icon }}</span>
                    <span>{{ item.label }}</span>
                  </a>
                }
              </div>
            }
          }
        </nav>

        <div class="operator">
          @if (auth.profile()?.avatar_url) {
            <img [src]="auth.profile()?.avatar_url" alt="" />
          } @else {
            <span class="avatar-fallback">{{ initial() }}</span>
          }
          <div class="operator-copy">
            <strong>{{ auth.profile()?.display_name || auth.profile()?.login || 'Operator' }}</strong>
            <small>Authenticated operator</small>
          </div>
          <button type="button" class="sign-out" (click)="auth.logout()" title="Sign out">↗</button>
        </div>
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
            <div class="health-chip"><span></span>SYSTEM NOMINAL</div>
            <div class="clock"><small>SECURE CONSOLE</small><strong>{{ currentTime() }}</strong></div>
          </div>
        </header>

        <main class="viewport"><ng-content /></main>
      </section>

      @if (mobileMenu()) {
        <button type="button" class="scrim" aria-label="Close navigation"
                (click)="mobileMenu.set(false)"></button>
      }
    </div>
  `,
  styles: [`
    .workspace{min-height:100vh;display:grid;grid-template-columns:276px minmax(0,1fr)}
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
    .sign-out{width:32px;height:32px;color:var(--muted);background:transparent;border:1px solid var(--line);border-radius:8px}
    .stage{min-width:0}.topbar{min-height:86px;position:sticky;top:0;z-index:20;display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:1rem 1.5rem;background:rgba(5,8,13,.78);border-bottom:1px solid var(--line);backdrop-filter:blur(22px)}
    .title-block{display:flex;align-items:center;gap:.75rem}.breadcrumb{display:flex;gap:.4rem;color:#557083;font-size:.58rem;font-weight:850;letter-spacing:.16em}.breadcrumb b{color:var(--primary)}h1{margin:.28rem 0 0;font-size:1.28rem}
    .menu-button{display:none;width:40px;height:40px;color:var(--text);background:var(--panel);border:1px solid var(--line);border-radius:9px}
    .top-actions{display:flex;align-items:center;gap:.75rem}.health-chip{min-height:35px;display:flex;align-items:center;gap:.5rem;padding:0 .75rem;color:#a7c8bd;border:1px solid rgba(53,226,178,.18);border-radius:999px;background:rgba(53,226,178,.045);font-size:.62rem;font-weight:850;letter-spacing:.1em}
    .health-chip span{width:.45rem;height:.45rem;border-radius:50%;background:var(--success);box-shadow:0 0 12px rgba(57,221,161,.75)}
    .clock{min-width:118px;display:grid;justify-items:end;gap:.1rem}.clock small{color:#587081;font-size:.55rem;letter-spacing:.12em}.clock strong{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.78rem}
    .viewport{min-width:0;padding:1.35rem 1.5rem 2.5rem}.scrim{display:none}
    @media(max-width:1000px){.workspace{grid-template-columns:1fr}.rail{position:fixed;left:0;transform:translateX(-102%);width:min(290px,88vw);transition:transform .22s ease}.menu-open .rail{transform:translateX(0)}.menu-button{display:grid;place-items:center}.scrim{display:block;position:fixed;inset:0;z-index:25;background:rgba(0,0,0,.6);backdrop-filter:blur(3px)}}
    @media(max-width:680px){.topbar{min-height:74px;padding:.8rem 1rem}.viewport{padding:1rem}.health-chip,.clock small{display:none}.clock{min-width:auto}.breadcrumb{display:none}h1{margin:0;font-size:1.05rem}}
  `],
})
export class ShellComponent implements OnInit, OnDestroy {
  @Input({ required: true }) title = '';

  readonly mobileMenu = signal(false);
  readonly installedPlugins = signal<GuildPluginInstallation[]>([]);
  readonly currentTime = signal('');
  private timerId: ReturnType<typeof setInterval> | null = null;

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
      { label: 'Overview', icon: '◫', path: ['/guild', id], exact: true },
      { label: 'Members', icon: '◉', path: ['/guild', id, 'members'] },
      { label: 'Security', icon: '◇', path: ['/guild', id, 'security'] },
      { label: 'Plugin runtime', icon: '⬢', path: ['/guild', id, 'plugin-runtime'] },
      { label: 'Audit trail', icon: '≡', path: ['/guild', id, 'audit'] },
      { label: 'Server control', icon: '⌬', path: ['/guild', id, 'control'] },
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
  ) {}

  ngOnInit(): void {
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
