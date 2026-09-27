import {CommonModule} from '@angular/common';
import {Component,ElementRef,EventEmitter,HostListener,Input,OnChanges,OnInit,Output,SimpleChanges,ViewChild,computed,inject,signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {HttpClient} from '@angular/common/http';
import {firstValueFrom} from 'rxjs';

interface ServerEmoji{id:string|number;name:string;animated:boolean;available:boolean}
interface ExplorerResponse{emojis?:ServerEmoji[]}
interface EmojiChoice{value:string;name:string;image?:string;symbol?:string;server:boolean}

@Component({
  selector:'sn-discord-emoji-picker',standalone:true,imports:[CommonModule,FormsModule],template:`
  <details class="picker" #menu (toggle)="onToggle(menu)">
    <summary #anchor><span class="preview">@if(selectedImage()){<img [src]="selectedImage()" [alt]="selectedName()">}@else{ {{selectedSymbol()||'＋'}} }</span><span class="chevron">⌄</span></summary>
    <div class="popover" [class.above]="opensAbove()" [style.top.px]="popoverTop()" [style.left.px]="popoverLeft()" [style.width.px]="popoverWidth()" [style.max-height.px]="popoverMaxHeight()">
      <div class="tools"><input [ngModel]="query()" (ngModelChange)="query.set($event)" placeholder="Search emoji"><button type="button" (click)="refresh($event)" [disabled]="loading()">{{loading()?'…':'↻'}}</button></div>
      <button type="button" class="clear" (click)="choose('',menu)">No emoji</button>
      @if(serverChoices().length){<h5>Server emoji</h5><div class="grid">@for(item of serverChoices();track item.value){<button type="button" (click)="choose(item.value,menu)" [class.active]="item.value===value" [title]="item.name"><img [src]="item.image" [alt]="item.name"><small>:{{item.name}}:</small></button>}</div>}
      <h5>Standard emoji</h5><div class="grid unicode">@for(item of unicodeChoices();track item.value){<button type="button" (click)="choose(item.value,menu)" [class.active]="item.value===value" [title]="item.name"><b>{{item.symbol}}</b><small>{{item.name}}</small></button>}</div>
      @if(error()){<p class="error">{{error()}}</p>}
    </div>
  </details>`,styles:[`
  :host{display:block;min-width:0}.picker{position:relative}.picker summary{box-sizing:border-box;height:52px;display:flex;align-items:center;justify-content:space-between;padding:.55rem .7rem;border:1px solid var(--line);border-radius:9px;background:var(--panel-2);color:var(--text);cursor:pointer;list-style:none}.picker summary::-webkit-details-marker{display:none}.picker[open] summary{border-color:var(--primary);box-shadow:0 0 0 2px var(--primary-soft)}.preview{display:grid;place-items:center;width:30px;height:30px;font-size:1.35rem}.preview img{width:28px;height:28px;object-fit:contain}.chevron{color:var(--muted)}.popover{position:fixed;z-index:1000;overflow:auto;padding:.75rem;border:1px solid var(--line-strong);border-radius:12px;background:var(--panel);box-shadow:0 18px 50px rgba(0,0,0,.45)}.popover.above{transform:translateY(-100%)}.tools{display:grid;grid-template-columns:1fr 42px;gap:.45rem;position:sticky;top:-.75rem;z-index:2;padding:.1rem 0 .55rem;background:var(--panel)}input{box-sizing:border-box;width:100%;height:42px;padding:.55rem .7rem;border:1px solid var(--line);border-radius:8px;background:var(--panel-2);color:var(--text)}button{border:1px solid var(--line);border-radius:8px;background:var(--panel-2);color:var(--text);cursor:pointer}.tools button{font-size:1.05rem}.clear{width:100%;min-height:38px;margin-bottom:.55rem}h5{margin:.6rem 0 .4rem;color:var(--muted);font-size:.68rem;text-transform:uppercase;letter-spacing:.08em}.grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.35rem}.grid button{min-width:0;height:58px;display:grid;place-items:center;gap:.05rem;padding:.3rem}.grid button.active{border-color:var(--primary);background:var(--primary-soft)}.grid img{width:27px;height:27px;object-fit:contain}.grid b{font-size:1.35rem;line-height:1}.grid small{display:block;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--muted);font-size:.56rem}.error{color:#ff8290;font-size:.7rem}@media(max-width:600px){.grid{grid-template-columns:repeat(4,minmax(0,1fr))}}
  `]
})
export class DiscordEmojiPickerComponent implements OnInit,OnChanges{
 private static cache=new Map<string,{expires:number,data:ServerEmoji[]}>();private http=inject(HttpClient);
 @Input({required:true})guildId='';@Input()value='';@Output()valueChange=new EventEmitter<string>();
 loading=signal(false);error=signal('');server=signal<ServerEmoji[]>([]);query=signal('');
 @ViewChild('anchor')anchor?:ElementRef<HTMLElement>;@ViewChild('menu')menu?:ElementRef<HTMLDetailsElement>;
 opensAbove=signal(false);popoverTop=signal(0);popoverLeft=signal(0);popoverWidth=signal(440);popoverMaxHeight=signal(410);
 private readonly unicode=[['🎮','Game'],['⚔️','Battle'],['🛡️','Shield'],['🏆','Trophy'],['⭐','Star'],['🔥','Fire'],['💎','Gem'],['👑','Crown'],['🎯','Target'],['🚀','Rocket'],['📢','News'],['🔔','Alerts'],['🎁','Gift'],['❤️','Heart'],['💬','Chat'],['🌍','Global'],['🎨','Creative'],['🎵','Music'],['📚','Learning'],['✅','Verified'],['❌','Disabled'],['🟢','Online'],['🔴','Offline'],['🟡','Away'],['👥','Community'],['🤝','Partners'],['🔒','Private'],['🔓','Public'],['🧪','Beta'],['🛠️','Tools']];
 serverChoices=computed(()=>{const q=this.query().trim().toLowerCase();return this.server().filter(x=>x.available&&(!q||x.name.toLowerCase().includes(q))).map(x=>({value:`<${x.animated?'a:':':'}${x.name}:${x.id}>`,name:x.name,image:this.url(x),server:true} as EmojiChoice))});
 unicodeChoices(){const q=this.query().trim().toLowerCase();return this.unicode.filter(([symbol,name])=>!q||name.toLowerCase().includes(q)||symbol.includes(q)).map(([symbol,name])=>({value:symbol,name,symbol,server:false} as EmojiChoice))}
 ngOnInit(){void this.load()}
 onToggle(menu:HTMLDetailsElement){if(menu.open)requestAnimationFrame(()=>this.position())}
 @HostListener('window:resize')onResize(){if(this.menu?.nativeElement.open)this.position()}
 @HostListener('window:scroll')onScroll(){if(this.menu?.nativeElement.open)this.position()}
 ngOnChanges(changes:SimpleChanges){if(changes['guildId']&&!changes['guildId'].firstChange)void this.load()}
 choose(value:string,menu:HTMLDetailsElement){this.value=value;this.valueChange.emit(value);menu.open=false}
 selectedServer(){const item=this.server().find(x=>`<${x.animated?'a:':':'}${x.name}:${x.id}>`===this.value);return item?{name:item.name,image:this.url(item)}:null}selectedImage(){return this.selectedServer()?.image||''}selectedSymbol(){return this.value&&!this.value.startsWith('<')?this.value:''}selectedName(){return this.selectedServer()?.name||this.value||'Choose emoji'}
 async refresh(event:Event){event.preventDefault();event.stopPropagation();if(this.loading())return;this.loading.set(true);try{await firstValueFrom(this.http.post(`/api/v1/discord/guilds/${this.guildId}/structure/refresh`,{}));await new Promise(r=>setTimeout(r,1800));DiscordEmojiPickerComponent.cache.delete(this.guildId);await this.load(true)}catch(e:any){this.error.set(e?.error?.detail||'Unable to refresh server emoji.')}finally{this.loading.set(false)}}
 private async load(force=false){if(!this.guildId)return;this.loading.set(true);this.error.set('');try{const cached=DiscordEmojiPickerComponent.cache.get(this.guildId);const rows=!force&&cached&&cached.expires>Date.now()?cached.data:(await firstValueFrom(this.http.get<ExplorerResponse>(`/api/v1/discord/guilds/${this.guildId}/explorer`))).emojis||[];DiscordEmojiPickerComponent.cache.set(this.guildId,{expires:Date.now()+30000,data:rows});this.server.set(rows)}catch(e:any){this.error.set(e?.error?.detail||'Unable to load server emoji.');this.server.set([])}finally{this.loading.set(false)}}
 private position(){const anchor=this.anchor?.nativeElement;if(!anchor)return;const rect=anchor.getBoundingClientRect(),margin=8,gap=6,width=Math.min(440,window.innerWidth-margin*2),below=window.innerHeight-rect.bottom-margin,above=rect.top-margin,useAbove=below<260&&above>below;this.opensAbove.set(useAbove);this.popoverTop.set(useAbove?rect.top-gap:rect.bottom+gap);this.popoverLeft.set(Math.max(margin,Math.min(rect.left,window.innerWidth-width-margin)));this.popoverWidth.set(width);this.popoverMaxHeight.set(Math.max(180,Math.min(410,(useAbove?above:below)-gap)))}
 private url(item:ServerEmoji){return`https://cdn.discordapp.com/emojis/${item.id}.${item.animated?'gif':'webp'}?size=64&quality=lossless`}
}
