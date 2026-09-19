import {HttpClient} from '@angular/common/http';
import {Injectable} from '@angular/core';
import {firstValueFrom} from 'rxjs';

export interface MerchantContent{locale?:string;business_name:string;tax_id:string;legal_address:string;actual_address:string;phone:string;email:string;service_description:string;service_terms:string;payment_methods:string;service_area:string;refund_policy:string;cancellation_policy:string;public_offer:string;privacy_policy:string}
@Injectable({providedIn:'root'})
export class MerchantPageService{
 constructor(private http:HttpClient){}
 get(locale='en'){return firstValueFrom(this.http.get<MerchantContent>('/api/v1/public/privacy-policy',{params:{locale}}))}
 save(value:MerchantContent,locale='en'){return firstValueFrom(this.http.put<MerchantContent>('/api/v1/platform/privacy-policy',value,{params:{locale}}))}
}
