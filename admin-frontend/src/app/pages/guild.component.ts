import { Component, OnInit, computed, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { GuildAccess } from '../core/api.models';
import { GuildService } from '../core/guild.service';
import { GuildModule } from '../core/module.models';
import { ModuleService } from '../core/module.service';
import { ShellComponent } from '../shared/shell.component';

interface QuickAction {
  title: string;
  description: string;
  icon: string;
  path: string;
}

@Component({
  standalone: true,
  imports: [ShellComponent, RouterLink],
  template: `
    <sn-shell [title]="guild()?.name || 'Server'">
      @if (error()) {
        <div class="error card">{{ error() }}</div>
      } @else if (guild(); as item) {
        <div class="page-actions">
          <div>
            <h2>Server management</h2>
            <p class="muted">Configure Discord, users, security and ShieldNet modules.</p>
          </div>
          <div class="top-buttons">
            <a class="button secondary" [routerLink]="['/guild', guildId, 'explorer']">Open Discord Explorer</a>
            <a class="button" [routerLink]="['/guild', guildId, 'control']">Server control</a>
          </div>
        </div>

        <div class="summary-grid">
          <div class="metric card"><span class="muted">Bot status</span><strong>{{ item.bot_status }}</strong><div class="status">● Connected</div></div>
          <div class="metric card"><span class="muted">Members</span><strong>{{ item.member_count }}</strong><a [routerLink]="['/guild', guildId, 'members']">Open members</a></div>
          <div class="metric card"><span class="muted">Your access</span><strong>{{ item.access_role }}</strong><a [routerLink]="['/guild', guildId, 'permissions']">View permissions</a></div>
          <div class="metric card"><span class="muted">Modules enabled</span><strong>{{ enabledCount() }}/{{ modules().length }}</strong><a href="#modules">Manage modules</a></div>
        </div>

        <section class="quick-section">
          <div class="section-heading"><div><h2>Quick access</h2><p class="muted">Main administration pages for this server.</p></div></div>
          <div class="quick-grid">
            @for (action of quickActions; track action.path) {
              <a class="quick-card card" [routerLink]="['/guild', guildId, action.path]">
                <span class="quick-icon">{{ action.icon }}</span>
                <span><strong>{{ action.title }}</strong><small class="muted">{{ action.description }}</small></span>
                <b>Open →</b>
              </a>
            }
          </div>
        </section>

        <div id="modules" class="module-header">
          <div><h2>Modules</h2><p class="muted">Enable a module and open its management page.</p></div>
          @if (savingKey()) { <div class="muted">Saving changes…</div> }
        </div>

        @if (loading()) {
          <div class="loading card">Loading modules…</div>
        } @else {
          <div class="module-grid">
            @for (module of modules(); track module.module_key) {
              <article class="module card" [class.enabled]="module.enabled">
                <div class="module-icon">{{ module.icon || '◈' }}</div>
                <div class="module-content">
                  <div class="module-title">
                    <h3>{{ module.name }}</h3>
                    @if (module.is_core) { <span class="badge core">Core</span> }
                    @else if (module.enabled) { <span class="badge enabled-badge">Enabled</span> }
                    @else { <span class="badge">Disabled</span> }
                  </div>
                  <p class="muted">{{ module.description }}</p>
                  <div class="module-meta"><span>v{{ module.version }}</span><span>Revision {{ module.revision }}</span></div>
                </div>
                <div class="module-actions">
                  @if (modulePath(module.module_key); as path) {
                    <a class="button compact" [class.disabled-link]="!module.enabled && !module.is_core" [routerLink]="['/guild', guildId, path]">Open</a>
                  }
                  <button class="toggle" [class.on]="module.enabled" [disabled]="module.is_core || savingKey() === module.module_key" (click)="toggle(module)" [attr.aria-label]="'Toggle ' + module.name"><span></span></button>
                </div>
              </article>
            }
          </div>
        }
      } @else if (loading()) {
        <div class="card loading">Loading server…</div>
      } @else {
        <div class="error card">Server was not found or access was revoked.</div>
      }
    </sn-shell>
  `,
  styles: [`
    .page-actions,.section-heading,.module-header{display:flex;justify-content:space-between;align-items:end;gap:1rem;margin-bottom:1rem}.page-actions h2,.page-actions p,.section-heading h2,.section-heading p,.module-header h2,.module-header p{margin:0}.page-actions p,.section-heading p,.module-header p{margin-top:.35rem}.top-buttons{display:flex;gap:.65rem;flex-wrap:wrap}.button{display:inline-flex;align-items:center;justify-content:center;padding:.7rem 1rem;border-radius:11px;background:var(--primary);color:#fff;font-weight:750;border:1px solid transparent}.button.secondary{background:var(--primary-soft);border-color:var(--line)}.button.compact{padding:.5rem .78rem;font-size:.8rem}.button.disabled-link{opacity:.45;pointer-events:none}.summary-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1rem}.metric{padding:1.2rem;display:grid;gap:.45rem}.metric strong{font-size:1.55rem;text-transform:capitalize}.metric a{font-size:.78rem;color:#aeb7ff}.status{color:var(--success);font-size:.8rem}.quick-section{margin-top:2rem}.quick-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.8rem}.quick-card{padding:1rem;display:grid;grid-template-columns:auto 1fr auto;gap:.8rem;align-items:center;transition:.2s}.quick-card:hover{transform:translateY(-2px);border-color:rgba(122,133,255,.5)}.quick-card strong,.quick-card small{display:block}.quick-card small{margin-top:.25rem}.quick-card b{font-size:.78rem;color:#aeb7ff}.quick-icon{width:2.6rem;height:2.6rem;border-radius:12px;background:var(--primary-soft);display:grid;place-items:center}.module-header{margin-top:2rem}.module-grid{display:grid;gap:.8rem}.module{padding:1rem;display:grid;grid-template-columns:auto 1fr auto;gap:1rem;align-items:center;transition:.2s}.module.enabled{border-color:rgba(75,214,155,.45)}.module:hover{transform:translateY(-1px)}.module-icon{width:3rem;height:3rem;border-radius:14px;display:grid;place-items:center;background:var(--primary-soft);font-size:1.25rem}.module-title{display:flex;align-items:center;gap:.65rem;flex-wrap:wrap}.module h3{margin:0}.module p{margin:.35rem 0 0}.module-meta{margin-top:.65rem;display:flex;gap:.8rem;color:var(--muted);font-size:.75rem}.module-actions{display:flex;align-items:center;gap:.65rem}.badge{padding:.22rem .52rem;border-radius:999px;border:1px solid var(--line);color:var(--muted);font-size:.7rem;font-weight:800;text-transform:uppercase}.badge.core{color:#cfd5ff;background:var(--primary-soft)}.badge.enabled-badge{color:#b9f4dc;background:rgba(75,214,155,.12);border-color:rgba(75,214,155,.35)}.toggle{width:3.1rem;height:1.75rem;padding:.2rem;border-radius:999px;background:#2a344b}.toggle span{display:block;width:1.35rem;height:1.35rem;border-radius:50%;background:white;transition:.2s}.toggle.on{background:var(--success)}.toggle.on span{transform:translateX(1.35rem)}.loading,.error{padding:1.3rem}.error{color:#ffd9de;border-color:rgba(255,107,125,.4)}
    @media(max-width:1100px){.summary-grid{grid-template-columns:repeat(2,1fr)}.quick-grid{grid-template-columns:repeat(2,1fr)}}
    @media(max-width:700px){.page-actions,.module-header{align-items:stretch;flex-direction:column}.top-buttons{display:grid}.summary-grid,.quick-grid{grid-template-columns:1fr}.module{grid-template-columns:auto 1fr}.module-actions{grid-column:1/-1;justify-content:flex-end}}
  `],
})
export class GuildComponent implements OnInit {
  readonly guilds = signal<GuildAccess[]>([]);
  readonly modules = signal<GuildModule[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly savingKey = signal('');

  readonly guildId = this.route.snapshot.paramMap.get('guildId') ?? '';
  readonly guild = computed(() => this.guilds().find((item) => item.guild_id === this.guildId) || null);
  readonly enabledCount = computed(() => this.modules().filter((m) => m.enabled).length);

  readonly quickActions: QuickAction[] = [
    { title: 'Members', description: 'Profiles, roles and member actions', icon: '👥', path: 'members' },
    { title: 'Verification', description: 'Verification requests and decisions', icon: '✅', path: 'verification' },
    { title: 'R5/R4 Applications', description: 'Leadership applications and role sync', icon: '⭐', path: 'leadership' },
    { title: 'Moderation', description: 'Warnings, cases, timeouts and bans', icon: '⚖️', path: 'moderation' },
    { title: 'Discord Explorer', description: 'Roles, channels and server structure', icon: '🧭', path: 'explorer' },
    { title: 'Automations', description: 'Designer, schedules and run monitor', icon: '⚙️', path: 'automations' },
    { title: 'Plugin Runtime', description: 'Usage, errors, limits and response time', icon: '◈', path: 'plugin-runtime' },
    { title: 'Security', description: 'Security checks and incident controls', icon: '🛡️', path: 'security' },
    { title: 'Backup Center', description: 'Create and restore configurations', icon: '💾', path: 'backups' },
    { title: 'Audit log', description: 'Review administrative activity', icon: '📋', path: 'audit' },
  ];

  constructor(private readonly route: ActivatedRoute, private readonly guildService: GuildService, private readonly moduleService: ModuleService) {}

  async ngOnInit(): Promise<void> {
    try {
      const [guilds, modules] = await Promise.all([
        this.guildService.list(),
        this.moduleService.list(this.guildId),
      ]);
      this.guilds.set(guilds);
      this.modules.set(modules);
    } catch {
      this.error.set('Unable to load server information and modules.');
    } finally {
      this.loading.set(false);
    }
  }

  async toggle(module: GuildModule): Promise<void> {
    if (module.is_core || this.savingKey()) return;
    this.savingKey.set(module.module_key);
    this.error.set('');
    try {
      const updated = await this.moduleService.update(this.guildId, module.module_key, !module.enabled, module.configuration);
      this.modules.update((items) => items.map((item) => item.module_key === updated.module_key ? updated : item));
    } catch {
      this.error.set(`Unable to update ${module.name}.`);
    } finally {
      this.savingKey.set('');
    }
  }

  modulePath(key: string): string | null {
    const map: Record<string, string> = {
      core: 'control', welcome: 'control', verification: 'verification', moderation: 'moderation', translator: 'control',
      security: 'security', automations: 'automations', automation: 'automations', plugin_runtime: 'plugin-runtime', runtime: 'plugin-runtime', plugins: 'plugin-runtime', members: 'members', leadership: 'leadership', audit: 'audit',
    };
    return map[key.toLowerCase()] || null;
  }
}
