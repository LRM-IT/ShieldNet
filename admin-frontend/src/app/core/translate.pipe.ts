import { Pipe, PipeTransform } from '@angular/core';
import { TranslationService } from './translation.service';

@Pipe({
  name: 'snT',
  standalone: true,
  pure: false,
})
export class TranslatePipe implements PipeTransform {
  constructor(private readonly i18n: TranslationService) {}

  transform(key: string, fallback = ''): string {
    return this.i18n.t(key, fallback);
  }
}
