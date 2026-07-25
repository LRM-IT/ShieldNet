import {
  Component,
  OnInit,
  signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';

import { DashboardService } from '../core/dashboard.service';
import { ShellComponent } from '../shared/shell.component';
import { TranslatePipe } from '../core/translate.pipe';
import { TranslationService } from '../core/translation.service';

@Component({
  standalone: true,
  imports: [
    RouterLink,
    ShellComponent,
    TranslatePipe,
  ],
  template: `
    <sn-shell [title]="'dashboard.title' | snT:'ShieldNet Dashboard'">
      <section class="hero card">
        <div>
          <div class="muted">{{ "dashboard.workspace" | snT:"Administration workspace" }}</div>
          <h2>{{ "dashboard.heading" | snT:"Discord infrastructure overview" }}</h2>
          <p class="muted">
            {{ "dashboard.description" | snT:"Live service status, verification queues and server activity." }}
          </p>
        </div>

        <button
          class="btn secondary"
          [disabled]="loading()"
          (click)="load()"
        >
          {{ loading() ? ('dashboard.refreshing' | snT:'Refreshing…') : ('dashboard.refresh' | snT:'Refresh') }}
        </button>
      </section>

      @if (error()) {
        <section class="card error">
          {{ error() }}
        </section>
      }

      @if (overview()) {
        <section class="service-grid">
          <article class="card service">
            <span class="indicator online"></span>
            <div>
              <strong>{{ "dashboard.backend" | snT:"Backend" }}</strong>
              <span>{{ overview().services.backend }}</span>
            </div>
          </article>

          <article class="card service">
            <span class="indicator online"></span>
            <div>
              <strong>PostgreSQL</strong>
              <span>{{ overview().services.database }}</span>
            </div>
          </article>

          <article class="card service">
            <span
              class="indicator"
              [class.online]="overview().totals.verification_failed === 0"
              [class.warning]="overview().totals.verification_failed > 0"
            ></span>
            <div>
              <strong>{{ "dashboard.verification" | snT:"Verification" }}</strong>
              <span>
                {{ overview().totals.verification_failed }}
                {{ "dashboard.failed" | snT:"failed" }}
              </span>
            </div>
          </article>
        </section>

        <section class="metric-grid">
          <article class="card metric">
            <strong>{{ overview().totals.guilds }}</strong>
            <span>{{ "dashboard.discord_servers" | snT:"Discord servers" }}</span>
          </article>

          <article class="card metric">
            <strong>{{ overview().totals.members }}</strong>
            <span>{{ "dashboard.active_members" | snT:"Active members" }}</span>
          </article>

          <article class="card metric">
            <strong>
              {{ overview().totals.verification_pending }}
            </strong>
            <span>{{ "dashboard.pending_verification" | snT:"Pending verification" }}</span>
          </article>

          <article class="card metric">
            <strong>{{ overview().totals.audit_24h }}</strong>
            <span>{{ "dashboard.audit_24h" | snT:"Audit events / 24h" }}</span>
          </article>
        </section>

        <div class="section-heading">
          <div>
            <h2>{{ "dashboard.servers" | snT:"Servers" }}</h2>
            <div class="muted">
              {{ "dashboard.generated" | snT:"Generated" }} {{ overview().generated_at }}
            </div>
          </div>
        </div>

        @if (overview().guilds.length === 0) {
          <section class="card empty">
            {{ "dashboard.empty" | snT:"No active server access was found." }}
          </section>
        } @else {
          <section class="guild-grid">
            @for (
              guild of overview().guilds;
              track guild.guild_id
            ) {
              <article class="guild card">
                <div class="guild-heading">
                  @if (guild.icon_url) {
                    <img [src]="guild.icon_url" alt="">
                  } @else {
                    <div class="placeholder">
                      {{ guild.name.slice(0, 1) }}
                    </div>
                  }

                  <div class="guild-name">
                    <h3>{{ guild.name }}</h3>
                    <span class="muted">
                      {{ guild.guild_id }}
                    </span>
                  </div>

                  <span
                    class="badge"
                    [class.online]="guild.bot_status === 'online'"
                    [class.warning]="guild.bot_status !== 'online'"
                  >
                    {{ guild.bot_status }}
                  </span>
                </div>

                <div class="guild-metrics">
                  <div>
                    <strong>{{ guild.member_count }}</strong>
                    <span>{{ "dashboard.members" | snT:"Members" }}</span>
                  </div>
                  <div>
                    <strong>
                      {{ guild.verification_pending }}
                    </strong>
                    <span>{{ "dashboard.pending" | snT:"Pending" }}</span>
                  </div>
                  <div>
                    <strong>
                      {{ guild.verification_failed }}
                    </strong>
                    <span>{{ "dashboard.failed" | snT:"Failed" }}</span>
                  </div>
                  <div>
                    <strong>{{ guild.audit_24h }}</strong>
                    <span>{{ "dashboard.audit" | snT:"Audit 24h" }}</span>
                  </div>
                </div>

                <div class="actions">
                  <a
                    class="btn secondary"
                    [routerLink]="[
                      '/guild',
                      guild.guild_id
                    ]"
                  >
                    {{ "dashboard.open_server" | snT:"Open server" }}
                  </a>

                  <a
                    class="btn secondary"
                    [routerLink]="[
                      '/guild',
                      guild.guild_id,
                      'verification'
                    ]"
                  >
                    {{ "dashboard.open_verification" | snT:"Verification" }}
                  </a>

                  <a
                    class="btn secondary"
                    [routerLink]="[
                      '/guild',
                      guild.guild_id,
                      'audit'
                    ]"
                  >
                    {{ "dashboard.open_audit" | snT:"Audit" }}
                  </a>
                </div>
              </article>
            }
          </section>
        }
      }
    </sn-shell>
  `,
  styles: [`
    .hero {
      padding: 1.4rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
    }

    .hero h2 {
      margin: .35rem 0;
    }

    .hero p {
      margin: 0;
    }

    .service-grid,
    .metric-grid,
    .guild-grid {
      display: grid;
      gap: 1rem;
    }

    .service-grid {
      margin-top: 1rem;
      grid-template-columns: repeat(3, 1fr);
    }

    .metric-grid {
      margin-top: 1rem;
      grid-template-columns: repeat(4, 1fr);
    }

    .service {
      padding: 1rem;
      display: flex;
      align-items: center;
      gap: .8rem;
    }

    .service div,
    .metric {
      display: grid;
      gap: .25rem;
    }

    .service span,
    .metric span {
      color: var(--muted);
    }

    .indicator {
      width: .75rem;
      height: .75rem;
      border-radius: 999px;
      background: #77808f;
      box-shadow: 0 0 14px currentColor;
    }

    .indicator.online,
    .badge.online {
      color: #74e9b3;
      background: rgba(75, 214, 155, .16);
    }

    .indicator.warning,
    .badge.warning {
      color: #ffd27a;
      background: rgba(255, 178, 66, .16);
    }

    .metric {
      padding: 1.1rem;
    }

    .metric strong {
      font-size: 1.8rem;
    }

    .section-heading {
      margin: 2rem 0 1rem;
    }

    .section-heading h2 {
      margin: 0 0 .25rem;
    }

    .guild-grid {
      grid-template-columns:
        repeat(auto-fit, minmax(320px, 1fr));
    }

    .guild {
      padding: 1.1rem;
      display: grid;
      gap: 1rem;
    }

    .guild-heading {
      display: flex;
      align-items: center;
      gap: .8rem;
    }

    .guild-heading img,
    .placeholder {
      width: 3.2rem;
      height: 3.2rem;
      border-radius: 14px;
    }

    .guild-heading img {
      object-fit: cover;
    }

    .placeholder {
      display: grid;
      place-items: center;
      background: var(--primary-soft);
      color: var(--primary);
      font-weight: 900;
    }

    .guild-name {
      flex: 1;
    }

    .guild-name h3 {
      margin: 0 0 .2rem;
    }

    .badge {
      padding: .3rem .55rem;
      border-radius: 999px;
      text-transform: uppercase;
      font-size: .7rem;
    }

    .guild-metrics {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: .55rem;
    }

    .guild-metrics div {
      padding: .7rem;
      display: grid;
      gap: .2rem;
      background: var(--panel-2);
      border-radius: 10px;
    }

    .guild-metrics span {
      color: var(--muted);
      font-size: .72rem;
    }

    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: .55rem;
    }

    .error,
    .empty {
      margin-top: 1rem;
      padding: 1rem;
    }

    .error {
      color: #ffd9de;
    }

    @media (max-width: 850px) {
      .service-grid,
      .metric-grid {
        grid-template-columns: repeat(2, 1fr);
      }
    }

    @media (max-width: 600px) {
      .hero {
        align-items: stretch;
        flex-direction: column;
      }

      .service-grid,
      .metric-grid {
        grid-template-columns: 1fr;
      }

      .guild-metrics {
        grid-template-columns: repeat(2, 1fr);
      }
    }
  `],
})
export class DashboardComponent implements OnInit {
  readonly overview = signal<any | null>(null);
  readonly loading = signal(false);
  readonly error = signal('');

  constructor(
    private readonly dashboardService: DashboardService,
  ) {}

  async ngOnInit(): Promise<void> {
    await this.load();
  }

  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set('');

    try {
      this.overview.set(
        await this.dashboardService.overview(),
      );
    } catch {
      this.error.set(
        this.i18n.t('dashboard.load_error_full','Unable to load the ShieldNet dashboard.'),
      );
    } finally {
      this.loading.set(false);
    }
  }
}
