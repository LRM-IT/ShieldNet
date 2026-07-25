import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';

import { SecurityFinding, SecurityService, SecuritySummary } from '../core/security.service';
import { ShellComponent } from '../shared/shell.component';
import { TranslatePipe } from '../core/translate.pipe';
import { TranslationService } from '../core/translation.service';

@Component({
  selector: 'sn-security',
  standalone: true,
  imports: [CommonModule, ShellComponent, TranslatePipe],
  template: `
    <sn-shell [title]="'security.title' | snT:'Security Center'">
      <div class="notice" *ngIf="loading">{{ 'security.loading' | snT:'Loading latest security snapshot…' }}</div>
      <div class="notice error" *ngIf="error">{{ error }}</div>

      <ng-container *ngIf="summary">
        <section class="hero">
          <div>
            <div class="eyebrow">{{ 'security.configuration_risk' | snT:'Configuration risk' }}</div>
            <h2>{{ riskLabel(summary.risk_score) }}</h2>
            <p>{{ 'security.description' | snT:'ShieldNet analyses Discord roles, channels, webhooks and the bot\'s effective permissions.' }}</p>
          </div>
          <div class="score" [class.high]="summary.risk_score >= 50" [class.critical]="summary.risk_score >= 75">
            <strong>{{ summary.risk_score }}</strong><span>/100</span>
          </div>
        </section>

        <section class="summary-grid">
          <article><span>{{ 'security.critical' | snT:'Critical' }}</span><strong class="critical-text">{{ count('critical') }}</strong></article>
          <article><span>{{ 'security.high' | snT:'High' }}</span><strong class="high-text">{{ count('high') }}</strong></article>
          <article><span>{{ 'security.medium' | snT:'Medium' }}</span><strong>{{ count('medium') }}</strong></article>
          <article><span>{{ 'security.low' | snT:'Low' }}</span><strong>{{ count('low') }}</strong></article>
          <article><span>{{ 'security.roles_scanned' | snT:'Roles scanned' }}</span><strong>{{ summary.role_count }}</strong></article>
          <article><span>{{ 'security.channels_scanned' | snT:'Channels scanned' }}</span><strong>{{ summary.channel_count }}</strong></article>
          <article><span>{{ 'security.webhooks_scanned' | snT:'Webhooks scanned' }}</span><strong>{{ summary.webhook_count }}</strong></article>
          <article><span>{{ 'security.last_scan' | snT:'Last scan' }}</span><strong class="date">{{ summary.collected_at ? (summary.collected_at | date:'short') : ('security.waiting_bot' | snT:'Waiting for bot') }}</strong></article>
        </section>

        <section class="panel" *ngIf="!summary.snapshot_id">
          <div class="eyebrow">{{ 'security.no_data' | snT:'No data yet' }}</div>
          <h2>{{ 'security.waiting_snapshot' | snT:'Waiting for the first bot snapshot' }}</h2>
          <p>{{ 'security.snapshot_help' | snT:'The ShieldNet bot sends a security snapshot every 15 minutes. Ensure the bot is online and the backend service token matches.' }}</p>
        </section>

        <section class="panel" *ngIf="summary.snapshot_id">
          <div class="panel-head">
            <div><div class="eyebrow">{{ 'security.findings' | snT:'Findings' }}</div><h2>{{ 'security.detected_risks' | snT:'Detected risks' }}</h2></div>
            <button (click)="reload()" [disabled]="loading">{{ 'security.refresh' | snT:'Refresh' }}</button>
          </div>

          <div class="findings">
            <article class="finding" *ngFor="let item of summary.findings" [attr.data-severity]="item.severity">
              <div class="finding-head">
                <span class="badge">{{ item.severity }}</span>
                <span class="category">{{ item.category }}</span>
              </div>
              <h3>{{ findingText(item.title) }}</h3>
              <p>{{ findingText(item.description) }}</p>
              <div class="resource" *ngIf="item.resource_name || item.resource_id">
                {{ item.resource_type || ('security.resource' | snT:'resource') }}: <b>{{ item.resource_name || item.resource_id }}</b>
              </div>
              <div class="recommendation" *ngIf="item.recommendation">
                <strong>{{ 'security.recommended_action' | snT:'Recommended action' }}</strong>
                <span>{{ findingText(item.recommendation) }}</span>
              </div>
            </article>
          </div>
        </section>
      </ng-container>
    </sn-shell>
  `,
  styles: [`
    .notice,.hero,.panel,.summary-grid article{border:1px solid var(--line);background:rgba(16,22,38,.72);border-radius:18px}
    .notice{padding:1rem;margin-bottom:1rem}.error{color:#ff9baa;border-color:rgba(255,80,100,.45)}
    .hero{display:flex;justify-content:space-between;align-items:center;gap:1.5rem;padding:1.4rem;margin-bottom:1rem}.hero h2{font-size:2rem;margin:.2rem 0}.hero p{color:var(--muted);margin:0;max-width:720px}
    .eyebrow,.category{text-transform:uppercase;letter-spacing:.12em;color:var(--primary);font-size:.72rem}.score{width:120px;height:120px;border-radius:50%;display:grid;place-content:center;text-align:center;background:conic-gradient(#6f7cff calc(var(--score, 0) * 1%),rgba(255,255,255,.08) 0);border:1px solid var(--line)}
    .score strong{font-size:2.25rem}.score span{color:var(--muted)}.score.high{box-shadow:0 0 30px rgba(255,170,70,.18)}.score.critical{box-shadow:0 0 34px rgba(255,70,95,.28)}
    .summary-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1rem;margin-bottom:1rem}.summary-grid article{padding:1rem;display:grid;gap:.35rem}.summary-grid span{color:var(--muted)}.summary-grid strong{font-size:1.55rem}.summary-grid .date{font-size:1rem}.critical-text{color:#ff6f86}.high-text{color:#ffb86b}
    .panel{padding:1.2rem;margin-top:1rem}.panel-head{display:flex;justify-content:space-between;align-items:center}.panel p{color:var(--muted)}button{border:1px solid var(--line);background:var(--primary-soft);color:var(--text);padding:.65rem .9rem;border-radius:10px}
    .findings{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem;margin-top:1rem}.finding{border:1px solid var(--line);border-radius:15px;padding:1rem;background:rgba(8,12,23,.55)}.finding[data-severity="critical"]{border-color:rgba(255,82,110,.55)}.finding[data-severity="high"]{border-color:rgba(255,175,75,.45)}
    .finding-head{display:flex;justify-content:space-between;gap:.7rem;align-items:center}.badge{padding:.3rem .55rem;border-radius:999px;border:1px solid var(--line);text-transform:uppercase;font-size:.7rem}.finding h3{margin:.75rem 0 .35rem}.resource{font-size:.85rem;color:var(--muted);margin-top:.7rem}.recommendation{display:grid;gap:.25rem;border-top:1px solid var(--line);padding-top:.75rem;margin-top:.85rem}.recommendation span{color:var(--muted)}
    @media(max-width:900px){.summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.findings{grid-template-columns:1fr}.hero{align-items:flex-start}.score{width:96px;height:96px;flex:0 0 96px}}
    @media(max-width:560px){.summary-grid{grid-template-columns:1fr}.hero{flex-direction:column}.score{width:100%;height:auto;border-radius:14px;padding:1rem;display:flex;justify-content:center;gap:.25rem}}
  `],
})
export class SecurityComponent implements OnInit {
  summary: SecuritySummary | null = null;
  loading = true;
  error = '';
  private guildId = '';

  constructor(
    private readonly route: ActivatedRoute,
    private readonly security: SecurityService,
    private readonly i18n: TranslationService,
  ) {}

  ngOnInit(): void {
    this.guildId = this.route.snapshot.paramMap.get('guildId') || '';
    this.reload();
  }

  reload(): void {
    this.loading = true;
    this.error = '';
    this.security.summary(this.guildId).subscribe({
      next: value => { this.summary = value; this.loading = false; },
      error: () => { this.error = this.i18n.t('security.load_error', 'Unable to load Security Center.'); this.loading = false; },
    });
  }

  count(level: string): number { return Number(this.summary?.counts?.[level] || 0); }


  findingText(value: string | null | undefined): string {
    if (!value) return '';
    const map: Record<string, string> = {
      'Role has broad management permissions': 'security.finding.role_broad_title',
      'Role Admin combines several sensitive permissions.': 'security.finding.role_broad_description',
      'Split responsibilities and remove permissions that are not required.': 'security.finding.role_broad_recommendation',
      '@everyone mentions are allowed': 'security.finding.everyone_title',
      'Disable Mention @everyone unless this is intentional.': 'security.finding.everyone_recommendation',
    };
    const key = map[value];
    return key ? this.i18n.t(key, value) : value;
  }

  riskLabel(score: number): string {
    if (score >= 75) return this.i18n.t('security.risk_critical', 'Critical risk');
    if (score >= 50) return this.i18n.t('security.risk_high', 'High risk');
    if (score >= 25) return this.i18n.t('security.risk_moderate', 'Moderate risk');
    if (score > 0) return this.i18n.t('security.risk_low', 'Low risk');
    return this.i18n.t('security.risk_healthy', 'Healthy baseline');
  }
}
