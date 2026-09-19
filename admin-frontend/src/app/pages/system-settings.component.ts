import {Component,OnInit,signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {BillingEmailSettings,BillingService} from '../core/billing.service';
import {ShellComponent} from '../shared/shell.component';

@Component({standalone:true,imports:[FormsModule,ShellComponent],template:`
<sn-shell title="System settings"><main class="page">
  <header><span>SUPERADMIN · INFRASTRUCTURE</span><h2>System settings</h2><p>Shared infrastructure used by the entire GuildConsole platform.</p></header>
  @if(error()){<div class="notice error">{{error()}}</div>}@if(success()){<div class="notice success">{{success()}}</div>}
  <article class="card">
    <div class="card-head"><div><h3>SMTP email delivery</h3><p>System mail transport for balance alerts, subscription expiry reminders and other platform messages.</p></div><button type="button" class="toggle" [class.on]="form.enabled" (click)="form.enabled=!form.enabled">{{form.enabled?'Enabled':'Disabled'}}</button></div>
    <div class="grid"><label>SMTP host<input [(ngModel)]="form.host" placeholder="smtp.example.com"></label><label>Port<input type="number" min="1" max="65535" [(ngModel)]="form.port"></label><label>Username<input [(ngModel)]="form.username"></label><label>Password<input type="password" [(ngModel)]="form.password" [placeholder]="settings()?.password_saved?'Saved · enter only to replace':''"></label><label>Sender email<input type="email" [(ngModel)]="form.from_email"></label><label>Sender name<input [(ngModel)]="form.from_name"></label></div>
    <div class="checks"><label><input type="checkbox" [(ngModel)]="form.use_tls"> STARTTLS</label><label><input type="checkbox" [(ngModel)]="form.use_ssl"> SSL/TLS</label></div>
    <div class="test"><input type="email" [(ngModel)]="testRecipient" placeholder="Test recipient email"><button class="secondary" (click)="sendTest()" [disabled]="!testRecipient.trim()">Send test</button><button (click)="save()">Save SMTP settings</button></div>
    <span class="status" [class.ready]="settings()?.enabled&&settings()?.configured"><i></i>{{settings()?.enabled&&settings()?.configured?'SMTP is ready':settings()?.configured?'SMTP is configured but disabled':'Configuration required'}}</span>
  </article>
</main></sn-shell>`,styles:[`
.page{max-width:1200px;margin:auto;display:grid;gap:1rem;padding-bottom:3rem}header span{color:var(--primary);font-size:.68rem;font-weight:900;letter-spacing:.14em}h2,h3,p{margin:.25rem 0}p{color:var(--muted)}.card,.notice{padding:1.2rem;border:1px solid var(--line);border-radius:16px;background:var(--panel)}.card{display:grid;gap:1.15rem}.card-head{display:flex;align-items:flex-start;justify-content:space-between;gap:1rem}.grid{display:grid;grid-template-columns:2fr .55fr 1.2fr 1.2fr 1.2fr 1.2fr;gap:.75rem}label{display:grid;gap:.4rem;color:var(--muted);font-size:.75rem}.checks{display:flex;align-items:center;gap:1.2rem}.checks label{display:flex;align-items:center;gap:.55rem;color:var(--text);font-size:.82rem}.test{display:grid;grid-template-columns:minmax(220px,1fr) auto auto;gap:.65rem}input{padding:.72rem;border:1px solid var(--line);border-radius:9px;background:var(--panel-2);color:var(--text)}button{padding:.7rem 1rem;border:1px solid transparent;border-radius:9px;background:var(--primary);color:#07120f;font-weight:800;cursor:pointer}.secondary,.toggle{background:var(--panel-2);color:var(--text);border-color:var(--line)}.toggle{min-width:110px;color:var(--muted)}.toggle.on{color:var(--success);border-color:var(--success)}.status{display:flex;align-items:center;gap:.5rem;color:var(--muted)}.status i{width:8px;height:8px;border-radius:50%;background:currentColor}.status.ready{color:var(--success)}.error{color:#ff8d96}.success{color:var(--success)}@media(max-width:900px){.grid{grid-template-columns:1fr 1fr}.test{grid-template-columns:1fr}}@media(max-width:600px){.grid{grid-template-columns:1fr}.card-head{flex-direction:column}.test{grid-template-columns:1fr}.checks{align-items:flex-start;flex-direction:column}}
`]})
export class SystemSettingsComponent implements OnInit{
 settings=signal<BillingEmailSettings|null>(null);error=signal('');success=signal('');testRecipient='';
 form={enabled:false,host:'',port:587,username:'',password:'',from_email:'',from_name:'GuildConsole',use_tls:true,use_ssl:false};
 constructor(private api:BillingService){}
 async ngOnInit(){await this.load()}
 async load(){this.error.set('');try{const value=await this.api.emailSettings();this.settings.set(value);this.form={...this.form,...value,password:''}}catch(e:any){this.error.set(e?.error?.detail||'Unable to load system email settings.')}}
 async save(){this.error.set('');this.success.set('');try{const value=await this.api.saveEmailSettings(this.form);this.settings.set(value);this.form.password='';this.success.set('SMTP settings saved.')}catch(e:any){this.error.set(e?.error?.detail||'Unable to save SMTP settings.')}}
 async sendTest(){this.error.set('');this.success.set('');try{await this.api.testEmail(this.testRecipient.trim());this.success.set('Test email delivered.')}catch(e:any){this.error.set(e?.error?.detail||'Unable to deliver test email.')}}
}
