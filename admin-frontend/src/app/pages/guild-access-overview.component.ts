import { Component, OnInit, computed, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { GuildAccess } from '../core/api.models';
import { GuildService } from '../core/guild.service';
import { ShellComponent } from '../shared/shell.component';

interface AccessModule {
  key: string;
  title: string;
  description: string;
  route: string;
}

@Component({
  standalone: true,
  imports: [ShellComponent, RouterLink],
  template: `
    <sn-shell [title]="guild()?.name || 'Guild access overview'">
      @if (loading()) {
        <div class="panel">Loading access profile…</div>
      } @else if (error()) {
        <div class="panel error">{{ error() }}</div>
      } @else if (guild(); as item) {
        <section class="hero">
          <div>
            <span>GUILD ACCESS PROFILE</span>
            <h2>{{ item.name }}</h2>
            <p>Current role, delegated permissions and available management modules.</p>
          </div>
          <a [routerLink]="['/guild', guildId]">Back to server</a>
        </section>

        <section class="facts">
          <article><span>ROLE</span><strong>{{ item.is_owner ? 'owner' : item.access_role }}</strong></article>
          <article><span>PERMISSIONS</span><strong>{{ fullAccess() ? 'FULL' : permissionCount() }}</strong></article>
          <article><span>ACCESS EXPIRES</span><strong>{{ expiryLabel() }}</strong></article>
          <article><span>SERVER STATUS</span><strong>{{ item.guild_status }}</strong></article>
        </section>

        @if (isExpired()) {
          <div class="warning">Delegated access has expired. Contact the server owner or platform administrator.</div>
        }

        <section class="title"><div><span>MODULE MATRIX</span><h3>Available management areas</h3></div></section>
        <section class="grid">
          @for (module of modules; track module.key) {
            <article [class.denied]="!allowed(module.key)">
              <div class="badge">{{ allowed(module.key) ? 'ALLOWED' : 'DENIED' }}</div>
              <h4>{{ module.title }}</h4>
              <p>{{ module.description }}</p>
              @if (allowed(module.key) && !isExpired()) {
                <a [routerLink]="['/guild', guildId, module.route]">Open module →</a>
              } @else {
                <span class="locked">Access unavailable</span>
              }
            </article>
          }
        </section>
      }
    </sn-shell>
  `,
  styles: [`
    .panel,.warning{padding:1.1rem;border:1px solid var(--line);border-radius:14px;background:var(--panel)}
    .error,.warning{color:#ffb4b4;border-color:rgba(255,100,100,.35)}
    .hero{display:flex;justify-content:space-between;gap:1rem;align-items:flex-start;padding:1rem 0 1.4rem}
    .hero span,.title span,.facts span{font-size:.66rem;font-weight:900;letter-spacing:.14em;color:var(--accent)}
    .hero h2,.title h3{margin:.35rem 0}.hero p{margin:0;color:var(--muted)}
    .hero a,.grid a{color:var(--accent);text-decoration:none;font-weight:800}
    .facts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.8rem;margin-bottom:1.2rem}
    .facts article,.grid article{padding:1rem;border:1px solid var(--line);border-radius:14px;background:var(--panel)}
    .facts article{display:grid;gap:.45rem}.facts strong{text-transform:uppercase}
    .title{padding:1.5rem 0 .8rem}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.8rem}
    .grid article{display:flex;min-height:170px;flex-direction:column}.grid article.denied{opacity:.58}
    .badge{align-self:flex-start;padding:.25rem .45rem;border-radius:999px;background:rgba(53,226,178,.12);color:var(--accent);font-size:.62rem;font-weight:900}
    .denied .badge{background:rgba(255,100,100,.1);color:#ff9f9f}.grid h4{margin:.8rem 0 .35rem}.grid p{margin:0 0 1rem;color:var(--muted);flex:1}
    .locked{color:var(--muted);font-size:.82rem;font-weight:700}
    @media(max-width:950px){.facts,.grid{grid-template-columns:1fr 1fr}}@media(max-width:620px){.hero{display:grid}.facts,.grid{grid-template-columns:1fr}}
  `],
})
export class GuildAccessOverviewComponent implements OnInit {
  readonly guildId: string;
  readonly loading = signal(true);
  readonly error = signal('');
  readonly guild = signal<GuildAccess | null>(null);

  readonly modules: AccessModule[] = [
    { key: 'members', title: 'Members', description: 'Member directory, identity inspection and operational actions.', route: 'members' },
    { key: 'verification', title: 'Verification', description: 'Verification workflow, review and approval controls.', route: 'verification' },
    { key: 'moderation', title: 'Moderation', description: 'Cases, evidence, sanctions and moderation operations.', route: 'moderation' },
    { key: 'security', title: 'Security', description: 'Security posture, alerts and protection configuration.', route: 'security' },
    { key: 'plugins', title: 'Plugins', description: 'Installed guild plugins and runtime controls.', route: 'plugin-runtime' },
    { key: 'automations', title: 'Automations', description: 'Automations, schedules and execution monitoring.', route: 'automations' },
    { key: 'audit', title: 'Audit', description: 'Guild audit trail and administrative activity.', route: 'audit' },
    { key: 'settings', title: 'Settings', description: 'Server control and guild configuration.', route: 'control' },
    { key: 'access', title: 'Access management', description: 'Delegated administrators and permission assignments.', route: 'access' },
  ];

  readonly fullAccess = computed(() => {
    const item = this.guild();
    return !!item && (item.is_owner === true || item.permissions?.includes('*') === true);
  });
  readonly permissionCount = computed(() => this.guild()?.permissions?.filter((p) => p !== '*').length ?? 0);
  readonly isExpired = computed(() => {
    const expires = this.guild()?.expires_at;
    return !!expires && new Date(expires).getTime() <= Date.now();
  });
  readonly expiryLabel = computed(() => {
    const expires = this.guild()?.expires_at;
    if (!expires) return 'NO LIMIT';
    const date = new Date(expires);
    return Number.isNaN(date.getTime()) ? 'UNKNOWN' : date.toLocaleString();
  });

  constructor(route: ActivatedRoute, private readonly guilds: GuildService) {
    this.guildId = route.snapshot.paramMap.get('guildId') ?? '';
  }

  async ngOnInit(): Promise<void> {
    try {
      const items = await this.guilds.list();
      const item = items.find((entry) => String(entry.guild_id) === this.guildId) ?? null;
      if (!item) this.error.set('This server is not available for the current account.');
      this.guild.set(item);
    } catch {
      this.error.set('Unable to load the guild access profile.');
    } finally {
      this.loading.set(false);
    }
  }

  allowed(key: string): boolean {
    const item = this.guild();
    if (!item || this.isExpired()) return false;
    return this.fullAccess() || item.permissions?.includes(key) === true;
  }
}
