import type { Metadata } from 'next';
import Link from 'next/link';
import { BRAND, Logo } from '@/brand';
import { calendar } from '@/features/month';
import { AccountLinks } from './account-links';
import { DemoButton } from './demo-button';
import { ForecastChart } from './forecast-chart';
import { Hero } from './hero';
import s from './page.module.css';

export const landingMetadata: Metadata = { title: `${BRAND.name}: ${BRAND.tagline.toLowerCase()}`, description: 'Log a payment in Telegram. LBStash saves it, tags it and shows the day your plan runs out, before the month ends.' };

const KEEPS = [
  { name: 'Two-step sign-in', text: 'An authenticator app is required. Passkeys and recovery codes are supported.' },
  { name: 'Walled-off data', text: 'Row-level security on user tables, and one database login and schema per service.' },
  { name: 'Encrypted secrets', text: 'AES-256-GCM for secrets, Argon2id for passwords, tokens stored only as hashes.' },
  { name: 'Allowed addresses, a locked bot', text: 'Limit the web app to your IPs. Only your Telegram account can link, and your message is deleted once read.' },
  { name: 'Yours to take', text: 'Export your data any time. Delete the account and it goes after a 7-day grace period.' },
];

const NEVER = [
  { k: 'Bank login', w: '100%' }, { k: 'UPI PIN', w: '38%' }, { k: 'Card number', w: '100%' }, { k: 'OTP', w: '48%' }, { k: 'Moves money', w: '28%' },
];

/** One sample day of the sample month. The numbers are made up and add up to the example above. */
function Day({ n, day, title, children, visual }: { n: string; day: string; title: string; children: React.ReactNode; visual: React.ReactNode }) {
  return (
    <article className={s.ev}>
      <div><div className={`mono ${s.evNum}`}>{n}</div><span className={`lbl ${s.evDay}`}>{day}</span></div>
      <div><h3>{title}</h3><p>{children}</p></div>
      <div className={s.vis}>{visual}</div>
    </article>
  );
}

export function Landing() {
  return (
    <div className={s.page}>
      <header className={s.top}>
        <div className={`${s.wrap} ${s.topRow}`}>
          <Link href="/" aria-label={`${BRAND.name}, home`}><Logo size={28} /></Link>
          <nav className={s.topNav} aria-label="Main">
            <a href="#month" className={`${s.topLink} ${s.topJump}`}>A month in {BRAND.name}</a>
            <a href="#private" className={`${s.topLink} ${s.topJump}`}>What it never sees</a>
            <AccountLinks linkClass={s.topLink ?? ''} demoClass={s.topDemo ?? ''} />
          </nav>
        </div>
      </header>

      <main>
        <Hero />

        <section id="month" className={s.story} aria-labelledby="story-h">
          <div className={s.spine} aria-hidden="true" />
          <div className={s.wrap}>
            <div className={s.storyHead}>
              <div><div className="lbl">A month in {BRAND.name}</div><h2 id="story-h" className={s.h2}>One month, <b>told in days.</b></h2></div>
              <p className={s.sub}>Every feature here is a thing that happened to someone on a particular day. This is that month, with sample data.</p>
            </div>

            <Day
              n="01" day="Day of the month" title="Salary lands."
              visual={
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 14 }}>
                  <div className={`mono ${s.sms}`} style={{ flex: '1 1 240px' }}>HDFCBK: Rs 85,000.00 credited to a/c XX4321 by ACME TECHNOLOGIES.</div>
                  <span className="mono" style={{ color: 'var(--accent)', fontSize: 20 }} aria-hidden="true">→</span>
                  <div><div className={s.big}>+85,000</div><span className={`mono ${s.chip}`} data-g="true" style={{ marginTop: 8 }}>#salary</span></div>
                </div>
              }
            >
              If you let bank messages in, it reads them. A credit becomes income, tagged <span className="mono">#salary</span>, with no typing.
            </Day>

            <Day
              n="05" day="Day of the month" title="Rent leaves by itself."
              visual={
                <div className={s.stems} role="img" aria-label="Repeats on a month line: rent 24,000 on day 5, SIP 15,000 on day 28">
                  <div className={s.stem} style={{ left: '8%', height: 112 }} /><span className={`mono ${s.stemLbl}`} style={{ left: 'calc(8% + 18px)', top: -4 }}>Rent −24,000</span>
                  <div className={s.stem} style={{ left: '46%', height: 30 }} /><span className={`mono ${s.stemLbl}`} style={{ left: 'calc(46% + 12px)', bottom: 34 }}>SIP −15,000 · day 28</span>
                </div>
              }
            >
              Repeats post on the due date and count as committed from day one, so the rest of the month is honest.
            </Day>

            <Day
              n="09" day="Day of the month" title="A payment it doesn’t know yet."
              visual={
                <div style={{ border: '1px solid var(--ink)', padding: '16px 18px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}><b style={{ fontWeight: 500, fontSize: 17 }}>UPI · RAMESH K</b><span className="mono">−1,200</span></div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 12, flexWrap: 'wrap' }}><span className={s.fix}>needs a tag</span><span className={`mono ${s.chip}`} data-g="true">#other</span><span className="mono" style={{ fontSize: 13, color: 'var(--accent)' }}>remembered</span></div>
                </div>
              }
            >
              It waits for you instead of guessing. Tag it once and every later payment from that name is sorted for you.
            </Day>

            <Day
              n="12" day="Day of the month" title="Three seconds, from Telegram."
              visual={<div className={s.msgs}><div className={`mono ${s.msg}`} data-who="me">/350 food</div><div className={s.msg} data-who="bot">Logged <b className="mono">₹350</b> in <b className="mono">#food</b>. Safe to spend today: ₹880.</div></div>}
            >
              You do not open an app to log a coffee. Type the amount and a word. It replies with what is safe to spend today.
            </Day>

            <Day
              n="18" day="Day of the month" title="Shopping crosses 80%."
              visual={
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}><b style={{ fontWeight: 500 }}>Shopping</b><span className="mono" style={{ fontSize: 13 }}>5,650 of 7,000</span></div>
                  <div className={s.limTrack}><div className={s.limFill} style={{ width: '56.5%' }} /><div className={s.limHatch} style={{ left: '56.5%', width: '38%' }} /><div className={s.limTick} /></div>
                  <div className={s.limNote}><b style={{ fontWeight: 500 }}>Hits the limit on day 23</b> <span>· in 5 days</span></div>
                </div>
              }
            >
              A limit warns you early and says which day it will be hit at your pace, not just that it is close.
            </Day>

            <Day
              n="20" day="Day of the month" title="The bank says ₹850 less."
              visual={
                <div className={`mono ${s.tally}`}>
                  <div className={s.tallyRow}><span>bank says</span><span>38,251</span></div>
                  <div className={s.tallyRow}><span>app says</span><span>39,101</span></div>
                  <div className={s.tallyRow} style={{ borderBottom: 0, fontWeight: 500 }}><span style={{ color: 'inherit' }}>Unaccounted</span><span style={{ color: 'var(--danger)' }}>−850</span></div>
                </div>
              }
            >
              Check against your bank balance. A gap is never hidden: it becomes an entry you tag or split.
            </Day>
          </div>
        </section>

        <section className={s.night} aria-labelledby="fc-h">
          <div className={`${s.wrap} ${s.nightWrap}`}>
            <div className={s.climax}>
              <div><div className="lbl">Day of the month</div><div className={`mono ${s.giant21}`}>21</div></div>
              <div className={s.climaxText}>
                <div className="lbl">Today</div>
                <h2 id="fc-h" className={s.h2}>The plan runs out <b style={{ color: 'var(--n-red)' }}>on day 29.</b> Two days early.</h2>
                <p className={s.sub} style={{ marginTop: 20, maxWidth: 560 }}>That is the whole point. Not what you spent, but what your pace does to the rest of the month, while there is still time to change it.</p>
              </div>
            </div>
            <div className={s.fcGrid}>
              <ForecastChart />
              <div className={s.stats}>
                <div className={s.stat}><div className="lbl">Spend ₹880 a day, not ₹1,250</div><div className={s.statV} style={{ color: 'var(--n-green)' }}>and it lasts</div><div className={`mono ${s.statN}`}>the plan survives to the last day</div></div>
                <div className={s.stat}><div className="lbl">Month ends with</div><div className={s.statV}>₹10,040</div><div className={`mono ${s.statN}`}>between ₹6,470 and ₹13,770</div></div>
                <div className={s.stat}><div className="lbl">Breaks first</div><div className={s.statV}>Shopping</div><div className={`mono ${s.statN}`}>limit hit on day 23</div></div>
              </div>
            </div>
          </div>
        </section>

        <section id="private" className={`${s.wrap} ${s.redact}`} aria-labelledby="priv-h">
          <div className="lbl">What it never sees</div>
          <h2 id="priv-h" className={s.h2}>Some things <b>stay blacked out.</b></h2>
          <div className={s.redGrid}>
            <figure className={s.doc} aria-label="Never collected: bank login, UPI PIN, card number, OTP. The app never moves money.">
              <div className={s.docHead}><span className="lbl">{BRAND.name} · collected from you</span><span className="lbl">page 1 of 1</span></div>
              {NEVER.map((x) => (
                <div key={x.k} className={s.line}><span className={`mono ${s.lineK}`}>{x.k}</span><span className={s.lineBar} style={{ maxWidth: x.w }} /><span className={`mono ${s.lineSt}`}>NEVER</span></div>
              ))}
            </figure>
            <ol className={s.keeps}>
              {KEEPS.map((k, i) => (
                <li key={k.name} className={s.keep}><span className={`mono ${s.keepN}`}>{String(i + 1).padStart(2, '0')}</span><div><h3>{k.name}</h3><p>{k.text}</p></div></li>
              ))}
            </ol>
          </div>
        </section>

        <section className={s.band} aria-labelledby="demo-h">
          <div className={`${s.wrap} ${s.bandWrap}`}>
            <div style={{ flex: '1 1 520px', minWidth: 0 }}>
              <div className="lbl">No account. No card. Read-only.</div>
              <h2 id="demo-h">Step into <b>a month.</b></h2>
              <p>Six months of sample payments, a plan, limits and a forecast, in a copy you cannot break. Like it? Make your own account. It starts empty and private.</p>
              <div className={s.actions}>
                <DemoButton className={`${s.bigBtn} ${s.bandBtn}`} />
                <Link href="/create-account" className={`ghost ${s.bigGhost} ${s.bandGhost}`}>Create account</Link>
              </div>
            </div>
            <div className={`mono ${s.cal}`} role="img" aria-label="A sample month as a grid of days. Days up to the 21st are logged, the rest is forecast.">
              {calendar().map((c) => <span key={c.day} className={s.calC} data-s={c.state}>{c.day}</span>)}
            </div>
          </div>
        </section>

        <section className={`${s.wrap} ${s.about}`} aria-labelledby="about-h">
          <div className={`lbl ${s.aboutLbl}`} id="about-h">About</div>
          <p className={s.aboutText}>
            LBStash is a small personal-finance project: a Next.js web app, eight small backend services and a Telegram bot, run on your own server. By default one server holds one account, so this page and the demo are for looking around before you make yours.
          </p>
        </section>
      </main>

      <footer className={`${s.night} ${s.foot}`}>
        <div className={s.wrap}>
          <div className={s.footRow}>
            <span className="mono" style={{ color: 'var(--n-dim)', fontSize: 13 }}>{BRAND.tagline}</span>
            <nav className={s.footNav} aria-label="Footer">
              <Link href="/sign-in">Sign in</Link>
              <Link href="/create-account">Create account</Link>
              <DemoButton link>Try the demo</DemoButton>
            </nav>
          </div>
          <div className={s.giant} aria-hidden="true">{BRAND.wordmark.slice(0, 2)}<b>{BRAND.wordmark.slice(2)}</b></div>
        </div>
      </footer>
    </div>
  );
}
