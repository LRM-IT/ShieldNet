import {CommonModule} from '@angular/common';
import {Component,OnInit,inject,signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import { DiscordChannelPickerComponent } from '../shared/discord-channel-picker.component';
import {ActivatedRoute} from '@angular/router';
import {ShellComponent} from '../shared/shell.component';
import {VotingService} from '../core/voting.service';
import {GlobalLanguage,GlobalLanguageService} from '../core/global-language.service';

@Component({
 selector:'sn-plugin-voting',standalone:true,
 imports:[CommonModule,FormsModule,ShellComponent,DiscordChannelPickerComponent],
 template:`
 <sn-shell title="Voting">
 <main class="page">
  <header><div><small>SHIELDNET PLUGIN</small><h2>Multilingual Voting</h2>
  <p>Create Discord polls in selected languages with manual or AI translation.</p></div>
  <button (click)="reload()">Refresh</button></header>
  @if(error()){<div class="notice error">{{error()}}</div>}
  @if(success()){<div class="notice success">{{success()}}</div>}
  <section class="panel">
   <div class="head"><h3>Create poll</h3><div class="language-add"><select [(ngModel)]="selectedLanguageCode"><option value="">Select language</option><option *ngFor="let language of availableLanguages()" [value]="language.code">{{language.flag || '🌐'}} {{language.native_name}}</option></select><button (click)="addSelectedLanguage()" [disabled]="!selectedLanguageCode">+ Add language</button></div></div>
   <div class="grid">
    <label>Primary language<select [(ngModel)]="form.primary_language" (ngModelChange)="setPrimaryLanguage($event)"><option *ngFor="let language of directoryLanguages()" [value]="language.code">{{language.flag || '🌐'}} {{language.native_name}} ({{language.code}})</option></select></label>
    <label>Publish channel<sn-discord-channel-picker [guildId]="guildId" [value]="form.channel_id" (valueChange)="form.channel_id = $event" /></label>
    <label>Choice mode<select [(ngModel)]="form.selection_mode"><option value="single">Single</option><option value="multiple">Multiple</option></select></label>
    <label>Close at<input type="datetime-local" [(ngModel)]="form.closes_at"></label>
   </div>
   <div class="toggles">
    <label><input type="checkbox" [(ngModel)]="form.anonymous"> Anonymous</label>
    <label><input type="checkbox" [(ngModel)]="form.allow_change_vote"> Allow vote change</label>
    <label><input type="checkbox" [(ngModel)]="form.show_live_results"> Live results</label>
   </div>
   <section class="language" *ngFor="let lang of languages;let li=index">
    <div class="head"><h4>{{lang.code}}</h4><div>
      <button (click)="copyPrimary(lang.code)">Copy source</button>
      <button (click)="removeLanguage(li)" [disabled]="lang.code===form.primary_language">Remove</button>
    </div></div>
    <label>Title<input [(ngModel)]="lang.title"></label>
    <label>Description<textarea [(ngModel)]="lang.description"></textarea></label>
    <div class="option" *ngFor="let option of options;let oi=index">
      <span>{{oi+1}}</span><input [(ngModel)]="option.labels[lang.code]" placeholder="Answer text">
    </div>
   </section>
   <div class="actions"><button (click)="addOption()">+ Option</button><button class="primary" (click)="create()">Save draft</button></div>
  </section>

  <section class="panel">
   <div class="head"><h3>Polls</h3><span>{{polls().length}}</span></div>
   <article class="poll" *ngFor="let poll of polls()">
    <div><small>{{poll.status}}</small><h4>{{title(poll)}}</h4><span>{{poll.options.length}} options · {{total(poll)}} votes</span></div>
    <div><button (click)="publish(poll)" [disabled]="poll.status!=='draft'">Publish</button>
    <button (click)="close(poll)" [disabled]="poll.status!=='active'">Close</button></div>
   </article>
  </section>
 </main></sn-shell>`,
 styles:[`
 .page{display:grid;gap:1rem;padding:1rem}header,.head,.poll,.actions{display:flex;justify-content:space-between;align-items:center;gap:1rem}
 h2,h3,h4,p{margin:0}small{color:var(--primary);letter-spacing:.12em}.panel,.language,.poll,.notice{border:1px solid var(--line);border-radius:12px;background:var(--surface);padding:1rem}
 .panel,.language{display:grid;gap:1rem}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:.7rem}label{display:grid;gap:.35rem;color:var(--muted);font-size:.78rem}
 input,textarea,select,button{font:inherit;border:1px solid var(--line);border-radius:8px;background:#081019;color:var(--text);padding:.7rem}textarea{min-height:90px}
 .toggles{display:flex;gap:1rem}.toggles label{display:flex;align-items:center}.option{display:grid;grid-template-columns:30px 1fr;align-items:center;gap:.5rem}
 button{cursor:pointer}.primary{background:var(--primary);color:#03130e}.poll{margin-top:.55rem}.success{color:var(--success)}.error{color:#ff8290}
 @media(max-width:900px){.grid{grid-template-columns:1fr}.poll,header{align-items:flex-start;flex-direction:column}}
 `]
})
export class PluginVotingComponent implements OnInit{
 private route=inject(ActivatedRoute);private api=inject(VotingService);private languageApi=inject(GlobalLanguageService);
 polls=signal<any[]>([]);error=signal('');success=signal('');directoryLanguages=signal<GlobalLanguage[]>([]);selectedLanguageCode='';
 guildId=this.route.snapshot.paramMap.get('guildId')||'';
 languages:any[]=[{code:'en',title:'',description:''}];
 options:any[]=[{labels:{en:''}},{labels:{en:''}}];
 form:any={primary_language:'en',fallback_language:'en',language_selection_mode:'automatic_with_selector',channel_id:'',selection_mode:'single',anonymous:true,allow_change_vote:true,show_live_results:true,min_choices:1,max_choices:1,allowed_role_ids:[],closes_at:''};
 ngOnInit(){this.reload();this.loadLanguages()}
 reload(){this.api.list(this.guildId).subscribe({next:v=>this.polls.set(v.items||[]),error:r=>this.error.set(r?.error?.detail||'Unable to load polls.')})}
 async loadLanguages(){try{const items=await this.languageApi.listActive();this.directoryLanguages.set(items);if(items.length&&!items.some(x=>x.code===this.form.primary_language)){this.form.primary_language=items[0].code;this.form.fallback_language=items[0].code;this.languages=[{code:items[0].code,title:'',description:''}];this.options=[{labels:{[items[0].code]:''}},{labels:{[items[0].code]:''}}]}}catch(e:any){this.error.set(e?.error?.detail||'Unable to load language directory.')}}availableLanguages(){return this.directoryLanguages().filter(x=>!this.languages.some(y=>y.code===x.code))}addSelectedLanguage(){const code=this.selectedLanguageCode;if(!code||this.languages.some(x=>x.code===code))return;this.languages.push({code,title:'',description:''});for(const o of this.options)o.labels[code]='';this.selectedLanguageCode=''}setPrimaryLanguage(code:string){if(!this.languages.some(x=>x.code===code)){this.languages.unshift({code,title:'',description:''});for(const o of this.options)o.labels[code]=''}this.form.fallback_language=code}
 removeLanguage(i:number){const code=this.languages[i].code;this.languages.splice(i,1);for(const o of this.options)delete o.labels[code]}
 addOption(){if(this.options.length>=10)return;const labels:any={};for(const l of this.languages)labels[l.code]='';this.options.push({labels})}
 copyPrimary(code:string){const src=this.languages.find(x=>x.code===this.form.primary_language);const dst=this.languages.find(x=>x.code===code);if(src&&dst){dst.title=src.title;dst.description=src.description}for(const o of this.options)o.labels[code]=o.labels[this.form.primary_language]||''}
 create(){this.error.set('');const translations:any={};for(const l of this.languages)translations[l.code]={title:l.title,description:l.description};const payload={...this.form,channel_id:this.form.channel_id?String(this.form.channel_id):null,closes_at:this.form.closes_at||null,translations,options:this.options.map(o=>({emoji:null,translations:o.labels}))};this.api.create(this.guildId,payload).subscribe({next:()=>{this.success.set('Poll saved.');this.reload()},error:r=>this.error.set(r?.error?.detail||'Unable to save poll.')})}
 publish(p:any){this.api.publish(this.guildId,p.id).subscribe({next:()=>{this.success.set('Publication queued.');this.reload()},error:r=>this.error.set(r?.error?.detail||'Unable to publish.')})}
 close(p:any){this.api.close(this.guildId,p.id).subscribe({next:()=>this.reload(),error:r=>this.error.set(r?.error?.detail||'Unable to close.')})}
 title(p:any){return p.translations?.[p.primary_language]?.title||'Untitled poll'}
 total(p:any){return (p.options||[]).reduce((n:number,x:any)=>n+(x.votes||0),0)}
}
