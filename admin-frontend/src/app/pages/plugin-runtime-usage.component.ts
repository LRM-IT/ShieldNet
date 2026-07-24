import { Component, OnInit, computed, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';

import { PluginManifest, PluginService } from '../core/plugin.service';
import {
  PluginUsageHistory,
  PluginUsageHistoryPoint,
  PluginUsageService,
  PluginUsageSummary,
} from '../core/plugin-usage.service';
import { ShellComponent } from '../shared/shell.component';

@Component({
  selector: 'sn-plugin-runtime-usage',
  standalone: true,
  imports: [ShellComponent],
  template: `
    <sn-shell title="Plugin Runtime">
      <section class="head">
        <div><h2>Runtime usage</h2><p class="muted">Requests, errors, rate limits and response time.</p></div>
        <button (click)="refresh()" [disabled]="loading() || !selectedKey()">{{ loading() ? 'Refreshing…' : 'Refresh' }}</button>
      </section>

      @if (error()) { <div class="error card">{{ error() }}</div> }

      <section class="picker card">
        <div><strong>Plugin</strong><small class="muted">Select a runtime to inspect</small></div>
        <select [value]="selectedKey()" (change)="selectPlugin($any($event.target).value)" [disabled]="pluginsLoading()">
          <option value="">{{ pluginsLoading() ? 'Loading plugins…' : 'Select plugin' }}</option>
          @for (plugin of plugins(); track plugin.plugin_key) {
            <option [value]="plugin.plugin_key">{{ plugin.name }} · {{ plugin.plugin_key }}</option>
          }
        </select>
      </section>

      @if (!selectedKey() && !pluginsLoading()) {
        <div class="card empty">Select a plugin to open its Runtime Usage dashboard.</div>
      }

      @if (selectedKey()) {
        <section class="banner card">
          <div><span class="eyebrow">Selected runtime</span><h3>{{ selectedPlugin()?.name || selectedKey() }}</h3><p class="muted">{{ selectedPlugin()?.description || 'ShieldNet plugin runtime statistics.' }}</p></div>
          <div class="meta"><span>v{{ selectedPlugin()?.version || '—' }}</span><span [class.good]="selectedPlugin()?.healthy">{{ selectedPlugin()?.healthy ? 'Healthy' : 'Status unknown' }}</span></div>
        </section>

        @if (loading() && !summary()) {
          <div class="card empty">Loading runtime statistics…</div>
        } @else if (summary(); as usage) {
          <section class="metrics">
            <article class="card metric"><span class="muted">Requests today</span><strong>{{ n(usage.requests_today) }}</strong><small>{{ n(usage.requests_total) }} total</small></article>
            <article class="card metric"><span class="muted">Successful</span><strong>{{ n(usage.successful_today) }}</strong><small>{{ successRate() }}% success rate</small></article>
            <article class="card metric" [class.warn]="usage.errors_today > 0"><span class="muted">Errors today</span><strong>{{ n(usage.errors_today) }}</strong><small>{{ n(usage.errors_total) }} total</small></article>
            <article class="card metric" [class.warn]="usage.rate_limited_today > 0"><span class="muted">Rate limited</span><strong>{{ n(usage.rate_limited_today) }}</strong><small>{{ n(usage.rate_limited_total) }} total</small></article>
            <article class="card metric"><span class="muted">Average response</span><strong>{{ duration(usage.average_duration_ms_today) }}</strong><small>{{ duration(usage.average_duration_ms_total) }} overall</small></article>
            <article class="card metric"><span class="muted">Last request</span><strong class="date">{{ date(usage.last_request_at) }}</strong><small>Updated {{ date(usage.generated_at) }}</small></article>
          </section>

          <section class="grid">
            <article class="card panel">
              <div class="section-head">
                <div><h3>Usage history</h3><p class="muted">Daily requests and errors.</p></div>
                <div class="periods">
                  @for (period of periods; track period) { <button [class.active]="days() === period" (click)="changePeriod(period)">{{ period }}d</button> }
                </div>
              </div>
              @if (historyLoading()) { <div class="chart-empty">Loading history…</div> }
              @else if (history(); as dataset) {
                <div class="legend"><span><i class="req"></i>Requests</span><span><i class="err"></i>Errors</span></div>
                <div class="chart">
                  @for (point of dataset.points; track point.day) {
                    <div class="col" [title]="tooltip(point)"><div class="bars"><span class="bar req" [style.height.%]="barHeight(point.requests)"></span><span class="bar err" [style.height.%]="barHeight(point.errors)"></span></div><small>{{ label(point.day) }}</small></div>
                  }
                </div>
              } @else { <div class="chart-empty">No history available.</div> }
            </article>

            <article class="card panel">
              <div class="section-head"><div><h3>Capabilities today</h3><p class="muted">Most-used Runtime API scopes.</p></div></div>
              @for (item of usage.scope_breakdown_today; track item.scope) {
                <div class="scope"><div><strong>{{ item.scope }}</strong><small class="muted">{{ n(item.requests) }}</small></div><div class="track"><span [style.width.%]="scopePercent(item.requests)"></span></div></div>
              } @empty { <div class="chart-empty small">No capability activity today.</div> }
            </article>
          </section>

          <section class="card panel status-panel">
            <div class="section-head"><div><h3>HTTP status distribution</h3><p class="muted">Response codes returned today.</p></div></div>
            <div class="statuses">
              @for (item of usage.status_breakdown_today; track item.status_code) {
                <div class="status" [class.bad]="item.status_code >= 400"><strong>{{ item.status_code }}</strong><span>{{ n(item.requests) }} requests</span></div>
              } @empty { <span class="muted">No requests recorded today.</span> }
            </div>
          </section>
        }
      }
    </sn-shell>
  `,
  styles: [`
    .head,.picker,.banner,.section-head{display:flex;justify-content:space-between;align-items:center;gap:1rem}.head{align-items:end;margin-bottom:1rem}.head h2,.head p,.banner h3,.banner p,.section-head h3,.section-head p{margin:0}.head p,.banner p,.section-head p{margin-top:.3rem}button,select{font:inherit}button{border:0;cursor:pointer}.head>button{padding:.72rem 1rem;border-radius:11px;background:var(--primary);color:#fff;font-weight:750}button:disabled{opacity:.5;cursor:not-allowed}.picker,.banner,.panel{padding:1rem}.picker{margin-bottom:1rem}.picker>div{display:grid;gap:.2rem}.picker select{min-width:min(28rem,100%);padding:.75rem;background:#1d273b;color:#fff;border:1px solid var(--line);border-radius:10px}.error,.empty{padding:1rem;margin-bottom:1rem}.error{color:#ffd9de;border-color:rgba(255,107,125,.4)}.banner{margin-bottom:1rem}.eyebrow{color:#aeb7ff;font-size:.68rem;font-weight:800;text-transform:uppercase;letter-spacing:.12em}.banner h3{margin-top:.25rem}.meta{display:flex;gap:.5rem}.meta span{padding:.28rem .55rem;border:1px solid var(--line);border-radius:999px;color:var(--muted);font-size:.72rem}.meta .good{color:#b9f4dc;border-color:rgba(75,214,155,.35)}.metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem;margin-bottom:1rem}.metric{padding:1rem;display:grid;gap:.35rem}.metric strong{font-size:1.55rem}.metric small{color:var(--muted)}.metric.warn{border-color:rgba(255,202,98,.42)}.metric .date{font-size:1rem}.grid{display:grid;grid-template-columns:minmax(0,2fr) minmax(18rem,1fr);gap:1rem;margin-bottom:1rem}.periods{display:flex;gap:.3rem}.periods button{padding:.42rem .58rem;border-radius:8px;background:#263149;color:var(--muted)}.periods .active{background:var(--primary);color:#fff}.legend{display:flex;gap:1rem;margin-top:1rem;color:var(--muted);font-size:.75rem}.legend span{display:flex;align-items:center;gap:.3rem}.legend i{width:.55rem;height:.55rem;border-radius:50%}.req{background:#7a85ff}.err{background:#ff6b7d}.chart{height:15rem;display:flex;align-items:end;gap:.2rem;padding-top:1rem;overflow:hidden}.col{flex:1;min-width:0;height:100%;display:grid;grid-template-rows:1fr 1.2rem;gap:.25rem}.bars{height:100%;display:flex;align-items:end;justify-content:center;gap:1px}.bar{width:43%;min-height:2px;border-radius:4px 4px 1px 1px}.col small{font-size:.55rem;color:var(--muted);text-align:center;white-space:nowrap}.chart-empty{min-height:12rem;display:grid;place-items:center;color:var(--muted)}.chart-empty.small{min-height:7rem}.scope{display:grid;gap:.45rem;padding:.75rem 0;border-bottom:1px solid var(--line)}.scope>div:first-child{display:flex;justify-content:space-between;gap:.6rem}.scope strong{font-size:.78rem;overflow-wrap:anywhere}.track{height:.35rem;background:#253047;border-radius:99px;overflow:hidden}.track span{display:block;height:100%;min-width:2px;background:var(--primary)}.status-panel{margin-bottom:1rem}.statuses{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:.6rem;margin-top:1rem}.status{padding:.75rem;border:1px solid var(--line);border-radius:10px;display:grid;gap:.2rem}.status strong{color:#b9f4dc}.status.bad strong{color:#ffd9de}.status span{font-size:.7rem;color:var(--muted)}@media(max-width:1050px){.metrics{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:1fr}.statuses{grid-template-columns:repeat(3,1fr)}}@media(max-width:700px){.head,.picker,.banner,.section-head{align-items:stretch;flex-direction:column}.picker select{min-width:0;width:100%}.metrics{grid-template-columns:1fr}.statuses{grid-template-columns:repeat(2,1fr)}}
  `],
})
export class PluginRuntimeUsageComponent implements OnInit {
  readonly guildId = this.route.snapshot.paramMap.get('guildId') ?? '';
  readonly plugins = signal<PluginManifest[]>([]);
  readonly selectedKey = signal('');
  readonly summary = signal<PluginUsageSummary | null>(null);
  readonly history = signal<PluginUsageHistory | null>(null);
  readonly pluginsLoading = signal(true);
  readonly loading = signal(false);
  readonly historyLoading = signal(false);
  readonly error = signal('');
  readonly days = signal<7 | 30 | 90>(7);
  readonly periods: Array<7 | 30 | 90> = [7, 30, 90];
  readonly selectedPlugin = computed(() => this.plugins().find((item) => item.plugin_key === this.selectedKey()) || null);
  readonly successRate = computed(() => { const u = this.summary(); return !u || u.requests_today <= 0 ? 0 : Math.round((u.successful_today / u.requests_today) * 1000) / 10; });
  readonly maxHistory = computed(() => Math.max(1, ...(this.history()?.points || []).flatMap((p) => [p.requests, p.errors])));
  readonly maxScope = computed(() => Math.max(1, ...(this.summary()?.scope_breakdown_today || []).map((i) => i.requests)));

  constructor(private readonly route: ActivatedRoute, private readonly pluginService: PluginService, private readonly usageService: PluginUsageService) {}

  async ngOnInit(): Promise<void> {
    try {
      this.plugins.set(await this.pluginService.list());
      const key = this.route.snapshot.queryParamMap.get('plugin') || this.plugins()[0]?.plugin_key || '';
      if (key) { this.selectedKey.set(key); await this.refresh(); }
    } catch { this.error.set('Unable to load the plugin list.'); }
    finally { this.pluginsLoading.set(false); }
  }

  async selectPlugin(key: string): Promise<void> { this.selectedKey.set(key); this.summary.set(null); this.history.set(null); this.error.set(''); if (key) await this.refresh(); }

  async refresh(): Promise<void> {
    if (!this.selectedKey()) return;
    this.loading.set(true); this.historyLoading.set(true); this.error.set('');
    const [summary, history] = await Promise.allSettled([
      this.usageService.summary(this.guildId, this.selectedKey()),
      this.usageService.history(this.guildId, this.selectedKey(), this.days()),
    ]);
    if (summary.status === 'fulfilled') this.summary.set(summary.value);
    else { this.summary.set(null); this.error.set('Runtime usage is unavailable. Confirm that the plugin is installed for this server and the Usage API is enabled.'); }
    this.history.set(history.status === 'fulfilled' ? history.value : null);
    this.loading.set(false); this.historyLoading.set(false);
  }

  async changePeriod(period: 7 | 30 | 90): Promise<void> {
    if (period === this.days() || !this.selectedKey()) return;
    this.days.set(period); this.historyLoading.set(true);
    try { this.history.set(await this.usageService.history(this.guildId, this.selectedKey(), period)); }
    catch { this.history.set(null); this.error.set('Unable to load Runtime Usage history.'); }
    finally { this.historyLoading.set(false); }
  }

  n(value: number): string { return new Intl.NumberFormat().format(value || 0); }
  duration(value: number): string { return value >= 1000 ? `${(value / 1000).toFixed(2)} s` : `${Math.round((value || 0) * 100) / 100} ms`; }
  date(value: string | null): string { if (!value) return 'No requests yet'; const d = new Date(value); return Number.isNaN(d.getTime()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(d); }
  label(value: string): string { const d = new Date(`${value}T00:00:00`); return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(d); }
  barHeight(value: number): number { return Math.max(value > 0 ? 2 : 0, (value / this.maxHistory()) * 100); }
  scopePercent(value: number): number { return Math.max(2, (value / this.maxScope()) * 100); }
  tooltip(point: PluginUsageHistoryPoint): string { return `${point.day}: ${point.requests} requests, ${point.errors} errors, ${point.rate_limited} rate limited`; }
}
