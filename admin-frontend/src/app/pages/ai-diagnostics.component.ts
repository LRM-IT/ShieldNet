import { HttpClient } from '@angular/common/http';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ShellComponent } from '../shared/shell.component';
import { TranslatePipe } from '../core/translate.pipe';

interface Settings { enabled: boolean; model: string; api_key_saved: boolean }
interface Snapshot { overall_status: string; summary: Record<string, number>; checks: {name: string; category: string; status: string}[]; jobs: {key: string; last_status: string | null}[]; recent_failed_runs: {job_key: string}[]; runtime: Record<string, unknown> }

@Component({
  standalone: true,
  imports: [FormsModule, ShellComponent, TranslatePipe],
  template: `
    <sn-shell [title]="'ai_diagnostics.title' | snT:'AI diagnostics'">
      <div class="page">
        <header><span class="eyebrow">SYSTEM · SUPERADMIN</span><h2>{{'ai_diagnostics.title' | snT:'AI diagnostics'}}</h2>
          <p>{{'ai_diagnostics.intro' | snT:'Review platform checks and failed jobs with OpenAI. Only status metadata is sent; actions require your confirmation.'}}</p></header>
        @if (error) { <div class="notice error">{{error}}</div> }
        @if (message) { <div class="notice">{{message}}</div> }
        <section class="panel">
          <h3>{{'ai_diagnostics.settings' | snT:'Global OpenAI connection'}}</h3>
          <div class="grid">
            <label>{{'ai_diagnostics.model' | snT:'Model'}}<input [(ngModel)]="settings.model" placeholder="gpt-5" /></label>
            <label>{{'ai_diagnostics.key' | snT:'API key'}}<input type="password" [(ngModel)]="apiKey" autocomplete="new-password" [placeholder]="settings.api_key_saved ? '•••••••• (saved)' : 'sk-…'" /></label>
          </div>
          <div class="actions"><label class="toggle"><input type="checkbox" [(ngModel)]="settings.enabled" /> {{'ai_diagnostics.enabled' | snT:'Enable analysis'}}</label>
            <span>{{settings.api_key_saved ? ('ai_diagnostics.key_saved' | snT:'Key saved securely') : ('ai_diagnostics.key_missing' | snT:'API key required')}}</span>
            <button (click)="save()" [disabled]="busy">{{'ai_diagnostics.save' | snT:'Save settings'}}</button></div>
        </section>
        <section class="panel">
          <div class="actions"><h3>{{'ai_diagnostics.snapshot' | snT:'System status'}}</h3><button class="secondary" (click)="refresh()" [disabled]="busy">{{'ai_diagnostics.refresh' | snT:'Refresh checks'}}</button></div>
          @if (snapshot) {
            <p><strong>{{snapshot.overall_status}}</strong> · {{snapshot.summary['ok'] || 0}} OK · {{snapshot.summary['warning'] || 0}} warning · {{snapshot.summary['failed'] || 0}} failed</p>
            <div class="checks">@for (check of snapshot.checks; track check.name) { <div><span>{{check.name}}</span><b [class.bad]="check.status === 'failed'">{{check.status}}</b></div> }</div>
          }
        </section>
        <section class="panel">
          <h3>{{'ai_diagnostics.analysis' | snT:'Analyze problems'}}</h3>
          <p>{{'ai_diagnostics.hint' | snT:'Ask about failed checks or incomplete jobs. The assistant provides recommendations and cannot run arbitrary commands.'}}</p>
          <textarea [(ngModel)]="question" rows="3" [placeholder]="'ai_diagnostics.question' | snT:'What needs attention?'" maxlength="1000"></textarea>
          <div class="actions"><button (click)="analyze()" [disabled]="busy || !settings.enabled || !settings.api_key_saved">{{busy ? ('ai_diagnostics.working' | snT:'Working…') : ('ai_diagnostics.run' | snT:'Analyze with AI')}}</button></div>
          @if (analysis) { <div class="answer">{{analysis}}</div> }
          @if (repairable.length) { <h4>{{'ai_diagnostics.repair' | snT:'Retry failed safe jobs'}}</h4>
            <p>{{'ai_diagnostics.repair_hint' | snT:'Each action reruns one read-only snapshot job and is recorded in the audit trail.'}}</p>
            <div class="actions">@for (job of repairable; track job) { <button class="secondary" (click)="retry(job)" [disabled]="busy">{{'ai_diagnostics.retry' | snT:'Retry'}} {{job}}</button> }</div> }
        </section>
      </div>
    </sn-shell>
  `,
  styles: [`
    .page{display:grid;gap:1.25rem;max-width:1200px}.eyebrow{color:var(--accent);font-size:.75rem;letter-spacing:.14em;font-weight:800}h2{font-size:2rem;margin:.5rem 0}h3{margin:0 0 .7rem}p{color:var(--muted);line-height:1.55}.panel,.notice{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:1.25rem}.error{color:var(--danger)}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem}.grid label{display:grid;gap:.5rem;font-weight:700}input:not([type=checkbox]),textarea{width:100%;box-sizing:border-box;background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:12px;padding:.9rem;font:inherit}textarea{resize:vertical}.actions{display:flex;align-items:center;flex-wrap:wrap;gap:.75rem;margin-top:1rem}.actions h3{margin:0 auto 0 0}.actions span{color:var(--muted)}.toggle{display:flex;align-items:center;gap:.6rem;margin-right:auto}.toggle input{width:18px;height:18px;accent-color:var(--accent)}button{border:0;border-radius:11px;padding:.8rem 1rem;background:var(--accent);color:var(--button-text,#071c20);font-weight:800;cursor:pointer}button.secondary{background:transparent;color:var(--text);border:1px solid var(--line)}button:disabled{opacity:.5;cursor:default}.checks{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.5rem}.checks>div{display:flex;justify-content:space-between;gap:1rem;padding:.65rem;border:1px solid var(--line);border-radius:9px}.checks b{color:var(--success)}.checks b.bad{color:var(--danger)}.answer{white-space:pre-wrap;line-height:1.6;margin-top:1rem;padding:1.2rem;background:var(--surface,#101b24);border:1px solid var(--line);border-radius:12px}@media(max-width:700px){.grid,.checks{grid-template-columns:1fr}.page{gap:.8rem}}
  `]
})
export class AiDiagnosticsComponent implements OnInit {
  private readonly base = '/api/v1/platform/ai-diagnostics';
  settings: Settings = { enabled: false, model: 'gpt-5', api_key_saved: false };
  apiKey = ''; question = ''; snapshot: Snapshot | null = null; analysis = ''; repairable: string[] = [];
  error = ''; message = ''; busy = false;
  constructor(private readonly http: HttpClient) {}
  ngOnInit(): void { this.http.get<Settings>(`${this.base}/settings`).subscribe({next: s => this.settings = s, error: e => this.fail(e)}); this.refresh(); }
  private fail(e: any): void { this.error = typeof e?.error?.detail === 'string' ? e.error.detail : 'Request failed'; this.busy = false; }
  refresh(): void { this.error = ''; this.http.get<Snapshot>(`${this.base}/snapshot`).subscribe({next: s => {this.snapshot = s; this.repairable = s.jobs.filter(j => j.last_status === 'failed').map(j => j.key);}, error: e => this.fail(e)}); }
  save(): void { this.busy = true; this.error = ''; this.http.put<Settings>(`${this.base}/settings`, {...this.settings, api_key: this.apiKey || null}).subscribe({next: s => {this.settings = s; this.apiKey = ''; this.message = 'Settings saved'; this.busy = false;}, error: e => this.fail(e)}); }
  analyze(): void { this.busy = true; this.error = ''; this.message = ''; this.http.post<{analysis: string; snapshot: Snapshot; repairable_jobs: string[]}>(`${this.base}/analyze`, {question: this.question}).subscribe({next: r => {this.analysis = r.analysis; this.snapshot = r.snapshot; this.repairable = r.repairable_jobs; this.busy = false;}, error: e => this.fail(e)}); }
  retry(job: string): void { if (!window.confirm(`Retry ${job}?`)) return; this.busy = true; this.error = ''; this.http.post<{status: string}>(`${this.base}/repair`, {job_key: job}).subscribe({next: r => {this.message = `${job}: ${r.status}`; this.busy = false; this.refresh();}, error: e => this.fail(e)}); }
}
