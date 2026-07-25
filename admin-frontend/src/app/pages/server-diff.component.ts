import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { ServerDiffResult, ServerDiffService, DiffGuildOption } from '../core/server-diff.service';
import { ShellComponent } from '../shared/shell.component';
import { TranslatePipe } from '../core/translate.pipe';
import { TranslationService } from '../core/translation.service';

@Component({
  selector:'sn-server-diff', standalone:true, imports:[CommonModule,FormsModule,ShellComponent,TranslatePipe],
  template:`<sn-shell [title]="'diff.title' | snT:'Server Diff'">
    <section class="hero">
      <div><div class="eyebrow">{{ "diff.eyebrow" | snT:"Configuration comparison" }}</div><h2>{{ "diff.heading" | snT:"Compare two Discord servers" }}</h2><p>{{ "diff.description" | snT:"Find missing roles, channel changes, permission drift, webhook differences and emoji mismatches." }}</p></div>
      <button (click)="run()" [disabled]="loading || !sourceId || !targetId || sourceId===targetId">{{ loading ? ('diff.comparing' | snT:'Comparing…') : ('diff.compare' | snT:'Compare servers') }}</button>
    </section>
    <section class="selector">
      <label>{{ "diff.source" | snT:"Source server" }}<select [(ngModel)]="sourceId"><option [ngValue]="''">{{ "diff.choose_source" | snT:"Choose source" }}</option><option *ngFor="let g of guilds" [ngValue]="g.guild_id">{{g.name}} · {{g.guild_id}}</option></select></label>
      <button class="swap" (click)="swap()">⇄</button>
      <label>{{ "diff.target" | snT:"Target server" }}<select [(ngModel)]="targetId"><option [ngValue]="''">{{ "diff.choose_target" | snT:"Choose target" }}</option><option *ngFor="let g of guilds" [ngValue]="g.guild_id">{{g.name}} · {{g.guild_id}}</option></select></label>
    </section>
    <div class="notice err" *ngIf="error">{{error}}</div>
    <ng-container *ngIf="result">
      <section class="summary">
        <article><span>{{ "diff.similarity" | snT:"Similarity" }}</span><strong>{{result.summary.similarity_percent}}%</strong></article>
        <article><span>{{ "diff.total_differences" | snT:"Total differences" }}</span><strong>{{result.summary.total_differences}}</strong></article>
        <article><span>{{ "diff.affected_sections" | snT:"Affected sections" }}</span><strong>{{result.summary.sections_with_differences}}</strong></article>
        <article><span>{{ "diff.source_members" | snT:"Source members" }}</span><strong>{{result.source.member_count}}</strong></article>
        <article><span>{{ "diff.target_members" | snT:"Target members" }}</span><strong>{{result.target.member_count}}</strong></article>
      </section>
      <section class="server-head"><div><b>{{result.source.name}}</b><code>{{result.source.guild_id}}</code></div><span>{{ "diff.compared_with" | snT:"compared with" }}</span><div><b>{{result.target.name}}</b><code>{{result.target.guild_id}}</code></div></section>
      <section class="diff-section" *ngFor="let section of result.sections">
        <header><div><h3>{{section.name}}</h3><span>{{section.source_count}} {{ "diff.source_label" | snT:"source" }} · {{section.target_count}} {{ "diff.target_label" | snT:"target" }}</span></div><b [class.ok]="section.difference_count===0">{{section.difference_count}} {{ "diff.differences" | snT:"differences" }}</b></header>
        <div class="empty" *ngIf="section.difference_count===0">{{ "diff.none" | snT:"No differences detected." }}</div>
        <article class="change" *ngFor="let change of section.changes">
          <div class="change-title"><span [class]="change.kind">{{label(change.kind)}}</span><b>{{change.name}}</b></div>
          <div class="pair" *ngIf="change.kind==='changed'"><pre>{{change.source|json}}</pre><pre>{{change.target|json}}</pre></div>
          <pre *ngIf="change.kind==='source_only'">{{change.source|json}}</pre>
          <pre *ngIf="change.kind==='target_only'">{{change.target|json}}</pre>
        </article>
      </section>
    </ng-container>
  </sn-shell>`,
  styles:[`.hero,.selector,.summary article,.server-head,.diff-section{border:1px solid var(--line);background:rgba(16,22,38,.72);border-radius:18px}.hero{padding:1.3rem;display:flex;justify-content:space-between;align-items:center}.hero h2{margin:.2rem 0}.hero p,.diff-section header span,.server-head span{color:var(--muted)}.eyebrow{color:var(--primary);text-transform:uppercase;letter-spacing:.12em;font-size:.72rem}.hero button,.swap{padding:.7rem 1rem;border-radius:11px;background:var(--primary);color:white}.selector{display:grid;grid-template-columns:1fr auto 1fr;gap:1rem;padding:1rem;margin:1rem 0;align-items:end}.selector label{display:grid;gap:.45rem;color:var(--muted)}select{background:#0c1323;color:var(--text);border:1px solid var(--line);padding:.8rem;border-radius:10px}.swap{background:var(--primary-soft)}.summary{display:grid;grid-template-columns:repeat(5,1fr);gap:.8rem}.summary article{padding:1rem;display:grid;gap:.3rem}.summary span{color:var(--muted)}.summary strong{font-size:1.55rem}.server-head{margin:1rem 0;padding:1rem;display:grid;grid-template-columns:1fr auto 1fr;align-items:center;text-align:center}.server-head div{display:grid;gap:.25rem}.server-head code{color:var(--muted)}.diff-section{margin:1rem 0;padding:1rem}.diff-section header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);padding-bottom:.8rem}.diff-section h3{margin:0}.diff-section header b{color:#ff9aab}.diff-section header b.ok{color:#74e9b3}.change{padding:1rem 0;border-bottom:1px solid var(--line)}.change-title{display:flex;gap:.7rem;align-items:center;margin-bottom:.7rem}.change-title span{font-size:.68rem;text-transform:uppercase;padding:.25rem .45rem;border-radius:7px}.source_only{background:rgba(255,176,80,.16);color:#ffc276}.target_only{background:rgba(105,194,255,.16);color:#91d3ff}.changed{background:rgba(255,102,128,.16);color:#ff91a5}.pair{display:grid;grid-template-columns:1fr 1fr;gap:.8rem}pre{margin:0;background:#09101d;border:1px solid var(--line);padding:.8rem;border-radius:10px;overflow:auto;color:#cdd6f4}.empty,.notice{padding:1rem;color:var(--muted)}.err{color:#ff91a5}@media(max-width:900px){.selector,.server-head,.pair{grid-template-columns:1fr}.summary{grid-template-columns:repeat(2,1fr)}}`]
})
export class ServerDiffComponent implements OnInit{
  guilds:DiffGuildOption[]=[]; sourceId=''; targetId=''; result:ServerDiffResult|null=null; loading=false; error='';
  constructor(private api:ServerDiffService,private route:ActivatedRoute,private i18n:TranslationService){}
  ngOnInit(){this.sourceId=this.route.snapshot.paramMap.get('guildId')||'';this.api.options().subscribe({next:v=>{this.guilds=v; if(!this.targetId){const other=v.find(x=>x.guild_id!==this.sourceId);this.targetId=other?.guild_id||''}},error:()=>this.error=this.i18n.t('diff.load_error','Unable to load available servers.')});}
  swap(){[this.sourceId,this.targetId]=[this.targetId,this.sourceId];this.result=null;}
  run(){this.error='';this.loading=true;this.api.compare(this.sourceId,this.targetId).subscribe({next:v=>{this.result=v;this.loading=false},error:e=>{this.error=e?.error?.detail||this.i18n.t('diff.compare_error','Unable to compare servers.');this.loading=false}})}
  label(k:string){return k==='source_only'?this.i18n.t('diff.only_source','Only in source'):k==='target_only'?this.i18n.t('diff.only_target','Only in target'):this.i18n.t('diff.changed','Changed')}
}
