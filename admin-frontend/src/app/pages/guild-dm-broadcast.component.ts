import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';

interface Campaign {
  id:string; name:string; message:string; status:string;
  total_count:number; sent_count:number; failed_count:number;
  skipped_count:number; created_at:string; last_error?:string|null;
}

@Component({
  selector:'sn-guild-dm-broadcast',
  standalone:true,
  imports:[CommonModule,FormsModule],
  template:`
  <section class="page">
    <header><div><div class="eyebrow">SHIELDNET PLUGIN</div>
      <h2>Guild DM Broadcast</h2>
      <p>Create and track Discord direct-message campaigns.</p></div>
      <button type="button" (click)="load()">Refresh</button>
    </header>
    @if(error()){<div class="notice error">{{error()}}</div>}
    @if(success()){<div class="notice success">{{success()}}</div>}
    <div class="stats">
      <article><small>CAMPAIGNS</small><strong>{{dashboard().total||0}}</strong></article>
      <article><small>QUEUED</small><strong>{{dashboard().queued||0}}</strong></article>
      <article><small>RUNNING</small><strong>{{dashboard().running||0}}</strong></article>
      <article><small>SENT</small><strong>{{dashboard().sent||0}}</strong></article>
      <article><small>FAILED</small><strong>{{dashboard().failed||0}}</strong></article>
    </div>
    <div class="layout">
      <form (ngSubmit)="create()" class="panel">
        <h3>Create campaign</h3>
        <label>Campaign name<input [(ngModel)]="form.name" name="name" maxlength="160" required></label>
        <label>Message<textarea [(ngModel)]="form.message" name="message" maxlength="2000" rows="10" required></textarea></label>
        <p class="hint">Variables:
          <code>{{ '{username}' }}</code>,
          <code>{{ '{display_name}' }}</code>,
          <code>{{ '{guild}' }}</code>
        </p>
        <label>Role IDs, separated by commas<input [(ngModel)]="form.roleIds" name="roleIds" placeholder="Empty means all members"></label>
        <label>Delay between messages, ms<input [(ngModel)]="form.delayMs" name="delayMs" type="number" min="750" max="10000"></label>
        <label class="check"><input [(ngModel)]="form.excludeBots" name="excludeBots" type="checkbox">Exclude bots</label>
        <button class="primary" type="submit" [disabled]="saving()">{{saving()?'Creating…':'Queue campaign'}}</button>
      </form>
      <section class="panel history"><h3>Campaign history</h3>
        @for(item of campaigns();track item.id){
          <article class="campaign">
            <div><strong>{{item.name}}</strong><span class="status">{{item.status}}</span></div>
            <p>{{item.message}}</p>
            <small>Sent {{item.sent_count||0}} · Failed {{item.failed_count||0}} · Skipped {{item.skipped_count||0}}</small>
            @if(item.last_error){<div class="campaign-error">{{item.last_error}}</div>}
            @if(item.status==='queued'||item.status==='running'){
              <button type="button" class="danger" (click)="cancel(item.id)">Cancel</button>
            }
          </article>
        } @empty {<div class="empty">No campaigns yet.</div>}
      </section>
    </div>
  </section>`,
  styles:[`
  .page{display:grid;gap:1rem;padding:1.25rem}header{display:flex;justify-content:space-between;gap:1rem;align-items:center}
  h2,h3,p{margin:0}.eyebrow{font-size:.68rem;font-weight:900;letter-spacing:.14em;color:var(--primary)}
  header p,.hint,small{color:var(--muted)}button,input,textarea{font:inherit}
  button{padding:.72rem 1rem;border:1px solid var(--line);border-radius:9px;background:var(--surface);color:var(--text);cursor:pointer}
  .primary{background:rgba(53,226,178,.14);border-color:rgba(53,226,178,.35);color:#dffff5}
  .danger{border-color:rgba(255,80,100,.45);color:#ff8290}
  .stats{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.75rem}
  .stats article,.panel{border:1px solid var(--line);border-radius:13px;background:var(--surface);padding:1rem}
  .stats article{display:grid;gap:.45rem}.stats strong{font-size:1.6rem}
  .layout{display:grid;grid-template-columns:minmax(320px,.8fr) minmax(420px,1.2fr);gap:1rem}
  form{display:grid;gap:.9rem;align-content:start}label{display:grid;gap:.4rem;font-size:.82rem;color:var(--muted)}
  input,textarea{width:100%;box-sizing:border-box;padding:.75rem;border:1px solid var(--line);border-radius:8px;background:#080d14;color:var(--text)}
  textarea{resize:vertical}.check{display:flex;grid-template-columns:auto 1fr;align-items:center}.check input{width:auto}
  .history{display:grid;gap:.75rem;align-content:start}.campaign{display:grid;gap:.55rem;padding:.85rem;border:1px solid var(--line);border-radius:10px}
  .campaign>div:first-child{display:flex;justify-content:space-between;gap:1rem}.status{text-transform:uppercase;font-size:.66rem;color:var(--primary)}
  .campaign p{white-space:pre-wrap;color:#bcc8d0}.campaign-error,.notice.error{color:#ff8290}
  .notice{padding:.8rem 1rem;border:1px solid var(--line);border-radius:9px}.notice.success{color:var(--primary)}
  code{color:var(--primary)}.empty{color:var(--muted);padding:2rem;text-align:center}
  @media(max-width:1000px){.stats{grid-template-columns:repeat(2,1fr)}.layout{grid-template-columns:1fr}}
  `]
})
export class GuildDMBroadcastComponent implements OnInit{
  private http=inject(HttpClient);private route=inject(ActivatedRoute);
  dashboard=signal<any>({});campaigns=signal<Campaign[]>([]);
  error=signal('');success=signal('');saving=signal(false);
  form={name:'',message:'',roleIds:'',excludeBots:true,delayMs:1200};
  private get guildId(){return this.route.snapshot.paramMap.get('guildId')||''}
  private get base(){return `/api/v1/discord/guilds/${this.guildId}/plugins/guild-dm-broadcast`}
  ngOnInit(){this.load()}
  load(){
    this.error.set('');
    this.http.get<any>(`${this.base}/dashboard`).subscribe({next:v=>this.dashboard.set(v),error:()=>this.error.set('Unable to load dashboard.')});
    this.http.get<{items:Campaign[]}>(`${this.base}/campaigns`).subscribe({next:v=>this.campaigns.set(v.items||[]),error:()=>this.error.set('Unable to load campaigns.')});
  }
  create(){
    this.error.set('');this.success.set('');this.saving.set(true);
    const role_ids=this.form.roleIds.split(',').map(v=>v.trim()).filter(Boolean).map(Number).filter(v=>Number.isSafeInteger(v)&&v>0);
    this.http.post(`${this.base}/campaigns`,{name:this.form.name,message:this.form.message,role_ids,exclude_bots:this.form.excludeBots,delay_ms:Number(this.form.delayMs)})
    .subscribe({next:()=>{this.saving.set(false);this.success.set('Campaign queued.');this.form.name='';this.form.message='';this.load()},
    error:r=>{this.saving.set(false);this.error.set(r?.error?.detail||'Unable to create campaign.')}});
  }
  cancel(id:string){this.http.post(`${this.base}/campaigns/${id}/cancel`,{}).subscribe({next:()=>this.load(),error:r=>this.error.set(r?.error?.detail||'Unable to cancel campaign.')})}
}
