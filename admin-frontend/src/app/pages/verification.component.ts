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
import { TranslationService } from '../core/translation.service';
import { DiscordChannelPickerComponent } from '../shared/discord-channel-picker.component';

@Component({
  standalone: true,
  imports: [
    FormsModule,
    ShellComponent,
    TranslatePipe,
    DiscordChannelPickerComponent,
  ],
  template: `
    <sn-shell [title]="'verification.title' | snT:'Verification'">
      <section class="card panel">
        <div class="heading">
          <div>
            <h2>{{ "verification.settings" | snT:"Verification settings" }}</h2>
            <p class="muted">
              {{ "verification.description" | snT:"Configure the verification command, approval mode and Verified role." }}
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

        <label>{{ "verification.review_channel" | snT:"Review channel" }}
          <sn-discord-channel-picker [guildId]="guildId" [value]="reviewChannelId || null" (valueChange)="reviewChannelId=$event || ''" />
        </label>

        <label>{{'verification.invocation_channel'|snT:'Verification command channel or thread'}}
          <sn-discord-channel-picker [guildId]="guildId" [value]="invocationChannelId || null" (valueChange)="invocationChannelId=$event || ''" />
          <small class="muted">{{'verification.invocation_channel_help'|snT:'Text commands and /verify are accepted only in this channel or thread.'}}</small>
        </label>

        <label>{{'verification.text_commands'|snT:'Text commands'}}
          <input [(ngModel)]="textCommands" maxlength="255" placeholder="!verify, !верифікація">
          <small class="muted">{{'verification.text_commands_help'|snT:'Up to 10 comma-separated commands. Prefixes !, . and ? are supported.'}}</small>
        </label>

        <label>{{'verification.slash_command'|snT:'Slash command name'}}
          <div class="command-input"><span>/</span><input [(ngModel)]="slashCommandName" maxlength="32" placeholder="verify"></div>
          <small class="muted">{{'verification.slash_command_help'|snT:'Use lowercase Latin letters, numbers, _ or -. Discord updates the command automatically after saving.'}}</small>
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
            &#123;server&#125;
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

      <section class="card panel levels">
        <div class="heading"><div><h2>{{'verification.levels'|snT:'Verification levels'}}</h2><p class="muted">{{'verification.levels_help'|snT:'The first level uses the form above. Additional levels check profile images through AI Center.'}}</p></div>
          <button class="btn" (click)="addLevel()">{{'verification.add_level'|snT:'Add level'}}</button></div>
        @for (level of levels(); track level.id) {
          <details class="level-card"><summary><strong>{{level.name}}</strong><span>{{level.enabled ? ('verification.active'|snT:'ACTIVE') : ('verification.disabled'|snT:'DISABLED')}}⌄</span></summary>
            <div class="level-body">
              <label>{{'verification.level_name'|snT:'Level name'}}<input [(ngModel)]="level.name" maxlength="80"></label>
              <label class="check"><input type="checkbox" [(ngModel)]="level.enabled"> {{'verification.level_enabled'|snT:'Level enabled'}}</label>
              <label>{{'verification.image_channel'|snT:'Image submission channel'}}<sn-discord-channel-picker [guildId]="guildId" [value]="level.channel_id" (valueChange)="level.channel_id=$event" /></label>
              <div class="criteria"><div class="heading"><div><h3>{{'verification.criteria_roles'|snT:'Criteria and roles'}}</h3><p class="muted">{{'verification.criteria_help'|snT:'AI checks each criterion separately and combines roles from all matches.'}}</p></div><button class="btn secondary" (click)="addCriterion(level)">{{'verification.add_criterion'|snT:'Add criterion'}}</button></div>
                @for (criterion of level.criteria; track $index) {
                  <article class="criterion"><label>{{'verification.criterion_name'|snT:'Criterion name'}}<input [(ngModel)]="criterion.label" maxlength="80" [placeholder]="'verification.criterion_example'|snT:'For example: Leader'"></label>
                    <label>{{'verification.accepted_values'|snT:'Accepted values'}}<input [(ngModel)]="criterion.values_text" maxlength="1000" [placeholder]="'verification.values_example'|snT:'For example: R4, R5'"><span class="field-help">{{'verification.values_help'|snT:'Separate values with commas or new lines. Any matching value activates the roles below.'}}</span></label>
                    <label>{{'verification.match_roles'|snT:'Roles for this match'}}<select multiple [(ngModel)]="criterion.role_ids">
                      @for (role of roles(); track role.discord_role_id) { <option [value]="role.discord_role_id">{{role.name}}</option> }
                    </select></label>
                    <button class="btn danger" (click)="removeCriterion(level,$index)">{{'verification.remove_criterion'|snT:'Remove criterion'}}</button>
                  </article>
                } @empty { <p class="muted">{{'verification.criteria_empty'|snT:'Add at least one rule, for example Leader with values R4 and R5.'}}</p> }
              </div>
              <label>{{'verification.reference_image'|snT:'Reference image'}}<input type="file" accept="image/png,image/jpeg,image/webp" (change)="selectTemplate(level,$event)"></label>
              @if (level.preview || level.template_url) {
                <div class="marker-image"><img [src]="level.preview || level.template_url"><div class="marker" [style.left.%]="level.marker.x*100" [style.top.%]="level.marker.y*100" [style.width.%]="level.marker.width*100" [style.height.%]="level.marker.height*100"></div></div>
                <button class="btn secondary" (click)="openMarkerEditor(level)">{{'verification.select_region'|snT:'Select the verification region visually'}}</button>
              }
              <p class="muted">{{'verification.region_help'|snT:'Mark the area where AI should look for the verification criterion.'}}</p>
              <div class="buttons"><button class="btn" (click)="saveLevel(level)">{{'verification.save_level'|snT:'Save level'}}</button><button class="btn danger" (click)="removeLevel(level)">{{'verification.delete'|snT:'Delete'}}</button></div>
            </div>
          </details>
        } @empty { <p class="muted">{{'verification.no_levels'|snT:'No additional levels yet.'}}</p> }
      </section>

      @if (markerLevel) {
        <div class="marker-modal" role="dialog" aria-modal="true">
          <section class="card marker-dialog">
            <div class="heading"><div><h2>{{'verification.verification_region'|snT:'Verification region'}}</h2><p class="muted">{{'verification.region_editor_help'|snT:'Drag over the required image area with a mouse or finger.'}}</p></div><button class="btn secondary" (click)="closeMarkerEditor()">{{'verification.close'|snT:'Close'}}</button></div>
            <div class="marker-editor" (pointerdown)="markerStart($event)" (pointermove)="markerMove($event)" (pointerup)="markerEnd($event)" (pointercancel)="markerEnd($event)">
              <img [src]="markerLevel.preview || markerLevel.template_url" draggable="false">
              <div class="marker active" [style.left.%]="markerDraft.x*100" [style.top.%]="markerDraft.y*100" [style.width.%]="markerDraft.width*100" [style.height.%]="markerDraft.height*100"></div>
            </div>
            <div class="buttons"><button class="btn secondary" (click)="resetMarker()">{{'verification.select_entire_image'|snT:'Select entire image'}}</button><button class="btn" (click)="applyMarker()">{{'verification.apply_region'|snT:'Apply region'}}</button></div>
          </section>
        </div>
      }

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
            {{ "verification.search" | snT:"Search" }}
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
              {{'verification.pending'|snT:'Pending'}}
            </option>
            <option value="approved">
              {{'verification.approved'|snT:'Approved'}}
            </option>
            <option value="processing">
              {{'verification.processing'|snT:'Processing'}}
            </option>
            <option value="completed">
              {{'verification.completed'|snT:'Completed'}}
            </option>
            <option value="rejected">
              {{'verification.rejected'|snT:'Rejected'}}
            </option>
            <option value="changes_requested">
              {{'verification.changes_requested'|snT:'Changes requested'}}
            </option>
            <option value="failed">
              {{'verification.failed'|snT:'Failed'}}
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
                {{'verification.alliance'|snT:'Alliance'}}: {{ item.alliance }}
                · {{'verification.discord_id'|snT:'Discord ID'}}:
                {{ item.discord_user_id }}
              </div>

              <small class="muted">
                {{'verification.created'|snT:'Created'}}: {{ item.created_at }}
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
                {{ statusLabel(item.status) }}
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
                    {{'verification.approve'|snT:'Approve'}}
                  </button>

                  <button class="btn secondary" (click)="openChanges(item)">{{ "verification.request_changes" | snT:"Request changes" }}</button>
                  <button
                    class="btn danger"
                    (click)="openReject(item)"
                  >
                    {{'verification.reject'|snT:'Reject'}}
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
                decisionMode() === 'approve' ? ('verification.approve_verification'|snT:'Approve verification') : decisionMode() === 'changes' ? ('verification.request_changes'|snT:'Request changes') : ('verification.reject_verification'|snT:'Reject verification')
              }}
            </h3>

            <p class="muted">
              {{ selectedRequest()?.requested_nickname }}
            </p>

            <label>
              {{
                decisionMode() === 'approve' ? ('verification.comment_optional'|snT:'Comment (optional)') : ('verification.reason_required'|snT:'Reason (required)')
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
                {{'verification.cancel'|snT:'Cancel'}}
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
                    ? ('verification.saving'|snT:'Saving…')
                    : decisionMode() === 'approve' ? ('verification.approve'|snT:'Approve') : decisionMode() === 'changes' ? ('verification.request_changes'|snT:'Request changes') : ('verification.reject'|snT:'Reject')
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

    .command-input { display:flex; align-items:center; background:var(--panel-2); border:1px solid var(--line); border-radius:10px; }
    .command-input span { padding-left:.8rem; font-weight:800; color:var(--text); }
    .command-input input { flex:1; border:0; background:transparent; }
    .levels{margin-top:1.2rem}.level-card{border:1px solid var(--line);border-radius:12px;overflow:hidden}.level-card summary{display:flex;justify-content:space-between;padding:1rem;cursor:pointer;list-style:none}.level-body{display:grid;gap:.8rem;padding:1rem;border-top:1px solid var(--line)}.criteria{display:grid;gap:.8rem}.criterion{display:grid;grid-template-columns:minmax(180px,.8fr) minmax(260px,1.2fr) minmax(260px,1.2fr);gap:1rem;align-items:start;padding:1rem;border:1px solid var(--line);border-radius:12px;background:var(--panel-2)}.criterion>label{min-width:0;align-content:start}.criterion input{min-height:3.75rem}.criterion select{height:8.5rem;overflow-y:auto}.criterion .field-help{min-height:3rem;font-size:.9rem;line-height:1.35;color:var(--muted)}.criterion>.danger{grid-column:1/-1;justify-self:end}.marker-image{position:relative;width:min(100%,700px)}.marker-image img{display:block;width:100%;border-radius:10px}.marker{position:absolute;border:3px solid #45e0b3;background:rgba(69,224,179,.14);pointer-events:none}.marker-modal{position:fixed;inset:0;z-index:1200;display:grid;place-items:center;padding:1rem;background:rgba(0,0,0,.78);backdrop-filter:blur(8px)}.marker-dialog{width:min(1100px,96vw);max-height:95vh;overflow:auto;padding:1.2rem}.marker-editor{position:relative;width:fit-content;max-width:100%;margin:auto;cursor:crosshair;touch-action:none;user-select:none;background:#050708;border-radius:12px;overflow:hidden}.marker-editor img{display:block;max-width:100%;max-height:72vh;width:auto;height:auto;pointer-events:none}.marker.active{border-width:4px;box-shadow:0 0 0 9999px rgba(0,0,0,.42)}

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

    @media (max-width: 1050px) {
      .criterion{grid-template-columns:1fr 1fr}.criterion>label:last-of-type{grid-column:1/-1}
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
      .criterion{grid-template-columns:1fr}.criterion>label:last-of-type{grid-column:auto}

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
  readonly levels = signal<any[]>([]);
  markerLevel:any=null;
  markerDraft:any={x:0,y:0,width:1,height:1};
  private markerOrigin:{x:number;y:number}|null=null;
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
  invocationChannelId = '';
  textCommands = '!verify';
  slashCommandName = 'verify';
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
    private readonly i18n: TranslationService,
  ) {}

  async ngOnInit(): Promise<void> {
    const [settings, roles, levels] = await Promise.all([
      this.verification.getSettings(this.guildId),
      this.guildRoles.list(this.guildId),
      this.verification.levels(this.guildId),
    ]);

    this.enabled = settings.enabled;
    this.autoApprove = settings.auto_approve;
    this.verifiedRoleId =
      settings.verified_role_id;
    this.reviewChannelId = settings.review_channel_id
      ? String(settings.review_channel_id)
      : '';
    this.invocationChannelId = settings.invocation_channel_id ? String(settings.invocation_channel_id) : '';
    this.textCommands = settings.text_commands || '';
    this.slashCommandName = settings.slash_command_name || 'verify';
    this.nicknameTemplate =
      settings.nickname_template;
    this.allianceMin =
      settings.alliance_min_length;
    this.allianceMax =
      settings.alliance_max_length;
    this.roles.set(roles);
    this.levels.set(levels.map(level=>({...level,criteria:(level.criteria||[]).map((criterion:any)=>({
      ...criterion,
      values_text:(criterion.values?.length ? criterion.values : [criterion.expected_text]).filter(Boolean).join(', '),
    }))})));

    await Promise.all([this.reloadRequests(), this.loadSummary()]);
  }

  async addLevel(): Promise<void> {
    const row=await this.verification.createLevel(this.guildId,{name:`${this.i18n.t('verification.level','Level')} ${this.levels().length+2}`,enabled:false,channel_id:null,expected_text:'',role_ids:[],criteria:[],marker:{x:0,y:0,width:1,height:1}});
    this.levels.update(items=>[...items,row]);
  }
  selectTemplate(level:any,event:Event):void { const file=(event.target as HTMLInputElement).files?.[0]; if(!file)return; level.file=file; if(level.preview)URL.revokeObjectURL(level.preview); level.preview=URL.createObjectURL(file); setTimeout(()=>this.openMarkerEditor(level)); }
  openMarkerEditor(level:any):void { this.markerLevel=level; this.markerDraft={...(level.marker||{x:0,y:0,width:1,height:1})}; }
  closeMarkerEditor():void { this.markerLevel=null; this.markerOrigin=null; }
  resetMarker():void { this.markerDraft={x:0,y:0,width:1,height:1}; }
  applyMarker():void { if(this.markerLevel){this.markerLevel.marker={...this.markerDraft};} this.closeMarkerEditor(); }
  private markerPoint(event:PointerEvent):{x:number;y:number}{const rect=(event.currentTarget as HTMLElement).getBoundingClientRect();return{x:Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width)),y:Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height))};}
  markerStart(event:PointerEvent):void { event.preventDefault(); (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId); const point=this.markerPoint(event); this.markerOrigin=point; this.markerDraft={x:point.x,y:point.y,width:.001,height:.001}; }
  markerMove(event:PointerEvent):void { if(!this.markerOrigin)return; const point=this.markerPoint(event),origin=this.markerOrigin; this.markerDraft={x:Math.min(origin.x,point.x),y:Math.min(origin.y,point.y),width:Math.max(.001,Math.abs(point.x-origin.x)),height:Math.max(.001,Math.abs(point.y-origin.y))}; }
  markerEnd(event:PointerEvent):void { if(!this.markerOrigin)return; this.markerMove(event); this.markerOrigin=null; try{(event.currentTarget as HTMLElement).releasePointerCapture(event.pointerId)}catch{} }
  addCriterion(level:any):void { level.criteria=level.criteria||[]; level.criteria.push({label:`${this.i18n.t('verification.criterion','Criterion')} ${level.criteria.length+1}`,expected_text:'',values:[],values_text:'',role_ids:[]}); }
  removeCriterion(level:any,index:number):void { level.criteria.splice(index,1); }
  async saveLevel(level:any):Promise<void> {
    const criteria=(level.criteria||[]).map((item:any)=>{
      const values=String(item.values_text||'').split(/[,\n]/).map(value=>value.trim()).filter(Boolean);
      return {label:item.label,expected_text:values[0]||'',values,role_ids:(item.role_ids||[]).map(Number)};
    });
    const payload={name:level.name,enabled:level.enabled,channel_id:level.channel_id?Number(level.channel_id):null,expected_text:criteria[0]?.expected_text||'',role_ids:criteria[0]?.role_ids||[],criteria,marker:level.marker};
    if(level.file)await this.verification.uploadLevelTemplate(this.guildId,level.id,level.file,level.marker);
    const saved=await this.verification.updateLevel(this.guildId,level.id,payload);
    Object.assign(level,saved,{file:null,preview:null,criteria:(saved.criteria||[]).map((criterion:any)=>({...criterion,values_text:(criterion.values||[criterion.expected_text]).filter(Boolean).join(', ')}))}); this.message.set(this.i18n.t('verification.level_saved','Level {name} saved.').replace('{name}',level.name));
  }
  async removeLevel(level:any):Promise<void> { await this.verification.deleteLevel(this.guildId,level.id); this.levels.update(items=>items.filter(item=>item.id!==level.id)); }

  statusLabel(status:string):string {
    const fallback:Record<string,string>={pending:'Pending',approved:'Approved',processing:'Processing',completed:'Completed',rejected:'Rejected',changes_requested:'Changes requested',failed:'Failed'};
    return this.i18n.t(`verification.${status}`,fallback[status]||status);
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
          invocation_channel_id: this.invocationChannelId ? Number(this.invocationChannelId) : null,
          text_commands: this.textCommands,
          slash_command_name: this.slashCommandName,
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
        this.i18n.t('verification.settings_saved','Verification settings saved.'),
      );
    } catch {
      this.message.set(
        this.i18n.t('verification.settings_save_error','Unable to save verification settings.'),
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
        this.i18n.t('verification.reason_required_error','Reason is required.'),
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
        this.i18n.t('verification.decision_save_error','Unable to save this decision.'),
      );
    } finally {
      this.deciding.set(false);
    }
  }
}
