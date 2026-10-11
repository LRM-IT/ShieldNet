import { CommonModule } from '@angular/common';
import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ShellComponent } from '../shared/shell.component';
import { DiscordChannelPickerComponent } from '../shared/discord-channel-picker.component';
import { GuildPluginService } from '../core/guild-plugin.service';
import { GuildLanguageService, GuildWorkspaceLanguage } from '../core/guild-language.service';
import { TranslationService } from '../core/translation.service';

interface SurveyText { title: string; description: string; button: string; label: string; placeholder: string; thanks: string; }
@Component({
  standalone: true,
  imports: [CommonModule, FormsModule, ShellComponent, DiscordChannelPickerComponent],
  template: `<sn-shell [title]="t('name')"><main class="page">
    <header><h2>💡 {{t('name')}}</h2><p>{{t('intro')}}</p></header>
    @if(error){<div class="card error" role="alert">{{error}}</div>}
    @if(success){<div class="card success" role="status">{{success}}</div>}
    <section class="card actions">
      <strong>{{t(!installed ? 'not_installed' : enabled ? 'enabled' : 'disabled')}}</strong>
      <button [disabled]="busy" (click)="changeState()">{{t(!installed ? 'install' : enabled ? 'disable' : 'enable')}}</button>
    </section>
    @if(installed){
      <nav class="actions"><button [class.active]="tab==='settings'" (click)="tab='settings'">{{t('settings')}}</button><button [class.active]="tab==='responses'" (click)="showResponses()">{{t('responses')}}</button></nav>
      @if(tab==='settings'){
        <section class="card editor">
          <div class="actions"><h3>{{t(editingId ? 'edit' : 'new')}}</h3><button class="secondary" [disabled]="busy" (click)="newSurvey()">＋ {{t('new')}}</button></div>
          <div class="grid">
            <label>{{t('channel')}}<sn-discord-channel-picker [guildId]="guildId" [value]="form.channel_id" [showHint]="false" (valueChange)="form.channel_id=$event || ''"/><small>{{t('channel_help')}}</small></label>
            <label>{{t('primary')}}<select [(ngModel)]="form.primary_language"><option *ngFor="let code of codes" [value]="code">{{languageName(code)}}</option></select></label>
          </div>
          <div class="actions"><select [(ngModel)]="addCode" [attr.aria-label]="t('language')"><option value="">{{t('language')}}</option><option *ngFor="let lang of availableLanguages()" [value]="lang.code" translate="no">{{lang.flag}} {{lang.name}} ({{lang.code}})</option></select><button [disabled]="!addCode || codes.length>=25" (click)="addLanguage()">＋ {{t('add')}}</button></div>
          <nav class="actions"><button *ngFor="let code of codes" [class.active]="activeCode===code" (click)="activeCode=code">{{languageName(code)}}</button></nav>
          @if(form.translations[activeCode]; as text){
            <div class="actions"><h3>{{languageName(activeCode)}}</h3><button class="secondary" [disabled]="busy || activeCode===form.primary_language" (click)="translate()">✨ {{t('translate')}}</button><button class="secondary" [disabled]="busy || activeCode===form.primary_language" (click)="removeLanguage()">{{t('remove')}}</button></div>
            <p>{{t('ai_help')}}</p>
            <label>{{t('title')}}<input maxlength="256" [(ngModel)]="text.title"></label>
            <label>{{t('description')}}<textarea rows="5" maxlength="4000" [(ngModel)]="text.description"></textarea></label>
            <div class="grid"><label>{{t('button')}}<input maxlength="80" [(ngModel)]="text.button"></label><label>{{t('label')}}<input maxlength="45" [(ngModel)]="text.label"></label></div>
            <label>{{t('placeholder')}}<input maxlength="100" [(ngModel)]="text.placeholder"></label>
            <label>{{t('thanks')}}<textarea rows="2" maxlength="1000" [(ngModel)]="text.thanks"></textarea></label>
            <div class="preview"><small>{{t('preview')}}</small><h3>💡 {{text.title}}</h3><p class="preserve">{{text.description}}</p><span class="preview-button">💡 {{text.button}}</span></div>
          }
          <p>{{t('privacy')}}</p>
          <div class="actions"><button [disabled]="busy" (click)="save(false)">{{t('save')}}</button><button [disabled]="busy || !enabled" (click)="save(true)">{{t('publish')}}</button></div>
        </section>
        <section class="card"><div class="actions"><h3>{{t('surveys')}}</h3><button class="secondary" [disabled]="busy" (click)="refresh()">{{t('refresh')}}</button></div>
          @for(survey of surveys; track survey.id){<article class="survey">
            <div><strong>{{survey.translations[survey.primary_language].title}}</strong><p>{{t(survey.job_status==='failed'?'status_failed':survey.job_status)}} · {{survey.response_count}} {{t('responses')}}</p>@if(survey.error){<p class="error">{{apiError(survey.error, 0, true)}}</p>}</div>
            <div class="actions"><button class="secondary" [disabled]="busy" (click)="edit(survey)">{{t('edit')}}</button><button class="secondary" (click)="showResponses(survey.id)">{{t('responses')}}</button><button class="secondary" [disabled]="busy || !survey.active" (click)="close(survey)">{{t('close')}}</button>@if(survey.message_id){<a [href]="'https://discord.com/channels/'+guildId+'/'+survey.channel_id+'/'+survey.message_id" target="_blank" rel="noopener">Discord ↗</a>}</div>
          </article>} @empty {<p>{{t('empty')}}</p>}
        </section>
      } @else {
        <section class="card editor"><div class="actions"><h3>{{t('responses')}} ({{responseTotal}})</h3><button class="secondary" [disabled]="busy" (click)="loadResponses()">{{t('refresh')}}</button></div>
          <label>{{t('survey')}}<select [(ngModel)]="responseSurvey" (ngModelChange)="offset=0;loadResponses()"><option value="">{{t('select')}}</option><option *ngFor="let survey of surveys" [value]="survey.id">{{survey.translations[survey.primary_language].title}}</option></select></label>
          <p>{{t('privacy')}}</p>
          @for(answer of answers; track answer.user_id){<article class="survey"><div><strong>{{answer.display_name}}</strong><small> · {{answer.user_id}} · {{answer.language}} · {{answer.updated_at | date:'medium'}}</small><p class="preserve">{{answer.text}}</p></div></article>} @empty {<p>{{t('no_answers')}}</p>}
          <div class="actions"><button class="secondary" [disabled]="busy || offset===0" (click)="offset=offset-50;loadResponses()">← {{t('previous')}}</button><button class="secondary" [disabled]="busy || offset+50>=responseTotal" (click)="offset=offset+50;loadResponses()">{{t('next')}} →</button></div>
        </section>
      }
    }
  </main></sn-shell>`,
  styles: [`
    .page{max-width:1120px;margin:auto;display:grid;gap:1rem;padding-bottom:3rem}.card{padding:1.3rem;border:1px solid var(--line);border-radius:16px;background:var(--panel)}.editor{display:grid;gap:1rem}h2,h3,p{margin:.3rem 0}p,small{color:var(--muted)}.actions{display:flex;gap:.65rem;flex-wrap:wrap;align-items:center}.actions>h3,.actions>strong{margin-inline-end:auto}.grid{align-items:start;display:grid;grid-template-columns:1fr 1fr;gap:1rem}label{align-content:start;display:grid;gap:.45rem;font-weight:600;min-width:0}input,select,textarea{box-sizing:border-box;width:100%;padding:.8rem;border:1px solid var(--line);border-radius:9px;background:var(--panel-2);color:var(--text);font:inherit;min-height:46px}textarea{resize:vertical}.grid select,.grid input{height:50px;min-height:50px}.grid sn-discord-channel-picker{min-height:50px}.error{white-space:pre-line}.actions select{width:auto;max-width:100%}button,.preview-button{padding:.75rem 1rem;border:1px solid var(--line);border-radius:9px;background:var(--primary);color:#061919;font-weight:700;cursor:pointer;min-height:44px}button.secondary,nav button{background:var(--panel-2);color:var(--text)}nav button.active{border-color:var(--primary);color:var(--primary)}button:disabled{opacity:.45;cursor:not-allowed}.preview{border-inline-start:4px solid var(--primary);padding:1rem;background:var(--panel-2);border-radius:8px}.preview-button{display:inline-block;margin-top:.8rem}.preserve{white-space:pre-wrap;overflow-wrap:anywhere}.survey{padding:1rem 0;border-top:1px solid var(--line);display:grid;gap:.8rem;margin-top:1rem}.error{color:#ff939f}.success{color:#70e7bd}a{color:var(--primary)}@media(max-width:650px){.grid{grid-template-columns:1fr}.card{padding:1rem}.actions select{width:100%}small{overflow-wrap:anywhere}}
  `],
})
export class PluginIdeaCollectionComponent implements OnInit, OnDestroy {
  private http=inject(HttpClient); private route=inject(ActivatedRoute); private plugins=inject(GuildPluginService);
  private languages=inject(GuildLanguageService); private i18n=inject(TranslationService);
  guildId=this.route.snapshot.paramMap.get('guildId') || ''; installed=false; enabled=false; busy=false; error=''; success='';
  tab='settings'; surveys:any[]=[]; directory:GuildWorkspaceLanguage[]=[]; editingId=''; activeCode=this.i18n.locale(); addCode='';
  responseSurvey=''; answers:any[]=[]; responseTotal=0; offset=0; timer?:ReturnType<typeof setInterval>;
  form:{channel_id:string;primary_language:string;translations:Record<string,SurveyText>}={channel_id:'',primary_language:this.activeCode,translations:{[this.activeCode]:this.defaults()}};
  get url(){return `/api/v1/discord/guilds/${this.guildId}/plugins/idea-collection`;}
  get codes(){return Object.keys(this.form.translations);}
  t(key:string){return this.i18n.t('idea_collection.'+key,key);}
  defaults():SurveyText{return Object.fromEntries(['title','description','button','label','placeholder','thanks'].map(key=>[key,this.t('defaults.'+key)])) as unknown as SurveyText;}
  apiError(detail:unknown,status=0,publication=false):string{
    const errors:Record<string,string>={
      'Install and enable Idea Collection first':'install','Enable Idea Collection before publishing':'install',
      'Survey not found':'missing','Select a text channel or an existing thread, not a forum category':'channel',
      'Select a text channel or an existing forum thread':'channel','Wait for publication to finish':'wait',
      'Create a new survey to change the published channel':'move',
      'Translation failed. Check the AI Center translation route and text length.':'translation',
      'This survey is closed or unavailable':'closed','Unsupported survey language':'language',
      'An active subscription is required to enable this plugin':'subscription'};
    if(typeof detail==='string' && errors[detail])return this.t('errors.'+errors[detail]);
    if(publication)return this.t('errors.publication');
    if(Array.isArray(detail))return detail.map(item=>{
      const loc=item.loc||[];const field=loc[loc.length-1];const index=loc.indexOf('translations');
      const code=index>=0?loc[index+1]:this.form.primary_language;
      const label=['title','description','button','label','placeholder','thanks'].includes(field)?this.t(field):field==='channel_id'?this.t('channel'):this.t('survey');
      const reason=item.ctx?.max_length?this.t('errors.too_long').replace('{max}',String(item.ctx.max_length)):this.t('errors.required');
      return `${this.languageName(code)} — ${label}: ${reason}`;
    }).join('\n');
    if(status===422)return this.t('errors.validation');
    if(status===401||status===403)return this.t('errors.permission');
    if(status===402)return this.t('errors.subscription');
    return this.t(status===0?'errors.network':'failed');
  }
  async ngOnInit(){await this.run(async()=>{this.directory=await this.languages.available(this.guildId);await this.load();});this.timer=setInterval(()=>{if(!this.busy&&this.surveys.some(s=>['pending','processing'].includes(s.job_status)))void this.refresh();},5000);}
  ngOnDestroy(){if(this.timer)clearInterval(this.timer);}
  async run(action:()=>Promise<void>){if(this.busy)return;this.busy=true;this.error='';this.success='';try{await action();}catch(e:any){this.error=this.apiError(e?.error?.detail,e?.status);}finally{this.busy=false;}}
  async load(){const r=await firstValueFrom(this.http.get<any>(this.url));this.installed=r.installed;this.enabled=r.enabled;this.surveys=r.items;}
  async refresh(){await this.run(()=>this.load());}
  async changeState(){await this.run(async()=>{if(!this.installed)await this.plugins.install(this.guildId,'idea_collection');else if(this.enabled)await this.plugins.disable(this.guildId,'idea_collection');else await this.plugins.enable(this.guildId,'idea_collection');await this.load();});}
  languageName(code:string){const l=this.directory.find(x=>x.code===code);return l?`${l.flag || '🌐'} ${l.name} (${code})`:code.toUpperCase();}
  availableLanguages(){return this.directory.filter(l=>!this.codes.includes(l.code));}
  async addLanguage(){if(!this.addCode)return;await this.run(async()=>{const code=this.addCode;const locale=['en','ru','uk','de','fr','it','pl','ar'].includes(code)?code:'en';const dictionary=await firstValueFrom(this.http.get<any>(`/locales/${locale}.json?v=16.76`));this.form.translations[code]={...dictionary.idea_collection.defaults,title:'',description:''};this.activeCode=code;this.addCode='';});}
  removeLanguage(){delete this.form.translations[this.activeCode];this.activeCode=this.form.primary_language;}
  newSurvey(){this.editingId='';this.activeCode=this.i18n.locale();this.form={channel_id:'',primary_language:this.activeCode,translations:{[this.activeCode]:this.defaults()}};this.error='';this.success='';}
  edit(s:any){this.editingId=s.id;this.form=structuredClone({channel_id:s.channel_id,primary_language:s.primary_language,translations:s.translations});this.activeCode=s.primary_language;this.tab='settings';}
  async translate(){await this.run(async()=>{const code=this.activeCode;const result=await firstValueFrom(this.http.post<SurveyText & {warnings?:any[]}>(this.url+'/translate',{source_language:this.form.primary_language,target_language:code,text:this.form.translations[this.form.primary_language]}));const {warnings,...text}=result;this.form.translations[code]=text;if(warnings?.length){this.error=this.apiError(warnings);this.success=this.t('translation_review');}else this.success=this.t('translated');});}
  async save(publish:boolean){await this.run(async()=>{const result=await firstValueFrom(this.editingId?this.http.put<any>(this.url+'/'+this.editingId,this.form):this.http.post<any>(this.url,this.form));this.editingId=result.id;if(publish)await firstValueFrom(this.http.post(this.url+'/'+result.id+'/publish',{}));await this.load();this.success=this.t(publish?'queued':'saved');});}
  async close(s:any){await this.run(async()=>{await firstValueFrom(this.http.post(this.url+'/'+s.id+'/close',{}));await this.load();this.success=this.t('queued');});}
  async showResponses(id?:string){this.tab='responses';this.responseSurvey=id||this.responseSurvey||this.surveys[0]?.id||'';this.offset=0;await this.loadResponses();}
  async loadResponses(){await this.run(async()=>{this.answers=[];this.responseTotal=0;if(!this.responseSurvey)return;const r=await firstValueFrom(this.http.get<any>(this.url+'/'+this.responseSurvey+'/responses?offset='+this.offset));this.answers=r.items;this.responseTotal=r.total;});}
}
