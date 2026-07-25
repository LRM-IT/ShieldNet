import { Component, computed } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslatePipe } from '../core/translate.pipe';
import { TranslationService } from '../core/translation.service';

import { AuthService } from '../core/auth.service';
import { ThemeService } from '../core/theme.service';
import { ShellComponent } from '../shared/shell.component';

@Component({
  standalone: true,
  imports: [ShellComponent, RouterLink, TranslatePipe],
  template: `
    <sn-shell [title]="'profile.title' | snT:'Profile'">
      <section class="profile-layout">
        <article class="identity-card panel-v4">
          <div class="identity-head">
            @if (auth.profile()?.avatar_url) {
              <img [src]="auth.profile()?.avatar_url" alt="" />
            } @else {
              <span class="avatar-fallback">{{ initial() }}</span>
            }

            <div>
              <span class="eyebrow">{{ 'profile.account' | snT:'ACCOUNT' }}</span>
              <h2>{{ auth.profile()?.display_name || auth.profile()?.login }}</h2>
              <p>{{ auth.profile()?.email }}</p>
            </div>
          </div>

          <dl>
            <div><dt>{{ "profile.discord_id" | snT:"Discord ID" }}</dt><dd>{{ auth.profile()?.discord_user_id || '—' }}</dd></div>
            <div><dt>{{ 'profile.global_role' | snT:'Global role' }}</dt><dd>{{ auth.profile()?.highest_role || 'operator' }}</dd></div>
            <div><dt>{{ 'profile.status' | snT:'Status' }}</dt><dd class="status-value">{{ auth.profile()?.status || 'active' }}</dd></div>
            <div><dt>{{ 'profile.email_verified' | snT:'Email verified' }}</dt><dd>{{ auth.profile()?.email_verified ? ('profile.yes' | snT:'Yes') : ('profile.no' | snT:'No') }}</dd></div>
          </dl>

          <div class="identity-actions">
            <a routerLink="/" class="secondary-action">← {{ 'profile.back' | snT:'Back to dashboard' }}</a>
            <button type="button" class="danger-action" (click)="auth.logout()">{{ 'profile.logout' | snT:'Sign out' }}</button>
          </div>
        </article>

        <div class="settings-stack">
          <article class="panel-v4 settings-panel">
            <div class="section-heading">
              <div>
                <span class="eyebrow">{{ 'profile.appearance' | snT:'APPEARANCE' }}</span>
                <h2>{{ 'profile.theme' | snT:'Interface theme' }}</h2>
                <p>{{ 'profile.theme_help' | snT:'Changes apply immediately and are saved in this browser.' }}</p>
              </div>
              <span class="active-label">{{ activeThemeName() }}</span>
            </div>

            <div class="theme-grid">
              @for (theme of themes.themes; track theme.id) {
                <button
                  type="button"
                  class="theme-option"
                  [class.active]="themes.activeTheme() === theme.id"
                  (click)="themes.setTheme(theme.id)"
                >
                  <span class="theme-preview">
                    @for (color of theme.preview; track color) {
                      <i [style.background]="color"></i>
                    }
                  </span>
                  <span class="theme-copy">
                    <strong><b>{{ theme.icon }}</b>{{ ('themes.' + theme.id + '.name') | snT:theme.name }}</strong>
                    <small>{{ ('themes.' + theme.id + '.description') | snT:theme.description }}</small>
                  </span>
                  <span class="check">{{ themes.activeTheme() === theme.id ? '✓' : '' }}</span>
                </button>
              }
            </div>
          </article>

          <article class="panel-v4 settings-panel">
            <div class="section-heading">
              <div>
                <span class="eyebrow">{{ 'profile.localization' | snT:'LOCALIZATION' }}</span>
                <h2>{{ 'profile.language_region' | snT:'Language and region' }}</h2>
                <p>{{ 'profile.language_help' | snT:'The initial language is detected automatically.' }}</p>
              </div>
              <span class="active-label">{{ i18n.currentLanguage()?.icon }} {{ i18n.currentLanguage()?.name }}</span>
            </div>

            <div class="language-grid">
              @for (language of i18n.languages(); track language.code) {
                <button
                  type="button"
                  class="language-option"
                  [class.active]="i18n.locale() === language.code"
                  (click)="changeLanguage(language.code)"
                >
                  <span class="flag">{{ language.icon }}</span>
                  <span><strong>{{ language.name }}</strong><small>{{ language.code.toUpperCase() }}</small></span>
                  <b>{{ i18n.locale() === language.code ? '✓' : '' }}</b>
                </button>
              }
            </div>

            <div class="preference-row">
              <div>
                <strong>{{ 'profile.timezone' | snT:'Timezone' }}</strong>
                <small>{{ 'profile.timezone_help' | snT:'Used for logs, jobs and events.' }}</small>
              </div>
              <button type="button" disabled>{{ timezone }}</button>
            </div>
          </article>
        </div>
      </section>
    </sn-shell>
  `,
  styles: [`
    .profile-layout{display:grid;grid-template-columns:minmax(280px,360px) minmax(0,1fr);gap:1rem;align-items:start}
    .panel-v4{background:linear-gradient(145deg,var(--panel-glow),transparent 32%),var(--surface-1);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow);overflow:hidden}
    .identity-card{position:sticky;top:105px;padding:1.2rem}.identity-head{display:flex;align-items:center;gap:1rem;padding-bottom:1rem;border-bottom:1px solid var(--line)}
    .identity-head img,.avatar-fallback{width:68px;height:68px;border-radius:18px}.identity-head img{object-fit:cover}.avatar-fallback{display:grid;place-items:center;background:var(--primary-soft);border:1px solid var(--line-strong);color:var(--primary);font-size:1.5rem;font-weight:900}
    .eyebrow{color:var(--primary);font-size:.58rem;font-weight:900;letter-spacing:.16em}.identity-head h2,.section-heading h2{margin:.3rem 0 0}.identity-head p,.section-heading p{margin:.35rem 0 0;color:var(--muted);font-size:.75rem;line-height:1.45}
    dl{display:grid;margin:1rem 0 0}dl div{display:grid;grid-template-columns:1fr minmax(0,1.2fr);gap:1rem;padding:.75rem 0;border-bottom:1px solid var(--line)}dt{color:var(--muted);font-size:.67rem}dd{margin:0;text-align:right;font-size:.72rem;font-weight:750;word-break:break-word}.status-value{color:var(--success);text-transform:uppercase}
    .identity-actions{display:grid;grid-template-columns:1fr auto;gap:.55rem;margin-top:1rem}.secondary-action,.danger-action{min-height:40px;display:grid;place-items:center;padding:.6rem .8rem;border-radius:9px;font-size:.68rem;font-weight:850}.secondary-action{background:var(--surface-2);border:1px solid var(--line)}.danger-action{color:#fff;background:rgba(255,111,127,.12);border:1px solid rgba(255,111,127,.25)}
    .settings-stack{display:grid;gap:1rem}.settings-panel{padding:1.2rem}.section-heading{display:flex;justify-content:space-between;gap:1rem;align-items:flex-start;padding-bottom:1rem;border-bottom:1px solid var(--line)}.active-label,.soon{padding:.42rem .58rem;border-radius:999px;font-size:.54rem;font-weight:900;letter-spacing:.09em}.active-label{color:var(--primary);background:var(--primary-soft);border:1px solid var(--line-strong)}.soon{color:var(--muted);background:var(--surface-2);border:1px solid var(--line)}
    .theme-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.65rem;margin-top:1rem}.theme-option{display:grid;grid-template-columns:64px 1fr 22px;align-items:center;gap:.75rem;padding:.75rem;text-align:left;color:var(--text);background:var(--surface-2);border:1px solid var(--line);border-radius:12px;transition:.18s}.theme-option:hover{transform:translateY(-1px);border-color:var(--line-strong)}.theme-option.active{background:var(--primary-soft);border-color:var(--primary)}
    .theme-preview{height:44px;display:grid;grid-template-columns:1.5fr 1fr .55fr;overflow:hidden;border-radius:8px;border:1px solid rgba(255,255,255,.12)}.theme-preview i{display:block}.theme-copy{display:grid;gap:.25rem;min-width:0}.theme-copy strong{display:flex;align-items:center;gap:.45rem;font-size:.75rem}.theme-copy small{color:var(--muted);font-size:.59rem;line-height:1.35}.check{color:var(--primary);font-weight:900;text-align:center}
    .language-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.65rem;margin-top:1rem}
    .language-option{display:grid;grid-template-columns:40px 1fr 20px;align-items:center;gap:.65rem;padding:.75rem;text-align:left;color:var(--text);background:var(--surface-2);border:1px solid var(--line);border-radius:11px}
    .language-option:hover,.language-option.active{border-color:var(--primary);background:var(--primary-soft)}
    .language-option .flag{font-size:1.35rem}.language-option span:nth-child(2){display:grid;gap:.15rem}.language-option small{color:var(--muted);font-size:.58rem}.language-option>b{color:var(--primary)}
    .preference-row{display:grid;grid-template-columns:1fr auto;align-items:center;gap:1rem;padding:.9rem 0;border-bottom:1px solid var(--line)}.preference-row div{display:grid;gap:.25rem}.preference-row strong{font-size:.74rem}.preference-row small{color:var(--muted);font-size:.62rem}.preference-row button{min-width:150px;padding:.6rem .7rem;color:var(--muted);background:var(--surface-2);border:1px solid var(--line);border-radius:9px}
    @media(max-width:950px){.profile-layout{grid-template-columns:1fr}.identity-card{position:static}.theme-grid{grid-template-columns:1fr}}
    @media(max-width:700px){.language-grid{grid-template-columns:1fr}}
    @media(max-width:600px){.theme-option{grid-template-columns:54px 1fr 18px}.section-heading,.preference-row{grid-template-columns:1fr;display:grid}.preference-row button{width:100%}}
  `],
})
export class ProfileComponent {
  readonly initial = computed(() =>
    (this.auth.profile()?.display_name || this.auth.profile()?.login || 'O')
      .slice(0, 1)
      .toUpperCase(),
  );

  readonly activeThemeName = computed(() =>
    this.themes.themes.find((item) => item.id === this.themes.activeTheme())?.name || 'ShieldNet',
  );

  readonly timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';

  constructor(
    public readonly auth: AuthService,
    public readonly themes: ThemeService,
    public readonly i18n: TranslationService,
  ) {}

  async changeLanguage(code: string): Promise<void> {
    await this.i18n.setLocale(code);
  }
}
