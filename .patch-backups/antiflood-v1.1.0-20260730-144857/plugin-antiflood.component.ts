import { CommonModule } from '@angular/common';
import { Component, HostListener, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { ShellComponent } from '../shared/shell.component';

interface ChannelItem { id:string; parent_id:string|null; name:string; type:string; }
interface RoleItem { id:string; name:string; managed:boolean; color:number; }
interface MemberItem { discord_user_id:number; username:string; display_name:string; }
interface Rule { channel_id:string; cooldown_seconds:number; enabled:boolean; }
interface Settings {
  enabled:boolean;
  ignore_bots:boolean;
  ignore_administrators:boolean;
  ignore_moderators:boolean;
  rules:Rule[];
  excluded_role_ids:string[];
  excluded_user_ids:string[];
}

@Component({
  selector:'sn-plugin-antiflood',
  standalone:true,
  imports:[CommonModule,FormsModule,ShellComponent],
  template:`
  <sn-shell title="AntiFlood">
    <section class="page">
      <header class="topline">
        <div><div class="eyebrow">SHIELDNET PLUGIN</div><h2>AntiFlood</h2>
        <p>Limit how often each user may write in selected channels.</p></div>
        <button type="button" (click)="reload()">Refresh</button>
      </header>

      @if(error()){<div class="notice error">{{error()}}</div>}
      @if(success()){<div class="notice success">{{success()}}</div>}

      <form class="panel" (ngSubmit)="save()">
        <div class="panel-head">
          <div><small>GENERAL</small><h3>Plugin settings</h3></div>
          <label class="switch"><input type="checkbox" [(ngModel)]="settings.enabled" name="enabled">Enabled</label>
        </div>

        <section class="box">
          <div class="panel-head"><div><small>RULES</small><h3>Protected channels</h3></div>
          <button type="button" (click)="addRule()">Add rule</button></div>

          @for(rule of settings.rules;track $index){
            <div class="rule">
              <div class="combo">
                <input [ngModel]="channelText(rule)" (ngModelChange)="searchRule($index,$event)"
                       [name]="'channel'+$index" (focus)="openRule($index)"
                       placeholder="Search channel">
                @if(openRuleIndex()===$index){
                  <div class="options">
                    @for(channel of filteredChannels($index);track channel.id){
                      <button type="button" (click)="selectChannel(rule,channel)">
                        <strong># {{channel.name}}</strong><small>{{channel.id}}</small>
                      </button>
                    } @empty {<div class="empty">No channels found.</div>}
                  </div>
                }
              </div>
              <label>Cooldown, seconds
                <input type="number" min="1" max="604800"
                       [(ngModel)]="rule.cooldown_seconds" [name]="'cooldown'+$index">
              </label>
              <label class="switch"><input type="checkbox" [(ngModel)]="rule.enabled" [name]="'ruleEnabled'+$index">Enabled</label>
              <button type="button" class="danger" (click)="removeRule($index)">Remove</button>
            </div>
          } @empty {<div class="empty">No AntiFlood rules configured.</div>}
        </section>

        <section class="box">
          <div><small>EXCEPTIONS</small><h3>Required exceptions</h3></div>
          <label class="switch"><input type="checkbox" [(ngModel)]="settings.ignore_bots" name="ignore_bots">Ignore bots</label>
          <label class="switch"><input type="checkbox" [(ngModel)]="settings.ignore_administrators" name="ignore_administrators">Ignore administrators</label>
          <label class="switch"><input type="checkbox" [(ngModel)]="settings.ignore_moderators" name="ignore_moderators">Ignore moderators with Manage Messages</label>

          <label class="field">Excluded roles
            <div class="combo">
              <input [(ngModel)]="roleSearch" name="roleSearch" (focus)="openSelector('roles')" (input)="openSelector('roles')" placeholder="Search role">
              @if(roleOpen()){
                <div class="options">
                  @for(role of filteredRoles();track role.id){
                    <button type="button" (click)="toggleRole(role)">
                      <strong>{{selectedRole(role)?'✓ ':''}}{{role.name}}</strong><small>{{role.id}}</small>
                    </button>
                  }
                </div>
              }
            </div>
          </label>
          <div class="chips">
            @for(id of settings.excluded_role_ids;track id){
              <button type="button" (click)="removeRole(id)">{{roleName(id)}} ×</button>
            }
          </div>

          <label class="field">Excluded users
            <div class="combo">
              <input [(ngModel)]="userSearch" name="userSearch" (focus)="openSelector('users')" (input)="loadMembers()" placeholder="Search member">
              @if(userOpen()){
                <div class="options">
                  @for(member of members();track member.discord_user_id){
                    <button type="button" (click)="toggleUser(member)">
                      <strong>{{selectedUser(member)?'✓ ':''}}{{member.display_name||member.username}}</strong>
                      <small>{{member.username}} · {{member.discord_user_id}}</small>
                    </button>
                  } @empty {<div class="empty">No members found.</div>}
                </div>
              }
            </div>
          </label>
          <div class="chips">
            @for(id of settings.excluded_user_ids;track id){
              <button type="button" (click)="removeUser(id)">{{userName(id)}} ×</button>
            }
          </div>
        </section>

        <button class="primary" type="submit" [disabled]="saving()">{{saving()?'Saving…':'Save settings'}}</button>
      </form>
    </section>
  </sn-shell>`,
  styles:[`
    .page{display:grid;gap:1rem;padding:1.25rem}.topline,.panel-head{display:flex;justify-content:space-between;align-items:center;gap:1rem}
    h2,h3,p{margin:0}.eyebrow,.panel-head small,.box small{font-size:.66rem;font-weight:900;letter-spacing:.14em;color:var(--primary)}
    .topline p,small,.field{color:var(--muted)}button,input{font:inherit}
    button{padding:.7rem .9rem;border:1px solid var(--line);border-radius:9px;background:var(--surface);color:var(--text);cursor:pointer}
    .panel,.box{display:grid;gap:1rem;border:1px solid var(--line);border-radius:13px;background:var(--surface);padding:1rem}
    .box{background:rgba(0,0,0,.08)}input{width:100%;box-sizing:border-box;padding:.76rem;border:1px solid var(--line);border-radius:8px;background:#080d14;color:var(--text)}
    .switch{display:flex;align-items:center;gap:.55rem;color:var(--text);font-size:.8rem}.switch input{width:auto}
    .rule{display:grid;grid-template-columns:minmax(240px,1fr) 180px 110px auto;gap:.75rem;align-items:end;padding:.8rem;border:1px solid var(--line);border-radius:10px}
    .rule label,.field{display:grid;gap:.35rem;font-size:.78rem}.combo{position:relative}
    .options{position:absolute;z-index:30;left:0;right:0;top:calc(100% + .3rem);max-height:280px;overflow:auto;border:1px solid var(--line);border-radius:9px;background:#0b1119;box-shadow:0 18px 45px rgba(0,0,0,.35)}
    .options button{width:100%;display:grid;gap:.15rem;text-align:left;border:0;border-bottom:1px solid rgba(126,160,166,.08);border-radius:0;background:transparent}
    .options button:hover{background:rgba(53,226,178,.06)}.chips{display:flex;flex-wrap:wrap;gap:.45rem}.chips button{padding:.35rem .55rem}
    .primary{background:rgba(53,226,178,.14);border-color:rgba(53,226,178,.35);color:#dffff5}.danger,.notice.error{color:#ff8290}
    .notice{padding:.8rem 1rem;border:1px solid var(--line);border-radius:9px}.notice.success{color:var(--primary)}.empty{padding:1rem;text-align:center;color:var(--muted)}
    @media(max-width:900px){.rule{grid-template-columns:1fr}}
  `]
})
export class PluginAntiFloodComponent implements OnInit{
  private http=inject(HttpClient); private route=inject(ActivatedRoute);
  channels=signal<ChannelItem[]>([]); roles=signal<RoleItem[]>([]); members=signal<MemberItem[]>([]);
  error=signal(''); success=signal(''); saving=signal(false);
  openRuleIndex=signal<number|null>(null); roleOpen=signal(false); userOpen=signal(false);
  ruleSearch:string[]=[]; roleSearch=''; userSearch='';

  settings:Settings={enabled:true,ignore_bots:true,ignore_administrators:true,ignore_moderators:true,rules:[],excluded_role_ids:[],excluded_user_ids:[]};

  private get guildId(){return this.route.snapshot.paramMap.get('guildId')||''}
  private get base(){return `/api/v1/discord/guilds/${this.guildId}/plugins/antiflood`}

  filteredRoles=computed(()=>{const q=this.roleSearch.trim().toLowerCase();return this.roles().filter(r=>r.name!=='@everyone'&&!r.managed&&(!q||r.name.toLowerCase().includes(q)||r.id.includes(q))).slice(0,50)});

  ngOnInit(){this.reload()}
  reload(){
    this.error.set('');
    this.channels.set([]);
    this.roles.set([]);
    this.members.set([]);
    this.ruleSearch=[];
    this.http.get<any>(`/api/v1/discord/guilds/${this.guildId}/structure`).subscribe({
      next:v=>{this.channels.set((v.channels||[]).filter((x:ChannelItem)=>['text','0','guild_text'].includes(String(x.type).toLowerCase())));this.roles.set(v.roles||[]);this.syncRuleLabels()},
      error:()=>this.error.set('Unable to load Discord channels and roles.')
    });
    this.http.get<Settings>(`${this.base}/settings`).subscribe({
      next:v=>{this.settings=v;this.syncRuleLabels()},
      error:()=>this.error.set('Unable to load AntiFlood settings.')
    });
  }
  addRule(){this.settings.rules.push({channel_id:'',cooldown_seconds:60,enabled:true});this.ruleSearch.push('');this.openRuleIndex.set(this.settings.rules.length-1)}
  removeRule(i:number){this.settings.rules.splice(i,1);this.ruleSearch.splice(i,1)}
  openRule(i:number){this.closeSelectors();this.openRuleIndex.set(i)}
  searchRule(i:number,v:string){this.ruleSearch[i]=v;this.settings.rules[i].channel_id='';this.openRule(i)}
  filteredChannels(i:number){const q=(this.ruleSearch[i]||'').trim().toLowerCase();return this.channels().filter(c=>!q||c.name.toLowerCase().includes(q)||c.id.includes(q)).slice(0,50)}
  selectChannel(rule:Rule,c:ChannelItem){rule.channel_id=c.id;const i=this.settings.rules.indexOf(rule);this.ruleSearch[i]=this.channelLabel(c);this.closeSelectors()}
  channelText(rule:Rule){const i=this.settings.rules.indexOf(rule);return this.ruleSearch[i]||this.channelName(rule.channel_id)}
  channelLabel(c:ChannelItem){return `#${c.name} · ${c.id}`}
  channelName(id:string){const c=this.channels().find(item=>item.id===id);return c?this.channelLabel(c):String(id||'')}
  syncRuleLabels(){this.ruleSearch=this.settings.rules.map(r=>this.channelName(r.channel_id))}

  openSelector(which:'roles'|'users'){this.closeSelectors();if(which==='roles')this.roleOpen.set(true);else{this.userOpen.set(true);this.loadMembers()}}
  closeSelectors(){this.openRuleIndex.set(null);this.roleOpen.set(false);this.userOpen.set(false)}
  @HostListener('document:keydown.escape') escape(){this.closeSelectors()}
  @HostListener('document:mousedown',['$event']) outside(e:MouseEvent){const target=e.target as HTMLElement;if(!target.closest('.combo'))this.closeSelectors()}

  selectedRole(r:RoleItem){return this.settings.excluded_role_ids.includes(r.id)}
  toggleRole(r:RoleItem){const id=r.id;this.selectedRole(r)?this.removeRole(id):this.settings.excluded_role_ids.push(id)}
  removeRole(id:string){this.settings.excluded_role_ids=this.settings.excluded_role_ids.filter(x=>x!==id)}
  roleName(id:string){return this.roles().find(r=>r.id===id)?.name||String(id)}

  loadMembers(){
    this.userOpen.set(true);
    const q=encodeURIComponent(this.userSearch.trim());
    this.http.get<any>(`/api/v1/discord/guilds/${this.guildId}/members?query=${q}&page_size=50&status_filter=active`).subscribe({
      next:v=>this.members.set(v.items||v.members||[])
    });
  }
  selectedUser(m:MemberItem){return this.settings.excluded_user_ids.includes(String(m.discord_user_id))}
  toggleUser(m:MemberItem){const id=String(m.discord_user_id);this.selectedUser(m)?this.removeUser(id):this.settings.excluded_user_ids.push(id)}
  removeUser(id:string){this.settings.excluded_user_ids=this.settings.excluded_user_ids.filter(x=>x!==id)}
  userName(id:string){const m=this.members().find(x=>String(x.discord_user_id)===id);return m?.display_name||m?.username||String(id)}

  save(){
    if(this.settings.rules.some(r=>!r.channel_id)){this.error.set('Select a channel for every rule.');return}
    const ids=this.settings.rules.map(r=>r.channel_id);
    if(new Set(ids).size!==ids.length){this.error.set('Each channel may be used only once.');return}
    const available=new Set(this.channels().map(channel=>channel.id));
    const foreign=ids.filter(id=>!available.has(id));
    if(foreign.length){this.error.set('A selected channel does not belong to this Discord server. Reload the page and select it again.');return}
    this.saving.set(true);this.error.set('');this.success.set('');
    this.http.put<Settings>(`${this.base}/settings`,this.settings).subscribe({
      next:v=>{this.settings=v;this.syncRuleLabels();this.saving.set(false);this.success.set('AntiFlood settings saved.')},
      error:r=>{this.saving.set(false);this.error.set(r?.error?.detail||'Unable to save AntiFlood settings.')}
    });
  }
}
