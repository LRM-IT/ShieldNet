import {Component,OnInit,signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {SeoService,SeoSettings} from '../core/seo.service';
import {ShellComponent} from '../shared/shell.component';
import {TranslationService} from '../core/translation.service';

@Component({standalone:true,imports:[FormsModule,ShellComponent],template:`
<sn-shell title="SEO"><main class="page">
  <header class="page-head"><div><span>SUPERADMIN</span><h2>SEO и аналитика</h2><p>Метаданные главной страницы и подключение систем аналитики.</p></div><label class="locale">Язык SEO<select [ngModel]="locale()" (ngModelChange)="load($event)">@for(language of i18n.languages();track language.code){<option [value]="language.code">{{language.icon}} {{language.name}}</option>}</select></label></header>
  @if(settings();as s){
    <section class="card"><h3>SEO главной страницы · {{locale().toUpperCase()}}</h3><div class="grid">
      <label>Название сайта<input [(ngModel)]="s.site_name"></label><label>Canonical URL<input type="url" [(ngModel)]="s.canonical_url"></label>
      <label class="wide">Title<input [(ngModel)]="s.title" maxlength="200"><small>{{s.title.length}} / 200</small></label>
      <label class="wide">Description<textarea rows="3" [(ngModel)]="s.description" maxlength="500"></textarea><small>{{s.description.length}} / 500</small></label>
      <label class="wide">Keywords<textarea rows="3" [(ngModel)]="s.keywords" maxlength="1000"></textarea></label>
      <label>Robots<select [(ngModel)]="s.robots"><option value="index,follow">index, follow</option><option value="index,nofollow">index, nofollow</option><option value="noindex,follow">noindex, follow</option><option value="noindex,nofollow">noindex, nofollow</option></select></label>
      <label>Open Graph image URL<input type="url" [(ngModel)]="s.og_image" placeholder="https://..."></label>
      <label class="wide">Open Graph title<input [(ngModel)]="s.og_title" maxlength="200"></label>
      <label class="wide">Open Graph description<textarea rows="3" [(ngModel)]="s.og_description" maxlength="500"></textarea></label>
    </div><div class="preview"><small>SEARCH PREVIEW</small><h3>{{s.title}}</h3><a>{{s.canonical_url}}</a><p>{{s.description}}</p></div></section>
    <section class="card"><div class="section-head"><div><h3>Аналитика</h3><p>Укажите идентификаторы счётчиков. Они запускаются только после согласия посетителя на cookie.</p></div><label class="toggle"><input type="checkbox" [(ngModel)]="s.analytics_enabled"><span>Включено</span></label></div>
      <div class="grid">
        <label>Google Analytics ID<input [(ngModel)]="s.google_analytics_id" placeholder="G-XXXXXXXXXX"></label>
        <label>Google Tag Manager ID<input [(ngModel)]="s.google_tag_manager_id" placeholder="GTM-XXXXXXX"></label>
        <label>Meta Pixel ID<input [(ngModel)]="s.meta_pixel_id" placeholder="1234567890"></label>
        <label>Яндекс Метрика ID<input [(ngModel)]="s.yandex_metrika_id" placeholder="12345678"></label>
        <label>Microsoft Clarity Project ID<input [(ngModel)]="s.clarity_project_id" placeholder="abcdefghij"></label>
      </div>
    </section>
    <footer>@if(message()){<span>{{message()}}</span>}<button (click)="save()" [disabled]="saving()">{{saving()?'Сохранение…':'Сохранить настройки'}}</button></footer>
  }
</main></sn-shell>`,styles:[`.page{max-width:1050px;margin:auto;display:grid;gap:1rem}.page-head{display:flex;align-items:flex-end;justify-content:space-between;gap:1rem}.locale{min-width:220px}.page>header span{color:var(--primary);font-size:.65rem;font-weight:900;letter-spacing:.14em}h2,h3,p{margin:.35rem 0}.page>header p,label small,.section-head p{color:var(--muted)}.card{padding:1.2rem;border:1px solid var(--line);border-radius:15px;background:var(--panel)}.card>h3,.section-head{margin-bottom:1rem}.section-head{display:flex;justify-content:space-between;align-items:center;gap:1rem}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:1rem}.wide{grid-column:1/-1}label{display:grid;gap:.4rem;color:var(--muted);font-size:.72rem}input,textarea,select{padding:.75rem;border:1px solid var(--line);border-radius:9px;background:var(--panel-2);color:var(--text);font:inherit}.code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.75rem;tab-size:2}.toggle{display:flex;grid-auto-flow:column;align-items:center;white-space:nowrap}.toggle input{width:1rem;height:1rem}.preview{margin-top:1rem;padding:1rem;border:1px solid var(--line);border-radius:12px;background:#fff;color:#202124}.preview small{color:#5f6368}.preview h3{color:#1a0dab;font:20px Arial}.preview a{color:#188038;font:14px Arial}.preview p{color:#4d5156;font:14px/1.5 Arial}footer{display:flex;align-items:center;justify-content:flex-end;gap:1rem}footer span{margin-right:auto;color:var(--success)}button{padding:.75rem 1rem;border:0;border-radius:9px;background:var(--primary);color:#04130f;font-weight:900}@media(max-width:700px){.page-head{display:grid}.locale{min-width:0}.grid{grid-template-columns:1fr}.wide{grid-column:auto}.section-head{align-items:flex-start}}`]})
export class SeoComponent implements OnInit{
  settings=signal<SeoSettings|null>(null);saving=signal(false);message=signal('');locale=signal('en');
  constructor(private api:SeoService,public i18n:TranslationService){}
  async ngOnInit(){await this.load(this.i18n.locale())}
  async load(locale:string){this.locale.set(locale);this.settings.set(await this.api.get(locale));this.message.set('')}
  async save(){const value=this.settings();if(!value)return;this.saving.set(true);this.message.set('');try{const saved=await this.api.save(value,this.locale());this.settings.set(saved);if(this.locale()===this.i18n.locale())this.api.applyValues(saved);this.message.set('Настройки сохранены.')}catch(e:any){this.message.set(e?.error?.detail||'Не удалось сохранить настройки.')}finally{this.saving.set(false)}}
}
