import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';

import { NotificationService, NotificationSummary, PlatformNotification } from '../core/notification.service';
import { ShellComponent } from '../shared/shell.component';
import { TranslatePipe } from '../core/translate.pipe';
import { TranslationService } from '../core/translation.service';
import { ToastService } from '../core/toast.service';

@Component({
  selector: 'sn-notifications',
  standalone: true,
  imports: [CommonModule, FormsModule, ShellComponent, TranslatePipe],
  template: `
    <sn-shell [title]="'notifications.title' | snT:'Notification Center'">
      <div class="topline">
        <div>
          <div class="eyebrow">{{ "notifications.eyebrow" | snT:"ALERT ROUTING & RESPONSE" }}</div>
          <h2>{{ "notifications.heading" | snT:"Platform notifications" }}</h2>
          @if (lastUpdated()) {
            <small class="updated">
              {{ "notifications.last_updated" | snT:"Last updated" }}:
              {{ lastUpdated() | date:'mediumTime' }}
            </small>
          }
        </div>

        <div class="top-actions">
          <label class="auto-refresh">
            <input type="checkbox" [(ngModel)]="autoRefresh" (change)="configureAutoRefresh()" />
            <span>{{ "notifications.auto_refresh" | snT:"Auto-refresh" }}</span>
          </label>
          <button (click)="evaluate()" [disabled]="busy()">
            {{ busy() ? ('notifications.evaluating' | snT:'Evaluating…') : ('notifications.evaluate' | snT:'Evaluate alert rules') }}
          </button>
        </div>
      </div>

      @if (summary(); as stats) {
        <div class="cards">
          <article><span>{{ "notifications.open" | snT:"Open" }}</span><b>{{ stats.open }}</b></article>
          <article class="critical"><span>{{ "notifications.critical" | snT:"Critical" }}</span><b>{{ stats.critical }}</b></article>
          <article class="high"><span>{{ "notifications.high" | snT:"High" }}</span><b>{{ stats.high }}</b></article>
          <article><span>{{ "notifications.acknowledged" | snT:"Acknowledged" }}</span><b>{{ stats.acknowledged }}</b></article>
          <article><span>{{ "notifications.resolved" | snT:"Resolved" }}</span><b>{{ stats.resolved }}</b></article>
        </div>
      }

      <div class="filters">
        <select [(ngModel)]="status" (change)="load()">
          <option value="">{{ "notifications.all_statuses" | snT:"All statuses" }}</option>
          <option value="open">{{ "notifications.open" | snT:"Open" }}</option>
          <option value="acknowledged">{{ "notifications.acknowledged" | snT:"Acknowledged" }}</option>
          <option value="resolved">{{ "notifications.resolved" | snT:"Resolved" }}</option>
        </select>

        <select [(ngModel)]="severity" (change)="load()">
          <option value="">{{ "notifications.all_severities" | snT:"All severities" }}</option>
          <option value="critical">{{ "notifications.critical" | snT:"Critical" }}</option>
          <option value="high">{{ "notifications.high" | snT:"High" }}</option>
          <option value="medium">{{ "notifications.medium" | snT:"Medium" }}</option>
          <option value="low">{{ "notifications.low" | snT:"Low" }}</option>
          <option value="info">{{ "notifications.info" | snT:"Info" }}</option>
        </select>

        <button class="secondary" (click)="load()" [disabled]="loading()">
          {{ loading() ? ('notifications.loading' | snT:'Loading…') : ('notifications.refresh' | snT:'Refresh') }}
        </button>
      </div>

      <section class="panel" [class.loading]="loading()">
        @for (item of items(); track item.id) {
          <article class="alert" [class]="item.severity">
            <div class="severity">{{ severityLabel(item.severity) }}</div>
            <div class="body">
              <div class="head"><h3>{{ item.title }}</h3><span>{{ statusLabel(item.status) }}</span></div>
              <p>{{ item.message }}</p>
              <small>
                {{ categoryLabel(item.category) }} · {{ sourceLabel(item.source) }} · {{ item.last_seen_at | date:'medium' }}
                @if (item.guild_id) { · {{ "notifications.guild" | snT:"Guild" }} {{ item.guild_id }} }
              </small>
            </div>
            <div class="actions">
              @if (item.status === 'open') {
                <button class="secondary" (click)="acknowledge(item)" [disabled]="busyItemId() === item.id">
                  {{ "notifications.acknowledge" | snT:"Acknowledge" }}
                </button>
              }
              @if (item.status !== 'resolved') {
                <button (click)="resolve(item)" [disabled]="busyItemId() === item.id">
                  {{ "notifications.resolve" | snT:"Resolve" }}
                </button>
              }
            </div>
          </article>
        } @empty {
          <div class="empty">{{ "notifications.empty" | snT:"No notifications match the selected filters." }}</div>
        }
      </section>
    </sn-shell>
  `,
  styles: [`
    .topline{display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;margin-bottom:1.4rem}
    .eyebrow{font-size:.72rem;letter-spacing:.14em;color:#7f8cff;font-weight:800}
    h2{margin:.35rem 0 0;font-size:2rem}
    .updated{display:block;margin-top:.45rem;color:var(--muted)}
    .top-actions{display:flex;align-items:center;gap:.8rem;flex-wrap:wrap;justify-content:flex-end}
    .auto-refresh{display:flex;align-items:center;gap:.5rem;color:var(--muted);font-size:.75rem;padding:.58rem .72rem;border:1px solid var(--line);border-radius:10px;background:rgba(255,255,255,.03)}
    .auto-refresh input{accent-color:#6675f4}
    button,select{border:1px solid var(--line);border-radius:11px;padding:.7rem .9rem;background:#6675f4;color:white}
    button{cursor:pointer}button:disabled{opacity:.55;cursor:not-allowed}
    .secondary,select{background:rgba(255,255,255,.045);color:var(--text)}
    .cards{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.8rem;margin-bottom:1rem}
    .cards article,.panel{background:rgba(14,20,37,.78);border:1px solid var(--line);border-radius:16px;padding:1rem}
    .cards span{color:var(--muted)}.cards b{display:block;font-size:1.8rem;margin-top:.35rem}
    .cards .critical b{color:#ff7f91}.cards .high b{color:#ffb15c}
    .filters{display:flex;gap:.7rem;margin-bottom:1rem;flex-wrap:wrap}
    .panel{padding:.2rem 1rem;transition:opacity .18s ease}.panel.loading{opacity:.62}
    .alert{display:grid;grid-template-columns:110px minmax(0,1fr) auto;gap:1rem;padding:1rem 0;border-bottom:1px solid rgba(255,255,255,.06);align-items:center}
    .alert:last-child{border-bottom:0}
    .severity{text-transform:uppercase;font-size:.72rem;font-weight:900;letter-spacing:.08em;color:#8fa0bf}
    .alert.critical .severity{color:#ff7f91}.alert.high .severity{color:#ffb15c}.alert.medium .severity{color:#ffe178}.alert.low .severity{color:#7ac6ff}.alert.info .severity{color:#a59cff}
    .head{display:flex;justify-content:space-between;gap:1rem}.head h3{margin:0}.head span{font-size:.72rem;text-transform:uppercase;color:#92a0bf}
    .body p{color:var(--muted);margin:.4rem 0}.body small{color:#7784a4}
    .actions{display:flex;gap:.5rem}.empty{padding:2rem;text-align:center;color:var(--muted)}
    @media(max-width:950px){.cards{grid-template-columns:repeat(2,1fr)}.alert{grid-template-columns:1fr}.actions,.filters,.topline{flex-wrap:wrap}.head{flex-direction:column}.top-actions{justify-content:flex-start}}
  `],
})
export class NotificationsComponent implements OnInit, OnDestroy {
  readonly items = signal<PlatformNotification[]>([]);
  readonly summary = signal<NotificationSummary | null>(null);
  readonly busy = signal(false);
  readonly loading = signal(false);
  readonly busyItemId = signal<string | null>(null);
  readonly lastUpdated = signal<Date | null>(null);

  status = '';
  severity = '';
  autoRefresh = true;

  private refreshTimer: number | null = null;

  constructor(
    private readonly notifications: NotificationService,
    private readonly i18n: TranslationService,
    private readonly toast: ToastService,
  ) {}

  ngOnInit(): void {
    void this.load();
    this.configureAutoRefresh();
  }

  ngOnDestroy(): void {
    this.stopAutoRefresh();
  }

  async load(showError = true): Promise<void> {
    this.loading.set(true);
    try {
      const [list, summary] = await Promise.all([
        firstValueFrom(this.notifications.list(this.status, this.severity)),
        firstValueFrom(this.notifications.summary()),
      ]);
      this.items.set(list.items);
      this.summary.set(summary);
      this.lastUpdated.set(new Date());
    } catch {
      if (showError) {
        this.toast.error(
          this.i18n.t('ui.error', 'Operation failed'),
          this.i18n.t('notifications.load_error', 'Unable to load notifications.'),
        );
      }
    } finally {
      this.loading.set(false);
    }
  }

  async evaluate(): Promise<void> {
    this.busy.set(true);
    try {
      const result = await firstValueFrom(this.notifications.evaluate());
      const details = this.i18n
        .t('notifications.rules_evaluated', 'Rules evaluated: {count} alert(s) refreshed.')
        .replace('{count}', String(result['alerts_created_or_refreshed'] || 0));

      this.toast.success(
        this.i18n.t('notifications.evaluate_success', 'Alert rules evaluated.'),
        details,
      );
      await this.load(false);
    } catch {
      this.toast.error(
        this.i18n.t('ui.error', 'Operation failed'),
        this.i18n.t('notifications.evaluate_error', 'Unable to evaluate alert rules.'),
      );
    } finally {
      this.busy.set(false);
    }
  }

  async acknowledge(item: PlatformNotification): Promise<void> {
    this.busyItemId.set(item.id);
    try {
      await firstValueFrom(this.notifications.acknowledge(item.id));
      this.toast.success(
        this.i18n.t('ui.success', 'Completed'),
        this.i18n.t('notifications.acknowledged_success', 'Notification acknowledged.'),
      );
      await this.load(false);
    } catch {
      this.toast.error(
        this.i18n.t('ui.error', 'Operation failed'),
        this.i18n.t('notifications.acknowledge_error', 'Unable to acknowledge notification.'),
      );
    } finally {
      this.busyItemId.set(null);
    }
  }

  async resolve(item: PlatformNotification): Promise<void> {
    this.busyItemId.set(item.id);
    try {
      await firstValueFrom(this.notifications.resolve(item.id));
      this.toast.success(
        this.i18n.t('ui.success', 'Completed'),
        this.i18n.t('notifications.resolved_success', 'Notification resolved.'),
      );
      await this.load(false);
    } catch {
      this.toast.error(
        this.i18n.t('ui.error', 'Operation failed'),
        this.i18n.t('notifications.resolve_error', 'Unable to resolve notification.'),
      );
    } finally {
      this.busyItemId.set(null);
    }
  }

  configureAutoRefresh(): void {
    this.stopAutoRefresh();
    if (!this.autoRefresh) return;
    this.refreshTimer = window.setInterval(() => void this.load(false), 30000);
  }

  statusLabel(value: string): string {
    const key = value?.toLowerCase();
    if (key === 'open') return this.i18n.t('notifications.status_open', 'Open');
    if (key === 'acknowledged') return this.i18n.t('notifications.status_acknowledged', 'Acknowledged');
    if (key === 'resolved') return this.i18n.t('notifications.status_resolved', 'Resolved');
    return value;
  }

  severityLabel(value: string): string {
    const key = value?.toLowerCase();
    if (key === 'critical') return this.i18n.t('notifications.severity_critical', 'Critical');
    if (key === 'high') return this.i18n.t('notifications.severity_high', 'High');
    if (key === 'medium') return this.i18n.t('notifications.severity_medium', 'Medium');
    if (key === 'low') return this.i18n.t('notifications.severity_low', 'Low');
    if (key === 'info') return this.i18n.t('notifications.severity_info', 'Info');
    return value;
  }

  categoryLabel(value: string): string {
    const key = value?.toLowerCase();
    if (key === 'security') return this.i18n.t('notifications.category_security', 'Security');
    if (key === 'system') return this.i18n.t('notifications.category_system', 'System');
    if (key === 'plugin') return this.i18n.t('notifications.category_plugin', 'Plugin');
    if (key === 'discord') return this.i18n.t('notifications.category_discord', 'Discord');
    if (key === 'backup') return this.i18n.t('notifications.category_backup', 'Backup');
    if (key === 'automation') return this.i18n.t('notifications.category_automation', 'Automation');
    return value;
  }

  sourceLabel(value: string): string {
    const key = value?.toLowerCase();
    if (key === 'platform') return this.i18n.t('notifications.source_platform', 'Platform');
    if (key === 'backend') return this.i18n.t('notifications.source_backend', 'Backend');
    if (key === 'scheduler') return this.i18n.t('notifications.source_scheduler', 'Scheduler');
    if (key === 'discord') return this.i18n.t('notifications.source_discord', 'Discord');
    if (key === 'plugin') return this.i18n.t('notifications.source_plugin', 'Plugin');
    return value;
  }

  private stopAutoRefresh(): void {
    if (this.refreshTimer !== null) {
      window.clearInterval(this.refreshTimer);
      this.refreshTimer = null;
    }
  }
}
