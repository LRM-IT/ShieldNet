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

@Component({
  selector: 'sn-root',
  standalone: true,
  imports: [RouterOutlet, ModalHostComponent, ToastContainerComponent,CookieBannerComponent],
  template: '<router-outlet /><sn-modal-host /><sn-toast-container /><sn-cookie-banner />',
})
export class AppComponent {
  constructor(
    private readonly auth: AuthService,
    private readonly themes: ThemeService,
    private readonly i18n: TranslationService,
    private readonly domTranslation: DomTranslationService,
    private readonly seo: SeoService,
  ) {
    this.themes.apply(this.themes.theme());
    void this.initialize();
  }
  private async initialize():Promise<void>{void this.seo.apply();let profile=this.auth.profile();if(!profile&&this.auth.accessToken){try{profile=await this.auth.loadProfile()}catch{}}await this.i18n.initialize(profile?.preferred_locale);this.domTranslation.start()}
}
