import { Component, OnInit, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { ShellComponent } from '../shared/shell.component';
import { TranslatePipe } from '../core/translate.pipe';
import { TranslationService } from '../core/translation.service';

@Component({
  standalone: true,
  imports: [ShellComponent, TranslatePipe],
  template: `
    <sn-shell [title]="'audit.title' | snT:'Audit Log'">
      <div class="card header">
        <h2>{{ "audit.recent" | snT:"Recent actions" }}</h2>
        <div class="muted">{{ total() }} {{ "audit.events" | snT:"events" }}</div>
      </div>

      <div class="events">
        @for (event of events(); track event.id) {
          <article class="card event">
            <div>
              <strong>{{ event.event_type }}</strong>
              <div class="muted">{{ event.target_type }} {{ event.target_id }}</div>
            </div>
            <div class="right">
              <span>{{ event.result }}</span>
              <small class="muted">{{ event.created_at }}</small>
            </div>
          </article>
        }
      </div>
    </sn-shell>
  `,
  styles: [`
    .header { padding: 1.2rem; }
    h2 { margin: 0 0 .3rem; }
    .events { margin-top: 1rem; display: grid; gap: .7rem; }
    .event { padding: 1rem; display: flex; justify-content: space-between; gap: 1rem; }
    .right { display: grid; text-align: right; gap: .25rem; }
  `],
})
export class AuditComponent implements OnInit {
  readonly guildId = this.route.snapshot.paramMap.get('guildId') ?? '';
  readonly events = signal<any[]>([]);
  readonly total = signal(0);

  constructor(private readonly route: ActivatedRoute, private readonly http: HttpClient) {}

  async ngOnInit(): Promise<void> {
    const response = await firstValueFrom(
      this.http.get<any>(`/api/v1/discord/guilds/${this.guildId}/audit`),
    );
    this.events.set(response.items);
    this.total.set(response.total);
  }
}
