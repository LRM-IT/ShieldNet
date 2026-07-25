import { Component, OnDestroy, OnInit, computed, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { TranslatePipe } from '../core/translate.pipe';

import {
  EnterpriseDashboardOverview,
  EnterpriseDashboardService,
} from '../core/enterprise-dashboard.service';
import { ShellComponent } from '../shared/shell.component';

@Component({
  standalone: true,
  imports: [ShellComponent, RouterLink, DatePipe, DecimalPipe, TranslatePipe],
  template: `
    <sn-shell [title]="'dashboard.title' | snT:'Command Center'">
      <section class="command-hero">
        <div class="hero-copy">
          <div class="eyebrow">{{ 'dashboard.global_fabric' | snT:'GLOBAL OPERATIONS FABRIC' }}</div>
          <h2>{{ 'dashboard.under_control' | snT:'Infrastructure under control.' }}</h2>
          <p>
            {{ 'dashboard.description' | snT:'Unified visibility across Discord estates, workers, security,             automation and runtime services.' }}
          </p>

          <div class="hero-links">
            <a routerLink="/platform/operations">{{ 'dashboard.open_operations' | snT:'Open live operations' }} <span>→</span></a>
            <a routerLink="/platform/doctor">{{ 'dashboard.run_doctor' | snT:'Run platform doctor' }} <span>↗</span></a>
          </div>
        </div>

        <div class="hero-status">
          <div class="status-ring" [class]="data()?.overall_status || 'loading'">
            <div>
              <small>{{ 'dashboard.platform' | snT:'PLATFORM' }}</small>
              <strong>{{ data()?.overall_status || ('dashboard.loading' | snT:'loading') }}</strong>
            </div>
          </div>

          <button type="button" class="refresh" [disabled]="loading()" (click)="load()">
            {{ loading() ? ('dashboard.synchronizing' | snT:'Synchronizing…') : ('dashboard.synchronize' | snT:'Synchronize') }}
          </button>
        </div>
      </section>

      @if (error()) {
        <section class="alert-panel">{{ error() }}</section>
      }

      @if (data(); as overview) {
        <section class="system-strip">
          <div class="strip-label">
            <span class="live-dot"></span>
            {{ 'dashboard.core_fabric' | snT:'CORE FABRIC' }}
          </div>

          <article>
            <span>{{ "enterprise_dashboard.api" | snT:"API" }}</span>
            <strong>{{ 'dashboard.online' | snT:'ONLINE' }}</strong>
            <small>{{ 'dashboard.backend_plane' | snT:'Backend control plane' }}</small>
          </article>

          <article>
            <span>{{ "enterprise_dashboard.postgresql" | snT:"POSTGRESQL" }}</span>
            <strong>{{ overview.components.postgresql.latency_ms }} MS</strong>
            <small>{{ 'dashboard.db_latency' | snT:'Primary database latency' }}</small>
          </article>

          <article>
            <span>{{ "enterprise_dashboard.valkey" | snT:"VALKEY" }}</span>
            <strong [class.warn]="overview.components.valkey.status !== 'online'">
              {{ overview.components.valkey.status }}
            </strong>
            <small>{{ overview.components.valkey.latency_ms ?? '—' }} {{ 'dashboard.latency' | snT:'latency' }}</small>
          </article>

          @for (worker of overview.workers.slice(0, 2); track worker.name) {
            <article>
              <span>{{ worker.type }}</span>
              <strong [class.warn]="worker.status !== 'online'">{{ worker.status }}</strong>
              <small>{{ worker.name }}</small>
            </article>
          }
        </section>

        <section class="overview-grid">
          <article class="primary-metric panel">
            <div class="panel-index">01</div>
            <div>
              <span>{{ 'dashboard.managed_servers' | snT:'MANAGED SERVERS' }}</span>
              <strong>{{ overview.metrics['guilds'] | number }}</strong>
              <small>{{ overview.scope }} {{ 'dashboard.infrastructure_scope' | snT:'infrastructure scope' }}</small>
            </div>
            <div class="metric-trend">{{ "dashboard.active" | snT:"ACTIVE" }}</div>
          </article>

          <article class="metric panel">
            <div class="panel-index">02</div>
            <span>{{ 'dashboard.active_members' | snT:'ACTIVE MEMBERS' }}</span>
            <strong>{{ overview.metrics['active_members'] | number }}</strong>
            <small>{{ overview.metrics['members'] | number }} {{ 'dashboard.identities_indexed' | snT:'identities indexed' }}</small>
          </article>

          <article class="metric panel">
            <div class="panel-index">03</div>
            <span>{{ 'dashboard.open_cases' | snT:'OPEN CASES' }}</span>
            <strong>{{ overview.metrics['open_cases'] | number }}</strong>
            <small [class.danger]="overview.metrics['overdue_cases'] > 0">
              {{ overview.metrics['overdue_cases'] | number }} {{ 'dashboard.overdue' | snT:'overdue' }}
            </small>
          </article>

          <article class="metric panel">
            <div class="panel-index">04</div>
            <span>{{ 'dashboard.security_risks' | snT:'SECURITY RISKS' }}</span>
            <strong [class.danger]="overview.metrics['security_risks'] > 0">
              {{ overview.metrics['security_risks'] | number }}
            </strong>
            <small>{{ 'dashboard.high_critical' | snT:'High and critical signals' }}</small>
          </article>

          <article class="metric panel">
            <div class="panel-index">05</div>
            <span>{{ 'dashboard.open_alerts' | snT:'OPEN ALERTS' }}</span>
            <strong>{{ overview.metrics['open_alerts'] | number }}</strong>
            <small>{{ overview.metrics['critical_alerts'] | number }} {{ 'dashboard.critical' | snT:'critical' }}</small>
          </article>

          <article class="metric panel">
            <div class="panel-index">06</div>
            <span>{{ 'dashboard.queue_depth' | snT:'QUEUE DEPTH' }}</span>
            <strong>{{ overview.metrics['queue_depth'] | number }}</strong>
            <small>{{ 'dashboard.pending_operations' | snT:'Pending Discord operations' }}</small>
          </article>
        </section>

        <section class="operations-grid">
          <article class="panel operations-panel">
            <div class="section-title">
              <div>
                <span>{{ 'dashboard.operational_access' | snT:'OPERATIONAL ACCESS' }}</span>
                <h3>{{ 'dashboard.control_surfaces' | snT:'Control surfaces' }}</h3>
              </div>
              <small>{{ 'dashboard.select_workspace' | snT:'SELECT WORKSPACE' }}</small>
            </div>

            <div class="action-grid">
              <a routerLink="/platform/operations">
                <b>{{ 'dashboard.live_ops' | snT:'LIVE OPS' }}</b>
                <strong>{{ 'dashboard.operations_stream' | snT:'Operations stream' }}</strong>
                <span>{{ 'dashboard.operations_desc' | snT:'Runtime events, queue state and active processes.' }}</span>
                <i>01</i>
              </a>

              <a routerLink="/platform/plugins">
                <b>{{ 'shell.plugin_fabric' | snT:'PLUGIN FABRIC' }}</b>
                <strong>{{ 'dashboard.runtime_platform' | snT:'Runtime platform' }}</strong>
                <span>{{ 'dashboard.runtime_desc' | snT:'Lifecycle, health, capabilities and execution state.' }}</span>
                <i>02</i>
              </a>

              <a routerLink="/platform/jobs">
                <b>{{ 'dashboard.jobs' | snT:'JOBS' }}</b>
                <strong>{{ 'dashboard.execution_center' | snT:'Execution center' }}</strong>
                <span>{{ 'dashboard.jobs_desc' | snT:'Inspect jobs, failures, retries and service health.' }}</span>
                <i>03</i>
              </a>

              <a routerLink="/platform/access">
                <b>{{ 'dashboard.identity' | snT:'IDENTITY' }}</b>
                <strong>{{ 'dashboard.platform_access' | snT:'Platform access' }}</strong>
                <span>{{ 'dashboard.identity_desc' | snT:'Global roles, permissions and trusted operators.' }}</span>
                <i>04</i>
              </a>
            </div>
          </article>

          <article class="panel telemetry-panel">
            <div class="section-title">
              <div>
                <span>{{ 'dashboard.live_capacity' | snT:'LIVE CAPACITY' }}</span>
                <h3>{{ 'dashboard.telemetry' | snT:'Telemetry' }}</h3>
              </div>
            </div>

            <div class="telemetry-row">
              <span>{{ 'dashboard.valkey_memory' | snT:'Valkey memory' }}</span>
              <strong>{{ formatBytes(overview.components.valkey.memory_bytes) }}</strong>
            </div>
            <div class="telemetry-row">
              <span>{{ 'dashboard.bot_accounts' | snT:'Bot accounts' }}</span>
              <strong>{{ overview.metrics['bots'] | number }}</strong>
            </div>
            <div class="telemetry-row">
              <span>{{ 'dashboard.watchlisted_users' | snT:'Watchlisted users' }}</span>
              <strong>{{ overview.metrics['watchlisted'] | number }}</strong>
            </div>
            <div class="telemetry-row">
              <span>{{ 'dashboard.audit_events' | snT:'Audit events / 24h' }}</span>
              <strong>{{ overview.metrics['audit_24h'] | number }}</strong>
            </div>
            <div class="telemetry-row">
              <span>{{ 'dashboard.successful_jobs' | snT:'Successful jobs / 7d' }}</span>
              <strong>{{ overview.metrics['successful_jobs_7d'] | number }}</strong>
            </div>

            <div class="generated">
              {{ 'dashboard.last_sync' | snT:'LAST SYNC' }} {{ overview.generated_at | date:'mediumTime' }}
            </div>
          </article>
        </section>

        <section class="estate-header">
          <div>
            <span>{{ 'dashboard.discord_estate' | snT:'DISCORD ESTATE' }}</span>
            <h3>{{ 'dashboard.managed_infrastructure' | snT:'Managed infrastructure' }}</h3>
          </div>
          <div class="estate-count">{{ overview.guilds.length }} {{ 'dashboard.nodes' | snT:'NODES' }}</div>
        </section>

        @if (overview.guilds.length === 0) {
          <section class="empty-state panel">
            No Discord servers are available for this operator.
          </section>
        } @else {
          <section class="guild-grid">
            @for (guild of overview.guilds; track guild.guild_id; let index = $index) {
              <article class="guild-node panel">
                <div class="node-index">
                  {{ (index + 1).toString().padStart(2, '0') }}
                </div>

                <div class="guild-head">
                  @if (guild.icon_url) {
                    <img [src]="guild.icon_url" alt="" />
                  } @else {
                    <div class="avatar">{{ guild.name.slice(0, 1) }}</div>
                  }

                  <div class="guild-name">
                    <span>{{ "enterprise_dashboard.discord_node" | snT:"DISCORD NODE" }}</span>
                    <h4>{{ guild.name }}</h4>
                    <small>{{ guild.guild_id }}</small>
                  </div>

                  <div class="node-state" [class.online]="guild.bot_status === 'online'">
                    <i></i>{{ guild.bot_status }}
                  </div>
                </div>

                <div class="guild-stats">
                  <div>
                    <span>{{ 'dashboard.members' | snT:'MEMBERS' }}</span>
                    <strong>{{ guild.member_count | number }}</strong>
                  </div>
                  <div>
                    <span>{{ "enterprise_dashboard.last_sync" | snT:"LAST SYNC" }}</span>
                    <strong>{{ guild.last_sync_at ? (guild.last_sync_at | date:'short') : ('dashboard.never' | snT:'NEVER') }}</strong>
                  </div>
                </div>

                <div class="guild-actions">
                  @if (guild.bot_status === 'online') {
                    <a class="open-node" [routerLink]="['/guild', guild.guild_id]">
                      {{ 'dashboard.enter_node' | snT:'ENTER NODE' }} <span>→</span>
                    </a>
                    <a class="security-node" [routerLink]="['/guild', guild.guild_id, 'security']">
                      SECURITY
                    </a>
                  } @else {
                    <a
                      class="connect-node"
                      [href]="connectUrl(guild.guild_id)"
                      target="_blank"
                      rel="noopener"
                    >
                      {{ 'dashboard.connect_bot' | snT:'CONNECT BOT' }} <span>↗</span>
                    </a>
                  }
                </div>
              </article>
            }
          </section>
        }
      }
    </sn-shell>
  `,
  styles: [`
    .command-hero{
      position:relative;
      overflow:hidden;
      min-height:285px;
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      align-items:center;
      gap:2rem;
      padding:2rem;
      background:
        linear-gradient(105deg,rgba(10,19,26,.98),rgba(7,12,18,.88)),
        var(--panel);
      border:1px solid var(--line);
      border-radius:18px
    }

    .command-hero::before{
      content:"";
      position:absolute;
      width:520px;
      height:520px;
      right:-210px;
      top:-190px;
      border:1px solid rgba(53,226,178,.11);
      border-radius:50%;
      box-shadow:
        0 0 0 48px rgba(53,226,178,.018),
        0 0 0 96px rgba(53,226,178,.012)
    }

    .command-hero::after{
      content:"";
      position:absolute;
      inset:0;
      pointer-events:none;
      background:
        linear-gradient(rgba(53,226,178,.025) 1px,transparent 1px),
        linear-gradient(90deg,rgba(53,226,178,.025) 1px,transparent 1px);
      background-size:24px 24px;
      mask-image:linear-gradient(90deg,black,transparent 80%)
    }

    .hero-copy,.hero-status{position:relative;z-index:2}
    .eyebrow{
      color:#6e908b;
      font-size:.6rem;
      font-weight:900;
      letter-spacing:.17em
    }

    .hero-copy h2{
      max-width:720px;
      margin:.7rem 0 .6rem;
      font-size:clamp(2rem,4vw,4rem);
      line-height:1;
      letter-spacing:-.055em
    }

    .hero-copy p{
      max-width:650px;
      margin:0;
      color:var(--muted);
      line-height:1.7
    }

    .hero-links{display:flex;gap:.65rem;flex-wrap:wrap;margin-top:1.35rem}
    .hero-links a{
      display:flex;
      align-items:center;
      gap:.8rem;
      padding:.65rem .8rem;
      color:#a7c7be;
      border:1px solid var(--line);
      border-radius:9px;
      background:rgba(255,255,255,.018);
      font-size:.72rem;
      font-weight:750
    }
    .hero-links a:hover{color:var(--primary);border-color:rgba(53,226,178,.23)}

    .hero-status{
      display:grid;
      justify-items:center;
      gap:1rem
    }

    .status-ring{
      width:150px;
      height:150px;
      display:grid;
      place-items:center;
      border:1px solid rgba(53,226,178,.2);
      border-radius:50%;
      background:
        radial-gradient(circle,rgba(53,226,178,.08),transparent 62%);
      box-shadow:
        inset 0 0 0 10px rgba(53,226,178,.018),
        inset 0 0 0 11px rgba(53,226,178,.08)
    }

    .status-ring>div{display:grid;justify-items:center;gap:.25rem}
    .status-ring small{color:#607c78;font-size:.57rem;letter-spacing:.16em}
    .status-ring strong{
      color:var(--primary);
      font-size:.72rem;
      text-transform:uppercase;
      letter-spacing:.12em
    }

    .status-ring.degraded{border-color:rgba(248,189,92,.28)}
    .status-ring.degraded strong{color:var(--warning)}
    .status-ring.critical{border-color:rgba(255,111,127,.3)}
    .status-ring.critical strong{color:var(--danger)}

    .refresh{
      min-width:150px;
      padding:.65rem .85rem;
      color:#b8d5cd;
      background:#0b141b;
      border:1px solid var(--line);
      border-radius:9px;
      font-size:.7rem;
      font-weight:800
    }

    .refresh:hover{border-color:rgba(53,226,178,.26);color:var(--primary)}
    .refresh:disabled{opacity:.5;cursor:wait}

    .alert-panel{
      margin-top:1rem;
      padding:1rem;
      color:#ffd8dc;
      background:rgba(255,111,127,.055);
      border:1px solid rgba(255,111,127,.25);
      border-radius:10px
    }

    .system-strip{
      display:grid;
      grid-template-columns:auto repeat(5,minmax(140px,1fr));
      margin-top:1rem;
      overflow:auto;
      background:#080e14;
      border:1px solid var(--line);
      border-radius:12px
    }

    .strip-label{
      min-width:145px;
      display:flex;
      align-items:center;
      gap:.55rem;
      padding:1rem;
      color:#779991;
      border-right:1px solid var(--line);
      font-size:.6rem;
      font-weight:900;
      letter-spacing:.14em
    }

    .live-dot{
      width:.48rem;
      height:.48rem;
      border-radius:50%;
      background:var(--success);
      box-shadow:0 0 12px rgba(57,221,161,.75)
    }

    .system-strip article{
      min-width:150px;
      display:grid;
      gap:.2rem;
      padding:.8rem 1rem;
      border-right:1px solid var(--line)
    }

    .system-strip article:last-child{border-right:0}
    .system-strip article span{color:#536b79;font-size:.56rem;letter-spacing:.12em}
    .system-strip article strong{
      color:var(--success);
      font-size:.69rem;
      text-transform:uppercase
    }
    .system-strip article strong.warn{color:var(--warning)}
    .system-strip article small{color:var(--muted);font-size:.61rem}

    .overview-grid{
      display:grid;
      grid-template-columns:repeat(4,minmax(0,1fr));
      gap:.8rem;
      margin-top:1rem
    }

    .panel{
      position:relative;
      overflow:hidden;
      background:
        linear-gradient(145deg,rgba(255,255,255,.022),transparent 40%),
        rgba(11,18,26,.95);
      border:1px solid var(--line);
      border-radius:13px
    }

    .panel::before{
      content:"";
      position:absolute;
      left:0;
      top:0;
      width:36px;
      height:1px;
      background:var(--primary);
      box-shadow:0 0 10px rgba(53,226,178,.55)
    }

    .primary-metric{
      grid-column:span 2;
      min-height:170px;
      display:grid;
      grid-template-columns:auto 1fr auto;
      align-items:end;
      gap:1rem;
      padding:1.2rem;
      background:
        radial-gradient(circle at 85% 10%,rgba(53,226,178,.1),transparent 16rem),
        linear-gradient(145deg,rgba(17,31,38,.98),rgba(8,14,20,.98))
    }

    .primary-metric>div:nth-child(2){display:grid;gap:.3rem}
    .primary-metric span,.metric span{
      color:#68818d;
      font-size:.59rem;
      font-weight:850;
      letter-spacing:.13em
    }

    .primary-metric strong{
      font-size:3.1rem;
      line-height:1
    }

    .primary-metric small,.metric small{color:var(--muted);font-size:.68rem}
    .metric-trend{
      color:var(--success);
      font-size:.62rem;
      letter-spacing:.13em
    }

    .panel-index{
      position:absolute!important;
      top:.7rem;
      right:.75rem;
      color:#30424d;
      font-family:ui-monospace,SFMono-Regular,Consolas,monospace;
      font-size:.58rem
    }

    .metric{
      min-height:170px;
      display:flex;
      flex-direction:column;
      justify-content:flex-end;
      gap:.35rem;
      padding:1rem
    }
    .metric strong{font-size:2rem}
    .danger{color:var(--danger)!important}

    .operations-grid{
      display:grid;
      grid-template-columns:minmax(0,1.9fr) minmax(280px,.8fr);
      gap:.8rem;
      margin-top:.8rem
    }

    .operations-panel,.telemetry-panel{padding:1rem}
    .section-title{
      display:flex;
      align-items:end;
      justify-content:space-between;
      gap:1rem
    }
    .section-title span{
      color:#607983;
      font-size:.58rem;
      font-weight:900;
      letter-spacing:.14em
    }
    .section-title h3{margin:.28rem 0 0}
    .section-title small{color:#40535f;font-size:.56rem;letter-spacing:.12em}

    .action-grid{
      display:grid;
      grid-template-columns:repeat(2,1fr);
      gap:.65rem;
      margin-top:1rem
    }

    .action-grid a{
      position:relative;
      min-height:126px;
      display:flex;
      flex-direction:column;
      justify-content:flex-end;
      gap:.32rem;
      padding:1rem;
      background:rgba(255,255,255,.015);
      border:1px solid var(--line);
      border-radius:10px
    }

    .action-grid a:hover{
      background:rgba(53,226,178,.035);
      border-color:rgba(53,226,178,.2)
    }

    .action-grid b{
      color:var(--primary);
      font-size:.55rem;
      letter-spacing:.14em
    }
    .action-grid strong{font-size:.84rem}
    .action-grid span{color:var(--muted);font-size:.68rem;line-height:1.45}
    .action-grid i{
      position:absolute;
      top:.75rem;
      right:.8rem;
      color:#32454f;
      font-style:normal;
      font-family:ui-monospace,SFMono-Regular,Consolas,monospace;
      font-size:.58rem
    }

    .telemetry-row{
      display:flex;
      justify-content:space-between;
      gap:1rem;
      padding:.85rem 0;
      border-bottom:1px solid var(--line)
    }
    .telemetry-row span{color:var(--muted);font-size:.7rem}
    .telemetry-row strong{font-size:.72rem}
    .generated{
      margin-top:1rem;
      padding:.65rem;
      color:#527168;
      background:rgba(53,226,178,.035);
      border:1px solid rgba(53,226,178,.1);
      border-radius:8px;
      font-size:.55rem;
      font-weight:850;
      letter-spacing:.12em
    }

    .estate-header{
      display:flex;
      justify-content:space-between;
      align-items:end;
      gap:1rem;
      margin:1.5rem 0 .8rem
    }
    .estate-header span{
      color:#607983;
      font-size:.58rem;
      font-weight:900;
      letter-spacing:.14em
    }
    .estate-header h3{margin:.25rem 0 0}
    .estate-count{
      color:#638379;
      font-size:.6rem;
      font-weight:900;
      letter-spacing:.12em
    }

    .guild-grid{
      display:grid;
      grid-template-columns:repeat(3,minmax(0,1fr));
      gap:.8rem
    }

    .guild-node{padding:1rem}
    .node-index{
      position:absolute;
      right:.8rem;
      top:.65rem;
      color:#31434d;
      font-family:ui-monospace,SFMono-Regular,Consolas,monospace;
      font-size:.58rem
    }

    .guild-head{
      display:grid;
      grid-template-columns:auto 1fr auto;
      align-items:center;
      gap:.7rem
    }

    .guild-head img,.avatar{
      width:44px;
      height:44px;
      border-radius:10px
    }
    .guild-head img{object-fit:cover}
    .avatar{
      display:grid;
      place-items:center;
      color:#03130e;
      background:var(--primary);
      font-weight:900
    }

    .guild-name{min-width:0}
    .guild-name span{color:#5f7883;font-size:.52rem;letter-spacing:.12em}
    .guild-name h4{
      margin:.16rem 0;
      overflow:hidden;
      text-overflow:ellipsis;
      white-space:nowrap
    }
    .guild-name small{color:var(--muted);font-size:.59rem}

    .node-state{
      display:flex;
      align-items:center;
      gap:.35rem;
      color:var(--warning);
      font-size:.55rem;
      font-weight:850;
      text-transform:uppercase
    }
    .node-state i{
      width:.4rem;
      height:.4rem;
      border-radius:50%;
      background:currentColor;
      box-shadow:0 0 9px currentColor
    }
    .node-state.online{color:var(--success)}

    .guild-stats{
      display:grid;
      grid-template-columns:1fr 1fr;
      gap:.55rem;
      margin:1rem 0
    }
    .guild-stats>div{
      display:grid;
      gap:.25rem;
      padding:.65rem;
      background:#091018;
      border:1px solid var(--line);
      border-radius:8px
    }
    .guild-stats span{color:#526a76;font-size:.52rem;letter-spacing:.12em}
    .guild-stats strong{font-size:.72rem}

    .guild-actions{display:grid;grid-template-columns:1fr auto;gap:.5rem}
    .guild-actions a{
      min-height:38px;
      display:flex;
      align-items:center;
      justify-content:center;
      gap:.6rem;
      padding:.55rem .7rem;
      border-radius:8px;
      font-size:.59rem;
      font-weight:900;
      letter-spacing:.08em
    }
    .open-node{color:#03130e;background:var(--primary)}
    .connect-node{grid-column:1/-1;color:#03130e;background:linear-gradient(135deg,var(--primary),#7cefd2);box-shadow:0 8px 24px rgba(53,226,178,.12)}
    .security-node{color:#8ca29d;border:1px solid var(--line)}
    .empty-state{padding:2rem;text-align:center;color:var(--muted)}

    @media(max-width:1200px){
      .overview-grid{grid-template-columns:repeat(2,1fr)}
      .guild-grid{grid-template-columns:repeat(2,1fr)}
    }

    @media(max-width:850px){
      .command-hero{grid-template-columns:1fr}
      .hero-status{grid-template-columns:auto auto;justify-content:start}
      .status-ring{width:110px;height:110px}
      .operations-grid{grid-template-columns:1fr}
      .system-strip{grid-template-columns:auto repeat(5,150px)}
    }

    @media(max-width:650px){
      .command-hero{padding:1.2rem}
      .hero-copy h2{font-size:2.3rem}
      .overview-grid,.guild-grid,.action-grid{grid-template-columns:1fr}
      .primary-metric{grid-column:span 1;grid-template-columns:1fr}
      .guild-head{grid-template-columns:auto 1fr}
      .node-state{grid-column:1/-1}
    }
  `],
})
export class EnterpriseDashboardComponent implements OnInit, OnDestroy {
  readonly data = signal<EnterpriseDashboardOverview | null>(null);
  readonly loading = signal(false);
  readonly error = signal('');
  private timer?: ReturnType<typeof setInterval>;

  constructor(private readonly dashboard: EnterpriseDashboardService) {}

  ngOnInit(): void {
    void this.load();
    this.timer = setInterval(() => void this.load(false), 30000);
  }

  ngOnDestroy(): void {
    if (this.timer) clearInterval(this.timer);
  }

  async load(showLoader = true): Promise<void> {
    if (showLoader) this.loading.set(true);
    this.error.set('');

    try {
      this.data.set(await this.dashboard.overview());
    } catch (error) {
      this.error.set(
        error instanceof Error ? error.message : 'Unable to load the dashboard.',
      );
    } finally {
      this.loading.set(false);
    }
  }

  connectUrl(guildId: string): string {
    return `/api/v1/auth/discord/bot-install?guild_id=${encodeURIComponent(guildId)}`;
  }

  formatBytes(value: number | null): string {
    if (value === null || value === undefined) return '—';
    if (value < 1024) return `${value} B`;

    const units = ['KB', 'MB', 'GB', 'TB'];
    let size = value / 1024;
    let unit = 0;

    while (size >= 1024 && unit < units.length - 1) {
      size /= 1024;
      unit += 1;
    }

    return `${size.toFixed(size >= 10 ? 1 : 2)} ${units[unit]}`;
  }
}
