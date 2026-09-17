import {HttpClient} from '@angular/common/http';
import {Injectable} from '@angular/core';
import {firstValueFrom} from 'rxjs';
export interface BillingPlan{plugin_key:string;name?:string;is_free:boolean;enabled:boolean;currency:string;monthly_price:number|null;quarterly_price:number|null;yearly_price:number|null;quarterly_discount_percent?:number;yearly_discount_percent?:number}
export interface BillingSubscription{id:string;guild_id:string;plugin_key:string;status:string;billing_period:string;starts_at:string;expires_at:string;provider?:string|null;auto_renew?:boolean}
export interface BillingProviders{wayforpay:{enabled:boolean;configured:boolean;active:boolean;merchant_account:string;merchant_domain:string;secret_saved:boolean};liqpay:{enabled:boolean;configured:boolean;active:boolean;public_key:string;secret_saved:boolean}}
export interface BillingPayment{id:string;order_reference:string;guild_id:string;guild_name?:string|null;plugin_key:string;billing_period:string;provider:string;amount:number;currency:string;status:string;signature_verified:boolean;created_at:string;paid_at?:string|null}
export interface BillingWallet{discord_user_id:string;display_name?:string|null;email?:string|null;balance:number;currency:string}
@Injectable({providedIn:'root'}) export class BillingService{
 constructor(private http:HttpClient){}
 plans(){return firstValueFrom(this.http.get<BillingPlan[]>('/api/v1/platform/billing/plans'))}
 savePlan(x:BillingPlan){return firstValueFrom(this.http.put<BillingPlan>(`/api/v1/platform/billing/plans/${x.plugin_key}`,x))}
 paidPackage(){return firstValueFrom(this.http.get<BillingPlan>('/api/v1/platform/billing/package'))}
 savePackage(x:BillingPlan){return firstValueFrom(this.http.put<BillingPlan>('/api/v1/platform/billing/package',x))}
 subscriptions(guildId?:string){return firstValueFrom(this.http.get<BillingSubscription[]>('/api/v1/platform/billing/subscriptions',{params:guildId?{guild_id:guildId}: {}}))}
 grant(x:{guild_id:string;plugin_key:string;billing_period:string;days:number}){return firstValueFrom(this.http.post<BillingSubscription>('/api/v1/platform/billing/subscriptions/grant',x))}
 revoke(id:string){return firstValueFrom(this.http.delete<BillingSubscription>(`/api/v1/platform/billing/subscriptions/${id}`))}
 providers(){return firstValueFrom(this.http.get<BillingProviders>('/api/v1/platform/billing/providers'))}
 saveProviders(x:any){return firstValueFrom(this.http.put<BillingProviders>('/api/v1/platform/billing/providers',x))}
 payments(){return firstValueFrom(this.http.get<BillingPayment[]>('/api/v1/platform/billing/payments'))}
 wallets(){return firstValueFrom(this.http.get<BillingWallet[]>('/api/v1/platform/billing/wallets'))}
 creditWallet(x:{discord_user_id:string;amount:number;comment:string}){return firstValueFrom(this.http.post('/api/v1/platform/billing/wallets/credit',x))}
 guildBilling(guildId:string){return firstValueFrom(this.http.get<any>(`/api/v1/discord/guilds/${guildId}/billing`))}
 checkout(guildId:string,x:{plugin_key:string;billing_period:string;provider:string}){return firstValueFrom(this.http.post<any>(`/api/v1/discord/guilds/${guildId}/billing/checkout`,x))}
 walletTopup(x:any){return firstValueFrom(this.http.post<any>('/api/v1/billing/wallet/checkout',x))}
 purchaseSubscription(x:any){return firstValueFrom(this.http.post<any>('/api/v1/billing/subscriptions/purchase',x))}
 saveWalletSettings(x:any){return firstValueFrom(this.http.put<any>('/api/v1/billing/wallet/settings',x))}
 redeemDiscount(guildId:string,code:string){return firstValueFrom(this.http.post<any>(`/api/v1/discord/guilds/${guildId}/billing/discount-card`,{code}))}
 discounts(){return firstValueFrom(this.http.get<any>('/api/v1/platform/billing/discounts'))}
 saveDiscountCard(x:any){return firstValueFrom(this.http.post('/api/v1/platform/billing/discounts/cards',x))}
 updateDiscountCard(id:string,x:any){return firstValueFrom(this.http.put(`/api/v1/platform/billing/discounts/cards/${id}`,x))}
 deleteDiscountCard(id:string){return firstValueFrom(this.http.delete(`/api/v1/platform/billing/discounts/cards/${id}`))}
 saveTenureDiscount(x:any){return firstValueFrom(this.http.post('/api/v1/platform/billing/discounts/tenure',x))}
 updateTenureDiscount(id:string,x:any){return firstValueFrom(this.http.put(`/api/v1/platform/billing/discounts/tenure/${id}`,x))}
 deleteTenureDiscount(id:string){return firstValueFrom(this.http.delete(`/api/v1/platform/billing/discounts/tenure/${id}`))}
}
