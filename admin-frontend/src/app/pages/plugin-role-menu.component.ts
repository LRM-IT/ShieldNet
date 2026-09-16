import {Component,OnInit,inject,signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {HttpClient} from '@angular/common/http';
import {ActivatedRoute} from '@angular/router';
import {firstValueFrom} from 'rxjs';
import {ShellComponent} from '../shared/shell.component';
import {DiscordChannelPickerComponent} from '../shared/discord-channel-picker.component';
import {GuildPluginService} from '../core/guild-plugin.service';

interface Role{id:string;name:string;managed:boolean;assignable:boolean}
interface Option{label:string;role_id:string;emoji:string;description:string}
interface Panel{id:string;name:string;title:string;description:string;enabled:boolean;channel_id:string|null;required_role_id:string|null;mode:'buttons'|'select';max_roles:number;options:Option[];message_id?:string|null;expanded?:boolean}
interface Settings{installed:boolean;enabled:boolean;panels:Panel[]}

@Component({standalone:true,imports:[FormsModule,ShellComponent,DiscordChannelPickerComponent],template:`
<sn-shell title="Role Menu"><main class="page">
  <header><span>GUILD PLUGIN</span><h2>Role Menu</h2><p>Members choose their own Discord roles using buttons or a select menu.</p></header>
  @if(error()){<div class="notice error">{{error()}}</div>} @if(success()){<div class="notice success">{{success()}}</div>}
  @if(!settings.installed){<section class="card"><p>Install the plugin to create role panels.</p><button (click)="install()" [disabled]="busy()">Install plugin</button></section>}
  @else {
    <section class="card heading"><div><h3>Role panels</h3><p>Create independent panels for game, notification, region or access roles.</p></div><div class="actions"><button class="secondary" (click)="toggle()">{{settings.enabled?'Disable':'Enable'}} plugin</button><button (click)="addPanel()">Add panel</button></div></section>
    @for(panel of settings.panels;track panel.id;let pi=$index){
      <article class="card panel">
        <button class="summary" (click)="panel.expanded=!panel.expanded"><span><strong>{{panel.name||'New panel'}}</strong><small>{{panel.options.length}} roles · {{panel.mode}} · {{panel.enabled?'Enabled':'Disabled'}}</small></span><b [class.open]="panel.expanded">⌄</b></button>
        @if(panel.expanded){<div class="body">
          <div class="grid"><label>Panel name<input [(ngModel)]="panel.name" maxlength="80"></label><label>Discord title<input [(ngModel)]="panel.title" maxlength="100"></label></div>
          <label>Description<textarea [(ngModel)]="panel.description" rows="3" maxlength="1000"></textarea></label>
          <div class="grid"><label>Channel<sn-discord-channel-picker [guildId]="guildId" [value]="panel.channel_id" (valueChange)="panel.channel_id=$event" /></label><label>Required role<select [(ngModel)]="panel.required_role_id"><option [ngValue]="null">Everyone</option>@for(role of roles();track role.id){<option [value]="role.id">{{role.name}}</option>}</select></label></div>
          <div class="grid three"><label>Display<select [(ngModel)]="panel.mode"><option value="buttons">Buttons</option><option value="select">Select menu</option></select></label><label>Maximum selected roles<input type="number" min="0" max="25" [(ngModel)]="panel.max_roles"><small>0 means unlimited.</small></label><label class="check"><input type="checkbox" [(ngModel)]="panel.enabled"> Panel enabled</label></div>
          <div class="options"><div class="heading"><h4>Roles</h4><button class="secondary" (click)="addOption(panel)">Add role</button></div>
            @for(option of panel.options;track $index;let oi=$index){<div class="option"><label>Label<input [(ngModel)]="option.label" maxlength="80"></label><label>Emoji<input [(ngModel)]="option.emoji" maxlength="40" placeholder="🎮"></label><label>Discord role<select [(ngModel)]="option.role_id"><option value="">Select role</option>@for(role of assignableRoles();track role.id){<option [value]="role.id">{{role.name}}</option>}</select></label><label>Description<input [(ngModel)]="option.description" maxlength="100"></label><button class="danger" (click)="panel.options.splice(oi,1)">Remove</button></div>}
          </div>
          <div class="footer"><button class="danger" (click)="settings.panels.splice(pi,1)">Delete panel</button><span></span><button class="secondary" (click)="save()">Save</button><button (click)="publish(panel)" [disabled]="!settings.enabled||!panel.enabled">Save and publish</button></div>
        </div>}
      </article>
    } @empty {<section class="card empty">No role panels yet.</section>}
    <button class="save" (click)="save()" [disabled]="busy()">Save all settings</button>
  }
</main></sn-shell>`,styles:[`
.page{max-width:1150px;margin:auto;display:grid;gap:1rem;padding-bottom:3rem}header span{color:var(--primary);font-size:.7rem;font-weight:800;letter-spacing:.12em}h2{margin:.3rem 0;font-size:1.8rem}h3,h4,p{margin:.2rem 0}p,small{color:var(--muted)}.card,.notice{padding:1.2rem;border:1px solid var(--line);border-radius:16px;background:var(--panel)}.heading,.actions,.footer{display:flex;align-items:center;justify-content:space-between;gap:.7rem}.panel{padding:0;overflow:hidden}.summary{width:100%;padding:1rem 1.2rem;display:flex;justify-content:space-between;align-items:center;text-align:left;background:transparent;color:var(--text);border:0}.summary span{display:grid;gap:.25rem}.summary b{font-size:1.5rem;transition:.2s}.summary b.open{transform:rotate(180deg)}.body{display:grid;gap:1rem;padding:1.2rem;border-top:1px solid var(--line)}.grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem}.grid.three{grid-template-columns:1fr 1fr 1fr}.options{display:grid;gap:.7rem;padding:1rem;border:1px solid var(--line);border-radius:12px}.option{display:grid;grid-template-columns:1fr 90px 1fr 1fr auto;gap:.7rem;align-items:end;padding-top:.7rem;border-top:1px solid var(--line)}label{display:grid;gap:.35rem;color:var(--muted)}label.check{display:flex;align-items:center;align-self:end;min-height:44px}input,select,textarea{width:100%;padding:.75rem;border:1px solid var(--line);border-radius:9px;background:var(--panel-2);color:var(--text);font:inherit}button{padding:.72rem 1rem;border:0;border-radius:9px;background:var(--primary);color:#07120f;font-weight:800;cursor:pointer}button.secondary,button.danger{background:transparent;color:var(--text);border:1px solid var(--line)}button.danger{color:#ff9ea3;border-color:rgba(255,90,100,.35)}button:disabled{opacity:.5}.footer span{flex:1}.save{justify-self:end}.error{color:#ff9ea3}.success{color:#76e8b8}.empty{text-align:center;color:var(--muted)}@media(max-width:800px){.grid,.grid.three,.option{grid-template-columns:1fr}.heading,.actions,.footer{flex-wrap:wrap}}
`]})
export class PluginRoleMenuComponent implements OnInit{
 private http=inject(HttpClient);private route=inject(ActivatedRoute);private plugins=inject(GuildPluginService);readonly guildId=this.route.snapshot.paramMap.get('guildId')||'';roles=signal<Role[]>([]);assignableRoles=signal<Role[]>([]);busy=signal(false);error=signal('');success=signal('');settings:Settings={installed:false,enabled:false,panels:[]};private get url(){return `/api/v1/discord/guilds/${this.guildId}/plugins/role-menu`;}
 async ngOnInit(){try{const [settings,structure]=await Promise.all([firstValueFrom(this.http.get<Settings>(`${this.url}/settings`)),firstValueFrom(this.http.get<any>(`/api/v1/discord/guilds/${this.guildId}/structure`))]);this.settings={...settings,panels:(settings.panels||[]).map(x=>({...x,expanded:false}))};const roles=(structure.roles||[]).filter((x:Role)=>!x.managed&&x.name!=='@everyone');this.roles.set(roles);this.assignableRoles.set(roles.filter((x:Role)=>x.assignable));}catch(e:any){this.error.set(e?.error?.detail||'Could not load Role Menu.')}}
 addPanel(){const id=`panel-${Date.now().toString(36)}`;this.settings.panels.push({id,name:'New panel',title:'Choose your roles',description:'',enabled:true,channel_id:null,required_role_id:null,mode:'buttons',max_roles:0,options:[],expanded:true});}
 addOption(panel:Panel){panel.options.push({label:'New role',role_id:'',emoji:'',description:''});}
 payload(){return{panels:this.settings.panels.map(({expanded,message_id,...panel})=>panel)}}
 async install(){this.busy.set(true);try{await this.plugins.install(this.guildId,'role_menu');await this.ngOnInit()}catch(e:any){this.error.set(e?.error?.detail||'Could not install Role Menu.')}finally{this.busy.set(false)}}
 async toggle(){this.busy.set(true);try{if(this.settings.enabled)await this.plugins.disable(this.guildId,'role_menu');else await this.plugins.enable(this.guildId,'role_menu');await this.ngOnInit()}catch(e:any){this.error.set(e?.error?.detail||'Could not change plugin state.')}finally{this.busy.set(false)}}
 async save(){this.busy.set(true);this.error.set('');try{const open=new Set(this.settings.panels.filter(x=>x.expanded).map(x=>x.id));const saved=await firstValueFrom(this.http.put<Settings>(`${this.url}/settings`,this.payload()));this.settings={...saved,panels:saved.panels.map(x=>({...x,expanded:open.has(x.id)}))};this.success.set('Role Menu settings saved.')}catch(e:any){this.error.set(e?.error?.detail||'Could not save settings.')}finally{this.busy.set(false)}}
 async publish(panel:Panel){await this.save();if(this.error())return;this.busy.set(true);try{const result=await firstValueFrom(this.http.post<any>(`${this.url}/publish`,{panel_id:panel.id}));for(let i=0;i<30;i++){await new Promise(r=>setTimeout(r,1000));const job=await firstValueFrom(this.http.get<any>(`${this.url}/jobs/${result.job_id}`));if(job.status==='completed'){this.success.set('Role panel published in Discord.');break}if(job.status==='failed')throw new Error(job.error||'Publication failed')}}catch(e:any){this.error.set(e?.error?.detail||e?.message||'Could not publish panel.')}finally{this.busy.set(false)}}
}
