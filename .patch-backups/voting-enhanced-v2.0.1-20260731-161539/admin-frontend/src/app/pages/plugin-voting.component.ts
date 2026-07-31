import {GlobalLanguage} from '../core/global-language.service';
import {GuildLanguageService} from '../core/guild-language.service';
import {CommonModule} from '@angular/common';
import {Component,OnInit,inject,signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {DiscordChannelPickerComponent} from '../shared/discord-channel-picker.component';
import {ActivatedRoute} from '@angular/router';
import {ShellComponent} from '../shared/shell.component';
import {VotingService} from '../core/voting.service';

@Component({
 selector:'sn-plugin-voting',standalone:true,
 imports:[CommonModule,FormsModule,ShellComponent,DiscordChannelPickerComponent],
 template:`
 <sn-shell title="Voting">
 <main class="page">
  <header class="hero panel"><div><small>SHIELDNET PLUGIN</small><h2>Multilingual Voting</h2>
  <p>Create, translate, edit and manage Discord polls.</p></div>
  <button class="primary" (click)="newPoll()">＋ New poll</button></header>

  @if(error()){<div class="notice error">{{error()}}</div>}
  @if(success()){<div class="notice success">{{success()}}</div>}

  <section class="panel editor">
   <div class="head">
    <div><small>{{editingId ? 'EDIT POLL' : 'CREATE POLL'}}</small><h3>{{editingId ? 'Edit poll' : 'Create poll'}}</h3></div>
    <div class="language-add">
      <select [(ngModel)]="selectedLanguageCode"><option value="">Select language</option>
      <option *ngFor="let language of availableLanguages()" [value]="language.code">{{language.flag || '🌐'}} {{language.native_name}}</option></select>
      <button (click)="addSelectedLanguage()" [disabled]="!selectedLanguageCode">＋ Add language</button>
    </div>
   </div>

   <div class="grid">
    <label>Primary language<select [(ngModel)]="form.primary_language" (ngModelChange)="setPrimaryLanguage($event)">
      <option *ngFor="let language of directoryLanguages()" [value]="language.code">{{language.flag || '🌐'}} {{language.native_name}}</option></select></label>
    <label>Publish channel<sn-discord-channel-picker [guildId]="guildId" [value]="form.channel_id" (valueChange)="form.channel_id = $event" /></label>
    <label>Choice mode<select [(ngModel)]="form.selection_mode"><option value="single">Single</option><option value="multiple">Multiple</option></select></label>
    <label>Close at<input type="datetime-local" [(ngModel)]="form.closes_at"></label>
   </div>

   <div class="toggles">
    <label><input type="checkbox" [(ngModel)]="form.anonymous"> Anonymous</label>
    <label><input type="checkbox" [(ngModel)]="form.allow_change_vote"> Allow vote change</label>
    <label><input type="checkbox" [(ngModel)]="form.show_live_results"> Live results</label>
   </div>

   <nav class="language-tabs">
     <button *ngFor="let lang of languages;let li=index" [class.active]="activeLanguage===lang.code" (click)="activeLanguage=lang.code">
       {{languageLabel(lang.code)}} <span *ngIf="lang.code!==form.primary_language" (click)="removeLanguage(li);$event.stopPropagation()">×</span>
     </button>
   </nav>

   <section class="language" *ngIf="currentLanguage() as lang">
    <div class="head">
      <h4>{{languageLabel(lang.code)}}</h4>
      <div class="lang-actions">
        <button (click)="copyPrimary(lang.code)" [disabled]="lang.code===form.primary_language">Copy source</button>
        <button class="ai" (click)="translateLanguage(lang.code)" [disabled]="!editingId || lang.code===form.primary_language || translating">
          {{translating ? 'Translating…' : '✨ Translate with AI'}}
        </button>
      </div>
    </div>
    <label>Title<input [(ngModel)]="lang.title"></label>
    <label>Description<textarea [(ngModel)]="lang.description"></textarea></label>
    <div class="option" *ngFor="let option of options;let oi=index">
      <span>{{oi+1}}</span><input [(ngModel)]="option.labels[lang.code]" placeholder="Answer text">
      <button class="danger" (click)="removeOption(oi)" [disabled]="options.length<=2">×</button>
    </div>
   </section>

   <div class="actions">
    <button (click)="addOption()">＋ Option</button>
    <div>
      <button *ngIf="editingId" (click)="newPoll()">Cancel</button>
      <button class="primary" (click)="save()">{{editingId ? 'Save changes' : 'Save draft'}}</button>
    </div>
   </div>
  </section>

  <section class="panel">
   <div class="head"><h3>Polls</h3><span class="count">{{polls().length}}</span></div>
   <article class="poll" *ngFor="let poll of polls()">
    <div class="poll-copy"><small>{{poll.status}}</small><h4>{{title(poll)}}</h4>
      <span>{{poll.options.length}} options · {{total(poll)}} votes · {{languageCount(poll)}} languages</span></div>
    <div class="poll-actions">
      <button (click)="edit(poll)" [disabled]="poll.status==='closed'">Edit</button>
      <button (click)="publish(poll)" [disabled]="poll.status!=='draft'">Publish</button>
      <button (click)="close(poll)" [disabled]="poll.status!=='active'">Close</button>
      <button class="danger" (click)="removePoll(poll)">Delete</button>
    </div>
   </article>
  </section>
 </main></sn-shell>`,
 styles:[`
 .page{display:grid;gap:1rem}.panel,.language,.poll,.notice{border:1px solid var(--line);border-radius:16px;background:var(--surface-1);padding:1rem}
 .hero,.head,.poll,.actions,.poll-actions,.language-add,.lang-actions{display:flex;justify-content:space-between;align-items:center;gap:.75rem}
 h2,h3,h4,p{margin:0}.hero p{color:var(--muted);margin-top:.3rem}small{color:var(--primary);letter-spacing:.12em}
 .editor,.language{display:grid;gap:1rem}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.7rem}
 label{display:grid;gap:.35rem;color:var(--muted);font-size:.72rem}input,textarea,select,button{font:inherit;border:1px solid var(--line);border-radius:9px;background:var(--surface-2);color:var(--text);padding:.7rem}
 textarea{min-height:90px}button{cursor:pointer}.primary,.ai{background:var(--primary);color:#03130e}.danger{color:#ff9aa8;border-color:rgba(255,92,114,.28);background:rgba(255,92,114,.08)}
 .toggles{display:flex;gap:1rem;flex-wrap:wrap}.toggles label{display:flex;align-items:center}.language-tabs{display:flex;gap:.45rem;flex-wrap:wrap}
 .language-tabs button.active{color:var(--primary);border-color:var(--line-strong);background:var(--primary-soft)}.language-tabs span{margin-left:.4rem}
 .option{display:grid;grid-template-columns:34px 1fr 42px;align-items:center;gap:.5rem}.actions>div{display:flex;gap:.5rem}.poll{margin-top:.6rem}.poll-copy{display:grid;gap:.2rem}
 .poll-copy span{color:var(--muted);font-size:.65rem}.count{padding:.25rem .5rem;border-radius:999px;background:var(--primary-soft);color:var(--primary)}.success{color:var(--success)}.error{color:#ff8290}
 @media(max-width:950px){.grid{grid-template-columns:1fr 1fr}.poll,.hero{align-items:flex-start;flex-direction:column}}
 @media(max-width:620px){.grid{grid-template-columns:1fr}.head,.actions{align-items:flex-start;flex-direction:column}.poll-actions{flex-wrap:wrap}}
 `]
})
export class PluginVotingComponent implements OnInit{
 private route=inject(ActivatedRoute);private api=inject(VotingService);private languageApi=inject(GuildLanguageService);
 polls=signal<any[]>([]);error=signal('');success=signal('');directoryLanguages=signal<GlobalLanguage[]>([]);
 selectedLanguageCode='';editingId='';activeLanguage='en';translating=false;
 guildId=this.route.snapshot.paramMap.get('guildId')||'';
 languages:any[]=[];options:any[]=[];form:any={};

 ngOnInit(){this.newPoll();this.reload();this.loadLanguages()}
 reload(){this.api.list(this.guildId).subscribe({next:v=>this.polls.set(v.items||[]),error:r=>this.error.set(r?.error?.detail||'Unable to load polls.')})}
 async loadLanguages(){try{const items=await this.languageApi.available(this.guildId);this.directoryLanguages.set(items);if(!this.languages.length)this.newPoll()}catch(e:any){this.error.set(e?.error?.detail||'Unable to load language directory.')}}
 newPoll(){const code=this.directoryLanguages()[0]?.code||'en';this.editingId='';this.activeLanguage=code;this.languages=[{code,title:'',description:''}];this.options=[{labels:{[code]:''}},{labels:{[code]:''}}];this.form={primary_language:code,fallback_language:code,language_selection_mode:'automatic_with_selector',channel_id:'',selection_mode:'single',anonymous:true,allow_change_vote:true,show_live_results:true,min_choices:1,max_choices:1,allowed_role_ids:[],closes_at:''}}
 availableLanguages(){return this.directoryLanguages().filter(x=>!this.languages.some(y=>y.code===x.code))}
 addSelectedLanguage(){const code=this.selectedLanguageCode;if(!code||this.languages.some(x=>x.code===code))return;this.languages.push({code,title:'',description:''});for(const o of this.options)o.labels[code]='';this.activeLanguage=code;this.selectedLanguageCode=''}
 setPrimaryLanguage(code:string){if(!this.languages.some(x=>x.code===code)){this.languages.unshift({code,title:'',description:''});for(const o of this.options)o.labels[code]=''}this.form.fallback_language=code;this.activeLanguage=code}
 removeLanguage(i:number){const code=this.languages[i].code;if(code===this.form.primary_language)return;this.languages.splice(i,1);for(const o of this.options)delete o.labels[code];if(this.activeLanguage===code)this.activeLanguage=this.form.primary_language}
 addOption(){if(this.options.length>=10)return;const labels:any={};for(const l of this.languages)labels[l.code]='';this.options.push({labels})}
 removeOption(i:number){if(this.options.length>2)this.options.splice(i,1)}
 copyPrimary(code:string){const src=this.languages.find(x=>x.code===this.form.primary_language);const dst=this.languages.find(x=>x.code===code);if(src&&dst){dst.title=src.title;dst.description=src.description}for(const o of this.options)o.labels[code]=o.labels[this.form.primary_language]||''}
 currentLanguage(){return this.languages.find(x=>x.code===this.activeLanguage)||this.languages[0]}
 payload(){const translations:any={};for(const l of this.languages)translations[l.code]={title:l.title,description:l.description};return {...this.form,channel_id:this.form.channel_id?String(this.form.channel_id):null,closes_at:this.form.closes_at||null,translations,options:this.options.map(o=>({emoji:null,translations:o.labels}))}}
 save(){this.error.set('');const req=this.editingId?this.api.update(this.guildId,this.editingId,this.payload()):this.api.create(this.guildId,this.payload());req.subscribe({next:()=>{this.success.set(this.editingId?'Poll updated.':'Poll saved.');this.newPoll();this.reload()},error:r=>this.error.set(r?.error?.detail||'Unable to save poll.')})}
 edit(p:any){this.editingId=p.id;this.form={primary_language:p.primary_language,fallback_language:p.fallback_language,language_selection_mode:p.language_selection_mode,channel_id:p.channel_id||'',selection_mode:p.selection_mode,anonymous:p.anonymous,allow_change_vote:p.allow_change_vote,show_live_results:p.show_live_results,min_choices:p.min_choices,max_choices:p.max_choices,allowed_role_ids:p.allowed_role_ids||[],closes_at:p.closes_at?String(p.closes_at).slice(0,16):''};this.languages=Object.entries(p.translations||{}).map(([code,v]:any)=>({code,title:v.title||'',description:v.description||''}));this.options=(p.options||[]).map((o:any)=>({labels:Object.fromEntries(Object.entries(o.translations||{}).map(([code,v]:any)=>[code,v.label||'']))}));this.activeLanguage=p.primary_language;window.scrollTo({top:0,behavior:'smooth'})}
 translateLanguage(code:string){if(!this.editingId)return;this.translating=true;this.api.generate(this.guildId,this.editingId,code,{source_language:this.form.primary_language,overwrite_existing:true}).subscribe({next:r=>{const lang=this.languages.find(x=>x.code===code);if(lang){lang.title=r.translation?.title||'';lang.description=r.translation?.description||''}for(const item of r.options||[]){const idx=(this.options||[]).findIndex((_:any,i:number)=>i===(r.options||[]).indexOf(item));if(idx>=0)this.options[idx].labels[code]=item.label}this.success.set('AI translation completed.');this.translating=false},error:e=>{this.error.set(e?.error?.detail||'AI translation failed.');this.translating=false}})}
 publish(p:any){this.api.publish(this.guildId,p.id).subscribe({next:()=>{this.success.set('Publication queued.');this.reload()},error:r=>this.error.set(r?.error?.detail||'Unable to publish.')})}
 close(p:any){this.api.close(this.guildId,p.id).subscribe({next:()=>this.reload(),error:r=>this.error.set(r?.error?.detail||'Unable to close.')})}
 removePoll(p:any){if(!confirm(`Delete poll "${this.title(p)}"?`))return;this.api.remove(this.guildId,p.id).subscribe({next:()=>{if(this.editingId===p.id)this.newPoll();this.success.set('Poll deleted.');this.reload()},error:r=>this.error.set(r?.error?.detail||'Unable to delete poll.')})}
 languageLabel(code:string){const language=this.directoryLanguages().find(item=>item.code===code);if(!language)return `🌐 ${code.toUpperCase()}`;const flag=(language.flag||'🌐').trim();const name=(language.name||language.native_name||code.toUpperCase()).trim();const nativeName=(language.native_name||'').trim();return nativeName&&nativeName.toLocaleLowerCase()!==name.toLocaleLowerCase()?`${flag} ${name} — ${nativeName}`:`${flag} ${name}`}
 title(p:any){return p.translations?.[p.primary_language]?.title||'Untitled poll'}
 total(p:any){return (p.options||[]).reduce((n:number,x:any)=>n+(x.votes||0),0)}
 languageCount(p:any){return Object.keys(p.translations||{}).length}
}
