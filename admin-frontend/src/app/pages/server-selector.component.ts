import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { GuildAccess } from '../core/api.models';
import { GuildService } from '../core/guild.service';
import { ShellComponent } from '../shared/shell.component';
import { TranslatePipe } from '../core/translate.pipe';
import { TranslationService } from '../core/translation.service';

@Component({
  standalone: true,
  imports: [ShellComponent, RouterLink, TranslatePipe],
  template: `<sn-shell title="Guild Control Center"><section class="head"><div><span>YOUR DISCORD SERVERS</span><h2>Select a server</h2><p>Open the management workspace for one of your authorized servers.</p></div><button type="button" (click)="refresh()" [disabled]="loading()">{{'server_control.refresh'|snT:'Refresh'}}</button></section>@if(error()){<div class="error">{{error()}}</div>}<section class="grid">@for(guild of guilds(); track guild.guild_id){<a class="card" [routerLink]="['/guild',guild.guild_id]"><div class="avatar">{{ guild.name.slice(0,1).toUpperCase() }}</div><div class="details"><strong>{{guild.name}}</strong><small>{{guild.member_count}} members · {{guild.access_role}}</small><span class="billing" [class.active]="isPaid(guild)" [class.expired]="isExpired(guild)" [title]="guild.billing_expires_at||''"><i></i>{{paymentLabel(guild)}}</span></div><b>→</b></a>}@empty{<div class="empty">No authorized servers.</div>}</section></sn-shell>`,
  styles:[`.head{display:flex;align-items:end;justify-content:space-between;gap:1rem;padding:1rem 0 1.5rem}.head span{color:var(--accent);font-size:.66rem;font-weight:900;letter-spacing:.14em}.head h2{margin:.35rem 0}.head p{margin:0;color:var(--muted)}.head button{padding:.7rem 1rem;border:1px solid var(--line);border-radius:9px;background:var(--panel);color:var(--text);font-weight:800;cursor:pointer}.head button:disabled{opacity:.55;cursor:wait}.error{margin-bottom:1rem;padding:1rem;border:1px solid rgba(255,90,110,.3);border-radius:12px;color:#ff8d96;background:rgba(255,90,110,.06)}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem}.card{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:.8rem;padding:1.1rem;border:1px solid var(--line);border-radius:14px;background:var(--panel);color:var(--text);text-decoration:none}.avatar{width:44px;height:44px;display:grid;place-items:center;border-radius:11px;background:rgba(53,226,178,.12);color:var(--accent);font-weight:900}.details{display:grid;gap:.25rem;min-width:0}.details>strong,.details>small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.card small{color:var(--muted)}.card>b{color:var(--accent)}.billing{display:flex;align-items:center;gap:.35rem;color:var(--muted);font-size:.72rem;font-variant-numeric:tabular-nums}.billing i{width:7px;height:7px;border-radius:50%;background:var(--muted);flex:none}.billing.active{color:var(--success)}.billing.active i{background:var(--success);box-shadow:0 0 8px var(--success)}.billing.expired{color:#ff8d96}.billing.expired i{background:#ff8d96}.billing em{padding:.12rem .35rem;border:1px solid currentColor;border-radius:99px;font-size:.58rem;font-style:normal}.empty{padding:2rem;border:1px solid var(--line);border-radius:14px;color:var(--muted)}@media(max-width:900px){.grid{grid-template-columns:1fr}}@media(max-width:600px){.head{align-items:flex-start;flex-direction:column}}`]
})
export class ServerSelectorComponent implements OnInit,OnDestroy {
  readonly guilds = signal<GuildAccess[]>([]);
  readonly loading=signal(false);readonly error=signal('');
  readonly now=signal(Date.now());private timer?:ReturnType<typeof setInterval>;
  constructor(private service: GuildService,private i18n:TranslationService) {}
  async ngOnInit(){await this.refresh();this.timer=setInterval(()=>this.now.set(Date.now()),1000)}
  async refresh(){this.loading.set(true);this.error.set('');try{this.guilds.set(await this.service.list())}catch{this.error.set(this.i18n.t('server_cards.load_error','Unable to refresh the server list.'))}finally{this.loading.set(false)}}
  ngOnDestroy(){if(this.timer)clearInterval(this.timer)}
  isPaid(g:GuildAccess){return g.billing_status==='active'&&!!g.billing_expires_at&&new Date(g.billing_expires_at).getTime()>this.now()}
  isExpired(g:GuildAccess){return !!g.billing_expires_at&&!this.isPaid(g)}
  paymentLabel(g:GuildAccess){
    if(!g.billing_expires_at)return this.i18n.t('server_cards.not_paid','Paid access is not active');
    const left=new Date(g.billing_expires_at).getTime()-this.now();
    if(left<=0||g.billing_status!=='active')return this.i18n.t('server_cards.expired','Paid access expired');
    const total=Math.floor(left/1000),days=Math.floor(total/86400),hours=Math.floor(total%86400/3600),minutes=Math.floor(total%3600/60),seconds=total%60;
    const time=days>0?`${days}${this.i18n.t('server_cards.day_short','d')} ${hours}${this.i18n.t('server_cards.hour_short','h')} ${minutes}${this.i18n.t('server_cards.minute_short','m')}`:`${hours}${this.i18n.t('server_cards.hour_short','h')} ${minutes}${this.i18n.t('server_cards.minute_short','m')} ${seconds}${this.i18n.t('server_cards.second_short','s')}`;
    return `${this.i18n.t('server_cards.paid_for','Paid for')} ${time}`;
  }
}
