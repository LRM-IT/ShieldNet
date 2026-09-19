import {Component,ElementRef,EventEmitter,HostListener,Input,Output,ViewChild,signal} from '@angular/core';
import {LanguageEntity} from '../core/translation.service';

@Component({selector:'sn-language-picker',standalone:true,template:`
<div class="picker"><button #trigger type="button" class="trigger" (click)="toggle()"><span>{{current()?.icon}}</span><strong>{{current()?.name}} — {{value.toUpperCase()}}</strong><span [class.open]="open()">⌄</span></button>
@if(open()){<div class="menu" [style.top.px]="position().top" [style.left.px]="position().left" [style.width.px]="position().width" (click)="$event.stopPropagation()">
 @for(language of options;track language.code){<button type="button" class="option" [class.selected]="language.code===value" (click)="choose(language.code)"><span>{{language.icon}}</span><span><strong>{{language.name}}</strong><small>{{language.code.toUpperCase()}}</small></span>@if(language.code===value){<b>✓</b>}</button>}
</div>}</div>`,styles:[`
:host{display:block;position:relative;isolation:isolate}:host:has(.menu){z-index:1000}.picker{position:relative}.trigger{width:100%;min-height:52px;display:grid;grid-template-columns:34px 1fr 20px;align-items:center;gap:.55rem;padding:.65rem .8rem;text-align:left;color:var(--text);background:var(--surface-2);border:1px solid var(--line);border-radius:11px}.trigger:hover,.trigger:focus{border-color:var(--primary)}.trigger>span:first-child{font-size:1.2rem}.trigger>span:last-child{text-align:center;transition:transform .18s}.trigger>span.open{transform:rotate(180deg)}.menu{position:fixed;z-index:10000;display:grid;gap:.25rem;max-height:min(420px,70vh);overflow-y:auto;overscroll-behavior:contain;padding:.55rem;border:1px solid var(--line-strong);border-radius:13px;background:#07131d;box-shadow:0 22px 65px rgba(0,0,0,.5)}.option{width:100%;display:grid;grid-template-columns:34px 1fr 20px;align-items:center;gap:.55rem;padding:.7rem;text-align:left;color:var(--text);border:1px solid transparent;border-radius:9px;background:transparent}.option>span:nth-child(2){display:grid;gap:.15rem}.option small{color:var(--muted);font-size:.62rem}.option:hover,.option.selected{border-color:rgba(45,212,191,.3);background:var(--primary-soft)}.option>b{color:var(--primary)}
`]})
export class LanguagePickerComponent{
 @Input({required:true}) value='en';@Input({required:true}) options:LanguageEntity[]=[];@Output() valueChange=new EventEmitter<string>();
 @ViewChild('trigger') trigger?:ElementRef<HTMLButtonElement>;readonly open=signal(false);readonly position=signal({top:0,left:0,width:320});
 current(){return this.options.find(item=>item.code===this.value)||this.options[0]}
 toggle(){if(this.open()){this.close();return}this.updatePosition();this.open.set(true)}
 choose(code:string){this.value=code;this.valueChange.emit(code);this.close()}
 close(){this.open.set(false)}
 @HostListener('document:click',['$event']) outside(event:MouseEvent){if(this.open()&&!this.trigger?.nativeElement.parentElement?.contains(event.target as Node))this.close()}
 @HostListener('document:keydown.escape') escape(){this.close()}
 @HostListener('window:resize') resize(){if(this.open())this.updatePosition()}
 private updatePosition(){const rect=this.trigger?.nativeElement.getBoundingClientRect();if(!rect)return;const margin=16,gap=7,width=Math.min(Math.max(rect.width,280),window.innerWidth-margin*2),left=Math.min(Math.max(rect.left,margin),window.innerWidth-width-margin),menuHeight=Math.min(420,window.innerHeight-margin*2),below=window.innerHeight-rect.bottom-gap-margin,top=below>=Math.min(menuHeight,260)?rect.bottom+gap:Math.max(margin,rect.top-gap-menuHeight);this.position.set({top,left,width})}
}
