import {HttpClient} from '@angular/common/http';
import {Injectable} from '@angular/core';
@Injectable({providedIn:'root'})
export class MediaAssetsService{
 constructor(private http:HttpClient){}
 list(type?:string){return this.http.get<any>('/api/v1/platform/media-assets',{params:type?{asset_type:type}:{}})}
 create(data:FormData){return this.http.post<any>('/api/v1/platform/media-assets',data)}
 update(id:string,data:any){return this.http.patch<any>(`/api/v1/platform/media-assets/${id}`,data)}
 remove(id:string){return this.http.delete<void>(`/api/v1/platform/media-assets/${id}`)}
}
