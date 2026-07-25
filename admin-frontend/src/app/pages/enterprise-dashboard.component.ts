import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, OnDestroy, OnInit, computed, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Subscription, debounceTime, filter, firstValueFrom } from 'rxjs';

import {
  EnterpriseDashboardOverview,
  EnterpriseDashboardService,
} from '../core/enterprise-dashboard.service';
import { EventBusService } from '../core/event-bus.service';
import {
  NotificationService,
  NotificationSummary,
  PlatformNotification,
} from '../core/notification.service';
import {
  OperationsService,
  OperationsSnapshot,
} from '../core/operations.service';
import { TranslatePipe } from '../core/translate.pipe';
import { ShellComponent } from '../shared/shell.component';
import { AuthService } from '../core/auth.service';

@Component({
  standalone: true,
  imports: [ShellComponent, RouterLink, DatePipe, DecimalPipe, TranslatePipe],
  template: `
    <sn-shell [title]="'dashboard.title' | snT:'Command Center'">
      <section class="dashboard-head">
        <div>
          <div class="eyebrow">SHIELDNET ADMIN V4 · STAGE 14.10</div>
          <h2>{{ 'dashboard.heading' | snT:'Discord infrastructure overview' }}</h2>
          <p>{{ 'dashboard.description' | snT:'Live servers, services, alerts and recent activity in one workspace.' }}</p>
        </div>
        <div class="head-actions">
          <span class="live-pill" [class.offline]="eventBus.state() !== 'online'">
            <i></i>{{ eventBus.state() === 'online' ? 'LIVE' : 'REST' }}
          </span>
          <button class="refresh" type="button" [disabled]="loading()" (click)="load()">
            {{ loading() ? ('dashboard.refreshing' | snT:'Refreshing…') : ('dashboard.refresh' | snT:'Refresh') }}
          </button>
        </div>
      </section>

      @if (error()) {
        <section class="error-panel">{{ error() }}</section>
      }

      @if (data(); as overview) {
        <section class="kpi-grid">
          <article class="kpi-card"><span>Guilds</span><strong>{{ overview.metrics['guilds'] | number }}</strong><small>Managed servers</small></article>
          <article class="kpi-card"><span>Members</span><strong>{{ overview.metrics['members'] | number }}</strong><small>{{ overview.metrics['active_members'] | number }} active</small></article>
          <article class="kpi-card"><span>Bots online</span><strong>{{ onlineWorkers() }}/{{ botWorkers() }}</strong><small>{{ workerStatusLabel() }}</small></article>
          <article class="kpi-card"><span>Plugins enabled</span><strong>{{ overview.metrics['enabled_plugins'] | number }}</strong><small>Across visible servers</small></article>
          <article class="kpi-card compact"><span>API</span><strong [class.status-ok]="apiOnline()" [class.danger]="!apiOnline()">{{ apiOnline() ? 'ONLINE' : 'OFFLINE' }}</strong><small>{{ overview.overall_status }} control plane</small></article>
          <article class="kpi-card compact"><span>Scheduler</span><strong [class.status-ok]="schedulerOnline()" [class.danger]="!schedulerOnline()">{{ schedulerOnline() ? 'ONLINE' : 'OFFLINE' }}</strong><small>Runtime worker</small></article>
        </section>

        <section class="content-grid">
          <article class="panel health-panel">
            <div class="section-title">
              <div><span>HEALTH</span><h3>Infrastructure status</h3></div>
              <a routerLink="/platform/health">Open monitor →</a>
            </div>
            <div class="health-grid">
              <div class="health-tile"><span>CPU</span>@if (hasSystemMetrics()) { <strong>{{ systemMetric('load_percent') | number:'1.0-1' }}%</strong> } @else { <strong class="restricted">Restricted</strong> }<i [style.width.%]="bar(systemMetric('load_percent'))"></i></div>
              <div class="health-tile"><span>RAM</span>@if (hasSystemMetrics()) { <strong>{{ systemMetric('memory_percent') | number:'1.0-1' }}%</strong> } @else { <strong class="restricted">Restricted</strong> }<i [style.width.%]="bar(systemMetric('memory_percent'))"></i></div>
              <div class="health-tile"><span>Disk</span>@if (hasSystemMetrics()) { <strong>{{ systemMetric('disk_percent') | number:'1.0-1' }}%</strong> } @else { <strong class="restricted">Restricted</strong> }<i [style.width.%]="bar(systemMetric('disk_percent'))"></i></div>
              <div class="health-tile"><span>PostgreSQL</span><strong>{{ overview.components.postgresql.latency_ms | number:'1.0-0' }} ms</strong><small>{{ overview.components.postgresql.status }}</small></div>
              <div class="health-tile"><span>Valkey</span><strong>{{ overview.components.valkey.latency_ms ?? '—' }} ms</strong><small>{{ overview.components.valkey.status }}</small></div>
              <div class="health-tile"><span>Queue</span><strong>{{ overview.components.valkey.queue_depth | number }}</strong><small>Pending jobs</small></div>
            </div>
          </article>

          <article class="panel actions-panel">
            <div class="section-title"><div><span>QUICK ACTIONS</span><h3>Administration</h3></div></div>
            <div class="quick-actions">
              <a routerLink="/platform/plugins"><b>＋</b><span>Install plugin</span></a>
              <a routerLink="/platform/jobs"><b>↻</b><span>Reload jobs</span></a>
              @if (hasPlatformOperations()) {
                <a routerLink="/platform/operations"><b>⌁</b><span>Live operations</span></a>
                <a routerLink="/platform/logs"><b>≡</b><span>Open logs</span></a>
              }
              <a routerLink="/platform/doctor"><b>✚</b><span>Run doctor</span></a>
              <a routerLink="/platform/access"><b>⌾</b><span>Access control</span></a>
            </div>
          </article>
        </section>

        <section class="section-title estate-title">
          <div><span>DISCORD ESTATE</span><h3>Managed servers</h3></div>
          <small>{{ overview.guilds.length }} nodes</small>
        </section>

        @if (overview.guilds.length === 0) {
          <section class="panel empty">No Discord servers are available for this operator.</section>
        } @else {
          <section class="guild-grid">
            @for (guild of overview.guilds; track guild.guild_id) {
              <article class="guild-card panel">
                <div class="guild-head">
                  @if (guild.icon_url) { <img [src]="guild.icon_url" alt=""> }
                  @else { <div class="avatar">{{ guild.name.slice(0, 1) }}</div> }
                  <div><h4>{{ guild.name }}</h4><small>{{ guild.guild_id }}</small></div>
                  <span class="node-state" [class.online]="guild.bot_status === 'online'" [class.stale]="guild.sync_status === 'stale'"><i></i>{{ guild.bot_status }} · {{ guild.sync_status }}</span>
                </div>
                <div class="guild-stats">
                  <div><span>Members</span><strong>{{ guild.member_count | number }}</strong></div>
                  <div><span>Last sync</span><strong>{{ guild.last_sync_at ? (guild.last_sync_at | date:'short') : 'Never' }}</strong></div>
                  <div><span>Plugins</span><strong>{{ guild.enabled_plugins | number }}</strong></div>
                </div>
                <div class="guild-actions">
                  <a [routerLink]="['/guild', guild.guild_id]">Open server</a>
                  <a [routerLink]="['/guild', guild.guild_id, 'members']">Members</a>
                  <a [routerLink]="['/guild', guild.guild_id, 'security']">Security</a>
                  <a [routerLink]="['/guild', guild.guild_id, 'plugin-runtime']">Plugins</a>
                </div>
              </article>
            }
          </section>
        }

        <section class="bottom-grid">
          <article class="panel activity-panel">
            <div class="section-title"><div><span>LIVE ACTIVITY</span><h3>Recent events</h3></div><a routerLink="/platform/logs">All logs →</a></div>
            <div class="activity-list">
              @for (event of recentEvents(); track event.id) {
                <div class="activity-row">
                  <i [class.error]="event.result === 'error' || event.result === 'failed'"></i>
                  <div><strong>{{ event.message || event.event_type }}</strong><span>{{ event.event_type }} · {{ event.created_at | date:'medium' }}</span></div>
                </div>
              } @empty { <div class="empty-inline">No recent events.</div> }
            </div>
          </article>

          <article class="panel notifications-panel">
            <div class="section-title"><div><span>NOTIFICATIONS</span><h3>Open alerts</h3></div>@if (hasPlatformOperations()) { <a routerLink="/platform/notifications">View all →</a> }</div>
            <div class="notification-summary">
              <div><strong>{{ openAlerts() }}</strong><span>Open</span></div>
              <div><strong class="danger">{{ criticalAlerts() }}</strong><span>Critical</span></div>
              <div><strong>{{ notificationSummary()?.high || 0 }}</strong><span>High</span></div>
            </div>
            <div class="notification-list">
              @for (item of notifications(); track item.id) {
                <div><span [class]="'severity ' + item.severity">{{ item.severity }}</span><strong>{{ item.title }}</strong><small>{{ item.last_seen_at | date:'short' }}</small></div>
              } @empty { <div class="empty-inline">No active notifications.</div> }
            </div>
          </article>
        </section>
      }
    </sn-shell>
  `,
  styles: [`
    :host{display:block}.dashboard-head{display:flex;justify-content:space-between;align-items:center;gap:1.5rem;padding:1.5rem 0 1.1rem}.eyebrow,.section-title span{font-size:.66rem;font-weight:900;letter-spacing:.15em;color:var(--accent)}.dashboard-head h2{margin:.35rem 0 .3rem;font-size:clamp(1.75rem,3vw,2.55rem)}.dashboard-head p{margin:0;color:var(--muted)}.head-actions{display:flex;align-items:center;gap:.7rem}.refresh,.live-pill{border:1px solid var(--line);background:var(--panel);color:var(--text);border-radius:10px;padding:.65rem .9rem}.refresh{cursor:pointer}.live-pill{font-size:.72rem;font-weight:900}.live-pill i,.node-state i{display:inline-block;width:7px;height:7px;border-radius:50%;background:#35e2b2;margin-right:.45rem;box-shadow:0 0 10px #35e2b2}.live-pill.offline i{background:#f0a94b;box-shadow:none}.error-panel{padding:1rem;border:1px solid rgba(255,90,90,.3);background:rgba(255,90,90,.08);border-radius:12px;color:#ff9494}.kpi-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:.8rem}.kpi-card{padding:1.05rem;border:1px solid var(--line);background:var(--panel);border-radius:14px;display:grid;gap:.35rem;min-height:112px}.kpi-card span{font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}.kpi-card strong{font-size:1.75rem}.kpi-card small{color:var(--muted)}.kpi-card.compact strong{font-size:1rem;margin-top:.35rem}.danger{color:#ff6b72!important}.status-ok{color:#35e2b2!important}.content-grid,.bottom-grid{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(300px,.8fr);gap:1rem;margin-top:1rem}.panel{border:1px solid var(--line);background:var(--panel);border-radius:16px}.health-panel,.actions-panel,.activity-panel,.notifications-panel{padding:1.2rem}.section-title{display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;margin-bottom:1rem}.section-title h3{margin:.2rem 0 0}.section-title a{color:var(--accent);text-decoration:none;font-size:.82rem}.health-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:.75rem}.health-tile{position:relative;overflow:hidden;padding:1rem;border:1px solid var(--line);border-radius:12px;background:var(--panel-2);display:grid;gap:.35rem}.health-tile span,.health-tile small{color:var(--muted)}.health-tile strong{font-size:1.15rem}.health-tile .restricted{font-size:.8rem;color:var(--muted)}.health-tile i{position:absolute;left:0;bottom:0;height:3px;background:var(--accent);max-width:100%}.quick-actions{display:grid;grid-template-columns:repeat(2,1fr);gap:.7rem}.quick-actions a{display:flex;align-items:center;gap:.7rem;padding:.8rem;border:1px solid var(--line);border-radius:11px;color:var(--text);text-decoration:none;background:var(--panel-2)}.quick-actions b{display:grid;place-items:center;width:28px;height:28px;border-radius:8px;background:rgba(53,226,178,.1);color:var(--accent)}.estate-title{margin:1.5rem 0 .8rem}.estate-title small{color:var(--muted);text-transform:uppercase}.guild-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem}.guild-card{padding:1.1rem}.guild-head{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:.8rem}.guild-head img,.avatar{width:44px;height:44px;border-radius:12px}.guild-head img{object-fit:cover}.avatar{display:grid;place-items:center;background:rgba(53,226,178,.12);color:var(--accent);font-weight:900}.guild-head h4{margin:0 0 .2rem}.guild-head small{color:var(--muted)}.node-state{font-size:.68rem;text-transform:uppercase;color:#f0a94b}.node-state.online{color:#35e2b2}.node-state i{background:#f0a94b;box-shadow:none}.node-state.online i{background:#35e2b2;box-shadow:0 0 8px #35e2b2}.guild-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:.5rem;margin:1rem 0}.guild-stats div{padding:.7rem;border:1px solid var(--line);border-radius:10px;display:grid;gap:.25rem}.guild-stats span{font-size:.67rem;color:var(--muted);text-transform:uppercase}.guild-stats strong{font-size:.9rem;overflow:hidden;text-overflow:ellipsis}.guild-actions{display:flex;gap:.5rem;flex-wrap:wrap}.guild-actions a{padding:.55rem .7rem;border:1px solid var(--line);border-radius:9px;color:var(--text);text-decoration:none;font-size:.78rem}.activity-list,.notification-list{display:grid}.activity-row{display:grid;grid-template-columns:auto 1fr;gap:.75rem;padding:.8rem 0;border-top:1px solid var(--line)}.activity-row i{width:8px;height:8px;border-radius:50%;margin-top:.4rem;background:#35e2b2}.activity-row i.error{background:#ff6b72}.activity-row div{display:grid;gap:.2rem}.activity-row span{font-size:.75rem;color:var(--muted)}.notification-summary{display:grid;grid-template-columns:repeat(3,1fr);gap:.5rem;margin-bottom:.7rem}.notification-summary div{padding:.7rem;border:1px solid var(--line);border-radius:10px;display:grid}.notification-summary strong{font-size:1.25rem}.notification-summary span{font-size:.7rem;color:var(--muted)}.notification-list>div{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:.6rem;padding:.65rem 0;border-top:1px solid var(--line)}.notification-list small{color:var(--muted)}.severity{font-size:.62rem;text-transform:uppercase;padding:.25rem .4rem;border-radius:6px;background:rgba(120,140,160,.14)}.severity.critical,.severity.high{color:#ff7379;background:rgba(255,80,90,.12)}.empty,.empty-inline{padding:1rem;color:var(--muted)}
    @media(max-width:1200px){.kpi-grid{grid-template-columns:repeat(3,1fr)}.guild-grid{grid-template-columns:repeat(2,1fr)}}
    @media(max-width:820px){.dashboard-head,.content-grid,.bottom-grid{display:grid;grid-template-columns:1fr}.kpi-grid,.health-grid{grid-template-columns:repeat(2,1fr)}.guild-grid{grid-template-columns:1fr}}
    @media(max-width:520px){.kpi-grid,.health-grid,.quick-actions{grid-template-columns:1fr}.head-actions{justify-content:space-between}.guild-stats{grid-template-columns:1fr}}
  `],
})
export class EnterpriseDashboardComponent implements OnInit, OnDestroy {
  readonly data = signal<EnterpriseDashboardOverview | null>(null);
  readonly operations = signal<OperationsSnapshot | null>(null);
  readonly notificationSummary = signal<NotificationSummary | null>(null);
  readonly notifications = signal<PlatformNotification[]>([]);
  readonly loading = signal(false);
  readonly error = signal('');
  private readonly subscriptions = new Subscription();

  readonly recentEvents = computed(() => (this.operations()?.events || []).slice(0, 8));
  readonly botWorkers = computed(() => this.data()?.workers.filter(worker => worker.type.toLowerCase().includes('bot')).length || 0);
  readonly onlineWorkers = computed(() => this.data()?.workers.filter(worker => worker.type.toLowerCase().includes('bot') && worker.status === 'online').length || 0);
  readonly apiOnline = computed(() => this.data()?.components.backend.status === 'online');
  readonly schedulerOnline = computed(() => this.data()?.workers.some(worker => worker.type.toLowerCase().includes('scheduler') && worker.status === 'online') || false);
  readonly hasSystemMetrics = computed(() => Boolean(this.operations()?.components?.['system']));
  readonly openAlerts = computed(() => this.notificationSummary()?.open ?? this.data()?.metrics['open_alerts'] ?? 0);
  readonly criticalAlerts = computed(() => this.notificationSummary()?.critical ?? this.data()?.metrics['critical_alerts'] ?? 0);
  readonly hasPlatformOperations = computed(() => {
    const profile = this.auth.profile();
    return Boolean(profile?.is_superadmin || profile?.roles?.some(role => ['superadmin', 'admin'].includes(role.toLowerCase())));
  });

  constructor(
    private readonly dashboard: EnterpriseDashboardService,
    private readonly auth: AuthService,
    private readonly operationsService: OperationsService,
    private readonly notificationService: NotificationService,
    readonly eventBus: EventBusService,
  ) {}

  ngOnInit(): void {
    this.eventBus.connect();
    this.load();
    this.subscriptions.add(
      this.eventBus.events$.pipe(
        filter(event => !event.type.startsWith('keepalive')),
        debounceTime(500),
      ).subscribe(() => this.load(false)),
    );
  }

  ngOnDestroy(): void { this.subscriptions.unsubscribe(); }

  async load(showSpinner = true): Promise<void> {
    if (this.loading()) return;
    if (showSpinner) this.loading.set(true);
    this.error.set('');
    try {
      const overview = await this.dashboard.overview();
      this.data.set(overview);

      // Platform-wide operations and notifications are intentionally restricted
      // to global administrators. Guild administrators still receive the scoped
      // dashboard instead of losing the whole page because of optional 403s.
      if (this.hasPlatformOperations()) {
        const [operations, summary, notifications] = await Promise.allSettled([
          firstValueFrom(this.operationsService.snapshot()),
          firstValueFrom(this.notificationService.summary()),
          firstValueFrom(this.notificationService.list('open')),
        ]);
        this.operations.set(operations.status === 'fulfilled' ? operations.value : null);
        this.notificationSummary.set(summary.status === 'fulfilled' ? summary.value : null);
        this.notifications.set(
          notifications.status === 'fulfilled' ? notifications.value.items.slice(0, 5) : [],
        );
      } else {
        this.operations.set(null);
        this.notificationSummary.set(null);
        this.notifications.set([]);
      }
    } catch (error) {
      this.error.set(error instanceof Error ? error.message : 'Unable to load dashboard.');
    } finally {
      this.loading.set(false);
    }
  }

  systemMetric(name: string): number {
    const system = this.operations()?.components?.['system'] as Record<string, unknown> | undefined;
    const value = system?.[name];
    return typeof value === 'number' ? value : 0;
  }

  bar(value: number): number { return Math.max(0, Math.min(100, value || 0)); }
  workerStatusLabel(): string { return this.botWorkers() === 0 ? 'No bot workers' : `${this.onlineWorkers()} healthy`; }
}
