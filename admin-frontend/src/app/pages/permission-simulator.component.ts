import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { debounceTime, distinctUntilChanged, Subject } from 'rxjs';

import { PermissionSimulatorService, SimulationResult, SimulatorChannel, SimulatorMember } from '../core/permission-simulator.service';
import { ShellComponent } from '../shared/shell.component';
import { TranslatePipe } from '../core/translate.pipe';
import { TranslationService } from '../core/translation.service';

@Component({
  selector:'sn-permission-simulator',
  standalone:true,
  imports: [CommonModule, FormsModule, ShellComponent, TranslatePipe],
  template:`
  <sn-shell [title]="'permission.title' | snT:'Permission Simulator'">
    <section class="hero">
      <div>
        <div class="eyebrow">{{ "permission.eyebrow" | snT:"Discord permission resolver" }}</div>
        <h2>{{ "permission.heading" | snT:"Explain access before changing roles" }}</h2>
        <p>{{ "permission.description" | snT:"Select a member and channel to calculate effective Discord permissions, including role permissions and channel overwrites." }}</p>
      </div>
      <button (click)="simulate()" [disabled]="!memberId || !channelId || loading">{{ loading ? ('permission.calculating' | snT:'Calculating…') : ('permission.run' | snT:'Run simulation') }}</button>
    </section>

    <section class="selector-grid">
      <article class="panel">
        <label>{{ "permission.find_member" | snT:"Find member" }}</label>
        <input [(ngModel)]="memberQuery" (ngModelChange)="memberSearch.next($event)" [placeholder]="'permission.member_placeholder' | snT:'Username, nickname or global name'">
        <select [(ngModel)]="memberId">
          <option value="">{{ "permission.select_member" | snT:"Select member" }}</option>
          <option *ngFor="let m of members" [value]="m.id">{{m.display_name}} · {{m.username}}{{m.bot?' [BOT]':''}}</option>
        </select>
        <small>{{members.length}} {{ "permission.matching_members" | snT:"matching members" }}</small>
      </article>
      <article class="panel">
        <label>{{ "permission.channel" | snT:"Channel" }}</label>
        <select [(ngModel)]="channelId">
          <option value="">{{ "permission.select_channel" | snT:"Select channel" }}</option>
          <option *ngFor="let c of channels" [value]="c.id"># {{c.name}} · {{c.type}}</option>
        </select>
        <small>{{channels.length}} {{ "permission.synced_channels" | snT:"synchronized channels" }}</small>
      </article>
    </section>

    <div class="notice error" *ngIf="error">{{error}}</div>
    <div class="notice" *ngIf="!result && !error">{{ "permission.choose_help" | snT:"Choose a member and channel, then run the simulation." }}</div>

    <ng-container *ngIf="result as r">
      <section class="summary-grid">
        <article class="identity panel">
          <img *ngIf="r.member.avatar_url" [src]="r.member.avatar_url" alt="">
          <div><span>{{ "permission.member" | snT:"Member" }}</span><strong>{{r.member.display_name}}</strong><small>{{r.member.username}} · {{r.member.id}}</small></div>
        </article>
        <article class="panel"><span>{{ "permission.channel" | snT:"Channel" }}</span><strong># {{r.channel.name}}</strong><small>{{r.channel.type}} · {{r.channel.id}}</small></article>
        <article class="panel"><span>{{ "permission.effective_allows" | snT:"Effective allows" }}</span><strong>{{allowedCount()}}</strong><small>{{ ("permission.of_known" | snT:"of {count} known permissions").replace("{count}", r.permissions.length + "") }}</small></article>
        <article class="panel" [class.warn]="r.owner_bypass || r.administrator_bypass"><span>{{ "permission.bypass" | snT:"Bypass" }}</span><strong>{{ r.owner_bypass ? ("permission.owner" | snT:"Owner") : r.administrator_bypass ? ("permission.administrator" | snT:"Administrator") : ("permission.no" | snT:"No") }}</strong><small>{{r.role_count}} {{ "permission.assigned_roles" | snT:"assigned roles" }}</small></article>
      </section>

      <div class="warning" *ngIf="!r.snapshot_complete">{{ "permission.snapshot_warning" | snT:"This channel snapshot is not marked as permissions-synced. The result uses the latest stored overwrites, but Discord may have changed since the last worker sync." }}</div>

      <section class="result-layout">
        <article class="panel permissions">
          <div class="panel-head"><div><span>{{ "permission.effective" | snT:"Effective permissions" }}</span><h3>{{ "permission.actions" | snT:"Allowed and denied actions" }}</h3></div><input [(ngModel)]="permissionFilter" [placeholder]="'permission.filter' | snT:'Filter permissions'"></div>
          <div class="permission-list">
            <div class="permission" *ngFor="let p of filteredPermissions()" [class.allowed]="p.allowed" [class.denied]="!p.allowed">
              <span class="state">{{p.allowed?'✓':'×'}}</span>
              <div><b>{{p.label}}</b><small>{{p.key}} · bit {{p.bit}}</small></div>
              <strong>{{ p.allowed ? ('permission.allowed' | snT:'Allowed') : ('permission.denied' | snT:'Denied') }}</strong>
            </div>
          </div>
        </article>

        <article class="panel trace">
          <span>{{ "permission.resolution_trace" | snT:"Resolution trace" }}</span>
          <h3>{{ "permission.why" | snT:"Why this result was produced" }}</h3>
          <div class="trace-item" *ngFor="let s of r.sources; let i=index">
            <i>{{i+1}}</i>
            <div><b>{{s.source}}</b><small>{{stageLabel(s.stage)}}</small></div>
            <div class="chips">
              <em *ngIf="s.permissions !== undefined">{{ "permission.base" | snT:"base" }} {{s.permissions}}</em>
              <em class="allow" *ngIf="s.allow">{{ "permission.allow" | snT:"allow" }} {{s.allow}}</em>
              <em class="deny" *ngIf="s.deny">{{ "permission.deny" | snT:"deny" }} {{s.deny}}</em>
            </div>
          </div>
          <div class="raw"><span>{{ "permission.base_bitfield" | snT:"Base bitfield" }}</span><code>{{r.base_permissions}}</code><span>{{ "permission.effective_bitfield" | snT:"Effective bitfield" }}</span><code>{{r.effective_permissions}}</code></div>
        </article>
      </section>
    </ng-container>
  </sn-shell>`,
  styles:[`
    .hero,.panel,.notice,.warning{border:1px solid var(--line);background:rgba(16,22,38,.74);border-radius:18px}.hero{display:flex;justify-content:space-between;gap:2rem;align-items:center;padding:1.35rem}.hero h2{margin:.25rem 0}.hero p{margin:0;color:var(--muted);max-width:760px}.eyebrow{color:var(--primary);font-size:.7rem;letter-spacing:.12em;text-transform:uppercase}.hero button{border:0;border-radius:12px;background:var(--primary);color:#fff;padding:.8rem 1.1rem;font-weight:700}.hero button:disabled{opacity:.45}.selector-grid,.summary-grid{display:grid;gap:1rem;margin:1rem 0}.selector-grid{grid-template-columns:1fr 1fr}.summary-grid{grid-template-columns:repeat(4,1fr)}.panel{padding:1rem}.panel label,.panel>span,.panel div>span{display:block;color:var(--muted);font-size:.78rem}.panel strong{display:block;font-size:1.15rem;margin:.3rem 0}.panel small{color:var(--muted)}input,select{width:100%;box-sizing:border-box;background:#0c1221;color:var(--text);border:1px solid var(--line);border-radius:10px;padding:.72rem;margin:.45rem 0}.identity{display:flex;gap:.8rem;align-items:center}.identity img{width:48px;height:48px;border-radius:50%;object-fit:cover}.warn{border-color:#ffc56f}.notice,.warning{padding:1rem;color:var(--muted)}.error{color:#ff91a5}.warning{border-color:#ffc56f;color:#ffd792;margin-bottom:1rem}.result-layout{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(300px,.8fr);gap:1rem}.panel-head{display:flex;justify-content:space-between;gap:1rem;align-items:center}.panel-head h3,.trace h3{margin:.25rem 0 1rem}.panel-head input{max-width:250px}.permission-list{display:grid;grid-template-columns:1fr 1fr;gap:.55rem}.permission{display:grid;grid-template-columns:34px 1fr auto;gap:.7rem;align-items:center;border:1px solid var(--line);border-radius:12px;padding:.7rem}.permission .state{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;font-weight:900}.permission.allowed .state{background:rgba(74,222,128,.14);color:#7af0ab}.permission.denied .state{background:rgba(248,113,113,.12);color:#ff9292}.permission.allowed>strong{color:#7af0ab}.permission.denied>strong{color:#ff9292}.permission b{display:block}.permission small{display:block}.trace-item{display:grid;grid-template-columns:32px 1fr;gap:.7rem;padding:.8rem 0;border-bottom:1px solid var(--line)}.trace-item i{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:var(--primary-soft);font-style:normal}.chips{grid-column:2;display:flex;gap:.35rem;flex-wrap:wrap}.chips em{font-style:normal;color:var(--muted);background:#0c1221;border-radius:999px;padding:.25rem .5rem;font-size:.72rem}.chips .allow{color:#7af0ab}.chips .deny{color:#ff9292}.raw{display:grid;gap:.35rem;margin-top:1rem}.raw code{overflow-wrap:anywhere;color:#b9c4ff;background:#0c1221;border-radius:8px;padding:.5rem}@media(max-width:1100px){.summary-grid{grid-template-columns:1fr 1fr}.result-layout{grid-template-columns:1fr}.permission-list{grid-template-columns:1fr}}@media(max-width:700px){.hero{align-items:flex-start;flex-direction:column}.selector-grid,.summary-grid{grid-template-columns:1fr}.panel-head{align-items:flex-start;flex-direction:column}.panel-head input{max-width:none}}
  `]
})
export class PermissionSimulatorComponent implements OnInit {
  guildId=''; members:SimulatorMember[]=[]; channels:SimulatorChannel[]=[]; memberId=''; channelId=''; memberQuery=''; permissionFilter=''; loading=false; error=''; result:SimulationResult|null=null;
  readonly memberSearch = new Subject<string>();
  constructor(private readonly route:ActivatedRoute, private readonly api:PermissionSimulatorService, private readonly i18n:TranslationService) {
    this.memberSearch.pipe(debounceTime(300), distinctUntilChanged()).subscribe(q=>this.loadOptions(q));
  }
  ngOnInit(){ this.guildId=this.route.snapshot.paramMap.get('guildId')||''; this.loadOptions(); }
  loadOptions(q=''){ this.api.options(this.guildId,q).subscribe({next:v=>{this.members=v.members;this.channels=v.channels},error:()=>this.error=this.i18n.t('permission.load_error','Unable to load simulator inventory. Wait for Discord Explorer synchronization.')}); }
  simulate(){ if(!this.memberId||!this.channelId)return; this.loading=true;this.error='';this.api.check(this.guildId,this.memberId,this.channelId).subscribe({next:v=>{this.result=v;this.loading=false},error:e=>{this.error=e?.error?.detail||this.i18n.t('permission.simulation_error','Permission simulation failed.');this.loading=false}}); }
  allowedCount(){ return this.result?.permissions.filter(x=>x.allowed).length||0; }
  filteredPermissions(){ const q=this.permissionFilter.trim().toLowerCase(); return (this.result?.permissions||[]).filter(x=>!q||x.label.toLowerCase().includes(q)||x.key.includes(q)); }
  stageLabel(stage:string){const keys:Record<string,string>={base:'permission.stage_base',role:'permission.stage_role',channel_everyone:'permission.stage_everyone',channel_roles:'permission.stage_roles',channel_member:'permission.stage_member',bypass:'permission.stage_bypass'};return this.i18n.t(keys[stage]||'',stage)}
}
