import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';

import {
  PlatformAccessIdentity,
  PlatformAccessOverview,
  PlatformAccessService,
  PlatformDiscordAdmin,
  PlatformDiscordAdminCreate,
} from '../core/platform-access.service';
import { ShellComponent } from '../shared/shell.component';

@Component({
  selector: 'sn-platform-access',
  standalone: true,
  imports: [CommonModule, FormsModule, ShellComponent],
  template: `
    <sn-shell title="Platform Access">
      <div class="notice" *ngIf="loading">Loading platform access…</div>
      <div class="notice error" *ngIf="error">{{ error }}</div>
      <div class="notice success" *ngIf="message">{{ message }}</div>

      <section class="hero" *ngIf="identity">
        <div>
          <div class="eyebrow">PLATFORM IDENTITY</div>
          <h2>{{ accessTitle }}</h2>
          <p>Authentication: <strong>{{ identity.auth_source }}</strong>
            <span *ngIf="identity.platform_role"> · Role: <strong>{{ identity.platform_role }}</strong></span>
          </p>
        </div>
        <span class="badge" [class.active]="identity.has_platform_access">{{ identity.has_platform_access ? 'ACTIVE' : 'DENIED' }}</span>
      </section>

      <div class="cards" *ngIf="overview">
        <article><span>Registered servers</span><strong>{{ overview.guild_count }}</strong></article>
        <article><span>Platform users</span><strong>{{ overview.user_count }}</strong></article>
        <article><span>Active memberships</span><strong>{{ overview.active_memberships }}</strong></article>
        <article><span>Discord platform admins</span><strong>{{ overview.configured_superadmins }}</strong></article>
      </div>

      <section class="panel locked" *ngIf="identity && !identity.can_manage_platform_admins">
        <h3>Discord administrator management</h3>
        <p>Viewing platform data is allowed, but administrator grants can only be changed after local login at <code>/control/auth</code>.</p>
      </section>

      <ng-container *ngIf="identity?.can_manage_platform_admins">
        <section class="panel">
          <div class="panel-head">
            <div><div class="eyebrow">LOCAL OWNER ONLY</div><h3>Add Discord administrator</h3></div>
          </div>
          <form class="form-grid" (ngSubmit)="createAdmin()">
            <label><span>Discord User ID</span><input name="discord_user_id" [(ngModel)]="form.discord_user_id" required pattern="[0-9]{15,22}" placeholder="123456789012345678"></label>
            <label><span>Role</span><select name="role" [(ngModel)]="form.role"><option value="platform_admin">Platform admin</option><option value="platform_operator">Platform operator</option><option value="platform_auditor">Platform auditor</option></select></label>
            <label><span>Display name</span><input name="display_name" [(ngModel)]="form.display_name" maxlength="128"></label>
            <label><span>Expires at</span><input name="expires_at" [(ngModel)]="form.expires_at" type="datetime-local"></label>
            <label class="wide"><span>Description</span><textarea name="description" [(ngModel)]="form.description" rows="3"></textarea></label>
            <div class="wide actions"><button class="primary" type="submit" [disabled]="saving">{{ saving ? 'Saving…' : 'Add administrator' }}</button></div>
          </form>
        </section>

        <section class="panel">
          <div class="panel-head"><div><div class="eyebrow">DATABASE GRANTS</div><h3>Discord administrators</h3></div><button type="button" (click)="loadAdmins()">Refresh</button></div>
          <div class="empty" *ngIf="!admins.length">No Discord platform administrators configured.</div>
          <div class="admin-list">
            <article class="admin-card" *ngFor="let admin of admins">
              <div class="admin-main">
                <div><strong>{{ admin.display_name || 'Discord administrator' }}</strong><small>{{ admin.discord_user_id }}</small></div>
                <span class="state" [class.disabled]="!admin.is_active">{{ admin.is_active ? 'ACTIVE' : 'DISABLED' }}</span>
              </div>
              <div class="edit-grid">
                <label><span>Role</span><select [(ngModel)]="admin.role"><option value="platform_admin">Platform admin</option><option value="platform_operator">Platform operator</option><option value="platform_auditor">Platform auditor</option></select></label>
                <label><span>Name</span><input [(ngModel)]="admin.display_name"></label>
                <label class="wide"><span>Description</span><textarea [(ngModel)]="admin.description" rows="2"></textarea></label>
              </div>
              <div class="meta">Created: {{ admin.created_at | date:'medium' }} · Last login: {{ admin.last_login_at ? (admin.last_login_at | date:'medium') : 'never' }} · Expires: {{ admin.expires_at ? (admin.expires_at | date:'medium') : 'never' }}</div>
              <div class="actions wrap">
                <button type="button" class="primary" (click)="saveAdmin(admin)">Save</button>
                <button type="button" (click)="toggleAdmin(admin)">{{ admin.is_active ? 'Disable' : 'Enable' }}</button>
                <button type="button" (click)="revokeSessions(admin)">Revoke sessions</button>
                <button type="button" class="danger" (click)="removeAdmin(admin)">Delete</button>
              </div>
            </article>
          </div>
        </section>
      </ng-container>
    </sn-shell>
  `,
  styles: [`
    .hero,.panel,.notice,article{border:1px solid var(--line);background:rgba(16,22,38,.72);border-radius:18px}.hero{padding:1.4rem;display:flex;justify-content:space-between;gap:1rem;align-items:center}.eyebrow{color:var(--primary);font-size:.7rem;font-weight:800;letter-spacing:.14em}.badge,.state{padding:.5rem .75rem;border-radius:999px;border:1px solid var(--line);font-size:.7rem;font-weight:800}.badge.active,.state{color:var(--primary);background:var(--primary-soft)}.state.disabled{color:#ff9baa;background:rgba(255,80,100,.08)}p,.meta,small{color:var(--muted)}.cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1rem;margin:1rem 0}.cards article{padding:1rem;display:grid;gap:.4rem}.cards strong{font-size:1.7rem}.panel{padding:1.2rem;margin-top:1rem}.panel-head,.admin-main{display:flex;align-items:center;justify-content:space-between;gap:1rem}.form-grid,.edit-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem;margin-top:1rem}.wide{grid-column:1/-1}label{display:grid;gap:.4rem}label span{font-size:.72rem;color:var(--muted);font-weight:700}input,select,textarea,button{font:inherit}input,select,textarea{width:100%;box-sizing:border-box;padding:.75rem;border:1px solid var(--line);border-radius:10px;background:rgba(5,9,15,.75);color:var(--text)}button{padding:.7rem .9rem;border:1px solid var(--line);border-radius:10px;background:rgba(255,255,255,.03);color:var(--text);cursor:pointer}.primary{border-color:rgba(53,226,178,.35);background:var(--primary-soft);color:var(--primary)}.danger{border-color:rgba(255,80,100,.4);color:#ff9baa}.actions{display:flex;gap:.65rem;justify-content:flex-end}.wrap{flex-wrap:wrap}.admin-list{display:grid;gap:1rem;margin-top:1rem}.admin-card{padding:1rem}.admin-main>div{display:grid;gap:.2rem}.meta{font-size:.75rem;margin:1rem 0}.notice{padding:1rem;margin-bottom:1rem}.error{color:#ff9baa;border-color:rgba(255,80,100,.5)}.success{color:var(--primary)}.locked code{color:var(--primary)}.empty{padding:1rem;color:var(--muted)}@media(max-width:900px){.cards{grid-template-columns:repeat(2,1fr)}}@media(max-width:650px){.hero,.panel-head{align-items:flex-start;flex-direction:column}.cards,.form-grid,.edit-grid{grid-template-columns:1fr}.wide{grid-column:auto}.actions{justify-content:flex-start}}
  `],
})
export class PlatformAccessComponent implements OnInit {
  identity: PlatformAccessIdentity | null = null;
  overview: PlatformAccessOverview | null = null;
  admins: PlatformDiscordAdmin[] = [];
  loading = true;
  saving = false;
  error = '';
  message = '';
  form: PlatformDiscordAdminCreate & { expires_at: string } = { discord_user_id: '', role: 'platform_admin', display_name: '', description: '', expires_at: '' };

  constructor(private readonly access: PlatformAccessService) {}

  get accessTitle(): string {
    if (this.identity?.auth_source === 'local_platform') return 'Local platform owner';
    return this.identity?.platform_role || 'Platform access';
  }

  async ngOnInit(): Promise<void> {
    try {
      this.identity = await firstValueFrom(this.access.identity());
      if (this.identity.has_platform_access) this.overview = await firstValueFrom(this.access.overview());
      if (this.identity.can_manage_platform_admins) await this.loadAdmins();
    } catch (error) { this.error = this.errorText(error); }
    finally { this.loading = false; }
  }

  async loadAdmins(): Promise<void> {
    try { this.admins = await firstValueFrom(this.access.discordAdmins()); }
    catch (error) { this.error = this.errorText(error); }
  }

  async createAdmin(): Promise<void> {
    this.clearAlerts();
    if (!/^\d{15,22}$/.test(this.form.discord_user_id.trim())) { this.error = 'Enter a valid Discord User ID.'; return; }
    this.saving = true;
    try {
      await firstValueFrom(this.access.addDiscordAdmin({ ...this.form, discord_user_id: this.form.discord_user_id.trim(), expires_at: this.form.expires_at ? new Date(this.form.expires_at).toISOString() : null }));
      this.form = { discord_user_id: '', role: 'platform_admin', display_name: '', description: '', expires_at: '' };
      this.message = 'Discord administrator added. The user can now sign in through Discord.';
      await this.loadAdmins();
    } catch (error) { this.error = this.errorText(error); }
    finally { this.saving = false; }
  }

  async saveAdmin(admin: PlatformDiscordAdmin): Promise<void> {
    this.clearAlerts();
    try { await firstValueFrom(this.access.updateDiscordAdmin(admin.id, { role: admin.role, display_name: admin.display_name, description: admin.description })); this.message = 'Administrator updated.'; await this.loadAdmins(); }
    catch (error) { this.error = this.errorText(error); }
  }

  async toggleAdmin(admin: PlatformDiscordAdmin): Promise<void> {
    this.clearAlerts();
    try { await firstValueFrom(this.access.updateDiscordAdmin(admin.id, { is_active: !admin.is_active })); if (admin.is_active) await firstValueFrom(this.access.revokeSessions(admin.id)); this.message = admin.is_active ? 'Administrator disabled and sessions revoked.' : 'Administrator enabled.'; await this.loadAdmins(); }
    catch (error) { this.error = this.errorText(error); }
  }

  async revokeSessions(admin: PlatformDiscordAdmin): Promise<void> {
    this.clearAlerts();
    if (!confirm(`Revoke all sessions for ${admin.display_name || admin.discord_user_id}?`)) return;
    try { await firstValueFrom(this.access.revokeSessions(admin.id)); this.message = 'Sessions revoked.'; }
    catch (error) { this.error = this.errorText(error); }
  }

  async removeAdmin(admin: PlatformDiscordAdmin): Promise<void> {
    this.clearAlerts();
    if (!confirm(`Delete platform access for ${admin.display_name || admin.discord_user_id}?`)) return;
    try { await firstValueFrom(this.access.deleteDiscordAdmin(admin.id)); this.message = 'Administrator deleted and sessions revoked.'; await this.loadAdmins(); }
    catch (error) { this.error = this.errorText(error); }
  }

  private clearAlerts(): void { this.error = ''; this.message = ''; }
  private errorText(error: any): string { return error?.error?.detail || error?.message || 'Operation failed.'; }
}
