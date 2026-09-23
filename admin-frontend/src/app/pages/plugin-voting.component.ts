import {GlobalLanguage} from '../core/global-language.service';
import {GuildLanguageService} from '../core/guild-language.service';
import {CommonModule} from '@angular/common';
import {Component,HostListener,OnInit,inject,signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {DiscordChannelPickerComponent} from '../shared/discord-channel-picker.component';
import {ActivatedRoute} from '@angular/router';
import {ShellComponent} from '../shared/shell.component';
import {VotingService} from '../core/voting.service';
import {TranslatePipe} from '../core/translate.pipe';
import {TranslationService} from '../core/translation.service';

@Component({
 selector:'sn-plugin-voting',standalone:true,
 imports:[CommonModule,FormsModule,ShellComponent,DiscordChannelPickerComponent,TranslatePipe],
 template:`
 <sn-shell [title]="'voting.title'|snT:'Voting'">
 <main class="page">
  <header class="hero panel"><div><small>{{'voting.eyebrow'|snT:'GUILDCONSOLE PLUGIN'}}</small><h2>{{'voting.heading'|snT:'Multilingual Voting'}}</h2>
  <p>{{'voting.description'|snT:'Create, translate, edit and manage Discord polls.'}}</p></div>
  <button class="primary" (click)="newPoll()">＋ {{'voting.new_poll'|snT:'New poll'}}</button></header>

  @if(error()){<div class="notice error">{{error()}}</div>}
  @if(success()){<div class="notice success">{{success()}}</div>}

  <section class="panel editor">
   <div class="head">
    <div><small>{{editingId ? ('voting.edit_poll_label'|snT:'EDIT POLL') : ('voting.create_poll_label'|snT:'CREATE POLL')}}</small><h3>{{editingId ? ('voting.edit_poll'|snT:'Edit poll') : ('voting.create_poll'|snT:'Create poll')}}</h3></div>
    <div class="language-add">
      <select [(ngModel)]="selectedLanguageCode"><option value="">{{'voting.select_language'|snT:'Select language'}}</option>
      <option *ngFor="let language of availableLanguages()" [value]="language.code">{{language.flag || '🌐'}} {{language.native_name}}</option></select>
      <button (click)="addSelectedLanguage()" [disabled]="!selectedLanguageCode">＋ {{'voting.add_language'|snT:'Add language'}}</button>
    </div>
   </div>

   <div class="grid">
    <label>{{'voting.primary_language'|snT:'Primary language'}}<select [(ngModel)]="form.primary_language" (ngModelChange)="setPrimaryLanguage($event)">
      <option *ngFor="let language of directoryLanguages()" [value]="language.code">{{language.flag || '🌐'}} {{language.native_name}}</option></select></label>
    <label>{{'voting.publish_channel'|snT:'Publish channel'}}<sn-discord-channel-picker [guildId]="guildId" [value]="form.channel_id" [showHint]="false" (valueChange)="form.channel_id = $event" /></label>
    <label>{{'voting.choice_mode'|snT:'Choice mode'}}<select [(ngModel)]="form.selection_mode"><option value="single">{{'voting.single'|snT:'Single'}}</option><option value="multiple">{{'voting.multiple'|snT:'Multiple'}}</option></select></label>
    <label>{{'voting.close_at'|snT:'Close at'}}<input type="datetime-local" [(ngModel)]="form.closes_at"></label>
   </div>

   <div class="toggles">
    <label><input type="checkbox" [(ngModel)]="form.anonymous"> {{'voting.anonymous'|snT:'Anonymous'}}</label>
    <label><input type="checkbox" [(ngModel)]="form.allow_change_vote"> {{'voting.allow_change'|snT:'Allow vote change'}}</label>
    <label><input type="checkbox" [(ngModel)]="form.show_live_results"> {{'voting.live_results'|snT:'Live results'}}</label>
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
        <button (click)="copyPrimary(lang.code)" [disabled]="lang.code===form.primary_language">{{'voting.copy_source'|snT:'Copy source'}}</button>
        <button class="ai" (click)="translateLanguage(lang.code)" [disabled]="lang.code===form.primary_language || translating">
          {{translating ? ('voting.translating'|snT:'Translating…') : ('voting.translate_ai'|snT:'✨ Translate with AI')}}
        </button>
      </div>
    </div>
    <label>{{'voting.poll_title'|snT:'Title'}}<input [(ngModel)]="lang.title"></label>
    <label>{{'voting.poll_description'|snT:'Description'}}<textarea [(ngModel)]="lang.description"></textarea></label>
    <div class="option" *ngFor="let option of options;let oi=index">
      <span>{{oi+1}}</span><input [(ngModel)]="option.labels[lang.code]" [placeholder]="'voting.answer_text'|snT:'Answer text'">
      <button class="danger" (click)="removeOption(oi)" [disabled]="options.length<=2">×</button>
    </div>
   </section>

   <div class="add-option-row"><button (click)="addOption()" [disabled]="options.length>=10">＋ {{'voting.add_option'|snT:'Add option'}}</button></div>
   <section class="result-settings">
    <div><small>{{'voting.result_label'|snT:'RESULT PRESENTATION'}}</small><h4>{{'voting.result_image'|snT:'Final result image'}}</h4></div>
    <div class="grid">
      <label>{{'voting.template'|snT:'Template'}}<select [(ngModel)]="form.result_template_id"><option [ngValue]="null">{{'voting.platform_default'|snT:'Platform default'}}</option><option *ngFor="let template of templates()" [value]="template.id">{{template.name}}</option></select></label>
      <label>{{'voting.result_channel'|snT:'Results channel'}}<sn-discord-channel-picker [guildId]="guildId" [value]="form.result_channel_id" [showHint]="false" (valueChange)="form.result_channel_id=$event" /></label>
      <label><input type="checkbox" [(ngModel)]="form.publish_result_image"> {{'voting.publish_result_image'|snT:'Publish template image after close'}}</label>
    </div>
    <button class="preview-button" type="button" (click)="openPreview()">{{'voting.preview'|snT:'Preview'}}</button>
   </section>
   <div class="actions">
    <div>
      <button *ngIf="editingId" (click)="newPoll()">{{'voting.cancel'|snT:'Cancel'}}</button>
      <button class="primary" (click)="save()">{{editingId ? ('voting.save_changes'|snT:'Save changes') : ('voting.save_draft'|snT:'Save draft')}}</button>
    </div>
   </div>
  </section>

  <section class="panel">
   <div class="head"><h3>{{'voting.polls'|snT:'Polls'}}</h3><span class="count">{{polls().length}}</span></div>
   <article class="poll" *ngFor="let poll of polls()">
    <div class="poll-copy"><small>{{statusLabel(poll.status)}}</small><h4>{{title(poll)}}</h4>
      <span>{{poll.options.length}} {{'voting.options_count'|snT:'options'}} · {{total(poll)}} {{'voting.votes_count'|snT:'votes'}} · {{languageCount(poll)}} {{'voting.languages_count'|snT:'languages'}}</span></div>
    <div class="poll-actions">
      <button (click)="edit(poll)" [disabled]="poll.status==='closed'">{{'voting.edit'|snT:'Edit'}}</button>
      <button (click)="publish(poll)" [disabled]="poll.status!=='draft'">{{'voting.publish'|snT:'Publish'}}</button>
      <button (click)="close(poll)" [disabled]="poll.status!=='active'">{{'voting.close'|snT:'Close'}}</button>
      <button class="danger" (click)="removePoll(poll)">{{'voting.delete'|snT:'Delete'}}</button>
    </div>
   </article>
  </section>
 </main>
 @if(previewOpen()){
  <div class="preview-backdrop" (click)="closePreview()" role="presentation">
   <section class="preview-modal" role="dialog" aria-modal="true" [attr.aria-label]="'voting.preview_aria'|snT:'Voting result preview'" (click)="$event.stopPropagation()">
    <div class="head"><div><small>{{'voting.result_demo'|snT:'RESULT DEMO'}}</small><h3>{{'voting.preview_title'|snT:'Voting preview'}}</h3></div><button type="button" (click)="closePreview()" [attr.aria-label]="'voting.close'|snT:'Close'">✕</button></div>
    <p>{{'voting.preview_help'|snT:'Example using the current title and options. Demo vote counts are illustrative.'}}</p>
    @if(previewLoading()){<div class="preview-state">{{'voting.creating_preview'|snT:'Creating image…'}}</div>}
    @if(previewError()){<div class="notice error">{{previewError()}}</div>}
    @if(previewUrl()){<img class="preview-image" [src]="previewUrl()" [alt]="'voting.preview_alt'|snT:'Voting final result preview'">}
   </section>
  </div>
 }
 </sn-shell>`,
 styles:[`
 .page{display:grid;gap:1rem}.panel,.language,.poll,.notice{border:1px solid var(--line);border-radius:16px;background:var(--surface-1);padding:1rem}
 .hero,.head,.poll,.actions,.poll-actions,.language-add,.lang-actions{display:flex;justify-content:space-between;align-items:center;gap:.75rem}
 h2,h3,h4,p{margin:0}.hero p{color:var(--muted);margin-top:.3rem}small{color:var(--primary);letter-spacing:.12em}
 .editor,.language{display:grid;gap:1rem}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem;align-items:start}
 label{display:grid;grid-template-rows:auto minmax(48px,auto);gap:.4rem;min-width:0;color:var(--muted);font-size:.72rem;font-weight:650}input:not([type=checkbox]),textarea,select,button{box-sizing:border-box;min-height:44px;font:inherit;border:1px solid var(--line);border-radius:9px;background:var(--surface-2);color:var(--text);padding:.72rem .8rem}input:not([type=checkbox]),textarea,select{width:100%;min-height:48px}input:not([type=checkbox]):focus,textarea:focus,select:focus{outline:none;border-color:var(--primary);box-shadow:0 0 0 2px var(--primary-soft)}
 textarea{min-height:96px;resize:vertical}button{cursor:pointer}.primary,.ai{background:var(--primary);color:#03130e}.danger{color:#ff9aa8;border-color:rgba(255,92,114,.28);background:rgba(255,92,114,.08)}
 .toggles{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.7rem}.toggles label,.result-settings .grid label:has(input[type=checkbox]){display:flex;align-items:center;gap:.65rem;min-height:48px;padding:.7rem;border:1px solid var(--line);border-radius:9px;background:var(--surface-2);color:var(--text)}.toggles input,.result-settings input[type=checkbox]{flex:0 0 18px;width:18px;height:18px;margin:0;accent-color:var(--primary)}.language-tabs{display:flex;gap:.45rem;flex-wrap:wrap}
 .language-tabs button.active{color:var(--primary);border-color:var(--line-strong);background:var(--primary-soft)}.language-tabs span{margin-left:.4rem}
 .result-settings{display:grid;gap:1rem;padding:1rem;border:1px solid var(--line);border-radius:12px;background:var(--surface-2)}.result-settings .grid{align-items:end}.option{display:grid;grid-template-columns:34px minmax(0,1fr) 44px;align-items:center;gap:.5rem}.actions>div,.add-option-row{display:flex;gap:.5rem}.actions{justify-content:flex-end}.preview-button{justify-self:start}.poll{margin-top:.6rem}.poll-copy{display:grid;gap:.2rem}
 .preview-backdrop{position:fixed;inset:0;z-index:1000;background:rgba(0,0,0,.78);display:grid;place-items:center;padding:1rem}.preview-modal{width:min(1100px,100%);max-height:92vh;overflow:auto;background:var(--surface-1);border:1px solid var(--line);border-radius:16px;padding:1rem;display:grid;gap:1rem}.preview-modal p{color:var(--muted)}.preview-image{display:block;width:100%;height:auto;border-radius:10px}.preview-state{padding:3rem;text-align:center;color:var(--muted)}
 .poll-copy span{color:var(--muted);font-size:.65rem}.count{padding:.25rem .5rem;border-radius:999px;background:var(--primary-soft);color:var(--primary)}.success{color:var(--success)}.error{color:#ff8290}
 @media(max-width:950px){.poll,.hero{align-items:flex-start;flex-direction:column}}
 @media(max-width:620px){.grid,.toggles{grid-template-columns:1fr}.head,.actions{align-items:stretch;flex-direction:column}.language-add,.lang-actions,.poll-actions{flex-wrap:wrap}.actions>div,.actions button{width:100%}}
 `]
})
export class PluginVotingComponent implements OnInit{
 private route=inject(ActivatedRoute);private api=inject(VotingService);private languageApi=inject(GuildLanguageService);private i18n=inject(TranslationService);
 polls=signal<any[]>([]);templates=signal<any[]>([]);error=signal('');success=signal('');directoryLanguages=signal<GlobalLanguage[]>([]);
 previewOpen=signal(false);previewLoading=signal(false);previewError=signal('');previewUrl=signal('');private previewRequest=0;
 selectedLanguageCode='';editingId='';activeLanguage='en';translating=false;
 guildId=this.route.snapshot.paramMap.get('guildId')||'';
 languages:any[]=[];options:any[]=[];form:any={};

 ngOnInit(){this.newPoll();this.reload();this.loadLanguages();this.api.templates(this.guildId).subscribe({next:r=>this.templates.set(r.items||[]),error:r=>this.error.set(this.apiError(r,'voting.load_templates_error'))})}
 reload(){this.api.list(this.guildId).subscribe({next:v=>this.polls.set(v.items||[]),error:r=>this.error.set(this.apiError(r,'voting.load_polls_error'))})}
 async loadLanguages(){try{const items=await this.languageApi.available(this.guildId);this.directoryLanguages.set(items);if(!this.languages.length)this.newPoll()}catch(e:any){this.error.set(this.apiError(e,'voting.load_languages_error'))}}
 newPoll(){const code=this.directoryLanguages()[0]?.code||'en';this.editingId='';this.activeLanguage=code;this.languages=[{code,title:'',description:''}];this.options=[{labels:{[code]:''}},{labels:{[code]:''}}];this.form={primary_language:code,fallback_language:code,language_selection_mode:'automatic_with_selector',channel_id:'',result_channel_id:null,selection_mode:'single',anonymous:true,allow_change_vote:true,show_live_results:true,min_choices:1,max_choices:1,allowed_role_ids:[],closes_at:'',result_template_id:null,publish_result_image:true,result_settings:{}}}
 availableLanguages(){return this.directoryLanguages().filter(x=>!this.languages.some(y=>y.code===x.code))}
 addSelectedLanguage(){const code=this.selectedLanguageCode;if(!code||this.languages.some(x=>x.code===code))return;this.languages.push({code,title:'',description:''});for(const o of this.options)o.labels[code]='';this.activeLanguage=code;this.selectedLanguageCode=''}
 setPrimaryLanguage(code:string){if(!this.languages.some(x=>x.code===code)){this.languages.unshift({code,title:'',description:''});for(const o of this.options)o.labels[code]=''}this.form.fallback_language=code;this.activeLanguage=code}
 removeLanguage(i:number){const code=this.languages[i].code;if(code===this.form.primary_language)return;this.languages.splice(i,1);for(const o of this.options)delete o.labels[code];if(this.activeLanguage===code)this.activeLanguage=this.form.primary_language}
 addOption(){if(this.options.length>=10)return;const labels:any={};for(const l of this.languages)labels[l.code]='';this.options.push({labels})}
 removeOption(i:number){if(this.options.length>2)this.options.splice(i,1)}
 copyPrimary(code:string){const src=this.languages.find(x=>x.code===this.form.primary_language);const dst=this.languages.find(x=>x.code===code);if(src&&dst){dst.title=src.title;dst.description=src.description}for(const o of this.options)o.labels[code]=o.labels[this.form.primary_language]||''}
 currentLanguage(){return this.languages.find(x=>x.code===this.activeLanguage)||this.languages[0]}
 openPreview(){
  const language=this.currentLanguage()?.code||this.form.primary_language||'en';
  const source=this.languages.find(x=>x.code===language)||this.languages[0];
  const primary=this.languages.find(x=>x.code===this.form.primary_language)||source;
  const title=String(source?.title||primary?.title||this.i18n.t('voting.preview_topic','Voting topic')).trim();
  const options=this.options.map((item,index)=>String(item.labels?.[language]||item.labels?.[this.form.primary_language]||`${this.i18n.t('voting.option','Option')} ${index+1}`).trim());
  const request=++this.previewRequest;
  if(this.previewUrl())URL.revokeObjectURL(this.previewUrl());
  this.previewUrl.set('');this.previewError.set('');this.previewLoading.set(true);this.previewOpen.set(true);
  this.api.previewResult(this.guildId,{result_template_id:this.form.result_template_id||null,language,title,options}).subscribe({
   next:blob=>{if(request!==this.previewRequest)return;if(!blob.type.startsWith('image/')){this.previewError.set(this.i18n.t('voting.preview_error','Unable to create preview.'));this.previewLoading.set(false);return}const reader=new FileReader();reader.onload=()=>{if(request===this.previewRequest)this.previewUrl.set(String(reader.result||''));this.previewLoading.set(false)};reader.onerror=()=>{this.previewError.set(this.i18n.t('voting.preview_error','Unable to create preview.'));this.previewLoading.set(false)};reader.readAsDataURL(blob)},
   error:r=>{if(request!==this.previewRequest)return;this.previewError.set(r?.status===404?this.i18n.t('voting.template_missing','No active template was found. Select or configure a voting template.'):this.i18n.t('voting.preview_error','Unable to create preview.'));this.previewLoading.set(false)}
  });
 }
 closePreview(){this.previewRequest++;this.previewOpen.set(false);this.previewLoading.set(false);this.previewUrl.set('')}
 @HostListener('document:keydown.escape') onEscape(){if(this.previewOpen())this.closePreview()}
 payload(){const translations:any={};for(const l of this.languages)translations[l.code]={title:l.title,description:l.description};const resultChannel=this.form.result_channel_id?String(this.form.result_channel_id):null;return {...this.form,channel_id:this.form.channel_id?String(this.form.channel_id):null,closes_at:this.form.closes_at||null,result_settings:{...(this.form.result_settings||{}),result_channel_id:resultChannel},translations,options:this.options.map(o=>({emoji:null,translations:o.labels}))}}
 save(){this.error.set('');const req=this.editingId?this.api.update(this.guildId,this.editingId,this.payload()):this.api.create(this.guildId,this.payload());req.subscribe({next:()=>{this.success.set(this.i18n.t(this.editingId?'voting.updated':'voting.saved',this.editingId?'Poll updated.':'Poll saved.'));this.newPoll();this.reload()},error:r=>this.error.set(this.apiError(r,'voting.save_error'))})}
 edit(p:any){this.editingId=p.id;this.form={primary_language:p.primary_language,fallback_language:p.fallback_language,language_selection_mode:p.language_selection_mode,channel_id:p.channel_id||'',result_channel_id:p.result_settings?.result_channel_id||null,selection_mode:p.selection_mode,anonymous:p.anonymous,allow_change_vote:p.allow_change_vote,show_live_results:p.show_live_results,min_choices:p.min_choices,max_choices:p.max_choices,allowed_role_ids:p.allowed_role_ids||[],closes_at:p.closes_at?String(p.closes_at).slice(0,16):'',result_template_id:p.result_template_id||null,publish_result_image:p.publish_result_image,result_settings:p.result_settings||{}};this.languages=Object.entries(p.translations||{}).map(([code,v]:any)=>({code,title:v.title||'',description:v.description||''}));this.options=(p.options||[]).map((o:any)=>({labels:Object.fromEntries(Object.entries(o.translations||{}).map(([code,v]:any)=>[code,v.label||'']))}));this.activeLanguage=p.primary_language;window.scrollTo({top:0,behavior:'smooth'})}
 translateLanguage(code:string){
  const source=this.languages.find(x=>x.code===this.form.primary_language);
  const target=this.languages.find(x=>x.code===code);
  if(!source||!target||code===this.form.primary_language)return;
  if(!String(source.title||'').trim()){this.error.set(this.i18n.t('voting.primary_title_required','Fill in the title in the primary language first.'));this.activeLanguage=this.form.primary_language;return}
  this.error.set('');this.translating=true;
  const apply=(r:any)=>{
    target.title=r.translation?.title||'';
    target.description=r.translation?.description||'';
    for(const item of r.options||[]){
      const index=Number(item.position);
      if(Number.isInteger(index)&&this.options[index])this.options[index].labels[code]=item.label||'';
    }
    this.success.set(this.i18n.t('voting.translation_complete','AI translation completed.'));this.translating=false;
  };
  const fail=(e:any)=>{this.error.set(this.apiError(e,'voting.translation_error'));this.translating=false};
  if(this.editingId){
    this.api.generate(this.guildId,this.editingId,code,{source_language:this.form.primary_language,overwrite_existing:true})
      .subscribe({next:apply,error:fail});
  }else{
    this.api.previewTranslation(this.guildId,{
      source_language:this.form.primary_language,
      target_language:code,
      title:source.title,
      description:source.description||null,
      options:this.options.map((o:any)=>o.labels[this.form.primary_language]||'')
    }).subscribe({next:apply,error:fail});
  }
 }
 publish(p:any){this.api.publish(this.guildId,p.id).subscribe({next:()=>{this.success.set(this.i18n.t('voting.publish_queued','Publication queued.'));this.reload()},error:r=>this.error.set(this.apiError(r,'voting.publish_error'))})}
 close(p:any){if(!confirm(this.i18n.t('voting.close_confirm','Close this poll now and publish the final results?')))return;this.api.close(this.guildId,p.id).subscribe({next:()=>{this.success.set(this.i18n.t('voting.close_queued','Poll closed. Final results are being published.'));this.reload()},error:r=>this.error.set(this.apiError(r,'voting.close_error'))})}
 removePoll(p:any){if(!confirm(this.i18n.t('voting.delete_confirm','Delete poll “{title}”?').replace('{title}',this.title(p))))return;this.api.remove(this.guildId,p.id).subscribe({next:()=>{if(this.editingId===p.id)this.newPoll();this.success.set(this.i18n.t('voting.deleted','Poll deleted.'));this.reload()},error:r=>this.error.set(this.apiError(r,'voting.delete_error'))})}
 languageLabel(code:string){const language=this.directoryLanguages().find(item=>item.code===code);if(!language)return `🌐 ${code.toUpperCase()}`;const flag=(language.flag||'🌐').trim();const name=(language.name||language.native_name||code.toUpperCase()).trim();const nativeName=(language.native_name||'').trim();return nativeName&&nativeName.toLocaleLowerCase()!==name.toLocaleLowerCase()?`${flag} ${name} — ${nativeName}`:`${flag} ${name}`}
 title(p:any){return p.translations?.[p.primary_language]?.title||this.i18n.t('voting.untitled','Untitled poll')}
 statusLabel(status:string){return this.i18n.t(`voting.status_${status}`,status)}
 total(p:any){return (p.options||[]).reduce((n:number,x:any)=>n+(x.votes||0),0)}
 languageCount(p:any){return Object.keys(p.translations||{}).length}
 private apiError(error:any,fallbackKey:string){
  const detail=typeof error?.error?.detail==='string'?error.error.detail:'';
  const exact:Record<string,string>={
   'Poll not found.':'error_poll_not_found','A poll must contain 2-10 options.':'error_options_range','Primary language translation is required.':'error_primary_translation','Select an active voting result template.':'error_active_template','Selected voting template is unavailable.':'error_template_unavailable','No active voting result template is available.':'template_missing','Closed polls cannot be edited.':'error_closed_edit','Select a Discord channel.':'error_select_channel','Source title is required.':'error_source_title','Source translation not found.':'error_source_translation','Translation already exists.':'error_translation_exists'
  };
  if(exact[detail])return this.i18n.t(`voting.${exact[detail]}`,detail);
  let match=detail.match(/^Title is required for (.+)\.$/);if(match)return this.i18n.t('voting.error_title_language',detail).replace('{language}',match[1]);
  match=detail.match(/^Option (\d+) is empty for (.+)\.$/);if(match)return this.i18n.t('voting.error_option_language',detail).replace('{number}',match[1]).replace('{language}',match[2]);
  match=detail.match(/^Source option (\d+) is missing\.$/);if(match)return this.i18n.t('voting.error_source_option',detail).replace('{number}',match[1]);
  return detail||this.i18n.t(fallbackKey);
 }
}
