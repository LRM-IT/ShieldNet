import { DatePipe } from '@angular/common';
import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { GuildAccess } from '../core/api.models';
import { GuildService } from '../core/guild.service';
import { AuthService } from '../core/auth.service';
import { ModalService } from '../core/modal.service';
import { ToastService } from '../core/toast.service';
import { ShellComponent } from '../shared/shell.component';
import { TranslatePipe } from '../core/translate.pipe';
import { TranslationService } from '../core/translation.service';

@Component({
  standalone: true,
  imports: [ShellComponent, RouterLink, TranslatePipe, DatePipe],
  template: `<sn-shell [title]="'server_cards.control_center'|snT:'Guild Control Center'">
    <section class="head">
      <div><span>{{'server_cards.eyebrow'|snT:'YOUR DISCORD SERVERS'}}</span><h2>{{'server_cards.title'|snT:'Select a server'}}</h2><p>{{'server_cards.subtitle'|snT:'Manage only the Discord servers available to your account.'}}</p></div>
      <button type="button" (click)="synchronize()" [disabled]="loading()">{{'server_cards.sync_discord'|snT:'Sync with Discord'}}</button>
    </section>
    @if(error()){<div class="error">{{error()}}</div>}
    <section class="grid">
      @for(guild of guilds(); track guild.guild_id){
        <article class="card">
          <div class="guild-head">
            @if(guild.icon_url){<img [src]="guild.icon_url" alt="">}@else{<div class="avatar">{{guild.name.slice(0,1).toUpperCase()}}</div>}
            <div><strong>{{guild.name}}</strong><small>{{guild.guild_id}}</small></div>
            <span class="state" [class.online]="isConnected(guild)" [class.stale]="!guild.custom_bot_active&&guild.sync_status==='stale'"><i></i>{{statusLabel(guild)}}</span>
          </div>
          <div class="stats">
            <div><span>{{'server_cards.members'|snT:'Members'}}</span><strong>{{guild.member_count}}</strong></div>
            <div><span>{{'server_cards.last_sync'|snT:'Last sync'}}</span><strong>{{guild.last_sync_at?(guild.last_sync_at|date:'short'):('server_cards.never'|snT:'Never')}}</strong></div>
            <div><span>{{'server_cards.plugins'|snT:'Plugins'}}</span><strong>{{guild.enabled_plugins||0}}</strong></div>
          </div>
          <span class="billing" [class.active]="isPaid(guild)" [class.expired]="isExpired(guild)"><i></i>{{paymentLabel(guild)}}</span>
          <div class="actions">
            @if(isConnected(guild)){
              <a class="primary" [routerLink]="['/guild',guild.guild_id]">{{'server_cards.open'|snT:'Open server'}}</a>
              <a [routerLink]="['/guild',guild.guild_id,'members']">{{'server_cards.members'|snT:'Members'}}</a>
              <a [routerLink]="['/guild',guild.guild_id,'plugin-runtime']">{{'server_cards.plugins'|snT:'Plugins'}}</a>
            }@else{
              <a class="primary" [href]="botInstallUrl(guild.guild_id)">{{'dashboard.connect_bot'|snT:'Connect bot'}}</a>
              @if(guild.is_owner){<button class="danger" type="button" (click)="remove(guild)">{{'server_cards.delete_record'|snT:'Delete permanently'}}</button>}
            }
          </div>
        </article>
      }@empty{<div class="empty">{{'server_cards.empty'|snT:'No manageable Discord servers. Sync with Discord to refresh access.'}}</div>}
    </section>
  </sn-shell>`,
  styles:[`:host{display:block}.head{display:flex;align-items:end;justify-content:space-between;gap:1rem;padding:1rem 0 1.5rem}.head span{color:var(--accent);font-size:.66rem;font-weight:900;letter-spacing:.14em}.head h2{margin:.35rem 0}.head p{margin:0;color:var(--muted)}.head button,.actions a,.actions button{padding:.7rem 1rem;border:1px solid var(--line);border-radius:9px;background:var(--panel);color:var(--text);font-weight:800;cursor:pointer;text-decoration:none}.head button:disabled{opacity:.55;cursor:wait}.error{margin-bottom:1rem;padding:1rem;border:1px solid rgba(255,90,110,.3);border-radius:12px;color:#ff8d96;background:rgba(255,90,110,.06)}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem;align-items:stretch}.card{display:flex;flex-direction:column;padding:1.1rem;border:1px solid var(--line);border-radius:16px;background:var(--panel);min-width:0}.guild-head{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:.75rem;min-height:56px}.guild-head img,.avatar{width:44px;height:44px;border-radius:11px}.guild-head img{object-fit:cover}.avatar{display:grid;place-items:center;background:rgba(53,226,178,.12);color:var(--accent);font-weight:900}.guild-head>div:nth-child(2){display:grid;gap:.2rem;min-width:0}.guild-head strong,.guild-head small{overflow:hidden;text-overflow:ellipsis}.guild-head small{color:var(--muted)}.state{font-size:.65rem;text-transform:uppercase;color:#f0a94b;white-space:nowrap}.state i,.billing i{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:.4rem;background:currentColor}.state.online{color:var(--success)}.state.stale{color:#f0a94b}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:.5rem;margin:1rem 0}.stats div{padding:.7rem;border:1px solid var(--line);border-radius:10px;display:grid;gap:.3rem;min-width:0;min-height:108px;align-content:center}.stats span{color:var(--muted);font-size:.66rem;text-transform:uppercase}.stats strong{overflow:hidden;text-overflow:ellipsis;font-size:.88rem}.billing{display:flex;align-items:center;min-height:20px;color:var(--muted);font-size:.72rem;margin-bottom:1rem}.billing.active{color:var(--success)}.billing.expired{color:#ff8d96}.actions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.5rem;margin-top:auto}.actions a,.actions button{display:flex;align-items:center;justify-content:center;min-height:46px;width:100%;font-size:.78rem;padding:.55rem .7rem;text-align:center;line-height:1.15}.actions .primary{background:var(--accent);border-color:var(--accent);color:#04130f}.actions .danger{color:#ff8d96;border-color:rgba(255,90,110,.35)}.empty{grid-column:1/-1;padding:2rem;border:1px solid var(--line);border-radius:14px;color:var(--muted)}@media(max-width:1100px){.grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:720px){.grid{grid-template-columns:1fr}.head{align-items:flex-start;flex-direction:column}.guild-head{grid-template-columns:auto minmax(0,1fr)}.state{grid-column:1/-1}.stats{grid-template-columns:1fr 1fr 1fr}}@media(max-width:430px){.stats{grid-template-columns:1fr}.stats div{min-height:auto}.actions{grid-template-columns:1fr}.actions>*{width:100%;text-align:center}}`]
})
export class ServerSelectorComponent implements OnInit,OnDestroy {
  readonly guilds=signal<GuildAccess[]>([]);readonly loading=signal(false);readonly error=signal('');readonly now=signal(Date.now());private timer?:ReturnType<typeof setInterval>;
  constructor(private service:GuildService,private auth:AuthService,private i18n:TranslationService,private modal:ModalService,private toast:ToastService){}
  async ngOnInit(){await this.refresh();this.timer=setInterval(()=>this.now.set(Date.now()),1000)}
  ngOnDestroy(){if(this.timer)clearInterval(this.timer)}
  async refresh(){this.loading.set(true);this.error.set('');try{this.guilds.set(await this.service.list())}catch(e:any){this.error.set(e?.error?.detail||this.i18n.t('server_cards.load_error','Unable to refresh the server list.'))}finally{this.loading.set(false)}}
  async synchronize(){this.loading.set(true);this.error.set('');try{await this.auth.startDiscordLogin(null);await this.refresh();this.toast.success(this.i18n.t('ui.success','Completed'),this.i18n.t('server_cards.synced','Discord server access has been refreshed.'))}catch(e:any){this.error.set(e?.message||this.i18n.t('server_cards.sync_error','Unable to synchronize with Discord.'))}finally{this.loading.set(false)}}
  async remove(g:GuildAccess){const ok=await this.modal.confirm(this.i18n.t('server_cards.delete_confirm','Permanently delete {name} and all saved GuildConsole settings?').replace('{name}',g.name),{title:this.i18n.t('server_cards.delete_title','Delete server record'),confirmLabel:this.i18n.t('server_cards.delete_record','Delete permanently'),cancelLabel:this.i18n.t('ui.cancel','Cancel'),danger:true});if(!ok)return;try{await this.service.remove(g.guild_id);this.guilds.update(items=>items.filter(x=>x.guild_id!==g.guild_id));this.toast.success(this.i18n.t('ui.success','Completed'),this.i18n.t('server_cards.deleted','Server record deleted.'))}catch(e:any){this.error.set(e?.error?.detail||this.i18n.t('server_cards.delete_error','Unable to delete the server record.'))}}
  isConnected(g:GuildAccess){return g.bot_status==='online'&&!!g.last_sync_at}
  botInstallUrl(id:string){return `/api/v1/auth/discord/bot-install?guild_id=${encodeURIComponent(id)}`}
  statusLabel(g:GuildAccess){if(g.custom_bot_active)return this.i18n.t('server_cards.custom_bot_online','Online on custom bot');return `${this.i18n.t('server_cards.status_'+g.bot_status,g.bot_status)} · ${this.i18n.t('server_cards.sync_'+(g.sync_status||'never'),g.sync_status||'never')}`}
  isPaid(g:GuildAccess){return g.billing_status==='active'&&!!g.billing_expires_at&&new Date(g.billing_expires_at).getTime()>this.now()}
  isExpired(g:GuildAccess){return !!g.billing_expires_at&&!this.isPaid(g)}
  paymentLabel(g:GuildAccess){if(!g.billing_expires_at)return this.i18n.t('server_cards.not_paid','Paid access is not active');const left=new Date(g.billing_expires_at).getTime()-this.now();if(left<=0||g.billing_status!=='active')return this.i18n.t('server_cards.expired','Paid access expired');const total=Math.floor(left/1000),days=Math.floor(total/86400),hours=Math.floor(total%86400/3600),minutes=Math.floor(total%3600/60),seconds=total%60;const time=days>0?`${days}${this.i18n.t('server_cards.day_short','d')} ${hours}${this.i18n.t('server_cards.hour_short','h')} ${minutes}${this.i18n.t('server_cards.minute_short','m')}`:`${hours}${this.i18n.t('server_cards.hour_short','h')} ${minutes}${this.i18n.t('server_cards.minute_short','m')} ${seconds}${this.i18n.t('server_cards.second_short','s')}`;return `${this.i18n.t('server_cards.paid_for','Paid for')} ${time}`}
}

