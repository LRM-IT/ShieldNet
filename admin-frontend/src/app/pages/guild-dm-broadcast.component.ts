import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';

import { ShellComponent } from '../shared/shell.component';
import { Member, MemberService } from '../core/member.service';

interface Campaign {
  id:string;
  name:string;
  message:string;
  status:string;
  total_count:number;
  sent_count:number;
  failed_count:number;
  skipped_count:number;
  created_at:string;
  last_error?:string|null;
}

@Component({
  selector:'sn-guild-dm-broadcast',
  standalone:true,
  imports:[CommonModule,FormsModule,ShellComponent],
  template:`
  <sn-shell title="Guild DM Broadcast">
    <section class="page">
      <header class="topline">
        <div>
          <div class="eyebrow">SHIELDNET PLUGIN</div>
          <h2>Guild DM Broadcast</h2>
          <p>Create targeted Discord direct-message campaigns.</p>
        </div>
        <button type="button" class="btn" (click)="reloadAll()">Refresh</button>
      </header>

      @if(error()){<div class="notice error">{{error()}}</div>}
      @if(success()){<div class="notice success">{{success()}}</div>}

      <section class="stats">
        <article><small>CAMPAIGNS</small><strong>{{dashboard().total||0}}</strong></article>
        <article><small>QUEUED</small><strong>{{dashboard().queued||0}}</strong></article>
        <article><small>RUNNING</small><strong>{{dashboard().running||0}}</strong></article>
        <article><small>SENT</small><strong>{{dashboard().sent||0}}</strong></article>
        <article><small>FAILED</small><strong>{{dashboard().failed||0}}</strong></article>
      </section>

      <div class="workspace">
        <main class="main-column">
          <form (ngSubmit)="create()" class="panel composer">
            <div class="panel-head">
              <div>
                <small>NEW CAMPAIGN</small>
                <h3>Message composer</h3>
              </div>
              <span class="recipient-count">{{recipientLabel()}}</span>
            </div>

            <label>
              Campaign name
              <input [(ngModel)]="form.name" name="name"
                     maxlength="160" required>
            </label>

            <label>
              Message
              <textarea [(ngModel)]="form.message" name="message"
                        maxlength="2000" rows="11" required></textarea>
            </label>

            <p class="hint">
              Variables:
              <code>{{ '{username}' }}</code>,
              <code>{{ '{display_name}' }}</code>,
              <code>{{ '{guild}' }}</code>
            </p>

            <div class="form-grid">
              <label>
                Role IDs, separated by commas
                <input [(ngModel)]="form.roleIds" name="roleIds"
                       placeholder="Optional role filter">
              </label>

              <label>
                Delay between messages, ms
                <input [(ngModel)]="form.delayMs" name="delayMs"
                       type="number" min="750" max="10000">
              </label>
            </div>

            <label class="check">
              <input [(ngModel)]="form.excludeBots" name="excludeBots"
                     type="checkbox">
              Exclude bots
            </label>

            <div class="actions">
              <button class="primary" type="submit" [disabled]="saving()">
                {{saving()?'Creating…':'Queue campaign'}}
              </button>
              <button type="button" (click)="clearSelection()"
                      [disabled]="selectedIds().size===0">
                Clear recipients
              </button>
            </div>
          </form>

          <section class="panel history">
            <div class="panel-head">
              <div><small>DELIVERY</small><h3>Campaign history</h3></div>
            </div>

            @for(item of campaigns();track item.id){
              <article class="campaign">
                <div class="campaign-title">
                  <strong>{{item.name}}</strong>
                  <span class="status" [attr.data-state]="item.status">
                    {{item.status}}
                  </span>
                </div>
                <p>{{item.message}}</p>
                <div class="metrics">
                  <span>Sent <b>{{item.sent_count||0}}</b></span>
                  <span>Failed <b>{{item.failed_count||0}}</b></span>
                  <span>Skipped <b>{{item.skipped_count||0}}</b></span>
                </div>
                @if(item.last_error){
                  <div class="campaign-error">{{item.last_error}}</div>
                }
                @if(item.status==='queued'||item.status==='running'){
                  <button type="button" class="danger"
                          (click)="cancel(item.id)">Cancel</button>
                }
              </article>
            } @empty {
              <div class="empty">No campaigns yet.</div>
            }
          </section>
        </main>

        <aside class="panel recipients">
          <div class="panel-head">
            <div>
              <small>RECIPIENTS</small>
              <h3>Server members</h3>
            </div>
            <span>{{membersTotal()}}</span>
          </div>

          <div class="member-search">
            <input [(ngModel)]="memberQuery"
                   (keyup.enter)="loadMembers()"
                   placeholder="Search name, nickname or ID">
            <button type="button" (click)="loadMembers()">Search</button>
          </div>

          <div class="selection-tools">
            <label>
              <input type="checkbox"
                     [checked]="allPageSelected()"
                     (change)="togglePage($event)">
              Select page
            </label>
            <button type="button" (click)="selectAllLoaded()">
              Select loaded
            </button>
          </div>

          @if(membersLoading()){
            <div class="empty">Loading members…</div>
          }

          <div class="member-list">
            @for(member of members();track member.discord_user_id){
              <label class="member"
                     [class.selected]="selectedIds().has(member.discord_user_id)">
                <input type="checkbox"
                       [checked]="selectedIds().has(member.discord_user_id)"
                       (change)="toggleMember(member.discord_user_id)">
                <span class="avatar">
                  @if(member.avatar_url){
                    <img [src]="member.avatar_url" alt="">
                  } @else {
                    {{initial(member)}}
                  }
                </span>
                <span class="identity">
                  <strong>{{displayName(member)}}</strong>
                  <small>@{{member.username}}</small>
                  <span class="role-line">
                    @for(role of member.roles.slice(0,2);
                         track role.discord_role_id){
                      <i>{{role.role_name}}</i>
                    }
                  </span>
                </span>
                @if(member.bot){<b class="bot">BOT</b>}
              </label>
            } @empty {
              @if(!membersLoading()){
                <div class="empty">No members found.</div>
              }
            }
          </div>

          <div class="pager">
            <button type="button" [disabled]="memberPage===1"
                    (click)="changeMemberPage(-1)">Previous</button>
            <span>{{memberPage}} / {{memberPages()}}</span>
            <button type="button"
                    [disabled]="memberPage>=memberPages()"
                    (click)="changeMemberPage(1)">Next</button>
          </div>
        </aside>
      </div>
    </section>
  </sn-shell>
  `,
  styles:[`
  .page{display:grid;gap:1rem;padding:1.25rem;min-width:0}
  .topline,.panel-head,.campaign-title,.actions,.selection-tools,.pager{
    display:flex;align-items:center;justify-content:space-between;gap:1rem
  }
  h2,h3,p{margin:0}
  .eyebrow,.panel-head small{
    font-size:.66rem;font-weight:900;letter-spacing:.14em;color:var(--primary)
  }
  .topline p,.hint,small{color:var(--muted)}
  button,input,textarea{font:inherit}
  button{
    padding:.7rem .95rem;border:1px solid var(--line);border-radius:9px;
    background:var(--surface);color:var(--text);cursor:pointer
  }
  button:disabled{opacity:.45;cursor:not-allowed}
  .primary{
    background:rgba(53,226,178,.14);
    border-color:rgba(53,226,178,.35);color:#dffff5
  }
  .danger{border-color:rgba(255,80,100,.45);color:#ff8290}
  .stats{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.75rem}
  .stats article,.panel{
    border:1px solid var(--line);border-radius:13px;
    background:var(--surface);padding:1rem
  }
  .stats article{display:grid;gap:.45rem}
  .stats strong{font-size:1.55rem}
  .workspace{
    display:grid;grid-template-columns:minmax(0,1fr) 390px;
    gap:1rem;align-items:start
  }
  .main-column{display:grid;gap:1rem;min-width:0}
  .composer{display:grid;gap:.9rem}
  label{display:grid;gap:.4rem;font-size:.8rem;color:var(--muted)}
  input,textarea{
    width:100%;box-sizing:border-box;padding:.75rem;
    border:1px solid var(--line);border-radius:8px;
    background:#080d14;color:var(--text)
  }
  textarea{resize:vertical}
  .form-grid{display:grid;grid-template-columns:1fr 220px;gap:.75rem}
  .check{display:flex;align-items:center;gap:.55rem}
  .check input{width:auto}
  .recipient-count{
    border:1px solid rgba(53,226,178,.25);border-radius:999px;
    padding:.35rem .65rem;color:var(--primary);font-size:.72rem
  }
  code{color:var(--primary)}
  .history{display:grid;gap:.75rem}
  .campaign{
    display:grid;gap:.65rem;padding:.85rem;
    border:1px solid var(--line);border-radius:10px
  }
  .campaign p{white-space:pre-wrap;color:#bcc8d0}
  .status{text-transform:uppercase;font-size:.65rem;color:var(--primary)}
  .metrics{display:flex;flex-wrap:wrap;gap:.55rem}
  .metrics span{
    padding:.32rem .5rem;border-radius:7px;background:#080d14;
    color:var(--muted);font-size:.72rem
  }
  .metrics b{color:var(--text)}
  .campaign-error,.notice.error{color:#ff8290}
  .notice{
    padding:.8rem 1rem;border:1px solid var(--line);border-radius:9px
  }
  .notice.success{color:var(--primary)}
  .recipients{position:sticky;top:84px;display:grid;gap:.75rem;max-height:calc(100vh - 105px)}
  .member-search{display:grid;grid-template-columns:1fr auto;gap:.5rem}
  .selection-tools{font-size:.75rem}
  .selection-tools label{display:flex;align-items:center;gap:.4rem}
  .selection-tools input{width:auto}
  .member-list{display:grid;gap:.4rem;overflow:auto;padding-right:.2rem}
  .member{
    display:grid;grid-template-columns:auto 38px minmax(0,1fr) auto;
    align-items:center;gap:.55rem;padding:.55rem;
    border:1px solid var(--line);border-radius:9px;cursor:pointer
  }
  .member.selected{
    border-color:rgba(53,226,178,.4);background:rgba(53,226,178,.06)
  }
  .member>input{width:auto}
  .avatar{
    width:36px;height:36px;display:grid;place-items:center;
    border-radius:9px;background:rgba(53,226,178,.12);
    color:var(--primary);font-weight:900;overflow:hidden
  }
  .avatar img{width:100%;height:100%;object-fit:cover}
  .identity{min-width:0;display:grid;gap:.1rem}
  .identity strong,.identity small{
    overflow:hidden;text-overflow:ellipsis;white-space:nowrap
  }
  .role-line{display:flex;gap:.25rem;overflow:hidden}
  .role-line i{
    font-style:normal;font-size:.58rem;padding:.15rem .3rem;
    border-radius:5px;background:#080d14;color:var(--muted)
  }
  .bot{font-size:.58rem;color:#f6c86a}
  .pager{font-size:.72rem}
  .empty{padding:1.5rem;text-align:center;color:var(--muted)}
  @media(max-width:1200px){
    .workspace{grid-template-columns:1fr}
    .recipients{position:static;max-height:none}
  }
  @media(max-width:800px){
    .stats{grid-template-columns:repeat(2,1fr)}
    .form-grid{grid-template-columns:1fr}
  }
  `]
})
export class GuildDMBroadcastComponent implements OnInit{
  private readonly http=inject(HttpClient);
  private readonly route=inject(ActivatedRoute);
  private readonly memberService=inject(MemberService);

  readonly dashboard=signal<any>({});
  readonly campaigns=signal<Campaign[]>([]);
  readonly members=signal<Member[]>([]);
  readonly membersTotal=signal(0);
  readonly selectedIds=signal<Set<string>>(new Set());
  readonly error=signal('');
  readonly success=signal('');
  readonly saving=signal(false);
  readonly membersLoading=signal(false);

  memberQuery='';
  memberPage=1;
  memberPageSize=50;

  form={
    name:'',
    message:'',
    roleIds:'',
    excludeBots:true,
    delayMs:1200
  };

  readonly memberPages=computed(
    ()=>Math.max(1,Math.ceil(this.membersTotal()/this.memberPageSize))
  );

  readonly allPageSelected=computed(()=>{
    const items=this.members();
    return items.length>0 &&
      items.every(item=>this.selectedIds().has(item.discord_user_id));
  });

  readonly recipientLabel=computed(()=>{
    const count=this.selectedIds().size;
    return count>0 ? `${count} selected members` : 'Role filter or all members';
  });

  private get guildId():string{
    return this.route.snapshot.paramMap.get('guildId')||'';
  }

  private get base():string{
    return `/api/v1/discord/guilds/${this.guildId}/plugins/guild-dm-broadcast`;
  }

  ngOnInit():void{this.reloadAll()}

  reloadAll():void{
    this.loadCampaigns();
    this.loadMembers();
  }

  loadCampaigns():void{
    this.error.set('');
    this.http.get<any>(`${this.base}/dashboard`).subscribe({
      next:v=>this.dashboard.set(v),
      error:()=>this.error.set('Unable to load plugin dashboard.')
    });
    this.http.get<{items:Campaign[]}>(`${this.base}/campaigns`).subscribe({
      next:v=>this.campaigns.set(v.items||[]),
      error:()=>this.error.set('Unable to load campaign history.')
    });
  }

  async loadMembers():Promise<void>{
    this.membersLoading.set(true);
    try{
      const result=await this.memberService.list(this.guildId,{
        q:this.memberQuery,
        type:this.form.excludeBots?'human':'all',
        status:'active',
        sort:'name',
        page:this.memberPage,
        page_size:this.memberPageSize
      });
      this.members.set(result.items||[]);
      this.membersTotal.set(result.total||0);
    }catch{
      this.error.set('Unable to load server members.');
    }finally{
      this.membersLoading.set(false);
    }
  }

  changeMemberPage(delta:number):void{
    const next=this.memberPage+delta;
    if(next<1||next>this.memberPages())return;
    this.memberPage=next;
    void this.loadMembers();
  }

  toggleMember(id:string):void{
    const next=new Set(this.selectedIds());
    next.has(id)?next.delete(id):next.add(id);
    this.selectedIds.set(next);
  }

  togglePage(event:Event):void{
    const checked=(event.target as HTMLInputElement).checked;
    const next=new Set(this.selectedIds());
    for(const member of this.members()){
      checked?next.add(member.discord_user_id):next.delete(member.discord_user_id);
    }
    this.selectedIds.set(next);
  }

  selectAllLoaded():void{
    const next=new Set(this.selectedIds());
    for(const member of this.members())next.add(member.discord_user_id);
    this.selectedIds.set(next);
  }

  clearSelection():void{this.selectedIds.set(new Set())}

  displayName(member:Member):string{
    return member.nickname||member.global_name||member.username;
  }

  initial(member:Member):string{
    return this.displayName(member).slice(0,1).toUpperCase();
  }

  create():void{
    this.error.set('');
    this.success.set('');
    this.saving.set(true);

    const role_ids=this.form.roleIds.split(',')
      .map(v=>v.trim()).filter(Boolean).map(Number)
      .filter(v=>Number.isSafeInteger(v)&&v>0);

    const member_ids=[...this.selectedIds()]
      .map(Number)
      .filter(v=>Number.isSafeInteger(v)&&v>0);

    this.http.post(`${this.base}/campaigns`,{
      name:this.form.name,
      message:this.form.message,
      role_ids,
      member_ids,
      exclude_bots:this.form.excludeBots,
      delay_ms:Number(this.form.delayMs)
    }).subscribe({
      next:()=>{
        this.saving.set(false);
        this.success.set('Campaign queued.');
        this.form.name='';
        this.form.message='';
        this.clearSelection();
        this.loadCampaigns();
      },
      error:r=>{
        this.saving.set(false);
        this.error.set(r?.error?.detail||'Unable to create campaign.');
      }
    });
  }

  cancel(id:string):void{
    this.http.post(`${this.base}/campaigns/${id}/cancel`,{}).subscribe({
      next:()=>this.loadCampaigns(),
      error:r=>this.error.set(
        r?.error?.detail||'Unable to cancel campaign.'
      )
    });
  }
}
