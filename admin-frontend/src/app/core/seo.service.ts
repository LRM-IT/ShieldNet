import {HttpClient} from '@angular/common/http';
import {Injectable} from '@angular/core';
import {Meta,Title} from '@angular/platform-browser';
import {firstValueFrom} from 'rxjs';
export interface SeoSettings{site_name:string;title:string;description:string;keywords:string;canonical_url:string;og_title:string;og_description:string;og_image:string;robots:string}
@Injectable({providedIn:'root'}) export class SeoService{
 constructor(private http:HttpClient,private title:Title,private meta:Meta){}
 get(){return firstValueFrom(this.http.get<SeoSettings>('/api/v1/public/seo'))}save(v:SeoSettings){return firstValueFrom(this.http.put<SeoSettings>('/api/v1/platform/seo',v))}
 async apply(){try{this.applyValues(await this.get())}catch{}}
 applyValues(v:SeoSettings){this.title.setTitle(v.title);this.meta.updateTag({name:'description',content:v.description});this.meta.updateTag({name:'keywords',content:v.keywords});this.meta.updateTag({name:'robots',content:v.robots});this.meta.updateTag({property:'og:type',content:'website'});this.meta.updateTag({property:'og:site_name',content:v.site_name});this.meta.updateTag({property:'og:title',content:v.og_title||v.title});this.meta.updateTag({property:'og:description',content:v.og_description||v.description});this.meta.updateTag({property:'og:url',content:v.canonical_url});this.meta.updateTag({name:'twitter:card',content:'summary_large_image'});if(v.og_image){this.meta.updateTag({property:'og:image',content:v.og_image});this.meta.updateTag({name:'twitter:image',content:v.og_image})}let link=document.querySelector<HTMLLinkElement>('link[rel="canonical"]');if(!link){link=document.createElement('link');link.rel='canonical';document.head.appendChild(link)}link.href=v.canonical_url}
}
