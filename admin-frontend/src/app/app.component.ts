import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { ModalHostComponent } from './shared/modal-host.component';
import { ToastContainerComponent } from './shared/toast-container.component';

import { AuthService } from './core/auth.service';
import { ThemeService } from './core/theme.service';
import { TranslationService } from './core/translation.service';
import { DomTranslationService } from './core/dom-translation.service';
import { SeoService } from './core/seo.service';
import { CookieBannerComponent } from './shared/cookie-banner.component';
import { MaintenanceService } from './core/maintenance.service';

@Component({
  selector: 'sn-root',
  standalone: true,
  imports: [RouterOutlet, ModalHostComponent, ToastContainerComponent,CookieBannerComponent],
  template: `
    @if (maintenance.mode() === 'maintenance') {
      <div class="system-mode-banner maintenance">TECHNICAL MAINTENANCE IS IN PROGRESS</div>
    } @else if (maintenance.mode() === 'testing') {
      <div class="system-mode-banner testing">THE SYSTEM IS OPERATING IN TEST MODE</div>
    }
    <router-outlet /><sn-modal-host /><sn-toast-container /><sn-cookie-banner />
  `,
  styles: [`
    .system-mode-banner{position:sticky;top:0;z-index:10000;min-height:34px;display:flex;align-items:center;justify-content:center;padding:.45rem 1rem;text-align:center;font-size:.68rem;font-weight:900;letter-spacing:.12em}
    .system-mode-banner.maintenance{color:#fff;background:#b31731;box-shadow:0 3px 18px rgba(179,23,49,.42)}
    .system-mode-banner.testing{color:#211500;background:#f6bd45;box-shadow:0 3px 18px rgba(246,189,69,.3)}
  `],
})
export class AppComponent {
  constructor(
    private readonly auth: AuthService,
    private readonly themes: ThemeService,
    private readonly i18n: TranslationService,
    private readonly domTranslation: DomTranslationService,
    private readonly seo: SeoService,
    readonly maintenance: MaintenanceService,
  ) {
    this.themes.apply(this.themes.theme());
    void this.initialize();
  }
  private async initialize():Promise<void>{
    void this.maintenance.load();
    const publicPaths=new Set(['/','/login','/docs','/pricing','/privacy','/privacy-policy','/merchant-information','/terms','/refund','/payment','/contacts']);
    const publicLocale=publicPaths.has(window.location.pathname.replace(/\/$/,'')||'/')?'uk':null;
    let profile=this.auth.profile();
    if(!profile&&!publicLocale&&this.auth.accessToken){try{profile=await this.auth.loadProfile()}catch{}}
    await this.i18n.initialize(publicLocale||profile?.preferred_locale);
    await this.seo.apply(this.i18n.locale());
    this.domTranslation.start()
  }
}
