import {HttpClient} from '@angular/common/http';
import {Injectable} from '@angular/core';
import {firstValueFrom} from 'rxjs';
export interface BillingPlan{plugin_key:string;name?:string;is_free:boolean;enabled:boolean;currency:string;monthly_price:number|null;quarterly_price:number|null;yearly_price:number|null}
export interface BillingSubscription{id:string;guild_id:number;plugin_key:string;status:string;billing_period:string;starts_at:string;expires_at:string;provider?:string|null}
@Injectable({providedIn:'root'}) export class BillingService{
 constructor(private http:HttpClient){}
 plans(){return firstValueFrom(this.http.get<BillingPlan[]>('/api/v1/platform/billing/plans'))}
 savePlan(x:BillingPlan){return firstValueFrom(this.http.put<BillingPlan>(`/api/v1/platform/billing/plans/${x.plugin_key}`,x))}
 subscriptions(guildId?:number){return firstValueFrom(this.http.get<BillingSubscription[]>('/api/v1/platform/billing/subscriptions',{params:guildId?{guild_id:guildId}: {}}))}
 grant(x:{guild_id:number;plugin_key:string;billing_period:string;days:number}){return firstValueFrom(this.http.post<BillingSubscription>('/api/v1/platform/billing/subscriptions/grant',x))}
 revoke(id:string){return firstValueFrom(this.http.delete<BillingSubscription>(`/api/v1/platform/billing/subscriptions/${id}`))}
}
