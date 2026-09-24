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
              {{ "verification.description" | snT:"Configure the verification command, member nickname and Verified role." }}
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

        <label>{{'verification.invocation_channel'|snT:'Verification command channel or thread'}}
          <sn-discord-channel-picker [guildId]="guildId" [value]="invocationChannelId || null" (valueChange)="invocationChannelId=$event || ''" />
          <small class="muted">{{'verification.invocation_channel_help'|snT:'Text commands and /verify are accepted only in this channel or thread.'}}</small>
        </label>

        <label>{{'verification.text_commands'|snT:'Text commands'}}
          <input [(ngModel)]="textCommands" maxlength="255" placeholder="!verify, !verification">
          <small class="muted">{{'verification.text_commands_help'|snT:'Up to 10 comma-separated commands. Prefixes !, . and ? are supported.'}}</small>
        </label>

        <label>{{'verification.slash_command'|snT:'Slash command name'}}
          <div class="command-input"><span>/</span><input [(ngModel)]="slashCommandName" maxlength="32" placeholder="verify"></div>
          <small class="muted">{{'verification.slash_command_help'|snT:'Use lowercase Latin letters, numbers, _ or -. Discord updates the command automatically after saving.'}}</small>
        </label>

        <label>{{'verification.cleanup_minutes'|snT:'Delete channel messages older than, minutes'}}
          <input type="number" min="0" max="10080" [(ngModel)]="channelCleanupMinutes">
          <small class="muted">{{'verification.cleanup_minutes_help'|snT:'All messages in the verification channel older than this value are deleted. Set 0 to disable cleanup.'}}</small>
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

    </sn-shell>
  `,
  styles: [`
    .panel {
      padding: 1.2rem;
      display: grid;
      gap: 1rem;
    }

    .heading {
      display: flex;
      justify-content: space-between;
      gap: 1rem;
    }

    .heading {
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

    .buttons,
    footer {
      display: flex;
      gap: .55rem;
    }

    .danger {
      color: #ffd9de;
      border-color: rgba(255,107,125,.35);
    }

    .message,
    .error {
      padding: .7rem;
      border-radius: 9px;
    }

    .message {
      background: rgba(75,214,155,.1);
      color: #b9f4dc;
    }

    .error {
      background: rgba(255,107,125,.1);
      color: #ffd9de;
    }

    footer {
      justify-content: flex-end;
    }

    @media (max-width: 1050px) {
      .criterion{grid-template-columns:1fr 1fr}.criterion>label:last-of-type{grid-column:1/-1}
    }

    @media (max-width: 700px) {
      .heading {
        flex-direction: column;
        align-items: stretch;
      }

      .grid {
        grid-template-columns: 1fr;
      }
      .criterion{grid-template-columns:1fr}.criterion>label:last-of-type{grid-column:auto}

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
  readonly saving = signal(false);
  readonly message = signal('');

  enabled = false;
  verifiedRoleId: string | null = null;
  invocationChannelId = '';
  textCommands = '!verify';
  slashCommandName = 'verify';
  channelCleanupMinutes = 0;
  nicknameTemplate = '[{alliance}] {nickname}';
  allianceMin = 2;
  allianceMax = 8;

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
    this.verifiedRoleId =
      settings.verified_role_id;
    this.invocationChannelId = settings.invocation_channel_id ? String(settings.invocation_channel_id) : '';
    this.textCommands = settings.text_commands || '';
    this.slashCommandName = settings.slash_command_name || 'verify';
    this.channelCleanupMinutes = Number(settings.channel_cleanup_minutes || 0);
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
    const payload={name:level.name,enabled:level.enabled,channel_id:level.channel_id ? String(level.channel_id) : null,expected_text:criteria[0]?.expected_text||'',role_ids:criteria[0]?.role_ids||[],criteria,marker:level.marker};
    if(level.file)await this.verification.uploadLevelTemplate(this.guildId,level.id,level.file,level.marker);
    const saved=await this.verification.updateLevel(this.guildId,level.id,payload);
    Object.assign(level,saved,{file:null,preview:null,criteria:(saved.criteria||[]).map((criterion:any)=>({...criterion,values_text:(criterion.values||[criterion.expected_text]).filter(Boolean).join(', ')}))}); this.message.set(this.i18n.t('verification.level_saved','Level {name} saved.').replace('{name}',level.name));
  }
  async removeLevel(level:any):Promise<void> { await this.verification.deleteLevel(this.guildId,level.id); this.levels.update(items=>items.filter(item=>item.id!==level.id)); }

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
          review_channel_id: null,
          invocation_channel_id: this.invocationChannelId || null,
          text_commands: this.textCommands,
          slash_command_name: this.slashCommandName,
          channel_cleanup_minutes: Number(this.channelCleanupMinutes || 0),
          nickname_template:
            this.nicknameTemplate,
          auto_approve: true,
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

}
