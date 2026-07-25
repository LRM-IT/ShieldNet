import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { AuthService } from '../core/auth.service';
import { OperationsService, OperationsSnapshot } from '../core/operations.service';
import { ShellComponent } from '../shared/shell.component';
import { TranslatePipe } from '../core/translate.pipe';
import { TranslationService } from '../core/translation.service';

@Component({
  selector: 'sn-operations',
  standalone: true,
  imports: [CommonModule, ShellComponent, TranslatePipe],
  template: `
    <sn-shell [title]="'operations.title' | snT:'Live Operations'">
      <div class="topline">
        <div>
          <div class="eyebrow">{{ "operations.eyebrow" | snT:"REAL-TIME CONTROL PLANE" }}</div>
          <h2>{{ "operations.telemetry" | snT:"Platform telemetry" }}</h2>
        </div>
        <div class="connection" [class.online]="connected()">
          <span></span>{{ connected() ? ('operations.connected' | snT:'Live stream connected') : ('operations.reconnecting' | snT:'Reconnecting…') }}
        </div>
      </div>

      @if (snapshot(); as data) {
        <div class="cards">
          @for (item of componentEntries(data); track item.key) {
            <article class="card">
              <div class="card-head"><b>{{ label(item.key) }}</b><span [class.good]="item.value.status === 'online'">{{ item.value.status }}</span></div>
              @if (item.value.latency_ms !== undefined && item.value.latency_ms !== null) { <strong>{{ item.value.latency_ms }} ms</strong> }
              @if (item.value.queue_depth !== undefined) { <div class="metric"><span>{{ "operations.queue" | snT:"Queue" }}</span><b>{{ item.value.queue_depth }}</b></div> }
              @if (item.value.memory_bytes) { <div class="metric"><span>{{ "operations.memory" | snT:"Memory" }}</span><b>{{ formatBytes(item.value.memory_bytes) }}</b></div> }
            </article>
          }
        </div>

        <div class="grid">
          <section class="panel">
            <div class="panel-title"><h3>{{ "operations.workers" | snT:"Runtime workers" }}</h3><span>{{ data.workers.length }}</span></div>
            <div class="worker-list">
              @for (worker of data.workers; track worker.worker_name) {
                <div class="worker">
                  <span class="dot" [class.stale]="worker.status !== 'online'"></span>
                  <div><b>{{ worker.worker_name }}</b><small>{{ worker.worker_type }} · {{ worker.last_seen_at | date:'mediumTime' }}</small></div>
                  <em [class.stale-text]="worker.status !== 'online'">{{ worker.status }}</em>
                </div>
              } @empty { <div class="empty">{{ "operations.no_heartbeat" | snT:"No heartbeat data yet." }}</div> }
            </div>
          </section>

          <section class="panel events">
            <div class="panel-title"><h3>{{ "operations.events" | snT:"Live event stream" }}</h3><span>{{ data.events.length }}</span></div>
            <div class="event-list">
              @for (event of data.events; track event.id) {
                <div class="event">
                  <time>{{ event.created_at | date:'HH:mm:ss' }}</time>
                  <div><b>{{ event.event_type }}</b><small>{{ event.message || event.target_type || ('operations.platform_event' | snT:'Platform event') }}</small></div>
                  <span>{{ event.result }}</span>
                </div>
              } @empty { <div class="empty">{{ "operations.no_events" | snT:"No audit events available." }}</div> }
            </div>
          </section>
        </div>
      } @else {
        <div class="loading">{{ "operations.loading" | snT:"Loading live telemetry…" }}</div>
      }
    </sn-shell>
  `,
  styles: [`
    .topline{display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem}.eyebrow{font-size:.72rem;letter-spacing:.14em;color:#7f8cff;font-weight:800}h2{margin:.35rem 0 0;font-size:2rem}.connection{display:flex;gap:.5rem;align-items:center;color:var(--muted);border:1px solid var(--line);padding:.55rem .8rem;border-radius:999px}.connection span{width:.6rem;height:.6rem;border-radius:50%;background:#ff8d9c}.connection.online span{background:#69e5ad;box-shadow:0 0 12px #69e5ad}.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem}.card,.panel{background:rgba(14,20,37,.78);border:1px solid var(--line);border-radius:18px;padding:1.1rem;box-shadow:0 20px 60px rgba(0,0,0,.16)}.card-head{display:flex;justify-content:space-between;text-transform:capitalize}.card-head span{color:#ff8d9c}.card-head span.good{color:#69e5ad}.card strong{display:block;font-size:1.8rem;margin:.9rem 0}.metric{display:flex;justify-content:space-between;color:var(--muted);margin-top:.55rem}.metric b{color:var(--text)}.grid{display:grid;grid-template-columns:minmax(0,.8fr) minmax(0,1.2fr);gap:1rem;margin-top:1rem}.panel-title{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);padding-bottom:.8rem}.panel-title h3{margin:0}.panel-title span{color:var(--muted)}.worker,.event{display:grid;align-items:center;gap:.8rem;padding:.85rem 0;border-bottom:1px solid rgba(255,255,255,.055)}.worker{grid-template-columns:auto 1fr auto}.event{grid-template-columns:74px 1fr auto}.dot{width:.65rem;height:.65rem;border-radius:50%;background:#69e5ad;box-shadow:0 0 10px #69e5ad}.dot.stale{background:#ffb35e;box-shadow:none}.worker small,.event small{display:block;color:var(--muted);margin-top:.2rem}.worker em,.event>span{font-style:normal;color:#69e5ad;font-size:.78rem;text-transform:uppercase}.stale-text{color:#ffb35e!important}.event time{font-family:monospace;color:#8d98b7}.event-list{max-height:520px;overflow:auto}.empty,.loading{padding:2rem;text-align:center;color:var(--muted)}@media(max-width:950px){.cards,.grid{grid-template-columns:1fr}.topline{align-items:flex-start;gap:1rem;flex-direction:column}}
  `],
})
export class OperationsComponent implements OnInit, OnDestroy {
  readonly snapshot = signal<OperationsSnapshot | null>(null);
  readonly connected = signal(false);
  private socket?: WebSocket;
  private retry?: number;

  constructor(private readonly auth: AuthService, private readonly operations: OperationsService, private readonly i18n: TranslationService) {}

  async ngOnInit(): Promise<void> {
    try { this.snapshot.set(await firstValueFrom(this.operations.snapshot())); } catch {}
    this.connect();
  }
  ngOnDestroy(): void { if (this.retry) window.clearTimeout(this.retry); this.socket?.close(); }
  componentEntries(data: OperationsSnapshot) { return Object.entries(data.components).map(([key, value]) => ({ key, value })); }
  label(key: string): string { return key === 'valkey' ? this.i18n.t('operations.valkey_queue', 'Valkey / Queue') : key; }
  formatBytes(value: number): string { return value < 1024 * 1024 ? `${Math.round(value / 1024)} KB` : `${(value / 1024 / 1024).toFixed(1)} MB`; }

  private connect(): void {
    const token = this.auth.accessToken;
    if (!token) return;
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    this.socket = new WebSocket(`${protocol}//${location.host}/api/v1/platform/operations/ws?token=${encodeURIComponent(token)}`);
    this.socket.onopen = () => this.connected.set(true);
    this.socket.onmessage = event => this.snapshot.set(JSON.parse(event.data) as OperationsSnapshot);
    this.socket.onclose = () => { this.connected.set(false); this.retry = window.setTimeout(() => this.connect(), 3000); };
    this.socket.onerror = () => this.socket?.close();
  }
}
