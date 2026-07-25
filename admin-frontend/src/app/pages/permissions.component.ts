import { Component, OnInit, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { FormsModule } from '@angular/forms';

import { PermissionRule, PermissionService } from '../core/permission.service';
import { GuildRoleService } from '../core/guild-role.service';
import { ShellComponent } from '../shared/shell.component';
import { TranslatePipe } from '../core/translate.pipe';
import { TranslationService } from '../core/translation.service';
import { ModalService } from '../core/modal.service';
import { ToastService } from '../core/toast.service';

@Component({
  standalone: true,
  imports: [FormsModule, ShellComponent, TranslatePipe],
  template: `
    <sn-shell [title]="'permissions_engine.title' | snT:'Permissions'">
      <div class="card heading">
        <div>
          <h2>{{ "permissions_engine.heading" | snT:"Permissions Engine" }}</h2>
          <p class="muted">{{ "permissions_engine.description" | snT:"Module access rules for ShieldNet and Discord roles." }}</p>
        </div>
        <button class="btn" (click)="dialog.set(true)">{{ "permissions_engine.add_rule" | snT:"Add rule" }}</button>
      </div>

      <div class="rules">
        @for (rule of rules(); track rule.id) {
          <article class="card rule">
            <div>
              <strong>{{ rule.module_key }} · {{ rule.permission }}</strong>
              <div class="muted">
                {{ rule.effect }} · {{ label(rule) }} · {{ "permissions_engine.priority" | snT:"priority" }} {{ rule.priority }}
              </div>
            </div>
            <button class="danger" (click)="remove(rule)">{{ "permissions_engine.delete" | snT:"Delete" }}</button>
          </article>
        }
      </div>

      @if (dialog()) {
        <div class="overlay" (click)="dialog.set(false)">
          <section class="dialog card" (click)="$event.stopPropagation()">
            <h3>{{ "permissions_engine.new_rule" | snT:"New permission rule" }}</h3>

            <label>{{ "permissions_engine.module" | snT:"Module" }}
              <select [(ngModel)]="moduleKey">
                <option value="*">{{ "permissions_engine.all_modules" | snT:"All modules" }}</option>
                <option value="core">{{ "permissions_engine.core" | snT:"Core" }}</option>
                <option value="verification">{{ "permissions_engine.verification" | snT:"Verification" }}</option>
                <option value="translator">{{ "permissions_engine.translator" | snT:"Translator" }}</option>
                <option value="moderation">{{ "permissions_engine.moderation" | snT:"Moderation" }}</option>
                <option value="welcome">{{ "permissions_engine.welcome" | snT:"Welcome" }}</option>
                <option value="tickets">{{ "permissions_engine.tickets" | snT:"Tickets" }}</option>
              </select>
            </label>

            <label>{{ "permissions_engine.permission" | snT:"Permission" }}
              <select [(ngModel)]="permission">
                <option value="view">{{ "permissions_engine.view" | snT:"View" }}</option>
                <option value="manage">{{ "permissions_engine.manage" | snT:"Manage" }}</option>
                <option value="execute">{{ "permissions_engine.execute" | snT:"Execute" }}</option>
                <option value="configure">{{ "permissions_engine.configure" | snT:"Configure" }}</option>
              </select>
            </label>

            <label>{{ "permissions_engine.effect" | snT:"Effect" }}
              <select [(ngModel)]="effect">
                <option value="allow">{{ "permissions_engine.allow" | snT:"Allow" }}</option>
                <option value="deny">{{ "permissions_engine.deny" | snT:"Deny" }}</option>
              </select>
            </label>

            <label>{{ "permissions_engine.subject" | snT:"Subject" }}
              <select [(ngModel)]="subjectType" (ngModelChange)="subjectChanged()">
                <option value="shieldnet_role">{{ "permissions_engine.shieldnet_role" | snT:"ShieldNet role" }}</option>
                <option value="discord_role">{{ "permissions_engine.discord_role" | snT:"Discord role" }}</option>
                <option value="discord_user">{{ "permissions_engine.discord_user" | snT:"Discord user ID" }}</option>
                <option value="everyone">{{ "permissions_engine.everyone" | snT:"Everyone" }}</option>
              </select>
            </label>

            @if (subjectType === 'shieldnet_role') {
              <label>{{ "permissions_engine.shieldnet_role" | snT:"ShieldNet role" }}
                <select [(ngModel)]="subjectValue">
                  <option value="moderator">{{ "permissions_engine.moderator" | snT:"Moderator" }}</option>
                  <option value="admin">{{ "permissions_engine.admin" | snT:"Admin" }}</option>
                </select>
              </label>
            }

            @if (subjectType === 'discord_role') {
              <label>{{ "permissions_engine.discord_role" | snT:"Discord role" }}
                <select [(ngModel)]="subjectValue">
                  <option value="">{{ "permissions_engine.select_role" | snT:"Select role" }}</option>
                  @for (role of discordRoles(); track role.discord_role_id) {
                    <option [value]="role.discord_role_id">{{ role.name }}</option>
                  }
                </select>
              </label>
            }

            @if (subjectType === 'discord_user') {
              <label>{{ "permissions_engine.discord_user" | snT:"Discord user ID" }}
                <input [(ngModel)]="subjectValue">
              </label>
            }

            <label>{{ "permissions_engine.priority" | snT:"Priority" }}
              <input type="number" [(ngModel)]="priority">
            </label>

            <footer>
              <button class="btn secondary" (click)="dialog.set(false)">{{ "permissions_engine.close" | snT:"Close" }}</button>
              <button class="btn" (click)="save()">{{ "permissions_engine.save" | snT:"Save" }}</button>
            </footer>
          </section>
        </div>
      }
    </sn-shell>
  `,
  styles: [`
    .heading,.rule{padding:1rem;display:flex;justify-content:space-between;gap:1rem}
    .rules{margin-top:1rem;display:grid;gap:.7rem}
    .danger{color:#ffd9de;background:var(--panel-2);border:1px solid rgba(255,107,125,.35);border-radius:8px;padding:.4rem .65rem}
    .overlay{position:fixed;inset:0;display:grid;place-items:center;background:rgba(0,0,0,.7);padding:1rem;z-index:1000}
    .dialog{width:min(560px,100%);padding:1.2rem;display:grid;gap:.8rem}
    label{display:grid;gap:.35rem;color:var(--muted)}
    select,input{padding:.8rem;color:var(--text);background:var(--panel-2);border:1px solid var(--line);border-radius:10px}
    footer{display:flex;justify-content:flex-end;gap:.6rem}
  `],
})
export class PermissionsComponent implements OnInit {
  readonly guildId = this.route.snapshot.paramMap.get('guildId') ?? '';
  readonly rules = signal<PermissionRule[]>([]);
  readonly discordRoles = signal<any[]>([]);
  readonly dialog = signal(false);

  moduleKey = '*';
  permission = 'view';
  effect = 'allow';
  subjectType = 'shieldnet_role';
  subjectValue = 'moderator';
  priority = 100;

  constructor(
    private readonly route: ActivatedRoute,
    private readonly permissions: PermissionService,
    private readonly guildRoles: GuildRoleService,
    private readonly i18n: TranslationService,
    private readonly modal: ModalService,
    private readonly toast: ToastService,
  ) {}

  async ngOnInit(): Promise<void> {
    try {
      this.rules.set(await this.permissions.list(this.guildId));
      this.discordRoles.set(await this.guildRoles.list(this.guildId));
    } catch {
      this.toast.error(this.i18n.t('ui.error','Operation failed'),this.i18n.t('permissions_engine.load_error','Unable to load permission rules.'));
    }
  }

  subjectChanged(): void {
    this.subjectValue =
      this.subjectType === 'everyone'
        ? '*'
        : this.subjectType === 'shieldnet_role'
          ? 'moderator'
          : '';
  }

  label(rule: PermissionRule): string {
    if (rule.subject_type !== 'discord_role') {
      return `${rule.subject_type}: ${rule.subject_value}`;
    }
    const role = this.discordRoles().find(
      item => String(item.discord_role_id) === rule.subject_value,
    );
    return `discord_role: ${role?.name || rule.subject_value}`;
  }

  async save(): Promise<void> {
    try {
      await this.permissions.save(
      this.guildId,
      this.moduleKey,
      this.permission,
      {
        effect: this.effect,
        subject_type: this.subjectType,
        subject_value: this.subjectValue,
        enabled: true,
        priority: Number(this.priority),
      },
    );
    this.rules.set(await this.permissions.list(this.guildId));
    this.dialog.set(false);
    this.toast.success(this.i18n.t('ui.success','Completed'),this.i18n.t('permissions_engine.saved_success','Permission rule saved.'));
    } catch {
      this.toast.error(this.i18n.t('ui.error','Operation failed'),this.i18n.t('permissions_engine.save_error','Unable to save permission rule.'));
    }
  }

  async remove(rule: PermissionRule): Promise<void> {
    if (!await this.modal.confirm(this.i18n.t('permissions_engine.delete_confirm','Delete this permission rule?'),{title:this.i18n.t('ui.confirm_title','Confirm action'),confirmLabel:this.i18n.t('ui.confirm','Confirm'),cancelLabel:this.i18n.t('ui.cancel','Cancel'),danger:true})) return;
    try {
      await this.permissions.remove(this.guildId, rule.id);
      this.rules.set(await this.permissions.list(this.guildId));
      this.toast.success(this.i18n.t('ui.success','Completed'),this.i18n.t('permissions_engine.deleted_success','Permission rule deleted.'));
    } catch {
      this.toast.error(this.i18n.t('ui.error','Operation failed'),this.i18n.t('permissions_engine.delete_error','Unable to delete permission rule.'));
    }
  }
}
