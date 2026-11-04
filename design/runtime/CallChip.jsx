// Port of React Bits CallChip (JS + CSS). Hugeicons replaced with inline stroke icons (no npm here).
const { useEffect, useLayoutEffect, useRef, useState } = React;
if (!document.getElementById('call-chip-css')) {
  const st = document.createElement('style'); st.id = 'call-chip-css';
  st.textContent = `.call-chip{--cc-ease-out:cubic-bezier(0.23,1,0.32,1);flex:none;position:relative;display:inline-flex;align-items:center;gap:var(--cc-gap);box-sizing:border-box;height:var(--cc-size);padding:0 var(--cc-pad);border-radius:var(--cc-radius);overflow:hidden;background:var(--cc-surface);color:var(--cc-color);font-size:var(--cc-font);line-height:1;white-space:nowrap;user-select:none;transition:transform 160ms var(--cc-ease-out)}
.call-chip[data-status='error']{cursor:pointer}.call-chip[data-pressed]{transform:scale(0.97)}
.call-chip__fill{position:absolute;inset:0;background:color-mix(in srgb,var(--cc-progress) var(--cc-progress-pct),transparent);transform:scaleX(0);transform-origin:left center;clip-path:inset(0 0 0 0);pointer-events:none}
.call-chip[data-status='running'] .call-chip__fill{transition:transform var(--cc-expected) linear}
.call-chip[data-status='done'] .call-chip__fill{background:color-mix(in srgb,var(--cc-done) var(--cc-wash-pct),transparent);clip-path:inset(100% 0 0 0);transition:transform 200ms var(--cc-ease-out),background-color 120ms ease,clip-path 400ms var(--cc-ease-out) 200ms}
.call-chip[data-status='error'] .call-chip__fill{background:color-mix(in srgb,var(--cc-error) var(--cc-wash-pct),transparent);transition:background-color 200ms ease}
.call-chip:not([data-mounted]) .call-chip__fill,.call-chip:not([data-mounted]) .call-chip__glyph{transition:none!important}
.call-chip__slot{position:relative;flex:none;width:calc(var(--cc-font) + 2px);height:calc(var(--cc-font) + 2px);overflow:hidden}
.call-chip__glyph{position:absolute;inset:0;display:grid;place-items:center;opacity:0;transform:translateY(70%);filter:blur(3px)}
.call-chip__glyph[data-state='in']{opacity:1;transform:none;filter:blur(0);transition:opacity 240ms var(--cc-ease-out),transform 240ms var(--cc-ease-out),filter 240ms var(--cc-ease-out)}
.call-chip__glyph[data-state='out']{transform:translateY(-70%);transition:opacity 160ms var(--cc-ease-out),transform 160ms var(--cc-ease-out),filter 160ms var(--cc-ease-out)}
.call-chip[data-status='done'] .call-chip__glyph[data-state='in']{color:var(--cc-done)}.call-chip[data-status='error'] .call-chip__glyph[data-state='in']{color:var(--cc-error)}
.call-chip__name,.call-chip__arg,.call-chip__timer{position:relative}.call-chip__name{font-weight:500}.call-chip__arg{opacity:0.72}
.call-chip__timer{min-width:6ch;font-variant-numeric:tabular-nums;text-align:right;opacity:0.5}
.call-chip__retry{position:absolute;inset:-5px;margin:0;padding:0;border:0;border-radius:var(--cc-radius);background:transparent;appearance:none;cursor:pointer;outline:none}
.call-chip__sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
@media (prefers-reduced-motion:reduce){.call-chip[data-status='done'] .call-chip__fill{clip-path:inset(0 0 0 0);transition:background-color 120ms ease}.call-chip__glyph{transform:none!important;filter:none!important}.call-chip[data-pressed]{transform:none}}`;
  document.head.appendChild(st);
}
const PATHS = {
  terminal: ['M4 17l6-5-6-5', 'M12 19h8'],
  file: ['M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z', 'M14 3v5h5'],
  search: ['M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z', 'M20 20l-3.5-3.5'],
  edit: ['M12 20h9', 'M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z'],
  calendar: ['M5 4h14a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z', 'M16 2v4M8 2v4M3 10h18'],
  check: ['M5 12.5l4.5 4.5L19 7.5'],
  retry: ['M20 11a8 8 0 1 0-2.3 5.7', 'M20 5v6h-6']
};
const Ico = ({ k, size, w }) => React.createElement('svg', { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: w, strokeLinecap: 'round', strokeLinejoin: 'round' }, PATHS[k].map((d, i) => React.createElement('path', { key: i, d })));
const HOLD_AT = 0.9, SHAKE = [0, -1, 1, -0.66, 0.66, -0.33, 0];
const WORDS = { running: '진행 중', done: '완료', error: '실패', idle: '대기' };
const fmt = ms => (ms < 10000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`);
const reduceMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
const glyphOf = s => (s === 'done' ? 'check' : s === 'error' ? 'retry' : 'tool');

function CallChip({ icon = 'terminal', name = 'bash', argument = 'npm test', status = 'running', expectedMs = 2500, size = 34, radius = 10, color = 'currentColor', surfaceColor = '#27272a', progressColor = 'currentColor', progressOpacity = 0.08, doneColor = '#22c55e', errorColor = '#ef4444', washOpacity = 0.14, shake = 6, showTimer = true, onRetry, className = '', style }) {
  const rootRef = useRef(null), fillRef = useRef(null), timerRef = useRef(null), mountedRef = useRef(false), fraction = useRef(0), clock = useRef({ ms: 0 }), shakeAnim = useRef(null), statusRef = useRef(status);
  statusRef.current = status;
  const [mounted, setMounted] = useState(false), [pressed, setPressed] = useState(false), [announce, setAnnounce] = useState('');
  const roll = useRef({ cur: glyphOf(status), prev: null });
  if (glyphOf(status) !== roll.current.cur) roll.current = { cur: glyphOf(status), prev: roll.current.cur };
  const setFraction = (f, instant) => { const fill = fillRef.current; if (!fill) return; fraction.current = f; if (instant) fill.style.transition = 'none'; fill.style.transform = `scaleX(${f})`; if (instant) { void fill.getBoundingClientRect(); fill.style.transition = ''; } };
  const apply = (s, animate) => {
    if (s === 'running') { shakeAnim.current?.cancel(); setFraction(0, true); if (animate) setFraction(HOLD_AT, false); }
    else if (s === 'done') setFraction(1, !animate);
    else if (s === 'error') { const fill = fillRef.current; const live = fill ? new DOMMatrix(getComputedStyle(fill).transform).a : fraction.current; setFraction(Math.min(1, Math.max(0, live)), true);
      if (animate && shake > 0 && !reduceMotion() && rootRef.current) shakeAnim.current = rootRef.current.animate(SHAKE.map(k => ({ transform: `translateX(${k * shake}px)`, easing: 'cubic-bezier(0.77, 0, 0.175, 1)' })), { duration: 450, composite: 'add' }); }
    else setFraction(0, true);
  };
  useEffect(() => { mountedRef.current = true; setMounted(true); apply(statusRef.current, statusRef.current === 'running'); return () => { mountedRef.current = false; shakeAnim.current?.cancel(); }; }, []);
  useLayoutEffect(() => { if (mountedRef.current) apply(status, true); }, [status]);
  useEffect(() => {
    const write = ms => { clock.current.ms = ms; if (timerRef.current) timerRef.current.textContent = fmt(ms); };
    if (status !== 'running') { if ((status === 'idle' || !clock.current.ms) && timerRef.current) timerRef.current.textContent = '–'; return undefined; }
    const t0 = performance.now(); write(0);
    if (reduceMotion()) { const id = setInterval(() => write(performance.now() - t0), 100); return () => { clearInterval(id); write(performance.now() - t0); }; }
    let raf = 0; const tick = () => { write(performance.now() - t0); raf = requestAnimationFrame(tick); }; tick();
    return () => { cancelAnimationFrame(raf); write(performance.now() - t0); };
  }, [status]);
  useEffect(() => { setAnnounce(`${name} ${argument}, ${WORDS[status] ?? status}`); }, [status]);
  const font = Math.max(11, Math.round(size * 0.38)), iconSize = font + 2;
  const gs = g => (g === roll.current.cur ? 'in' : g === roll.current.prev ? 'out' : undefined);
  const h = React.createElement;
  return h('span', { ref: rootRef, role: 'status', 'aria-busy': status === 'running' || undefined, 'data-status': status, 'data-mounted': mounted ? '' : undefined, 'data-pressed': pressed ? '' : undefined, className: 'call-chip' + (className ? ' ' + className : ''),
    style: { '--cc-size': `${size}px`, '--cc-font': `${font}px`, '--cc-pad': `${Math.round(size * 0.35)}px`, '--cc-gap': `${Math.round(font * 0.55)}px`, '--cc-radius': `${radius}px`, '--cc-color': color, '--cc-surface': surfaceColor, '--cc-progress': progressColor, '--cc-progress-pct': `${progressOpacity * 100}%`, '--cc-done': doneColor, '--cc-error': errorColor, '--cc-wash-pct': `${washOpacity * 100}%`, '--cc-expected': `${expectedMs}ms`, ...style } },
    h('span', { ref: fillRef, className: 'call-chip__fill', 'aria-hidden': true }),
    h('span', { className: 'call-chip__slot', 'aria-hidden': true },
      h('span', { className: 'call-chip__glyph', 'data-state': gs('tool') }, typeof icon === 'string' ? h(Ico, { k: PATHS[icon] ? icon : 'terminal', size: iconSize, w: 1.8 }) : icon),
      h('span', { className: 'call-chip__glyph', 'data-state': gs('check') }, h(Ico, { k: 'check', size: iconSize, w: 2.2 })),
      h('span', { className: 'call-chip__glyph', 'data-state': gs('retry') }, h(Ico, { k: 'retry', size: iconSize, w: 2 }))),
    h('span', { className: 'call-chip__name', 'aria-hidden': true }, name),
    h('span', { className: 'call-chip__arg', 'aria-hidden': true }, argument),
    showTimer ? h('span', { ref: timerRef, className: 'call-chip__timer', 'aria-hidden': true }, '0 ms') : null,
    status === 'error' && onRetry ? h('button', { type: 'button', className: 'call-chip__retry', 'aria-label': `${name} ${argument} 다시 시도`, onClick: () => onRetry(), onPointerDown: () => setPressed(true), onPointerUp: () => setPressed(false), onPointerCancel: () => setPressed(false) }) : null,
    h('span', { className: 'call-chip__sr' }, announce));
}
module.exports = { CallChip };
