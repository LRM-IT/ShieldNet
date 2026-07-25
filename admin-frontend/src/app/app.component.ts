import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { ModalHostComponent } from './shared/modal-host.component';
import { ToastContainerComponent } from './shared/toast-container.component';

import { AuthService } from './core/auth.service';
import { ThemeService } from './core/theme.service';
import { TranslationService } from './core/translation.service';

@Component({
  selector: 'sn-root',
  standalone: true,
  imports: [RouterOutlet, ModalHostComponent, ToastContainerComponent],
  template: '<router-outlet /><sn-modal-host /><sn-toast-container />',
})
export class AppComponent {
  constructor(
    private readonly auth: AuthService,
    private readonly themes: ThemeService,
    private readonly i18n: TranslationService,
  ) {
    this.themes.apply(this.themes.theme());
    void this.i18n.initialize(this.auth.profile()?.preferred_locale);
  }
}
