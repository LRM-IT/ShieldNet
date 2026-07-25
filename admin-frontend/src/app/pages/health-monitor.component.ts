import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit, computed, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { EventBusService } from '../core/event-bus.service';
import { OperationsService, OperationsSnapshot } from '../core/operations.service';
import { ShellComponent } from '../shared/shell.component';
import { TranslatePipe } from '../core/translate.pipe';

@Component({
  selector: 'sn-health-monitor',
  standalone: true,
  imports: [CommonModule, ShellComponent, TranslatePipe],
  template: `
    <sn-shell [title]="'health.title' | snT:'Health Monitor'">
      <header class="hero">
        <div><div class="eyebrow">REAL-TIME INFRASTRUCTURE</div><h2>Health Monitor</h2><p>CPU, memory, disk, PostgreSQL, Valkey and runtime workers.</p></div>
        <div class="live" [class.online]="eventBus.state() === 'online'"><span></span>{{ eventBus.state() }}</div>
      </header>

      @if (snapshot(); as data) {
        <section class="metrics">
          <article class="metric"><span>CPU load</span><strong>{{ system(data).load_percent || 0 }}%</strong><div class="bar"><i [style.width.%]="system(data).load_percent || 0"></i></div><small>{{ system(data).cpu_count || 0 }} cores · {{ system(data).load_1m || 0 }} / {{ system(data).load_5m || 0 }} / {{ system(data).load_15m || 0 }}</small></article>
          <article class="metric"><span>Memory</span><strong>{{ system(data).memory_percent || 0 }}%</strong><div class="bar"><i [style.width.%]="system(data).memory_percent || 0"></i></div><small>{{ bytes(system(data).memory_used_bytes) }} / {{ bytes(system(data).memory_total_bytes) }}</small></article>
          <article class="metric"><span>Disk</span><strong>{{ system(data).disk_percent || 0 }}%</strong><div class="bar"><i [style.width.%]="system(data).disk_percent || 0"></i></div><small>{{ bytes(system(data).disk_used_bytes) }} / {{ bytes(system(data).disk_total_bytes) }}</small></article>
        </section>

        <section class="services">
          @for (item of services(data); track item.name) {
            <article><span class="dot" [class.bad]="item.status !== 'online'"></span><div><b>{{ item.name }}</b><small>{{ item.detail }}</small></div><em [class.bad-text]="item.status !== 'online'">{{ item.status }}</em></article>
          }
        </section>

        <section class="workers card">
          <div class="heading"><h3>Runtime workers</h3><span>Updated {{ data.generated_at | date:'mediumTime' }}</span></div>
          @for (worker of data.workers; track worker.worker_name) {
            <div class="worker"><span class="dot" [class.bad]="worker.status !== 'online'"></span><div><b>{{ worker.worker_name }}</b><small>{{ worker.worker_type }} · {{ worker.last_seen_at | date:'medium' }}</small></div><em>{{ worker.status }}</em></div>
          } @empty { <div class="empty">No heartbeat data.</div> }
        </section>
      } @else { <div class="empty">Loading health telemetry…</div> }
    </sn-shell>
  `,
  styles: [`
    .hero{display:flex;justify-content:space-between;gap:1rem;align-items:center;margin-bottom:1rem}.eyebrow{font-size:.7rem;letter-spacing:.14em;color:#7f8cff;font-weight:800}.hero h2{margin:.3rem 0}.hero p{margin:0;color:var(--muted)}.live{display:flex;gap:.5rem;align-items:center;border:1px solid var(--line);border-radius:999px;padding:.55rem .8rem;text-transform:uppercase;font-size:.72rem}.live span,.dot{width:.65rem;height:.65rem;border-radius:50%;background:#ff8d9c}.live.online span,.dot{background:#69e5ad;box-shadow:0 0 10px #69e5ad}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem}.metric,.card,.services article{background:rgba(14,20,37,.78);border:1px solid var(--line);border-radius:16px;padding:1rem}.metric span,.metric small{color:var(--muted)}.metric strong{display:block;font-size:2rem;margin:.6rem 0}.bar{height:8px;background:rgba(255,255,255,.06);border-radius:999px;overflow:hidden;margin-bottom:.65rem}.bar i{display:block;height:100%;background:linear-gradient(90deg,#6675f4,#69e5ad);border-radius:inherit}.services{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin:1rem 0}.services article,.worker{display:grid;grid-template-columns:auto 1fr auto;gap:.8rem;align-items:center}.services small,.worker small{display:block;color:var(--muted);margin-top:.2rem}.services em,.worker em{font-style:normal;text-transform:uppercase;font-size:.72rem;color:#69e5ad}.dot.bad{background:#ff8d9c;box-shadow:none}.bad-text{color:#ff8d9c!important}.heading{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);padding-bottom:.8rem}.heading h3{margin:0}.heading span{color:var(--muted)}.worker{padding:.85rem 0;border-bottom:1px solid rgba(255,255,255,.05)}.empty{text-align:center;padding:2rem;color:var(--muted)}@media(max-width:900px){.metrics,.services{grid-template-columns:1fr}.hero{align-items:flex-start;flex-direction:column}}
  `],
})
export class HealthMonitorComponent implements OnInit, OnDestroy {
  readonly snapshot = signal<OperationsSnapshot | null>(null);
  private timer: number | null = null;
  constructor(private readonly operations: OperationsService, public readonly eventBus: EventBusService) {}
  ngOnInit(): void { this.eventBus.connect(); void this.load(); this.timer = window.setInterval(() => void this.load(), 5000); }
  ngOnDestroy(): void { if (this.timer !== null) window.clearInterval(this.timer); }
  async load(): Promise<void> { try { this.snapshot.set(await firstValueFrom(this.operations.snapshot())); } catch {} }
  system(data: OperationsSnapshot) { return data.components['system'] || {}; }
  bytes(value?: number | null): string { if (!value) return '0 B'; const units=['B','KB','MB','GB','TB']; let n=value,i=0; while(n>=1024&&i<units.length-1){n/=1024;i++;} return `${n.toFixed(i<2?0:1)} ${units[i]}`; }
  services(data: OperationsSnapshot) { return Object.entries(data.components).filter(([name])=>name!=='system').map(([name,value])=>({name,status:value.status,detail:value.latency_ms!=null?`${value.latency_ms} ms`:value.queue_depth!=null?`Queue ${value.queue_depth}`:'Available'})); }
}
