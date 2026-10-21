import s from './page.module.css';

/** The sample forecast (day 21 of October): running flexible spend against a ₹36,000 plan. Fixed coordinates, made-up numbers. */
const SO_FAR =
  'M52 265.1 L76.9 259.9 L101.9 252 L126.8 248 L151.7 240.9 L176.7 230.1 L201.6 221.5 L226.5 217 L251.5 213 L276.4 206.7 L301.3 203.3 L326.3 198.5 L351.2 191.1 L376.1 186.5 L401.1 176.8 L426 168 L450.9 159.2 L475.9 149 L500.8 140.7 L525.7 125.8 L550.7 122.4';

export function ForecastChart() {
  return (
    <figure className={s.chartBox}>
      <figcaption className={`lbl ${s.chartCap}`}><span>Flexible spending this month · sample data</span><span>so far · at this pace · range</span></figcaption>
      <svg viewBox="0 0 960 310" role="img" aria-label="Running total of flexible spending. At the current pace it reaches the ₹36,000 plan line on Oct 29. The range runs from ₹35,100 at the best week's pace to ₹42,400 at the last seven days' pace.">
        <path className={s.cGrid} d="M52 186.7 H800 M52 101.3 H800 M52 16 H800" />
        <path className={s.cAxis} d="M52 272 H800" />
        <g className={s.cTxt} textAnchor="end"><text x="44" y="276">0</text><text x="44" y="190.7">15K</text><text x="44" y="105.3">30K</text><text x="44" y="20">45K</text></g>
        <path className={s.cBand} d="M550.7 122.4 L800 72.3 L800 30.8 Z" />
        <path className={s.cPlan} d="M52 67.2 H800" />
        <path className={s.cToday} d="M550.7 16 V272" />
        <path className={s.cDash} d="M550.7 122.4 L800 51.1" />
        <path className={s.cLine} d={SO_FAR} />
        <circle className={s.cDot} cx="550.7" cy="122.4" r="4.5" />
        <circle className={s.cRun} cx="743.6" cy="67.2" r="6" />
        <path className={s.cLeader} d="M743.6 74 V102" />
        <g className={s.cTxt}>
          <text x="56" y="60" style={{ fill: 'var(--n-green)' }}>plan ₹36,000</text>
          <text x="544" y="30" textAnchor="end">today · ₹26,300</text>
          <text x="748" y="116" textAnchor="end" style={{ fill: 'var(--n-red)' }}>plan runs out Oct 29</text>
          <text x="808" y="35">₹42,400 last 7 days</text>
          <text x="808" y="55" style={{ fill: '#fff', fontWeight: 500 }}>₹38,830 this month</text>
          <text x="808" y="76">₹35,100 best week</text>
        </g>
        <g className={s.cTxt} textAnchor="middle">
          <text x="52" y="292">Oct 1</text><text x="276.4" y="292">10</text><text x="401.1" y="292">15</text>
          <text x="550.7" y="292" style={{ fill: 'var(--n-green)', fontWeight: 500 }}>21</text><text x="650.4" y="292">25</text><text x="800" y="292">31</text>
        </g>
      </svg>
    </figure>
  );
}
