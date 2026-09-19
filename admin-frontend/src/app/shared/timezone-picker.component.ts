import {Component,ElementRef,EventEmitter,HostListener,Input,Output,ViewChild,signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {TranslatePipe} from '../core/translate.pipe';

@Component({selector:'sn-timezone-picker',standalone:true,imports:[FormsModule,TranslatePipe],template:`
<div class="picker"><button #trigger type="button" class="trigger" (click)="toggle()"><span class="trigger-main"><b>◷</b><span class="copy"><strong>{{value}}</strong><small>{{'timezone_picker.hint'|snT:'Search by city or region'}}</small></span></span><span [class.open]="open()">⌄</span></button>
@if(open()){<div class="menu" [style.top.px]="position().top" [style.left.px]="position().left" [style.width.px]="position().width" [style.max-height.px]="position().height" (click)="$event.stopPropagation()">
  <div class="search"><span>⌕</span><input #search type="search" [(ngModel)]="query" [placeholder]="'timezone_picker.search'|snT:'Enter at least 2 characters…'" autocomplete="off"></div>
  <div class="options" (wheel)="$event.stopPropagation()">
    @if(query.trim().length<2){<div class="hint">{{'timezone_picker.min_chars'|snT:'Enter at least 2 characters to search.'}}</div>}
    @else{@for(zone of filtered();track zone){<button type="button" class="option" [class.selected]="zone===value" (click)="choose(zone)"><span>◷</span><span><strong>{{city(zone)}}</strong><small>{{region(zone)}}</small></span>@if(zone===value){<b>✓</b>}</button>}@empty{<div class="hint">{{'timezone_picker.empty'|snT:'No matching timezones.'}}</div>}}
  </div>
</div>}</div>`,styles:[`
:host{display:block;position:relative;isolation:isolate;min-width:270px}:host:has(.menu){z-index:1000}.picker{position:relative}.trigger{width:100%;min-height:52px;display:flex;align-items:center;justify-content:space-between;gap:.8rem;padding:.65rem .8rem;text-align:left;color:var(--text);background:var(--surface-2);border:1px solid var(--line);border-radius:11px}.trigger:hover,.trigger:focus{border-color:var(--line-strong)}.trigger-main{display:flex;align-items:center;gap:.65rem;min-width:0}.trigger-main>b{width:30px;height:30px;display:grid;place-items:center;color:var(--primary);background:var(--primary-soft);border-radius:8px}.copy{display:grid;min-width:0}.copy strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.copy small,.option small{color:var(--muted);font-size:.64rem}.trigger>span:last-child{transition:transform .18s}.trigger>span.open{transform:rotate(180deg)}.menu{position:fixed;z-index:10000;min-width:300px;display:flex;flex-direction:column;overflow:hidden;padding:.6rem;border:1px solid var(--line-strong);border-radius:13px;background:#07131d;box-shadow:0 22px 65px rgba(0,0,0,.5)}.search{display:grid;grid-template-columns:28px 1fr;align-items:center;padding:0 .55rem;border:1px solid var(--line);border-radius:9px;background:#091720}.search>span{color:var(--primary);font-size:1rem}.search input{min-height:43px;padding:.55rem .2rem;border:0;outline:0;background:transparent;color:var(--text)}.options{flex:1;min-height:150px;overflow-y:auto;overscroll-behavior:contain;margin-top:.45rem;padding-right:.15rem}.options::-webkit-scrollbar{width:8px}.options::-webkit-scrollbar-thumb{background:var(--line-strong);border-radius:8px}.option{width:100%;display:grid;grid-template-columns:28px 1fr 20px;align-items:center;gap:.55rem;padding:.65rem;text-align:left;color:var(--text);border:1px solid transparent;border-radius:9px;background:transparent}.option>span:nth-child(2){display:grid}.option:hover,.option.selected{border-color:rgba(45,212,191,.3);background:var(--primary-soft)}.option.selected>span:first-child,.option>b{color:var(--primary)}.hint{padding:1.2rem;text-align:center;color:var(--muted);font-size:.72rem}@media(max-width:700px){:host{min-width:0}.menu{min-width:0}}
`]})
export class TimezonePickerComponent{
  @Input({required:true}) value='UTC';@Input({required:true}) options:string[]=[];@Output() valueChange=new EventEmitter<string>();
  @ViewChild('trigger') trigger?:ElementRef<HTMLButtonElement>;@ViewChild('search') search?:ElementRef<HTMLInputElement>;
  readonly open=signal(false);readonly position=signal({top:0,left:0,width:340,height:420});query='';
  filtered(){const q=this.query.trim().toLocaleLowerCase();if(q.length<2)return[];return this.options.filter(zone=>zone.toLocaleLowerCase().includes(q)).slice(0,150)}
  toggle(){if(this.open()){this.close();return}this.updatePosition();this.open.set(true);setTimeout(()=>this.search?.nativeElement.focus())}
  choose(zone:string){this.value=zone;this.valueChange.emit(zone);this.close()}
  close(){this.open.set(false);this.query=''}
  city(zone:string){return zone.split('/').at(-1)?.replaceAll('_',' ')||zone}
  region(zone:string){return zone.includes('/')?zone.split('/').slice(0,-1).join(' / '):zone}
  @HostListener('document:click',['$event']) outside(event:MouseEvent){if(this.open()&&!this.trigger?.nativeElement.parentElement?.contains(event.target as Node))this.close()}
  @HostListener('document:keydown.escape') escape(){this.close()}
  @HostListener('window:resize') resize(){if(this.open())this.updatePosition()}
  private updatePosition(){const rect=this.trigger?.nativeElement.getBoundingClientRect();if(!rect)return;const margin=16,gap=7,width=Math.min(Math.max(rect.width,300),window.innerWidth-margin*2),left=Math.min(Math.max(rect.left,margin),window.innerWidth-width-margin),below=window.innerHeight-rect.bottom-gap-margin,above=rect.top-gap-margin,height=Math.min(420,Math.max(220,below>=220?below:above)),top=below>=220?rect.bottom+gap:Math.max(margin,rect.top-gap-height);this.position.set({top,left,width,height})}
}
