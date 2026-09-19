import {HttpClient} from '@angular/common/http';
import {Injectable} from '@angular/core';
import {firstValueFrom} from 'rxjs';

export interface SupportAttachment{id:string;file_name:string;mime_type:string;file_size:number;object_url?:string}
export interface SupportMessage{id:string;body:string;is_staff:boolean;author_name:string;created_at:string;attachments?:SupportAttachment[]}
export interface SupportTicket{id:string;topic:'bug'|'suggestion';subject:string;status:string;priority:string;author_name?:string;author_email?:string;created_at:string;updated_at:string;message_id?:string;messages?:SupportMessage[]}

@Injectable({providedIn:'root'})
export class SupportService{
 constructor(private http:HttpClient){}
 list(staff=false,status=''){const url=staff?`/api/v1/support/tickets/platform/all${status?`?status=${status}`:''}`:'/api/v1/support/tickets';return firstValueFrom(this.http.get<SupportTicket[]>(url))}
 get(id:string,staff=false){return firstValueFrom(this.http.get<SupportTicket>(staff?`/api/v1/support/tickets/platform/${id}`:`/api/v1/support/tickets/${id}`))}
 create(data:{topic:string;subject:string;body:string}){return firstValueFrom(this.http.post<SupportTicket>('/api/v1/support/tickets',data))}
 reply(id:string,body:string,staff=false){return firstValueFrom(this.http.post(staff?`/api/v1/support/tickets/platform/${id}/messages`:`/api/v1/support/tickets/${id}/messages`,{body}))}
 update(id:string,data:{status?:string;priority?:string}){return firstValueFrom(this.http.patch(`/api/v1/support/tickets/platform/${id}`,data))}
 upload(ticketId:string,messageId:string,files:File[]){const data=new FormData();files.forEach(file=>data.append('files',file));return firstValueFrom(this.http.post(`/api/v1/support/tickets/${ticketId}/messages/${messageId}/attachments`,data))}
 file(ticketId:string,attachmentId:string){return firstValueFrom(this.http.get(`/api/v1/support/tickets/${ticketId}/attachments/${attachmentId}`,{responseType:'blob'}))}
}
