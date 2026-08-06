import {HttpClient} from '@angular/common/http';
import {Injectable} from '@angular/core';
@Injectable({providedIn:'root'})
export class MediaVariablesService{
  constructor(private http:HttpClient){}
  list(schema:string){return this.http.get<any>('/api/v1/platform/media/variables',{params:{schema}})}
  validate(schema:string,tokens:string[]){return this.http.post<any>('/api/v1/platform/media/variables/validate',{schema,tokens})}
}
