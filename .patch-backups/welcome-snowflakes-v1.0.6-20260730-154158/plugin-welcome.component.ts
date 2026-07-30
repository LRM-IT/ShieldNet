import { CommonModule } from '@angular/common';
import { Component, HostListener, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { ShellComponent } from '../shared/shell.component';

interface ChannelItem {
  id:string; parent_id:string|null; name:string; type:string;
  position:number; nsfw:boolean; topic:string|null;
}
interface RoleItem {
  id:string; name:string; position:number; color:number;
  managed:boolean; assignable:boolean;
}
interface Settings {
  enabled:boolean;
  welcome_channel_id:number|null;
  verification_channel_id:number|null;
  required_role_id:number|null;
  message_template:string;
  repeat_enabled:boolean;
  repeat_minutes:number;
  max_reminders:number;
  delete_after_verified:boolean;
  ignore_bots:boolean;
}

@Component({
  selector:'sn-plugin-welcome',
  standalone:true,
  imports:[CommonModule,FormsModule,ShellComponent],
  template:`
  <sn-shell title="Welcome">
    <section class="page">
      <header class="topline">
        <div>
          <div class="eyebrow">SHIELDNET PLUGIN</div>
          <h2>Welcome</h2>
          <p>Welcome new members and redirect them to verification.</p>
        </div>
        <button class="btn" type="button" (click)="reload()">Refresh</button>
      </header>

      @if(error()){<div class="notice error">{{error()}}</div>}
      @if(success()){<div class="notice success">{{success()}}</div>}

      <div class="layout">
        <form class="panel form" (ngSubmit)="save()">
          <div class="panel-head">
            <div><small>SETTINGS</small><h3>Welcome flow</h3></div>
            <label class="switch">
              <input type="checkbox" [(ngModel)]="settings.enabled" name="enabled">
              Enabled
            </label>
          </div>

          <label class="field">
            General channel
            <div class="combo">
              <input [(ngModel)]="welcomeSearch" name="welcomeSearch"
                     (focus)="openSelector('welcome')"
                     (input)="openSelector('welcome')"
                     placeholder="Search text channel">
              @if(selectedWelcome()){<button type="button" class="clear" (click)="clearWelcome()">×</button>}
              @if(welcomeOpen()){
                <div class="options">
                  @for(channel of filteredWelcome();track channel.id){
                    <button type="button" (click)="selectWelcome(channel)">
                      <strong># {{channel.name}}</strong>
                      <small>{{categoryName(channel)}} · {{channel.id}}</small>
                    </button>
                  } @empty {<div class="empty">No text channels found.</div>}
                </div>
              }
            </div>
            @if(selectedWelcome();as channel){
              <span class="selected">Selected: #{{channel.name}}</span>
            }
          </label>

          <label class="field">
            Verification channel
            <div class="combo">
              <input [(ngModel)]="verificationSearch" name="verificationSearch"
                     (focus)="openSelector('verification')"
                     (input)="openSelector('verification')"
                     placeholder="Search verification channel">
              @if(selectedVerification()){<button type="button" class="clear" (click)="clearVerification()">×</button>}
              @if(verificationOpen()){
                <div class="options">
                  @for(channel of filteredVerification();track channel.id){
                    <button type="button" (click)="selectVerification(channel)">
                      <strong># {{channel.name}}</strong>
                      <small>{{categoryName(channel)}} · {{channel.id}}</small>
                    </button>
                  } @empty {<div class="empty">No text channels found.</div>}
                </div>
              }
            </div>
            @if(selectedVerification();as channel){
              <span class="selected">Selected: #{{channel.name}}</span>
            }
          </label>

          <label class="field">
            Stop when member receives role
            <div class="combo">
              <input [(ngModel)]="roleSearch" name="roleSearch"
                     (focus)="openSelector('role')"
                     (input)="openSelector('role')"
                     placeholder="Search role">
              @if(selectedRole()){<button type="button" class="clear" (click)="clearRole()">×</button>}
              @if(roleOpen()){
                <div class="options">
                  @for(role of filteredRoles();track role.id){
                    <button type="button" [disabled]="role.managed" (click)="selectRole(role)">
                      <strong><i class="role-dot" [style.background]="roleColor(role)"></i>{{role.name}}</strong>
                      <small>{{role.managed?'Managed role · ':''}}{{role.id}}</small>
                    </button>
                  } @empty {<div class="empty">No roles found.</div>}
                </div>
              }
            </div>
            @if(selectedRole();as role){
              <span class="selected">Selected: {{role.name}}</span>
            }
          </label>

          <label class="field">
            Welcome message
            <textarea [(ngModel)]="settings.message_template"
                      name="message_template" rows="9" maxlength="2000"></textarea>
          </label>

          <p class="hint">
            Variables:
            <code>{{'{mention}'}}</code>,
            <code>{{'{username}'}}</code>,
            <code>{{'{display_name}'}}</code>,
            <code>{{'{guild}'}}</code>,
            <code>{{'{verification_channel}'}}</code>
          </p>

          <section class="repeat-box">
            <label class="switch">
              <input type="checkbox" [(ngModel)]="settings.repeat_enabled" name="repeat_enabled">
              Repeat until the required role is received
            </label>
            <div class="grid">
              <label>Repeat every, minutes
                <input type="number" min="1" max="1440"
                       [(ngModel)]="settings.repeat_minutes" name="repeat_minutes">
              </label>
              <label>Maximum messages (0 = unlimited)
                <input type="number" min="0" max="1000"
                       [(ngModel)]="settings.max_reminders" name="max_reminders">
              </label>
            </div>
            <label class="switch">
              <input type="checkbox"
                     [(ngModel)]="settings.delete_after_verified"
                     name="delete_after_verified">
              Delete all welcome messages after verification
            </label>
            <label class="switch">
              <input type="checkbox" [(ngModel)]="settings.ignore_bots" name="ignore_bots">
              Ignore bots
            </label>
          </section>

          <button class="primary" type="submit" [disabled]="saving()">
            {{saving()?'Saving…':'Save settings'}}
          </button>
        </form>

        <aside class="right">
          <section class="panel preview">
            <div class="panel-head"><div><small>PREVIEW</small><h3>Discord message</h3></div></div>
            <div class="discord">
              <div class="avatar">S</div>
              <div>
                <div class="author"><strong>ShieldNet</strong><span>BOT</span><small>Today at 12:00</small></div>
                <div class="message">{{preview()}}</div>
              </div>
            </div>
          </section>

          <section class="panel tasks">
            <div class="panel-head"><div><small>ACTIVE FLOW</small><h3>Recent members</h3></div></div>
            @for(task of tasks();track task.id){
              <article>
                <div><strong>{{task.username}}</strong><span [attr.data-status]="task.status">{{task.status}}</span></div>
                <small>Messages: {{task.sent_count}} · Next: {{date(task.next_send_at)}}</small>
                @if(task.last_error){<p>{{task.last_error}}</p>}
              </article>
            } @empty {<div class="empty">No welcome tasks yet.</div>}
          </section>
        </aside>
      </div>
    </section>
  </sn-shell>
  `,
  styles:[`
    .page{display:grid;gap:1rem;padding:1.25rem}.topline,.panel-head{display:flex;justify-content:space-between;align-items:center;gap:1rem}
    h2,h3,p{margin:0}.eyebrow,.panel-head small{font-size:.66rem;font-weight:900;letter-spacing:.14em;color:var(--primary)}
    .topline p,.hint,small{color:var(--muted)}button,input,textarea{font:inherit}
    button{padding:.7rem .9rem;border:1px solid var(--line);border-radius:9px;background:var(--surface);color:var(--text);cursor:pointer}
    .layout{display:grid;grid-template-columns:minmax(0,1fr) 420px;gap:1rem;align-items:start}
    .panel{border:1px solid var(--line);border-radius:13px;background:var(--surface);padding:1rem}
    .form{display:grid;gap:1rem}.field{display:grid;gap:.42rem;color:var(--muted);font-size:.8rem}
    input,textarea{width:100%;box-sizing:border-box;padding:.76rem;border:1px solid var(--line);border-radius:8px;background:#080d14;color:var(--text)}
    textarea{resize:vertical}.switch{display:flex;align-items:center;gap:.55rem;color:var(--text);font-size:.8rem}.switch input{width:auto}
    .combo{position:relative}.clear{position:absolute;right:.35rem;top:.32rem;padding:.25rem .5rem;z-index:3}
    .options{position:absolute;z-index:20;left:0;right:0;top:calc(100% + .3rem);max-height:280px;overflow:auto;border:1px solid var(--line);border-radius:9px;background:#0b1119;box-shadow:0 18px 45px rgba(0,0,0,.35)}
    .options button{width:100%;display:grid;gap:.15rem;text-align:left;border:0;border-bottom:1px solid rgba(126,160,166,.08);border-radius:0;background:transparent}
    .options button:hover{background:rgba(53,226,178,.06)}.options button:disabled{opacity:.45}
    .selected{font-size:.7rem;color:var(--primary)}.role-dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:.45rem}
    code{color:var(--primary)}.repeat-box{display:grid;gap:.8rem;padding:.85rem;border:1px solid var(--line);border-radius:10px}
    .grid{display:grid;grid-template-columns:1fr 1fr;gap:.75rem}.grid label{display:grid;gap:.35rem;color:var(--muted);font-size:.76rem}
    .primary{background:rgba(53,226,178,.14);border-color:rgba(53,226,178,.35);color:#dffff5}
    .right{display:grid;gap:1rem;position:sticky;top:85px}.discord{display:grid;grid-template-columns:42px 1fr;gap:.7rem;margin-top:1rem}
    .avatar{width:42px;height:42px;display:grid;place-items:center;border-radius:50%;background:rgba(53,226,178,.16);color:var(--primary);font-weight:900}
    .author{display:flex;align-items:center;gap:.4rem}.author span{font-size:.58rem;padding:.1rem .28rem;border-radius:3px;background:#5865f2;color:white}.author small{font-size:.66rem}
    .message{white-space:pre-wrap;margin-top:.2rem;color:#d8dee4}.tasks{display:grid;gap:.65rem}.tasks article{display:grid;gap:.35rem;padding:.7rem;border:1px solid var(--line);border-radius:9px}
    .tasks article>div{display:flex;justify-content:space-between;gap:.5rem}.tasks span{text-transform:uppercase;font-size:.62rem;color:var(--primary)}
    .tasks p,.notice.error{color:#ff8290}.notice{padding:.8rem 1rem;border:1px solid var(--line);border-radius:9px}.notice.success{color:var(--primary)}
    .empty{padding:1rem;text-align:center;color:var(--muted)}@media(max-width:1100px){.layout{grid-template-columns:1fr}.right{position:static}}@media(max-width:700px){.grid{grid-template-columns:1fr}}
  `]
})
export class PluginWelcomeComponent implements OnInit{
  private http=inject(HttpClient);
  private route=inject(ActivatedRoute);

  channels=signal<ChannelItem[]>([]);
  roles=signal<RoleItem[]>([]);
  tasks=signal<any[]>([]);
  error=signal('');success=signal('');saving=signal(false);
  welcomeOpen=signal(false);verificationOpen=signal(false);roleOpen=signal(false);
  welcomeSearch='';verificationSearch='';roleSearch='';

  settings:Settings={
    enabled:true,welcome_channel_id:null,verification_channel_id:null,
    required_role_id:null,
    message_template:'👋 Welcome, {mention}!\\n\\nWelcome to **{guild}**.\\n\\nPlease continue to {verification_channel} and complete verification.',
    repeat_enabled:true,repeat_minutes:5,max_reminders:12,
    delete_after_verified:true,ignore_bots:true
  };

  private get guildId(){return this.route.snapshot.paramMap.get('guildId')||''}
  private get base(){return `/api/v1/discord/guilds/${this.guildId}/plugins/welcome`}

  selectedWelcome=computed(()=>this.channels().find(x=>Number(x.id)===this.settings.welcome_channel_id)||null);
  selectedVerification=computed(()=>this.channels().find(x=>Number(x.id)===this.settings.verification_channel_id)||null);
  selectedRole=computed(()=>this.roles().find(x=>Number(x.id)===this.settings.required_role_id)||null);

  filteredWelcome=computed(()=>this.filterChannels(this.welcomeSearch));
  filteredVerification=computed(()=>this.filterChannels(this.verificationSearch));
  filteredRoles=computed(()=>{
    const q=this.roleSearch.trim().toLowerCase();
    return this.roles().filter(r=>r.name!=='@everyone'&&(!q||r.name.toLowerCase().includes(q)||r.id.includes(q))).slice(0,50);
  });
  preview=computed(()=>{
    const wc=this.selectedVerification();
    return this.settings.message_template
      .replaceAll('{mention}','@NewMember')
      .replaceAll('{username}','newmember')
      .replaceAll('{display_name}','New Member')
      .replaceAll('{guild}','Example Server')
      .replaceAll('{verification_channel}',wc?`#${wc.name}`:'#verification');
  });

  @HostListener('document:mousedown', ['$event'])
  closeSelectorsOnOutsideClick(event: MouseEvent): void {
    const target = event.target;
    if (!(target instanceof Element) || !target.closest('.combo')) {
      this.closeSelectors();
    }
  }

  @HostListener('document:keydown.escape')
  closeSelectorsOnEscape(): void {
    this.closeSelectors();
  }

  openSelector(selector: 'welcome' | 'verification' | 'role'): void {
    this.welcomeOpen.set(selector === 'welcome');
    this.verificationOpen.set(selector === 'verification');
    this.roleOpen.set(selector === 'role');
  }

  closeSelectors(): void {
    this.welcomeOpen.set(false);
    this.verificationOpen.set(false);
    this.roleOpen.set(false);
  }

  ngOnInit(){this.reload()}
  reload(){
    this.error.set('');
    this.http.get<any>(`/api/v1/discord/guilds/${this.guildId}/structure`).subscribe({
      next:v=>{this.channels.set((v.channels||[]).filter((x:ChannelItem)=>['text','0','guild_text'].includes(String(x.type).toLowerCase())));this.roles.set(v.roles||[])},
      error:()=>this.error.set('Unable to load Discord channels and roles.')
    });
    this.http.get<Settings>(`${this.base}/settings`).subscribe({next:v=>this.settings={...this.settings,...v},error:()=>this.error.set('Unable to load Welcome settings.')});
    this.http.get<any>(`${this.base}/tasks`).subscribe({next:v=>this.tasks.set(v.items||[])});
  }
  filterChannels(query:string){
    const q=query.trim().toLowerCase();
    return this.channels().filter(c=>!q||c.name.toLowerCase().includes(q)||c.id.includes(q)).slice(0,50);
  }
  categoryName(channel:ChannelItem){const p=this.channels().find(x=>x.id===channel.parent_id);return p?.name||'No category'}
  selectWelcome(c:ChannelItem){this.settings.welcome_channel_id=Number(c.id);this.welcomeSearch=c.name;this.closeSelectors()}
  selectVerification(c:ChannelItem){this.settings.verification_channel_id=Number(c.id);this.verificationSearch=c.name;this.closeSelectors()}
  selectRole(r:RoleItem){if(r.managed)return;this.settings.required_role_id=Number(r.id);this.roleSearch=r.name;this.closeSelectors()}
  clearWelcome(){this.settings.welcome_channel_id=null;this.welcomeSearch=''}
  clearVerification(){this.settings.verification_channel_id=null;this.verificationSearch=''}
  clearRole(){this.settings.required_role_id=null;this.roleSearch=''}
  roleColor(role:RoleItem){return role.color?`#${role.color.toString(16).padStart(6,'0')}`:'#7289da'}
  date(v:string|null){return v?new Date(v).toLocaleString():'—'}
  save(){
    this.saving.set(true);this.error.set('');this.success.set('');
    this.http.put<Settings>(`${this.base}/settings`,this.settings).subscribe({
      next:v=>{this.settings=v;this.saving.set(false);this.success.set('Welcome settings saved.')},
      error:r=>{this.saving.set(false);this.error.set(r?.error?.detail||'Unable to save settings.')}
    });
  }
}
