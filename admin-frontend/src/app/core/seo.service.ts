import {HttpClient} from '@angular/common/http';
import {Injectable} from '@angular/core';
import {Meta,Title} from '@angular/platform-browser';
import {firstValueFrom} from 'rxjs';

export interface SeoSettings {
  locale?:string;
  site_name:string; title:string; description:string; keywords:string; canonical_url:string;
  og_title:string; og_description:string; og_image:string; robots:string;
  analytics_enabled:boolean; google_analytics_id:string; google_tag_manager_id:string;
  meta_pixel_id:string; yandex_metrika_id:string; clarity_project_id:string;
}

@Injectable({providedIn:'root'})
export class SeoService {
  private current:SeoSettings|null=null;
  constructor(private http:HttpClient,private title:Title,private meta:Meta){
    window.addEventListener('guildconsole-cookie-consent',()=>this.applyTracking());
    window.addEventListener('guildconsole-locale-changed',(event)=>void this.apply((event as CustomEvent<string>).detail||'en'));
  }
  get(locale='en'){return firstValueFrom(this.http.get<SeoSettings>('/api/v1/public/seo',{params:{locale}}))}
  save(v:SeoSettings,locale='en'){return firstValueFrom(this.http.put<SeoSettings>('/api/v1/platform/seo',v,{params:{locale}}))}
  async apply(locale='en'){try{this.applyValues(await this.get(locale))}catch{}}
  applyValues(v:SeoSettings){
    this.current=v;
    this.title.setTitle(v.title);
    this.meta.updateTag({name:'description',content:v.description});
    this.meta.updateTag({name:'keywords',content:v.keywords});
    this.meta.updateTag({name:'robots',content:v.robots});
    this.meta.updateTag({property:'og:type',content:'website'});
    this.meta.updateTag({property:'og:site_name',content:v.site_name});
    this.meta.updateTag({property:'og:title',content:v.og_title||v.title});
    this.meta.updateTag({property:'og:description',content:v.og_description||v.description});
    this.meta.updateTag({property:'og:url',content:v.canonical_url});
    this.meta.updateTag({name:'twitter:card',content:'summary_large_image'});
    if(v.og_image){this.meta.updateTag({property:'og:image',content:v.og_image});this.meta.updateTag({name:'twitter:image',content:v.og_image})}
    let link=document.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if(!link){link=document.createElement('link');link.rel='canonical';document.head.appendChild(link)}
    link.href=v.canonical_url;
    this.applyTracking();
  }
  private applyTracking(){
    if(!this.current?.analytics_enabled||localStorage.getItem('guildconsole_cookie_consent')!=='accepted')return;
    document.querySelectorAll('[data-seo-injection]').forEach(node=>node.remove());
    const v=this.current;
    if(v.google_tag_manager_id){const id=this.escape(v.google_tag_manager_id);this.inject(document.head,`<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f)})(window,document,'script','dataLayer','${id}');</script>`);this.inject(document.body,`<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=${id}" height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>`)}
    if(v.google_analytics_id){const id=this.escape(v.google_analytics_id);this.inject(document.head,`<script async src="https://www.googletagmanager.com/gtag/js?id=${id}"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}gtag('js',new Date());gtag('config','${id}');</script>`)}
    if(v.meta_pixel_id)this.inject(document.head,`<script>!function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');fbq('init','${this.escape(v.meta_pixel_id)}');fbq('track','PageView');</script>`);
    if(v.yandex_metrika_id){const id=this.escape(v.yandex_metrika_id);this.inject(document.head,`<script>(function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};m[i].l=1*new Date();k=e.createElement(t);a=e.getElementsByTagName(t)[0];k.async=1;k.src=r;a.parentNode.insertBefore(k,a)})(window,document,'script','https://mc.yandex.ru/metrika/tag.js','ym');ym('${id}','init',{clickmap:true,trackLinks:true,accurateTrackBounce:true,webvisor:true});</script>`)}
    if(v.clarity_project_id){const id=this.escape(v.clarity_project_id);this.inject(document.head,`<script>(function(c,l,a,r,i,t,y){c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};t=l.createElement(r);t.async=1;t.src='https://www.clarity.ms/tag/'+i;y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y)})(window,document,'clarity','script','${id}');</script>`)}
  }
  private escape(value:string){return value.replace(/[^A-Za-z0-9_-]/g,'')}
  private inject(target:HTMLElement,html:string){
    if(!html.trim())return;
    const template=document.createElement('template');template.innerHTML=html;
    for(const source of Array.from(template.content.childNodes)){
      let node:Node=source;
      if(source instanceof HTMLScriptElement){const script=document.createElement('script');for(const attr of Array.from(source.attributes))script.setAttribute(attr.name,attr.value);script.text=source.text;node=script}
      if(node instanceof HTMLElement)node.dataset['seoInjection']='true';
      target.appendChild(node);
    }
  }
}
