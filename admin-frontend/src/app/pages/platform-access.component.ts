import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';

import {
  PlatformAccessIdentity,
  PlatformAccessOverview,
  PlatformAccessService,
} from '../core/platform-access.service';
import { ShellComponent } from '../shared/shell.component';
import { TranslatePipe } from '../core/translate.pipe';
import { TranslationService } from '../core/translation.service';

@Component({
  selector: 'sn-platform-access',
  standalone: true,
  imports: [CommonModule, ShellComponent,TranslatePipe],
  template: `
    <sn-shell [title]="'access.title' | snT:'Platform Access'">
      <div class="notice" *ngIf="loading">{{ "access.checking" | snT:"Checking platform access…" }}</div>
      <div class="notice error" *ngIf="error">{{ error }}</div>

      <section class="hero" *ngIf="identity">
        <div>
          <div class="eyebrow">{{ "access.eyebrow" | snT:"Global RBAC" }}</div>
          <h2>{{ identity.is_superadmin ? ('access.superadmin' | snT:'SuperAdmin access active') : ('access.standard' | snT:'Standard platform access') }}</h2>
          <p>
            {{ "access.discord_id" | snT:"Discord ID" }}: <strong>{{ identity.discord_user_id || ('access.not_linked' | snT:'not linked') }}</strong>
            · {{ "access.source" | snT:"Source" }}: <strong>{{ identity.superadmin_source || ('access.membership_source' | snT:'membership / database roles') }}</strong>
          </p>
        </div>
        <span class="badge" [class.active]="identity.is_superadmin">
          {{ identity.highest_role || ('access.no_role' | snT:'no global role') }}
        </span>
      </section>

      <div class="cards" *ngIf="overview">
        <article><span>{{ "access.registered_servers" | snT:"Registered servers" }}</span><strong>{{ overview.guild_count }}</strong></article>
        <article><span>{{ "access.platform_users" | snT:"Platform users" }}</span><strong>{{ overview.user_count }}</strong></article>
        <article><span>{{ "access.active_memberships" | snT:"Active memberships" }}</span><strong>{{ overview.active_memberships }}</strong></article>
        <article><span>{{ "access.configured_superadmins" | snT:"Configured SuperAdmins" }}</span><strong>{{ overview.configured_superadmins }}</strong></article>
      </div>

      <section class="panel" *ngIf="identity">
        <h3>{{ "access.effective_roles" | snT:"Effective roles" }}</h3>
        <div class="roles" *ngIf="identity.roles.length; else noRoles">
          <span *ngFor="let role of identity.roles">{{ role }}</span>
        </div>
        <ng-template #noRoles><p class="muted">{{ "access.no_roles" | snT:"No global roles assigned." }}</p></ng-template>
      </section>

      <section class="panel setup" *ngIf="identity?.is_superadmin">
        <h3>{{ "access.configuration" | snT:"Server configuration" }}</h3>
        <p>{{ "access.configuration_help" | snT:"Add one or more Discord user IDs to the backend environment:" }}</p>
        <code>SHIELDNET_SUPERADMIN_IDS=123456789012345678,987654321098765432</code>
        <p class="muted">{{ "access.restart_help" | snT:"Restart shieldnet-backend after changing the environment file." }}</p>
      </section>
    </sn-shell>
  `,
  styles: [`
    .hero, .panel, .notice, article {
      border: 1px solid var(--line);
      background: rgba(16,22,38,.72);
      border-radius: 18px;
    }
    .hero { padding: 1.4rem; display:flex; justify-content:space-between; gap:1rem; align-items:center; }
    h2 { margin:.25rem 0; }
    p { color:var(--muted); }
    .eyebrow { text-transform:uppercase; letter-spacing:.12em; color:var(--primary); font-size:.75rem; }
    .badge { padding:.55rem .8rem; border-radius:999px; border:1px solid var(--line); text-transform:uppercase; font-size:.75rem; }
    .badge.active { background:var(--primary-soft); color:#cfd5ff; }
    .cards { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:1rem; margin:1rem 0; }
    article { padding:1rem; display:grid; gap:.45rem; }
    article span { color:var(--muted); }
    article strong { font-size:1.7rem; }
    .panel { padding:1.2rem; margin-top:1rem; }
    .roles { display:flex; flex-wrap:wrap; gap:.55rem; }
    .roles span { padding:.4rem .65rem; border-radius:9px; background:var(--primary-soft); }
    code { display:block; overflow:auto; padding:1rem; border-radius:12px; background:#080c17; color:#cbd4ff; }
    .notice { padding:1rem; margin-bottom:1rem; }
    .error { border-color:rgba(255,80,100,.5); color:#ff9baa; }
    @media(max-width:900px){ .cards{grid-template-columns:repeat(2,minmax(0,1fr));} }
    @media(max-width:600px){ .hero{align-items:flex-start;flex-direction:column}.cards{grid-template-columns:1fr;} }
  `],
})
export class PlatformAccessComponent implements OnInit {
  identity: PlatformAccessIdentity | null = null;
  overview: PlatformAccessOverview | null = null;
  loading = true;
  error = '';

  constructor(private readonly access: PlatformAccessService, private readonly i18n: TranslationService) {}

  ngOnInit(): void {
    this.access.identity().subscribe({
      next: (identity) => {
        this.identity = identity;
        if (!identity.is_superadmin) {
          this.loading = false;
          return;
        }
        this.access.overview().subscribe({
          next: (overview) => { this.overview = overview; this.loading = false; },
          error: () => { this.error = this.i18n.t('access.overview_error','Unable to load SuperAdmin overview.'); this.loading = false; },
        });
      },
      error: () => { this.error = this.i18n.t('access.verify_error','Unable to verify platform access.'); this.loading = false; },
    });
  }
}
