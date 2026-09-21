import {Component,Input} from '@angular/core';
import {RouterLink} from '@angular/router';
import {TranslatePipe} from '../core/translate.pipe';

@Component({selector:'sn-public-brand',standalone:true,imports:[RouterLink,TranslatePipe],template:`<a routerLink="/" [attr.aria-label]="ariaLabel"><span class="symbol"><i></i><i></i><i></i></span><span class="copy"><strong>GUILDCONSOLE</strong><small>{{'login.brand_subtitle'|snT:'SECURE CONTROL FABRIC'}}</small></span></a>`,styles:[`
:host{display:block}a{display:flex;align-items:center;gap:.85rem;width:max-content;text-decoration:none}.symbol{position:relative;width:42px;height:42px;display:grid;place-items:center;border:1px solid rgba(53,226,178,.36);border-radius:11px;transform:rotate(45deg);background:rgba(53,226,178,.07)}.symbol i{position:absolute;height:2px;border-radius:10px;background:var(--primary);box-shadow:0 0 9px rgba(53,226,178,.65);transform:rotate(-45deg)}.symbol i:nth-child(1){width:19px;transform:translateY(-6px) rotate(-45deg)}.symbol i:nth-child(2){width:26px}.symbol i:nth-child(3){width:12px;transform:translateY(6px) rotate(-45deg)}.copy{display:grid;gap:.12rem}.copy strong{color:var(--text);font-size:.94rem;letter-spacing:.16em}.copy small{color:#66808e;font-size:.58rem;letter-spacing:.17em}
`]})
export class PublicBrandComponent{@Input() ariaLabel='GuildConsole'}
