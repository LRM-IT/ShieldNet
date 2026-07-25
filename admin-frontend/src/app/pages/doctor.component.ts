import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { DoctorCheck, DoctorReport, DoctorService } from '../core/doctor.service';
import { ShellComponent } from '../shared/shell.component';
import { TranslatePipe } from '../core/translate.pipe';
import { TranslationService } from '../core/translation.service';

@Component({
  selector: 'sn-doctor',
  standalone: true,
  imports: [CommonModule, ShellComponent, TranslatePipe],
  template: `
    <sn-shell [title]="'doctor.title' | snT:'ShieldNet Doctor'">
      <section class="hero">
        <div><div class="eyebrow">{{ "doctor.eyebrow" | snT:"Platform diagnostics" }}</div><h2>{{ "doctor.heading" | snT:"Installation and runtime health" }}</h2>
          <p>{{ "doctor.description" | snT:"Checks application configuration, PostgreSQL privileges, Valkey, heartbeats and required resources." }}</p></div>
        <button (click)="load()" [disabled]="loading">{{ loading ? ('doctor.running' | snT:'Running…') : ('doctor.run' | snT:'Run diagnostics') }}</button>
      </section>

      <div class="notice error" *ngIf="error">{{ error }}</div>
      <ng-container *ngIf="report">
        <section class="status" [class]="'status ' + report.overall_status">
          <div><span>{{ "doctor.overall" | snT:"Overall status" }}</span><strong>{{ report.overall_status }}</strong></div>
          <small>{{ report.generated_at | date:'medium' }}</small>
        </section>
        <div class="cards">
          <article><span>{{ "doctor.passed" | snT:"Passed" }}</span><strong>{{ report.summary['ok'] || 0 }}</strong></article>
          <article><span>{{ "doctor.warnings" | snT:"Warnings" }}</span><strong>{{ report.summary['warning'] || 0 }}</strong></article>
          <article><span>{{ "doctor.failed" | snT:"Failed" }}</span><strong>{{ report.summary['failed'] || 0 }}</strong></article>
          <article><span>{{ "doctor.manual" | snT:"Manual checks" }}</span><strong>{{ report.summary['manual'] || 0 }}</strong></article>
        </div>

        <section class="panel" *ngFor="let category of categories()">
          <h3>{{ category }}</h3>
          <div class="check" *ngFor="let item of checksFor(category)">
            <span class="dot" [class]="'dot ' + item.status"></span>
            <div class="body"><div class="row"><b>{{ item.name }}</b><span class="badge" [class]="'badge ' + item.status">{{ item.status }}</span></div>
              <p>{{ item.message }}</p>
              <code *ngIf="item.remediation">{{ item.remediation }}</code>
              <details *ngIf="hasDetails(item)"><summary>{{ "doctor.technical" | snT:"Technical details" }}</summary><pre>{{ item.details | json }}</pre></details>
            </div>
          </div>
        </section>
      </ng-container>
    </sn-shell>
  `,
  styles: [`
    .hero,.panel,.status,.notice,article{border:1px solid var(--line);background:rgba(16,22,38,.72);border-radius:18px}.hero{padding:1.35rem;display:flex;justify-content:space-between;gap:1rem;align-items:center}.hero h2{margin:.25rem 0}.hero p,.check p,small{color:var(--muted)}button{padding:.75rem 1rem;border-radius:11px;background:var(--primary);color:white}.eyebrow{text-transform:uppercase;letter-spacing:.12em;color:var(--primary);font-size:.72rem}.status{margin-top:1rem;padding:1rem 1.2rem;display:flex;justify-content:space-between;align-items:center}.status div{display:grid}.status strong{text-transform:uppercase;font-size:1.4rem}.status.healthy{border-color:rgba(76,220,155,.45)}.status.degraded{border-color:rgba(255,190,74,.5)}.status.critical{border-color:rgba(255,80,100,.55)}.cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1rem;margin:1rem 0}article{padding:1rem;display:grid;gap:.4rem}article span{color:var(--muted)}article strong{font-size:1.65rem}.panel{padding:1.15rem;margin-top:1rem;text-transform:none}.panel h3{text-transform:capitalize}.check{display:grid;grid-template-columns:12px 1fr;gap:.75rem;padding:.9rem 0;border-top:1px solid var(--line)}.check:first-of-type{border-top:0}.dot{width:.65rem;height:.65rem;border-radius:50%;margin-top:.35rem}.dot.ok{background:#55dda6}.dot.warning{background:#ffc76b}.dot.failed{background:#ff667d}.dot.manual{background:#8f9ab8}.row{display:flex;justify-content:space-between;gap:1rem}.badge{font-size:.65rem;text-transform:uppercase;padding:.25rem .45rem;border-radius:7px;background:rgba(130,140,170,.14)}.badge.ok{color:#76e7b8}.badge.warning{color:#ffd282}.badge.failed{color:#ff91a1}.badge.manual{color:#adb7d0}code,pre{display:block;white-space:pre-wrap;overflow:auto;padding:.75rem;border-radius:10px;background:#080c17;color:#cad3ff}details{margin-top:.6rem}summary{cursor:pointer;color:var(--muted)}.notice{padding:1rem;margin-top:1rem}.error{color:#ff9baa}@media(max-width:800px){.hero{align-items:flex-start;flex-direction:column}.cards{grid-template-columns:repeat(2,1fr)}}
  `],
})
export class DoctorComponent implements OnInit {
  report: DoctorReport | null = null; loading = false; error = '';
  constructor(private readonly doctor: DoctorService, private readonly i18n: TranslationService) {}
  ngOnInit(): void { this.load(); }
  load(): void { this.loading = true; this.error = ''; this.doctor.report().subscribe({next:r=>{this.report=r;this.loading=false;},error:()=>{this.error=this.i18n.t('doctor.error','Unable to run platform diagnostics.');this.loading=false;}}); }
  categories(): string[] { return [...new Set((this.report?.checks || []).map(i=>i.category))]; }
  checksFor(category: string): DoctorCheck[] { return (this.report?.checks || []).filter(i=>i.category===category); }
  hasDetails(item: DoctorCheck): boolean { return Object.keys(item.details || {}).length > 0; }
}
