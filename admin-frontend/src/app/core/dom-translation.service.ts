import { DOCUMENT } from '@angular/common';
import { Injectable, effect, inject } from '@angular/core';
import { TranslationService } from './translation.service';

/** Translates legacy literal UI text while components migrate to translation keys. */
@Injectable({ providedIn: 'root' })
export class DomTranslationService {
  private readonly document = inject(DOCUMENT);
  private readonly i18n = inject(TranslationService);
  private readonly textSources = new WeakMap<Text, string>();
  private readonly attributeSources = new WeakMap<Element, Map<string, string>>();
  private observer?: MutationObserver;

  constructor() {
    effect(() => {
      this.i18n.locale();
      this.i18n.dictionary();
      queueMicrotask(() => this.translateTree(this.document.body));
    });
  }

  start(): void {
    if (this.observer) return;
    this.translateTree(this.document.body);
    this.observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.type === 'characterData' && mutation.target instanceof Text) {
          this.translateText(mutation.target);
        }
        for (const node of Array.from(mutation.addedNodes)) this.translateTree(node);
      }
    });
    this.observer.observe(this.document.body, { childList: true, subtree: true, characterData: true });
  }

  private translateTree(root: Node): void {
    if (root instanceof Text) this.translateText(root);
    if (!(root instanceof Element || root instanceof Document || root instanceof DocumentFragment)) return;
    if (root instanceof Element) this.translateAttributes(root);
    const walker = this.document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    let node: Node | null;
    while ((node = walker.nextNode())) {
      if (node instanceof Text) this.translateText(node);
      else if (node instanceof Element) this.translateAttributes(node);
    }
  }

  private translateText(node: Text): void {
    const parent = node.parentElement;
    if (!parent || ['SCRIPT', 'STYLE', 'CODE', 'PRE'].includes(parent.tagName)) return;
    const visible = node.data.trim();
    if (!visible) return;
    const saved = this.textSources.get(node);
    const source = saved && this.i18n.hasPhrase(saved) ? saved : visible;
    if (!this.i18n.hasPhrase(source)) return;
    this.textSources.set(node, source);
    const translated = this.i18n.phrase(source);
    const leading = node.data.match(/^\s*/)?.[0] ?? '';
    const trailing = node.data.match(/\s*$/)?.[0] ?? '';
    if (node.data !== `${leading}${translated}${trailing}`) node.data = `${leading}${translated}${trailing}`;
  }

  private translateAttributes(element: Element): void {
    for (const name of ['placeholder', 'title', 'aria-label']) {
      const visible = element.getAttribute(name);
      if (!visible) continue;
      let sources = this.attributeSources.get(element);
      if (!sources) { sources = new Map(); this.attributeSources.set(element, sources); }
      const saved = sources.get(name);
      const source = saved && this.i18n.hasPhrase(saved) ? saved : visible;
      if (!this.i18n.hasPhrase(source)) continue;
      sources.set(name, source);
      const translated = this.i18n.phrase(source);
      if (visible !== translated) element.setAttribute(name, translated);
    }
  }
}
