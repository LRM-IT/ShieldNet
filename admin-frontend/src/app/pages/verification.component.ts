import {
  Component,
  OnInit,
  signal,
} from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { FormsModule } from '@angular/forms';

import { GuildRoleService } from '../core/guild-role.service';
import { VerificationService } from '../core/verification.service';
import { ShellComponent } from '../shared/shell.component';
import { TranslatePipe } from '../core/translate.pipe';

@Component({
  standalone: true,
  imports: [
    FormsModule,
    ShellComponent,
    TranslatePipe,
  ],
  template: `
    <sn-shell [title]="'verification.title' | snT:'Verification'">
      <section class="card panel">
        <div class="heading">
          <div>
            <h2>{{ "verification.settings" | snT:"Verification settings" }}</h2>
            <p class="muted">
              {{ "verification.description" | snT:"Configure /verify, approval mode and Verified role." }}
            </p>
          </div>

          <button
            class="btn"
            [disabled]="saving()"
            (click)="saveSettings()"
          >
            {{ saving() ? ('verification.saving' | snT:'Saving…') : ('verification.save' | snT:'Save settings') }}
          </button>
        </div>

        <label class="check">
          <input
            type="checkbox"
            [(ngModel)]="enabled"
          >
          {{ "verification.enabled" | snT:"Verification module enabled" }}
        </label>

        <label class="check">
          <input
            type="checkbox"
            [(ngModel)]="autoApprove"
          >
          {{ "verification.auto_approve" | snT:"Automatically approve new requests" }}
        </label>

        <label>
          {{ "verification.review_channel" | snT:"Review channel ID" }}
          <input
            [(ngModel)]="reviewChannelId"
            [placeholder]="'verification.channel_placeholder' | snT:'Discord channel ID'"
          >
        </label>

        <label>
          {{ "verification.verified_role" | snT:"Verified role" }}
          <select [(ngModel)]="verifiedRoleId">
            <option [ngValue]="null">
              {{ "verification.no_role" | snT:"Do not assign a role" }}
            </option>

            @for (
              role of roles();
              track role.discord_role_id
            ) {
              <option
                [ngValue]="role.discord_role_id"
              >
                {{ role.name }}
              </option>
            }
          </select>
        </label>

        <label>
          {{ "verification.nickname_template" | snT:"Nickname template" }}
          <input [(ngModel)]="nicknameTemplate">
          <small class="muted">
            {{ "verification.variables" | snT:"Variables" }}:
            &#123;alliance&#125;,
            &#123;nickname&#125;
          </small>
        </label>

        <div class="grid">
          <label>
            {{ "verification.alliance_min" | snT:"Alliance minimum" }}
            <input
              type="number"
              min="1"
              max="16"
              [(ngModel)]="allianceMin"
            >
          </label>

          <label>
            {{ "verification.alliance_max" | snT:"Alliance maximum" }}
            <input
              type="number"
              min="1"
              max="32"
              [(ngModel)]="allianceMax"
            >
          </label>
        </div>

        @if (message()) {
          <div class="message">
            {{ message() }}
          </div>
        }
      </section>

      <section class="card stats">
        <h2>{{ "verification.statistics" | snT:"Verification statistics" }}</h2>
        <div class="stats-grid">
          <div><strong>{{ summaryData().total || 0 }}</strong><span>{{ "verification.total" | snT:"Total" }}</span></div>
          <div><strong>{{ summaryData().pending || 0 }}</strong><span>{{ "verification.pending" | snT:"Pending" }}</span></div>
          <div><strong>{{ summaryData().completed || 0 }}</strong><span>{{ "verification.completed" | snT:"Completed" }}</span></div>
          <div><strong>{{ summaryData().failed || 0 }}</strong><span>{{ "verification.failed" | snT:"Failed" }}</span></div>
        </div>
      </section>

      <section class="queue">
        <div class="control-toolbar card">
          <strong>{{ "verification.control_center" | snT:"Control Center" }}</strong>

          <input
            [(ngModel)]="searchText"
            (keyup.enter)="reloadRequests()"
            [placeholder]="'verification.search_placeholder' | snT:'Search nickname, alliance or Discord ID'"
          >

          <button class="btn" (click)="reloadRequests()">
            Search
          </button>

          <button
            class="btn secondary"
            [disabled]="selectedIds().size === 0"
            (click)="bulkCancel()"
          >
            {{ "verification.cancel_selected" | snT:"Cancel selected" }}
          </button>

          <button
            class="btn secondary"
            [disabled]="selectedIds().size === 0"
            (click)="bulkRequeue()"
          >
            {{ "verification.requeue_selected" | snT:"Requeue selected" }}
          </button>

          <input
            class="minutes"
            type="number"
            min="1"
            max="1440"
            [(ngModel)]="staleMinutes"
          >

          <button class="btn secondary" (click)="recoverStale()">
            {{ "verification.recover_stale" | snT:"Recover stale" }}
          </button>

          <a
            class="btn secondary"
            [href]="exportUrl()"
          >
            {{ "verification.export_csv" | snT:"Export CSV" }}
          </a>
        </div>

        <div class="queue-heading">
          <div>
            <h2>{{ "verification.queue" | snT:"Verification queue" }}</h2>
            <p class="muted">
              {{ pendingCount() }} {{ "verification.waiting_review" | snT:"waiting for review" }}
            </p>
          </div>

          <select
            [(ngModel)]="statusFilter"
            (ngModelChange)="reloadRequests()"
          >
            <option value="">
              {{ "verification.all_statuses" | snT:"All statuses" }}
            </option>
            <option value="pending">
              Pending
            </option>
            <option value="approved">
              Approved
            </option>
            <option value="processing">
              Processing
            </option>
            <option value="completed">
              Completed
            </option>
            <option value="rejected">
              Rejected
            </option>
            <option value="changes_requested">
              Changes requested
            </option>
            <option value="failed">
              Failed
            </option>
          </select>
        </div>

        @for (
          item of requests();
          track item.id
        ) {
          <article class="card request">
            <label class="select-request">
              <input
                type="checkbox"
                [checked]="selectedIds().has(item.id)"
                (change)="toggleSelected(item.id)"
              >
            </label>

            <div class="request-main">
              <strong>
                {{ item.requested_nickname }}
              </strong>

              <div class="muted">
                Alliance: {{ item.alliance }}
                · Discord ID:
                {{ item.discord_user_id }}
              </div>

              <small class="muted">
                Created: {{ item.created_at }}
              </small>

              @if (
                item.decision_reason ||
                item.result_message
              ) {
                <div class="reason">
                  {{
                    item.decision_reason ||
                    item.result_message
                  }}
                </div>
              }
            </div>

            <div class="request-side">
              <span
                class="status"
                [class.failed]="
                  item.status === 'failed' ||
                  item.status === 'rejected'
                "
              >
                {{ item.status }}
              </span>

              @if (item.status === 'failed' || item.status === 'processing') {
                <button class="btn" (click)="requeue(item)">{{ "verification.requeue" | snT:"Requeue" }}</button>
              }

              @if (item.status === 'pending') {
                <div class="buttons">
                  <button class="btn secondary" (click)="resendReview(item)">{{ "verification.resend" | snT:"Resend" }}</button>
                  <button class="btn danger" (click)="cancel(item)">{{ "verification.cancel" | snT:"Cancel" }}</button>
                  <button
                    class="btn"
                    (click)="openApprove(item)"
                  >
                    Approve
                  </button>

                  <button class="btn secondary" (click)="openChanges(item)">{{ "verification.request_changes" | snT:"Request changes" }}</button>
                  <button
                    class="btn danger"
                    (click)="openReject(item)"
                  >
                    Reject
                  </button>
                </div>
              }
            </div>
          </article>
        }
      </section>

      @if (decisionDialog()) {
        <div
          class="overlay"
          (click)="closeDecision()"
        >
          <section
            class="card dialog"
            (click)="$event.stopPropagation()"
          >
            <h3>
              {{
                decisionMode() === 'approve' ? 'Approve verification' : decisionMode() === 'changes' ? 'Request changes' : 'Reject verification'
              }}
            </h3>

            <p class="muted">
              {{ selectedRequest()?.requested_nickname }}
            </p>

            <label>
              {{
                decisionMode() === 'approve' ? 'Comment (optional)' : 'Reason (required)'
              }}

              <textarea
                rows="5"
                [(ngModel)]="decisionReason"
              ></textarea>
            </label>

            @if (decisionError()) {
              <div class="error">
                {{ decisionError() }}
              </div>
            }

            <footer>
              <button
                class="btn secondary"
                (click)="closeDecision()"
              >
                Cancel
              </button>

              <button
                class="btn"
                [class.danger]="
                  decisionMode() === 'reject'
                "
                [disabled]="deciding()"
                (click)="submitDecision()"
              >
                {{
                  deciding()
                    ? 'Saving…'
                    : decisionMode() === 'approve' ? 'Approve' : decisionMode() === 'changes' ? 'Request changes' : 'Reject'
                }}
              </button>
            </footer>
          </section>
        </div>
      }
    </sn-shell>
  `,
  styles: [`
    .panel {
      padding: 1.2rem;
      display: grid;
      gap: 1rem;
    }

    .heading,
    .queue-heading,
    .request {
      display: flex;
      justify-content: space-between;
      gap: 1rem;
    }

    .heading,
    .queue-heading {
      align-items: center;
    }

    h2,
    h3,
    p {
      margin: 0;
    }

    label {
      display: grid;
      gap: .35rem;
      color: var(--muted);
    }

    input,
    select,
    textarea {
      padding: .8rem;
      color: var(--text);
      background: var(--panel-2);
      border: 1px solid var(--line);
      border-radius: 10px;
    }

    textarea {
      resize: vertical;
    }

    .check {
      display: flex;
      align-items: center;
      gap: .6rem;
    }

    .check input {
      width: auto;
    }

    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: .8rem;
    }

    .stats { margin-top: 1.2rem; padding: 1rem; }
    .stats-grid { margin-top: .8rem; display: grid; grid-template-columns: repeat(4, 1fr); gap: .7rem; }
    .stats-grid div { padding: .8rem; display: grid; gap: .2rem; background: var(--panel-2); border-radius: 10px; }
    .stats-grid strong { font-size: 1.4rem; }

    .control-toolbar {
      margin-bottom: 1rem;
      padding: .8rem;
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: .6rem;
    }

    .control-toolbar input {
      min-width: 220px;
      flex: 1;
    }

    .control-toolbar .minutes {
      min-width: 90px;
      max-width: 110px;
      flex: 0 0 auto;
    }

    .select-request {
      display: flex;
      align-items: flex-start;
      padding-top: .15rem;
    }

    .select-request input {
      width: auto;
    }

    .queue {
      margin-top: 1.2rem;
    }

    .request {
      margin-top: .7rem;
      padding: 1rem;
      align-items: flex-start;
    }

    .request-main {
      display: grid;
      gap: .35rem;
    }

    .request-side {
      display: grid;
      justify-items: end;
      gap: .75rem;
    }

    .status {
      padding: .25rem .55rem;
      border-radius: 999px;
      border: 1px solid rgba(75,214,155,.35);
      color: #b9f4dc;
      text-transform: uppercase;
      font-size: .72rem;
    }

    .status.failed {
      color: #ffd9de;
      border-color: rgba(255,107,125,.35);
    }

    .buttons,
    footer {
      display: flex;
      gap: .55rem;
    }

    .danger {
      color: #ffd9de;
      border-color: rgba(255,107,125,.35);
    }

    .reason,
    .message,
    .error {
      padding: .7rem;
      border-radius: 9px;
    }

    .reason {
      background: var(--panel-2);
    }

    .message {
      background: rgba(75,214,155,.1);
      color: #b9f4dc;
    }

    .error {
      background: rgba(255,107,125,.1);
      color: #ffd9de;
    }

    .overlay {
      position: fixed;
      inset: 0;
      z-index: 1000;
      display: grid;
      place-items: center;
      padding: 1rem;
      background: rgba(0,0,0,.72);
      backdrop-filter: blur(8px);
    }

    .dialog {
      width: min(540px,100%);
      padding: 1.2rem;
      display: grid;
      gap: 1rem;
    }

    footer {
      justify-content: flex-end;
    }

    @media (max-width: 700px) {
      .heading,
      .queue-heading,
      .request {
        flex-direction: column;
        align-items: stretch;
      }

      .grid {
        grid-template-columns: 1fr;
      }

      .request-side {
        justify-items: stretch;
      }
    }
  `],
})
export class VerificationComponent
  implements OnInit
{
  readonly guildId = this.route.snapshot.paramMap.get('guildId') ?? '';

  readonly roles = signal<any[]>([]);
  readonly requests = signal<any[]>([]);
  readonly summaryData = signal<any>({});
  readonly saving = signal(false);
  readonly message = signal('');
  readonly decisionDialog = signal(false);
  readonly decisionMode = signal<
    'approve' | 'reject' | 'changes'
  >('approve');
  readonly selectedRequest = signal<any | null>(
    null,
  );
  readonly deciding = signal(false);
  readonly decisionError = signal('');

  enabled = false;
  autoApprove = false;
  verifiedRoleId: number | null = null;
  reviewChannelId = '';
  nicknameTemplate = '[{alliance}] {nickname}';
  allianceMin = 2;
  allianceMax = 8;
  statusFilter = '';
  searchText = '';
  staleMinutes = 10;
  readonly selectedIds = signal<Set<string>>(new Set());
  decisionReason = '';

  constructor(
    private readonly route: ActivatedRoute,
    private readonly verification: VerificationService,
    private readonly guildRoles: GuildRoleService,
  ) {}

  async ngOnInit(): Promise<void> {
    const [settings, roles] = await Promise.all([
      this.verification.getSettings(this.guildId),
      this.guildRoles.list(this.guildId),
    ]);

    this.enabled = settings.enabled;
    this.autoApprove = settings.auto_approve;
    this.verifiedRoleId =
      settings.verified_role_id;
    this.reviewChannelId = settings.review_channel_id
      ? String(settings.review_channel_id)
      : '';
    this.nicknameTemplate =
      settings.nickname_template;
    this.allianceMin =
      settings.alliance_min_length;
    this.allianceMax =
      settings.alliance_max_length;
    this.roles.set(roles);

    await Promise.all([this.reloadRequests(), this.loadSummary()]);
  }

  pendingCount(): number {
    return this.requests().filter(
      (item) => item.status === 'pending',
    ).length;
  }

  toggleSelected(requestId: string): void {
    const selected = new Set(this.selectedIds());

    if (selected.has(requestId)) {
      selected.delete(requestId);
    } else {
      selected.add(requestId);
    }

    this.selectedIds.set(selected);
  }

  async bulkCancel(): Promise<void> {
    await this.verification.bulkCancel(
      this.guildId,
      [...this.selectedIds()],
    );

    this.selectedIds.set(new Set());

    await Promise.all([
      this.reloadRequests(),
      this.loadSummary(),
    ]);
  }

  async bulkRequeue(): Promise<void> {
    await this.verification.bulkRequeue(
      this.guildId,
      [...this.selectedIds()],
    );

    this.selectedIds.set(new Set());

    await Promise.all([
      this.reloadRequests(),
      this.loadSummary(),
    ]);
  }

  async recoverStale(): Promise<void> {
    await this.verification.recoverStale(
      this.guildId,
      Number(this.staleMinutes),
    );

    await Promise.all([
      this.reloadRequests(),
      this.loadSummary(),
    ]);
  }

  exportUrl(): string {
    return this.verification.exportUrl(
      this.guildId,
      this.statusFilter || undefined,
    );
  }

  async loadSummary(): Promise<void> {
    this.summaryData.set(await this.verification.summary(this.guildId));
  }

  async cancel(item: any): Promise<void> {
    await this.verification.cancel(this.guildId, item.id);
    await Promise.all([this.reloadRequests(), this.loadSummary()]);
  }

  async requeue(item: any): Promise<void> {
    await this.verification.requeue(this.guildId, item.id);
    await Promise.all([this.reloadRequests(), this.loadSummary()]);
  }

  async resendReview(item: any): Promise<void> {
    await this.verification.resendReview(this.guildId, item.id);
    await this.reloadRequests();
  }

  async reloadRequests(): Promise<void> {
    const result =
      await this.verification.listRequests(
        this.guildId,
        this.statusFilter || undefined,
      );

    this.requests.set(result.items || []);
  }

  async saveSettings(): Promise<void> {
    this.saving.set(true);
    this.message.set('');

    try {
      await this.verification.saveSettings(
        this.guildId,
        {
          enabled: this.enabled,
          verified_role_id:
            this.verifiedRoleId,
          review_channel_id: this.reviewChannelId
            ? Number(this.reviewChannelId)
            : null,
          nickname_template:
            this.nicknameTemplate,
          auto_approve:
            this.autoApprove,
          alliance_min_length:
            Number(this.allianceMin),
          alliance_max_length:
            Number(this.allianceMax),
        },
      );

      this.message.set(
        'Verification settings saved.',
      );
    } catch {
      this.message.set(
        'Unable to save verification settings.',
      );
    } finally {
      this.saving.set(false);
    }
  }

  async retry(item: any): Promise<void> {
    await this.verification.retry(
      this.guildId,
      item.id,
    );

    await this.reloadRequests();
  }

  openApprove(item: any): void {
    this.selectedRequest.set(item);
    this.decisionMode.set('approve');
    this.decisionReason = '';
    this.decisionError.set('');
    this.decisionDialog.set(true);
  }

  openChanges(item: any): void {
    this.selectedRequest.set(item);
    this.decisionMode.set('changes');
    this.decisionReason = '';
    this.decisionError.set('');
    this.decisionDialog.set(true);
  }

  openReject(item: any): void {
    this.selectedRequest.set(item);
    this.decisionMode.set('reject');
    this.decisionReason = '';
    this.decisionError.set('');
    this.decisionDialog.set(true);
  }

  closeDecision(): void {
    this.decisionDialog.set(false);
    this.selectedRequest.set(null);
  }

  async submitDecision(): Promise<void> {
    const item = this.selectedRequest();

    if (!item) {
      return;
    }

    const reason = this.decisionReason.trim();

    if (
      this.decisionMode() !== 'approve' &&
      !reason
    ) {
      this.decisionError.set(
        'Reason is required.',
      );
      return;
    }

    this.deciding.set(true);
    this.decisionError.set('');

    try {
      if (this.decisionMode() === 'approve') {
        await this.verification.approve(this.guildId, item.id, reason || null);
      } else if (this.decisionMode() === 'changes') {
        await this.verification.requestChanges(this.guildId, item.id, reason);
      } else {
        await this.verification.reject(this.guildId, item.id, reason);
      }

      this.closeDecision();
      await this.reloadRequests();
    } catch {
      this.decisionError.set(
        'Unable to save this decision.',
      );
    } finally {
      this.deciding.set(false);
    }
  }
}
