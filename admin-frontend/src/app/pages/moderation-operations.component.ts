import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { ModerationCase, ModerationOperationsService, ModerationStats, ModeratorWorkload } from '../core/moderation-operations.service';
import { ShellComponent } from '../shared/shell.component';
import { TranslatePipe } from '../core/translate.pipe';
import { TranslationService } from '../core/translation.service';

@Component({
  standalone:true,
  imports:[FormsModule,RouterLink,ShellComponent,TranslatePipe],
  template:`
  <sn-shell [title]="'moderation.title' | snT:'Moderation Operations Center'">
    <section class="hero">
      <div><div class="eyebrow">SHIELDNET v2.0</div><h2>{{ "moderation.heading" | snT:"Moderation Operations Center" }}</h2><p>{{ "moderation.description" | snT:"One operational queue for active cases, deadlines, ownership and moderator workload." }}</p></div>
      <div class="hero-actions"><a class="btn secondary" [routerLink]="['/guild',guildId,'members']">{{ "moderation.members" | snT:"Members" }}</a><button class="btn" (click)="reload()">↻ {{ "moderation.refresh" | snT:"Refresh" }}</button></div>
    </section>

    @if(stats()){
      <section class="stats">
        <button (click)="statusFilter='open';overdueOnly=false;loadCases()"><strong>{{stats()!.total_open}}</strong><span>{{ "moderation.open_queue" | snT:"Open queue" }}</span></button>
        <button (click)="statusFilter='investigating';overdueOnly=false;loadCases()"><strong>{{stats()!.investigating}}</strong><span>{{ "moderation.investigating" | snT:"Investigating" }}</span></button>
        <button class="danger" (click)="overdueOnly=true;statusFilter='all';loadCases()"><strong>{{stats()!.overdue}}</strong><span>{{ "moderation.overdue" | snT:"Overdue" }}</span></button>
        <button (click)="priority='urgent';loadCases()"><strong>{{stats()!.urgent}}</strong><span>{{ "moderation.urgent" | snT:"Urgent" }}</span></button>
        <button (click)="assignee='unassigned';loadCases()"><strong>{{stats()!.unassigned}}</strong><span>{{ "moderation.unassigned" | snT:"Unassigned" }}</span></button>
        <button><strong>{{stats()!.due_today}}</strong><span>{{ "moderation.due_today" | snT:"Due today" }}</span></button>
        <button><strong>{{stats()!.resolved_7d}}</strong><span>{{ "moderation.resolved_7d" | snT:"Resolved 7d" }}</span></button>
      </section>
    }

    <section class="filters card">
      <input [(ngModel)]="query" (keyup.enter)="resetAndLoad()" [placeholder]="'moderation.search_placeholder' | snT:'Search case or member'">
      <select [(ngModel)]="statusFilter" (change)="resetAndLoad()"><option value="all">{{ "moderation.all_statuses" | snT:"All statuses" }}</option><option value="open">{{ "moderation.open" | snT:"Open" }}</option><option value="investigating">{{ "moderation.investigating" | snT:"Investigating" }}</option><option value="resolved">{{ "moderation.resolved" | snT:"Resolved" }}</option><option value="dismissed">{{ "moderation.dismissed" | snT:"Dismissed" }}</option></select>
      <select [(ngModel)]="priority" (change)="resetAndLoad()"><option value="all">{{ "moderation.all_priorities" | snT:"All priorities" }}</option><option value="urgent">{{ "moderation.urgent" | snT:"Urgent" }}</option><option value="high">{{ "moderation.high" | snT:"High" }}</option><option value="normal">{{ "moderation.normal" | snT:"Normal" }}</option><option value="low">{{ "moderation.low" | snT:"Low" }}</option></select>
      <select [(ngModel)]="assignee" (change)="resetAndLoad()"><option value="all">{{ "moderation.all_owners" | snT:"All owners" }}</option><option value="unassigned">{{ "moderation.unassigned" | snT:"Unassigned" }}</option>@for(w of workload();track w.user_id){@if(w.user_id){<option [value]="w.user_id">{{w.display_name}}</option>}}</select>
      <label class="check"><input type="checkbox" [(ngModel)]="overdueOnly" (change)="resetAndLoad()">{{ "moderation.overdue_only" | snT:"Overdue only" }}</label>
      <button class="btn" (click)="resetAndLoad()">{{ "moderation.apply" | snT:"Apply" }}</button>
    </section>

    @if(error()){<div class="alert">{{error()}}</div>}

    <section class="layout">
      <div class="queue card">
        <div class="section-head"><h3>{{ "moderation.queue" | snT:"Case queue" }}</h3><span>{{ total }} {{ "moderation.cases" | snT:"cases" }}</span></div>
        @if(loading()){<div class="empty">{{ "moderation.loading" | snT:"Loading queue…" }}</div>}
        @for(item of cases();track item.id){
          <button class="case-row" [class.active]="selected()?.id===item.id" [class.overdue]="item.overdue" (click)="select(item)">
            <span class="priority" [attr.data-priority]="item.priority">{{item.priority}}</span>
            <span class="case-main"><strong>{{item.title}}</strong><small>{{item.member_name}} · {{item.category}} · {{item.status}}</small></span>
            <span class="owner">{{item.assignee_name || ('moderation.unassigned' | snT:'Unassigned')}}<small>{{item.due_at ? date(item.due_at) : ('moderation.no_deadline' | snT:'No deadline')}}</small></span>
          </button>
        } @empty { @if(!loading()){<div class="empty">{{ "moderation.empty" | snT:"No cases match the selected filters." }}</div>} }
        <div class="pager"><button [disabled]="page<=1" (click)="changePage(-1)">←</button><span>{{page}} / {{pages}}</span><button [disabled]="page>=pages" (click)="changePage(1)">→</button></div>
      </div>

      <aside class="side">
        @if(selected();as item){
          <section class="card editor">
            <div class="section-head"><h3>{{ "moderation.control" | snT:"Case control" }}</h3><span [class.red]="item.overdue">{{ item.overdue ? ('moderation.overdue_caps' | snT:'OVERDUE') : ('moderation.active_caps' | snT:'ACTIVE') }}</span></div>
            <h4>{{item.title}}</h4><p>{{item.member_name}} · {{ "moderation.discord_id" | snT:"Discord ID" }} {{item.discord_user_id}}</p>
            <label>{{ "moderation.status" | snT:"Status" }}<select [(ngModel)]="editStatus"><option value="open">{{ "moderation.open" | snT:"Open" }}</option><option value="investigating">{{ "moderation.investigating" | snT:"Investigating" }}</option><option value="resolved">{{ "moderation.resolved" | snT:"Resolved" }}</option><option value="dismissed">{{ "moderation.dismissed" | snT:"Dismissed" }}</option></select></label>
            <label>{{ "moderation.priority" | snT:"Priority" }}<select [(ngModel)]="editPriority"><option value="urgent">{{ "moderation.urgent" | snT:"Urgent" }}</option><option value="high">{{ "moderation.high" | snT:"High" }}</option><option value="normal">{{ "moderation.normal" | snT:"Normal" }}</option><option value="low">{{ "moderation.low" | snT:"Low" }}</option></select></label>
            <label>{{ "moderation.responsible" | snT:"Responsible administrator" }}<input [(ngModel)]="editAssignee" [placeholder]="'moderation.administrator_placeholder' | snT:'User UUID; empty = unassigned'"></label>
            <label>{{ "moderation.deadline" | snT:"Deadline" }}<input type="datetime-local" [(ngModel)]="editDueAt"></label>
            <button class="btn" (click)="saveSelected()">{{ "moderation.save_operations" | snT:"Save operations data" }}</button>
            <a [routerLink]="['/guild',guildId,'members']" [queryParams]="{member:item.discord_user_id}">{{ "moderation.open_member" | snT:"Open member center" }} →</a>
            <dl><div><dt>{{ "moderation.created" | snT:"Created" }}</dt><dd>{{date(item.created_at)}}</dd></div><div><dt>{{ "moderation.first_response" | snT:"First response" }}</dt><dd>{{item.first_response_at?date(item.first_response_at) : ('moderation.not_started' | snT:'Not started')}}</dd></div><div><dt>{{ "moderation.updated" | snT:"Updated" }}</dt><dd>{{date(item.updated_at)}}</dd></div></dl>
          </section>
        } @else {<section class="card empty">{{ "moderation.select_case" | snT:"Select a case to manage its owner, priority and SLA." }}</section>}

        <section class="card workload"><div class="section-head"><h3>{{ "moderation.workload" | snT:"Moderator workload" }}</h3><span>{{ "moderation.live" | snT:"Live" }}</span></div>@for(w of workload();track w.user_id){<button (click)="filterOwner(w)"><span>{{w.display_name}}</span><strong>{{w.open_cases}}</strong><small>{{w.overdue_cases}} {{ "moderation.overdue" | snT:"overdue" }} · {{w.urgent_cases}} {{ "moderation.urgent_short" | snT:"urgent" }}</small></button>}@empty{<div class="empty">{{ "moderation.no_workload" | snT:"No workload data." }}</div>}</section>
      </aside>
    </section>
  </sn-shell>`,
  styles:[`
    .hero{display:flex;justify-content:space-between;gap:1rem;align-items:end;margin-bottom:1.2rem}.hero h2{margin:.2rem 0;font-size:1.8rem}.hero p,.section-head span,.case-row small,.editor p,.editor a,dt{color:var(--muted)}.eyebrow{color:var(--primary);font-size:.72rem;font-weight:800;letter-spacing:.15em}.hero-actions{display:flex;gap:.6rem}.btn{background:var(--primary);color:white;padding:.7rem 1rem;border-radius:10px}.secondary{background:var(--panel-2);border:1px solid var(--line)}.card{background:var(--panel);border:1px solid var(--line);border-radius:15px}.stats{display:grid;grid-template-columns:repeat(7,1fr);gap:.65rem;margin-bottom:1rem}.stats button{padding:.9rem;background:var(--panel);border:1px solid var(--line);border-radius:13px;text-align:left;color:var(--text)}.stats strong,.stats span{display:block}.stats strong{font-size:1.45rem}.stats span{font-size:.72rem;color:var(--muted)}.stats .danger strong{color:var(--danger)}.filters{display:grid;grid-template-columns:2fr repeat(3,1fr) auto auto;gap:.65rem;padding:.8rem;margin-bottom:1rem}.filters input,.filters select,.editor input,.editor select{width:100%;background:var(--panel-2);border:1px solid var(--line);border-radius:9px;color:var(--text);padding:.65rem}.check{display:flex;align-items:center;gap:.4rem;color:var(--muted);font-size:.8rem}.check input{width:auto}.layout{display:grid;grid-template-columns:minmax(0,1fr) 350px;gap:1rem}.queue{overflow:hidden}.section-head{display:flex;justify-content:space-between;align-items:center;padding:1rem;border-bottom:1px solid var(--line)}.section-head h3{margin:0}.case-row{width:100%;display:grid;grid-template-columns:78px minmax(0,1fr) 170px;gap:.8rem;align-items:center;text-align:left;padding:.85rem 1rem;background:transparent;color:var(--text);border-bottom:1px solid var(--line)}.case-row:hover,.case-row.active{background:var(--primary-soft)}.case-row.overdue{box-shadow:inset 3px 0 var(--danger)}.priority{text-transform:uppercase;font-size:.64rem;font-weight:900;padding:.35rem .45rem;border-radius:999px;text-align:center;background:var(--panel-2)}.priority[data-priority=urgent]{color:var(--danger)}.priority[data-priority=high]{color:var(--warning)}.case-main strong,.case-main small,.owner small{display:block}.owner{text-align:right;font-size:.8rem}.pager{display:flex;justify-content:center;align-items:center;gap:1rem;padding:.8rem}.pager button{background:var(--panel-2);color:var(--text);padding:.4rem .7rem;border-radius:8px}.side{display:grid;gap:1rem;align-content:start}.editor{padding:1rem;display:grid;gap:.8rem}.editor .section-head{padding:0 0 .8rem}.editor h4,.editor p{margin:0}.editor label{display:grid;gap:.35rem;color:var(--muted);font-size:.75rem}.editor a{font-size:.78rem}.red{color:var(--danger)!important}dl{margin:0;display:grid;gap:.45rem}dl div{display:flex;justify-content:space-between;gap:1rem}dt,dd{font-size:.72rem;margin:0}.workload{overflow:hidden}.workload button{width:100%;display:grid;grid-template-columns:1fr auto;text-align:left;padding:.75rem 1rem;background:transparent;color:var(--text);border-bottom:1px solid var(--line)}.workload small{grid-column:1/-1;color:var(--muted)}.empty{padding:2rem;text-align:center;color:var(--muted)}.alert{padding:.8rem 1rem;margin-bottom:1rem;border:1px solid var(--danger);border-radius:10px;color:var(--danger)}
    @media(max-width:1150px){.stats{grid-template-columns:repeat(4,1fr)}.layout{grid-template-columns:1fr}.side{grid-template-columns:1fr 1fr}}@media(max-width:760px){.hero{align-items:flex-start}.hero p{display:none}.stats{grid-template-columns:repeat(2,1fr)}.filters{grid-template-columns:1fr}.case-row{grid-template-columns:65px 1fr}.owner{grid-column:2;text-align:left}.side{grid-template-columns:1fr}}
  `]
})
export class ModerationOperationsComponent implements OnInit{
  readonly guildId=this.route.snapshot.paramMap.get('guildId') ?? '';
  readonly cases=signal<ModerationCase[]>([]);readonly stats=signal<ModerationStats|null>(null);readonly workload=signal<ModeratorWorkload[]>([]);readonly selected=signal<ModerationCase|null>(null);readonly loading=signal(false);readonly error=signal('');
  query='';statusFilter='all';priority='all';assignee='all';overdueOnly=false;page=1;pageSize=50;total=0;editStatus='open';editPriority='normal';editAssignee='';editDueAt='';
  constructor(private route:ActivatedRoute,private service:ModerationOperationsService,private i18n:TranslationService){}
  async ngOnInit(){await this.reload()}
  get pages(){return Math.max(1,Math.ceil(this.total/this.pageSize))}
  async reload(){await Promise.all([this.loadCases(),this.loadStats(),this.loadWorkload()])}
  private requestError(error: unknown, fallback: string): string {
    if (error instanceof HttpErrorResponse) {
      if (error.status === 401) return this.i18n.t('moderation.session_expired','Your session has expired. Sign in again.');
      if (error.status === 403) return this.i18n.t('moderation.forbidden','You do not have permission to manage this server.');
      if (error.status === 0) return this.i18n.t('moderation.server_unavailable','The server is temporarily unavailable.');
      const detail = typeof error.error?.detail === 'string' ? error.error.detail : '';
      if (detail) return detail;
    }
    return fallback;
  }

  async loadCases(){this.loading.set(true);this.error.set('');try{const r=await this.service.list(this.guildId,{query:this.query,status_filter:this.statusFilter,priority:this.priority,assignee:this.assignee,overdue_only:this.overdueOnly,page:this.page,page_size:this.pageSize});this.cases.set(r.items);this.total=r.total;if(this.selected()){const fresh=r.items.find(x=>x.id===this.selected()!.id);if(fresh)this.select(fresh)}}catch(error){this.error.set(this.requestError(error,this.i18n.t('moderation.load_error','Unable to load moderation operations.')))}finally{this.loading.set(false)}}
  async loadStats(){try{this.stats.set(await this.service.stats(this.guildId))}catch{}}
  async loadWorkload(){try{this.workload.set(await this.service.workload(this.guildId))}catch{}}
  resetAndLoad(){this.page=1;this.loadCases()}
  async changePage(delta:number){this.page+=delta;await this.loadCases()}
  select(item:ModerationCase){this.selected.set(item);this.editStatus=item.status;this.editPriority=item.priority;this.editAssignee=item.assigned_to||'';this.editDueAt=this.toLocal(item.due_at)}
  filterOwner(w:ModeratorWorkload){this.assignee=w.user_id||'unassigned';this.resetAndLoad()}
  date(v:string){return new Date(v).toLocaleString()}
  toLocal(v:string|null){if(!v)return'';const d=new Date(v),p=(n:number)=>String(n).padStart(2,'0');return`${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`}
  async saveSelected(){const item=this.selected();if(!item)return;try{await this.service.update(this.guildId,item,{status:this.editStatus,priority:this.editPriority,assigned_to:this.editAssignee||null,due_at:this.editDueAt?new Date(this.editDueAt).toISOString():null});await this.reload()}catch{this.error.set(this.i18n.t('moderation.update_error','Unable to update case. Verify the administrator UUID and supplied values.'))}}
}
