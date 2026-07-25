import { Component, signal } from '@angular/core';

import { AuthService } from '../core/auth.service';
import { TranslatePipe } from '../core/translate.pipe';
import { TranslationService } from '../core/translation.service';

@Component({
  standalone: true,
  imports: [TranslatePipe],
  template: `
    <main class="access-page">
      <section class="visual-zone">
        <div class="grid-field"></div>
        <div class="orbit orbit-one"></div>
        <div class="orbit orbit-two"></div>

        <div class="visual-content">
          <a class="brand" href="/" aria-label="ShieldNet">
            <span class="brand-symbol">
              <i></i><i></i><i></i>
            </span>
            <span>
              <strong>SHIELDNET</strong>
              <small>{{ "login.brand_subtitle" | snT:"SECURE CONTROL FABRIC" }}</small>
            </span>
          </a>

          <div class="hero">
            <div class="classification">{{ "login.classification" | snT:"RESTRICTED SYSTEM · AUTHORIZED OPERATORS ONLY" }}</div>
            <h1>
              {{ "login.hero_line_1" | snT:"Command your" }}
              <span>{{ "login.hero_line_2" | snT:"Discord infrastructure." }}</span>
            </h1>
            <p>
              {{ "login.hero_description" | snT:"One hardened control surface for servers, identities, automation, security policy and plugin runtimes." }}
            </p>

            <div class="capabilities">
              <article>
                <strong>{{ "login.identity" | snT:"IDENTITY" }}</strong>
                <span>{{ "login.identity_desc" | snT:"Discord OAuth and scoped access" }}</span>
              </article>
              <article>
                <strong>{{ "login.control" | snT:"CONTROL" }}</strong>
                <span>{{ "login.control_desc" | snT:"Live server and module operations" }}</span>
              </article>
              <article>
                <strong>{{ "login.observe" | snT:"OBSERVE" }}</strong>
                <span>{{ "login.observe_desc" | snT:"Health, audit and runtime telemetry" }}</span>
              </article>
            </div>
          </div>

          <div class="visual-footer">
            <span><i></i> {{ "login.online" | snT:"CONTROL PLANE ONLINE" }}</span>
            <span>SHIELDNET // LRM-IT</span>
          </div>
        </div>
      </section>

      <section class="access-zone">
        <div class="access-card">
          <div class="access-header">
            <div class="terminal-mark">SN</div>
            <div>
              <div class="eyebrow">{{ "login.gateway" | snT:"SECURE ACCESS GATEWAY" }}</div>
              <h2>{{ "login.heading" | snT:"Operator authentication" }}</h2>
            </div>
          </div>

          <p class="intro">
            {{ "login.intro" | snT:"Continue through Discord to verify your identity and server permissions." }}
          </p>

          <div class="security-status">
            <div>
              <span class="status-dot"></span>
              <strong>{{ "login.oauth_ready" | snT:"OAuth gateway ready" }}</strong>
            </div>
            <small>{{ "login.encrypted" | snT:"Encrypted redirect · permission-scoped session" }}</small>
          </div>

          <button
            class="discord-login"
            type="button"
            [disabled]="loading()"
            (click)="login()"
          >
            <span class="discord-icon">⌁</span>
            <span>
              <strong>{{ loading() ? ('login.establishing' | snT:'Establishing secure session…') : ('login.continue' | snT:'Continue with Discord') }}</strong>
              <small>{{ loading() ? ('login.do_not_close' | snT:'Do not close this window') : ('login.authenticate' | snT:'Authenticate authorized operator') }}</small>
            </span>
            <b>→</b>
          </button>

          @if (error()) {
            <div class="error">
              <strong>{{ "login.failure" | snT:"ACCESS FAILURE" }}</strong>
              <span>{{ error() }}</span>
            </div>
          }

          <div class="trust-grid">
            <div><span>01</span><p>{{ "login.step_1" | snT:"Discord verifies your account." }}</p></div>
            <div><span>02</span><p>{{ "login.step_2" | snT:"ShieldNet checks server access." }}</p></div>
            <div><span>03</span><p>{{ "login.step_3" | snT:"A scoped console session is issued." }}</p></div>
          </div>

          <footer>
            <span>{{ "login.footer" | snT:"By continuing, you enter a monitored administrative environment." }}</span>
            <span class="build">{{ "login.build" | snT:"BUILD 2.0 // SECURE" }}</span>
          </footer>
        </div>
      </section>
    </main>
  `,
  styles: [`
    .access-page{
      min-height:100vh;
      display:grid;
      grid-template-columns:minmax(0,1.15fr) minmax(420px,.85fr);
      background:#05080d
    }

    .visual-zone{
      position:relative;
      min-height:100vh;
      overflow:hidden;
      background:
        radial-gradient(circle at 20% 22%,rgba(53,226,178,.13),transparent 22rem),
        radial-gradient(circle at 85% 72%,rgba(45,128,154,.13),transparent 26rem),
        linear-gradient(145deg,#08121a,#05080d 62%)
    }

    .visual-zone::after{
      content:"";
      position:absolute;
      width:520px;
      height:520px;
      right:-210px;
      top:16%;
      border:1px solid rgba(53,226,178,.12);
      border-radius:50%;
      box-shadow:
        0 0 0 60px rgba(53,226,178,.018),
        0 0 0 120px rgba(53,226,178,.012)
    }

    .grid-field{
      position:absolute;
      inset:0;
      background:
        linear-gradient(rgba(78,195,174,.04) 1px,transparent 1px),
        linear-gradient(90deg,rgba(78,195,174,.04) 1px,transparent 1px);
      background-size:40px 40px;
      mask-image:linear-gradient(135deg,black,transparent 80%)
    }

    .orbit{
      position:absolute;
      border:1px solid rgba(53,226,178,.11);
      border-radius:50%
    }

    .orbit-one{width:360px;height:360px;left:-170px;bottom:-100px}
    .orbit-two{width:180px;height:180px;right:14%;top:9%}

    .visual-content{
      position:relative;
      z-index:2;
      min-height:100vh;
      display:flex;
      flex-direction:column;
      padding:2.1rem 2.5rem
    }

    .brand{
      display:flex;
      align-items:center;
      gap:.85rem;
      width:max-content
    }

    .brand-symbol{
      position:relative;
      width:42px;
      height:42px;
      display:grid;
      place-items:center;
      border:1px solid rgba(53,226,178,.36);
      border-radius:11px;
      transform:rotate(45deg);
      background:rgba(53,226,178,.07)
    }

    .brand-symbol i{
      position:absolute;
      height:2px;
      border-radius:10px;
      background:var(--primary);
      box-shadow:0 0 9px rgba(53,226,178,.65);
      transform:rotate(-45deg)
    }

    .brand-symbol i:nth-child(1){width:19px;transform:translateY(-6px) rotate(-45deg)}
    .brand-symbol i:nth-child(2){width:26px}
    .brand-symbol i:nth-child(3){width:12px;transform:translateY(6px) rotate(-45deg)}

    .brand>span:last-child{display:grid;gap:.12rem}
    .brand strong{font-size:.94rem;letter-spacing:.16em}
    .brand small{color:#66808e;font-size:.58rem;letter-spacing:.17em}

    .hero{
      width:min(680px,100%);
      margin:auto 0;
      padding:4rem 0
    }

    .classification{
      width:max-content;
      max-width:100%;
      padding:.45rem .65rem;
      color:#87b8ac;
      border-left:2px solid var(--primary);
      background:rgba(53,226,178,.045);
      font-size:.6rem;
      font-weight:850;
      letter-spacing:.14em
    }

    h1{
      max-width:720px;
      margin:1.4rem 0 1rem;
      font-size:clamp(2.7rem,5vw,5.8rem);
      line-height:.96;
      letter-spacing:-.055em;
      font-weight:780
    }

    h1 span{
      display:block;
      color:transparent;
      background:linear-gradient(110deg,#dffdf5 5%,var(--primary) 70%);
      background-clip:text
    }

    .hero>p{
      max-width:620px;
      color:#8ca0ad;
      font-size:1rem;
      line-height:1.75
    }

    .capabilities{
      display:grid;
      grid-template-columns:repeat(3,1fr);
      gap:.65rem;
      margin-top:2.2rem
    }

    .capabilities article{
      min-height:108px;
      display:flex;
      flex-direction:column;
      justify-content:flex-end;
      gap:.45rem;
      padding:1rem;
      background:linear-gradient(145deg,rgba(255,255,255,.025),rgba(10,17,24,.5));
      border:1px solid rgba(129,170,176,.12);
      border-radius:12px
    }

    .capabilities strong{
      color:var(--primary);
      font-size:.62rem;
      letter-spacing:.16em
    }

    .capabilities span{
      color:#82939f;
      font-size:.72rem;
      line-height:1.45
    }

    .visual-footer{
      display:flex;
      justify-content:space-between;
      gap:1rem;
      color:#516572;
      font-size:.57rem;
      font-weight:800;
      letter-spacing:.13em
    }

    .visual-footer span:first-child{display:flex;align-items:center;gap:.5rem}
    .visual-footer i{
      width:.45rem;
      height:.45rem;
      border-radius:50%;
      background:var(--success);
      box-shadow:0 0 12px rgba(57,221,161,.75)
    }

    .access-zone{
      min-height:100vh;
      display:grid;
      place-items:center;
      padding:2rem;
      background:
        linear-gradient(180deg,rgba(255,255,255,.012),transparent 40%),
        #070b11;
      border-left:1px solid var(--line)
    }

    .access-card{
      width:min(470px,100%);
      padding:2rem
    }

    .access-header{
      display:grid;
      grid-template-columns:auto 1fr;
      align-items:center;
      gap:.9rem
    }

    .terminal-mark{
      width:48px;
      height:48px;
      display:grid;
      place-items:center;
      color:#06120f;
      background:var(--primary);
      border-radius:10px;
      font-size:.78rem;
      font-weight:950;
      letter-spacing:.08em;
      box-shadow:0 0 36px rgba(53,226,178,.18)
    }

    .eyebrow{
      color:#668090;
      font-size:.58rem;
      font-weight:900;
      letter-spacing:.16em
    }

    h2{margin:.3rem 0 0;font-size:1.35rem}
    .intro{margin:1.5rem 0;color:var(--muted);line-height:1.7}

    .security-status{
      display:grid;
      gap:.4rem;
      padding:.85rem 0;
      border-top:1px solid var(--line);
      border-bottom:1px solid var(--line)
    }

    .security-status>div{display:flex;align-items:center;gap:.55rem}
    .security-status strong{font-size:.75rem}
    .security-status small{padding-left:1rem;color:#5f7380;font-size:.65rem}

    .status-dot{
      width:.45rem;
      height:.45rem;
      border-radius:50%;
      background:var(--success);
      box-shadow:0 0 10px rgba(57,221,161,.7)
    }

    .discord-login{
      width:100%;
      min-height:72px;
      margin:1.3rem 0;
      display:grid;
      grid-template-columns:auto 1fr auto;
      align-items:center;
      gap:.8rem;
      padding:.8rem 1rem;
      text-align:left;
      color:#03130e;
      background:linear-gradient(110deg,var(--primary),#7cefd2);
      border:1px solid rgba(255,255,255,.25);
      border-radius:12px;
      box-shadow:0 18px 45px rgba(53,226,178,.13);
      transition:.18s
    }

    .discord-login:hover:not(:disabled){transform:translateY(-2px);filter:brightness(1.04)}
    .discord-login:disabled{opacity:.65;cursor:wait}

    .discord-icon{
      width:38px;
      height:38px;
      display:grid;
      place-items:center;
      color:#dffcf5;
      background:#071b16;
      border-radius:9px;
      font-size:1.2rem
    }

    .discord-login>span:nth-child(2){display:grid;gap:.18rem}
    .discord-login strong{font-size:.82rem}
    .discord-login small{opacity:.68;font-size:.62rem}
    .discord-login b{font-size:1.1rem}

    .error{
      display:grid;
      gap:.25rem;
      margin-bottom:1rem;
      padding:.8rem;
      color:#ffd7dc;
      background:rgba(255,111,127,.07);
      border:1px solid rgba(255,111,127,.28);
      border-radius:10px
    }

    .error strong{font-size:.6rem;letter-spacing:.12em}
    .error span{font-size:.72rem}

    .trust-grid{
      display:grid;
      gap:.65rem;
      margin-top:1.4rem
    }

    .trust-grid>div{
      display:grid;
      grid-template-columns:30px 1fr;
      align-items:center;
      gap:.65rem
    }

    .trust-grid span{
      color:#4f6b77;
      font-family:ui-monospace,SFMono-Regular,Consolas,monospace;
      font-size:.65rem
    }

    .trust-grid p{
      margin:0;
      color:#768a97;
      font-size:.72rem
    }

    footer{
      display:grid;
      gap:.75rem;
      margin-top:2rem;
      padding-top:1rem;
      color:#536570;
      border-top:1px solid var(--line);
      font-size:.6rem;
      line-height:1.55
    }

    .build{color:#6f8b87;font-weight:850;letter-spacing:.12em}

    @media(max-width:1000px){
      .access-page{grid-template-columns:1fr}
      .visual-zone{min-height:auto}
      .visual-content{min-height:auto}
      .hero{padding:5rem 0}
      .access-zone{min-height:auto;border-left:0;border-top:1px solid var(--line)}
    }

    @media(max-width:650px){
      .visual-content{padding:1.4rem}
      .hero{padding:4rem 0 3rem}
      h1{font-size:2.8rem}
      .capabilities{grid-template-columns:1fr}
      .capabilities article{min-height:auto}
      .visual-footer{align-items:flex-start;flex-direction:column}
      .access-zone{padding:1rem}
      .access-card{padding:1rem 0}
    }
  `],
})
export class LoginComponent {
  readonly loading = signal(false);
  readonly error = signal('');

  constructor(private readonly auth: AuthService, private readonly i18n: TranslationService) {}

  async login(): Promise<void> {
    this.loading.set(true);
    this.error.set('');

    try {
      await this.auth.startDiscordLogin();
    } catch (error) {
      this.error.set(
        error instanceof Error ? error.message : 'Discord login failed.',
      );
    } finally {
      this.loading.set(false);
    }
  }
}
