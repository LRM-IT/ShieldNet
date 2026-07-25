import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';

import { JobDefinition, JobsOverview, JobsService } from '../core/jobs.service';
import { ShellComponent } from '../shared/shell.component';
import { TranslatePipe } from '../core/translate.pipe';
import { TranslationService } from '../core/translation.service';
import { ModalService } from '../core/modal.service';
import { ToastService } from '../core/toast.service';

@Component({
  selector: 'sn-jobs-center',
  standalone: true,
  imports: [CommonModule, ShellComponent, TranslatePipe],
  template: `
    <sn-shell [title]="'jobs.title' | snT:'Jobs Center & System Health'">
      <div class="notice" *ngIf="loading">{{ "jobs.loading" | snT:"Loading platform jobs…" }}</div>
      <div class="notice error" *ngIf="error">{{ error }}</div>

      <ng-container *ngIf="overview">
        <section class="health-grid">
          <article><span>{{ "jobs.backend" | snT:"Backend" }}</span><strong class="ok">{{ overview.health.backend }}</strong></article>
          <article><span>{{ "jobs.postgresql" | snT:"PostgreSQL" }}</span><strong class="ok">{{ overview.health.database }}</strong><small>{{ overview.health.database_latency_ms }} {{ "jobs.milliseconds" | snT:"ms" }}</small></article>
          <article><span>{{ "jobs.scheduler" | snT:"Scheduler" }}</span><strong>{{ overview.health.scheduler }}</strong></article>
          <article><span>{{ "jobs.worker" | snT:"Worker" }}</span><strong>{{ overview.health.worker }}</strong></article>
        </section>

        <section class="summary-grid">
          <article><span>{{ "jobs.registered" | snT:"Registered jobs" }}</span><strong>{{ overview.totals.registered_jobs }}</strong></article>
          <article><span>{{ "jobs.recent_runs" | snT:"Recent runs" }}</span><strong>{{ overview.totals.recent_runs }}</strong></article>
          <article><span>{{ "jobs.failed_runs" | snT:"Failed runs" }}</span><strong [class.danger]="overview.totals.failed_runs > 0">{{ overview.totals.failed_runs }}</strong></article>
          <article><span>{{ "jobs.running" | snT:"Running" }}</span><strong>{{ overview.totals.running_runs }}</strong></article>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div><div class="eyebrow">{{ "jobs.operations" | snT:"Operations" }}</div><h2>{{ "jobs.available" | snT:"Available jobs" }}</h2></div>
            <button (click)="reload()" [disabled]="loading">{{ "jobs.refresh" | snT:"Refresh" }}</button>
          </div>

          <div class="jobs">
            <article class="job" *ngFor="let job of overview.jobs" (dblclick)="showJob(job)">
              <div>
                <div class="category">{{ job.category }}</div>
                <h3>{{ job.name }}</h3>
                <p>{{ job.description }}</p>
                <small>
                  {{ "jobs.last_run" | snT:"Last run" }}: {{ job.last_run_at ? (job.last_run_at | date:'medium') : ("jobs.never" | snT:"never") }}
                  <span *ngIf="job.last_duration_ms !== null"> · {{ job.last_duration_ms }} {{ "jobs.milliseconds" | snT:"ms" }}</span>
                </small>
              </div>
              <div class="job-actions">
                <span class="status" [class.success]="job.last_status === 'success'" [class.failed]="job.last_status === 'failed'">
                  {{ job.last_status ? statusLabel(job.last_status) : ('jobs.not_run' | snT:'not run') }}
                </span>
                <button class="secondary" (click)="showJob(job)">
                  {{ "jobs.view_details" | snT:"View details" }}
                </button>
                <button (click)="run(job)" [disabled]="runningKey === job.key">
                  {{ runningKey === job.key ? ('jobs.running_now' | snT:'Running…') : ('jobs.run_now' | snT:'Run now') }}
                </button>
              </div>
            </article>
          </div>
        </section>

        <section class="panel">
          <div class="eyebrow">{{ "jobs.history" | snT:"History" }}</div>
          <h2>{{ "jobs.recent_executions" | snT:"Recent executions" }}</h2>
          <div class="table-wrap">
            <table>
              <thead><tr><th>{{ "jobs.job" | snT:"Job" }}</th><th>{{ "jobs.status" | snT:"Status" }}</th><th>{{ "jobs.trigger" | snT:"Trigger" }}</th><th>{{ "jobs.duration" | snT:"Duration" }}</th><th>{{ "jobs.finished" | snT:"Finished" }}</th><th>{{ "jobs.result" | snT:"Result" }}</th></tr></thead>
              <tbody>
                <tr *ngFor="let run of overview.recent_runs" class="clickable" (click)="showRun(run)">
                  <td>{{ run.job_key }}</td>
                  <td><span class="status" [class.success]="run.status === 'success'" [class.failed]="run.status === 'failed'">{{ statusLabel(run.status) }}</span></td>
                  <td>{{ triggerLabel(run.trigger) }}</td>
                  <td>{{ run.duration_ms ?? '—' }}<span *ngIf="run.duration_ms !== null"> {{ "jobs.milliseconds" | snT:"ms" }}</span></td>
                  <td>{{ run.finished_at ? (run.finished_at | date:'medium') : '—' }}</td>
                  <td><code>{{ run.error_message || formatResult(run.result) }}</code></td>
                </tr>
                <tr *ngIf="!overview.recent_runs.length"><td colspan="6" class="empty">{{ "jobs.empty" | snT:"No jobs have been run yet." }}</td></tr>
              </tbody>
            </table>
          </div>
        </section>
      </ng-container>
    </sn-shell>
  `,
  styles: [`
    .notice,.panel,.health-grid article,.summary-grid article{border:1px solid var(--line);background:rgba(16,22,38,.72);border-radius:18px}
    .notice{padding:1rem;margin-bottom:1rem}.error{color:#ff9baa;border-color:rgba(255,80,100,.45)}
    .health-grid,.summary-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1rem;margin-bottom:1rem}
    article{padding:1rem}.health-grid article,.summary-grid article{display:grid;gap:.35rem}.health-grid span,.summary-grid span,small,p{color:var(--muted)}
    strong{font-size:1.35rem}.summary-grid strong{font-size:1.8rem}.ok{color:#72e6a1}.danger{color:#ff8193}
    .panel{padding:1.2rem;margin-top:1rem}.panel-head{display:flex;justify-content:space-between;align-items:center;gap:1rem}
    .eyebrow,.category{text-transform:uppercase;letter-spacing:.12em;color:var(--primary);font-size:.72rem}.category{margin-bottom:.35rem}
    h2,h3{margin:.2rem 0}.jobs{display:grid;gap:.8rem;margin-top:1rem}.job{border:1px solid var(--line);border-radius:14px;display:flex;justify-content:space-between;gap:1rem;align-items:center}
    .job p{margin:.45rem 0}.job-actions{display:flex;align-items:center;gap:.7rem;flex-wrap:wrap;justify-content:flex-end}
    button{border:1px solid var(--line);background:var(--primary-soft);color:var(--text);padding:.65rem .9rem;border-radius:10px}button:disabled{opacity:.55}
    .status{display:inline-block;padding:.3rem .55rem;border-radius:999px;border:1px solid var(--line);font-size:.75rem;text-transform:uppercase}.status.success{color:#72e6a1}.status.failed{color:#ff8193}
    .table-wrap{overflow:auto;margin-top:1rem}table{width:100%;border-collapse:collapse;min-width:850px}th,td{text-align:left;padding:.75rem;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-size:.75rem;text-transform:uppercase}code{display:block;max-width:420px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#cbd4ff}.empty{text-align:center;color:var(--muted)}.clickable{cursor:pointer}.clickable:hover{background:rgba(255,255,255,.025)}
    @media(max-width:900px){.health-grid,.summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.job{align-items:flex-start;flex-direction:column}.job-actions{justify-content:flex-start}}
    @media(max-width:560px){.health-grid,.summary-grid{grid-template-columns:1fr}}
  `],
})
export class JobsCenterComponent implements OnInit {
  overview: JobsOverview | null = null;
  loading = true;
  error = '';
  runningKey = '';

  constructor(private readonly jobs: JobsService, private readonly i18n: TranslationService, private readonly modal: ModalService, private readonly toast: ToastService) {}

  ngOnInit(): void { this.reload(); }

  reload(): void {
    this.loading = true;
    this.error = '';
    this.jobs.overview().subscribe({
      next: (value) => { this.overview = value; this.loading = false; },
      error: () => { this.error = this.i18n.t('jobs.load_error', 'Unable to load Jobs Center. SuperAdmin access is required.'); this.loading = false; },
    });
  }

  run(job: JobDefinition): void {
    this.runningKey = job.key;
    this.error = '';
    this.jobs.run(job.key).subscribe({
      next: () => {
        this.runningKey = '';
        this.toast.success(this.i18n.t('ui.success','Completed'), this.i18n.t('jobs.started_success','Job started successfully.'));
        this.reload();
      },
      error: () => {
        this.runningKey = '';
        this.error = this.i18n.t('jobs.start_error', 'Job {name} failed to start.').replace('{name}', job.name);
        this.toast.error(this.i18n.t('ui.error','Operation failed'), this.i18n.t('jobs.start_failed','Unable to start job.'));
      },
    });
  }


  showJob(job: JobDefinition): void {
    this.modal.details(
      this.i18n.t('jobs.definition_details', 'Job definition'),
      [
        { label: this.i18n.t('jobs.key', 'Key'), value: job.key, code: true },
        { label: this.i18n.t('jobs.category', 'Category'), value: job.category },
        { label: this.i18n.t('jobs.last_status', 'Last status'), value: job.last_status ? this.statusLabel(job.last_status) : this.i18n.t('jobs.not_run', 'not run') },
        { label: this.i18n.t('jobs.last_run', 'Last run'), value: job.last_run_at || '—' },
        { label: this.i18n.t('jobs.duration', 'Duration'), value: job.last_duration_ms === null ? '—' : `${job.last_duration_ms} ${this.i18n.t('jobs.milliseconds','ms')}` },
        { label: this.i18n.t('jobs.description', 'Description'), value: job.description || '—', wide: true },
      ],
      {
        message: job.name,
        closeLabel: this.i18n.t('ui.close', 'Close'),
      },
    );
  }

  showRun(run: any): void {
    const raw = JSON.stringify(run.result || {}, null, 2);
    this.modal.details(
      this.i18n.t('jobs.details', 'Execution details'),
      [
        { label: this.i18n.t('jobs.job', 'Job'), value: run.job_key, code: true },
        { label: this.i18n.t('jobs.status', 'Status'), value: this.statusLabel(run.status) },
        { label: this.i18n.t('jobs.trigger', 'Trigger'), value: this.triggerLabel(run.trigger) },
        { label: this.i18n.t('jobs.duration', 'Duration'), value: run.duration_ms === null ? '—' : `${run.duration_ms} ${this.i18n.t('jobs.milliseconds','ms')}` },
        { label: this.i18n.t('jobs.started', 'Started'), value: run.started_at || '—' },
        { label: this.i18n.t('jobs.finished', 'Finished'), value: run.finished_at || '—' },
        { label: this.i18n.t('jobs.error', 'Error'), value: run.error_message || '—', wide: true, code: true },
      ],
      {
        raw,
        closeLabel: this.i18n.t('ui.close', 'Close'),
        copyLabel: this.i18n.t('ui.copy', 'Copy'),
        danger: run.status === 'failed',
      },
    );
  }

  statusLabel(value: string): string {
    const key = value?.toLowerCase();
    if (key === 'success') return this.i18n.t('jobs.status_success', 'Success');
    if (key === 'failed') return this.i18n.t('jobs.status_failed', 'Failed');
    if (key === 'running') return this.i18n.t('jobs.status_running', 'Running');
    if (key === 'pending') return this.i18n.t('jobs.status_pending', 'Pending');
    return value;
  }

  triggerLabel(value: string): string {
    const key = value?.toLowerCase();
    if (key === 'manual') return this.i18n.t('jobs.trigger_manual', 'Manual');
    if (key === 'scheduler') return this.i18n.t('jobs.trigger_scheduler', 'Scheduler');
    if (key === 'system') return this.i18n.t('jobs.trigger_system', 'System');
    return value;
  }

  formatResult(result: Record<string, unknown>): string {
    return JSON.stringify(result);
  }
}
