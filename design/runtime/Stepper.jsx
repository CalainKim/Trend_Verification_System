// Adapted from React Bits Stepper (JS + CSS): numbered track with spring glider, animated check, sliding panes with height spring, back/next footer. Light design-system theme; steps are the template children, titles via prop.
const { useLayoutEffect, useRef, useState } = React;
if (!document.getElementById('stepper-css')) {
  const st = document.createElement('style'); st.id = 'stepper-css';
  st.textContent = `.stp{position:relative;display:flex;flex-direction:column;width:100%;box-sizing:border-box;padding:8px;border-radius:14px;background:var(--color-surface-card);box-shadow:inset 0 0 0 1px var(--color-hairline);color:var(--color-ink)}
.stp__track{position:relative;display:flex;gap:4px;padding:4px;border-radius:10px;background:var(--color-canvas-soft)}
.stp__glider{position:absolute;top:0;left:0;border-radius:7px;background:var(--color-surface-card);box-shadow:inset 0 0 0 1px var(--color-hairline),0 4px 10px -6px rgba(38,37,30,0.3);opacity:0;pointer-events:none}
.stp__seg{position:relative;display:flex;flex:1 1 auto;align-items:center;justify-content:center;gap:8px;min-width:0;height:40px;padding:0 10px;box-sizing:border-box;border:0;border-radius:7px;background:none;color:var(--color-body);font:inherit;cursor:pointer;transition:background-color 200ms ease}
.stp__seg:disabled{cursor:default}
.stp__seg:not(:disabled):hover{background:rgba(38,37,30,0.035)}
.stp__seg:focus-visible,.stp__btn:focus-visible{outline:2px solid var(--color-ink);outline-offset:2px}
.stp__badge{display:grid;flex:none;place-items:center;width:22px;height:22px;border-radius:50%;box-shadow:inset 0 0 0 1px var(--color-hairline-strong);color:var(--color-muted);font-size:11.5px;font-weight:600;font-variant-numeric:tabular-nums;line-height:1;transition:background-color 150ms ease,box-shadow 150ms ease,color 150ms ease}
.stp__badge[data-s='active']{box-shadow:inset 0 0 0 1.5px var(--color-ink);color:var(--color-ink)}
.stp__badge[data-s='complete']{background:var(--color-ink);box-shadow:none;color:var(--color-canvas)}
.stp__title{overflow:hidden;font-size:13px;font-weight:600;white-space:nowrap;text-overflow:ellipsis;color:var(--color-muted);transition:color 200ms ease}
.stp__title:not([data-s='upcoming']){color:var(--color-ink)}
.stp__count{font-family:var(--font-mono);font-size:11px;color:var(--color-muted)}
.stp__body{display:flex;flex-direction:column;min-width:0;padding:12px 4px 4px}
.stp__view{position:relative;overflow:hidden;margin:0 -4px}
.stp__pane{box-sizing:border-box;padding:0 4px;outline:none}
.stp__pane--leaving{position:absolute;top:0;left:0;right:0;pointer-events:none}
.stp__foot{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 8px 6px}
.stp__btn{display:inline-flex;align-items:center;gap:6px;height:36px;padding:0 14px;border:0;border-radius:8px;font:inherit;font-size:13px;font-weight:600;cursor:pointer;transition:filter 200ms ease,transform 200ms ease,opacity 200ms ease}
.stp__btn--back{padding-left:10px;background:var(--color-surface-card);box-shadow:inset 0 0 0 1px var(--color-hairline-strong);color:var(--color-ink)}
.stp__btn--back[data-hidden]{visibility:hidden;opacity:0}
.stp__btn--next{margin-left:auto;padding-right:11px;background:var(--color-ink);color:var(--color-canvas)}
.stp__btn--next:hover{filter:brightness(1.3)}
.stp__btn:active{transform:scale(0.96);transition-duration:0s}
.stp[data-narrow] .stp__title{display:none}`;
  document.head.appendChild(st);
}
const SPRING = 'linear(0, 0.0603, 0.2033, 0.3821, 0.5633, 0.7258, 0.8584, 0.9574, 1.0242, 1.0634, 1.0809, 1.0828, 1.0747, 1.0613, 1.046, 1.0313, 1.0186, 1.0085, 1.0012, 0.9965, 0.994, 0.9931, 0.9933, 0.9941, 0.9953, 0.9966, 0.9978, 0.9988, 1)';
const ease = () => (CSS.supports?.('transition-timing-function', 'linear(0, 1)') ? SPRING : 'cubic-bezier(0.34,1.4,0.64,1)');
const h = React.createElement;
const Arrow = ({ d }) => h('svg', { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true }, h('path', { d }));
function Check() {
  const ref = useRef(null);
  useLayoutEffect(() => { const p = ref.current?.querySelector('path'); if (!p || matchMedia('(prefers-reduced-motion: reduce)').matches) return; p.style.strokeDasharray = '24'; p.animate([{ strokeDashoffset: 24 }, { strokeDashoffset: 0 }], { duration: 360, easing: 'cubic-bezier(0.22,1,0.36,1)' }); }, []);
  return h('span', { ref, style: { display: 'grid', placeItems: 'center' } }, h('svg', { width: 13, height: 13, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 3, strokeLinecap: 'round', strokeLinejoin: 'round' }, h('path', { d: 'M5 12.5l4.5 4.5L19 7.5' })));
}
function Stepper({ titles = [], counts = [], children, backText = '이전', nextText = '다음', doneText = '확인 완료', onDone }) {
  const steps = React.Children.toArray(children).filter(c => c && typeof c === 'object'), total = steps.length;
  const [cur, setCur] = useState(1), [narrow, setNarrow] = useState(false);
  const [view, setView] = useState({ step: 1, prev: null, dir: 1, id: 0 });
  if (view.step !== cur) setView({ step: cur, prev: view.step, dir: cur > view.step ? 1 : -1, id: view.id + 1 });
  const rootRef = useRef(null), trackRef = useRef(null), gliderRef = useRef(null), segs = useRef([]), vpRef = useRef(null), paneRef = useRef(null), leaveRef = useRef(null), hRef = useRef(0), placed = useRef(false);
  const go = n => { const x = Math.min(total, Math.max(1, n)); if (x !== cur) setCur(x); };
  useLayoutEffect(() => { const r = rootRef.current; if (!r) return; const m = () => setNarrow(r.clientWidth < 420); m(); const ro = new ResizeObserver(m); ro.observe(r); return () => ro.disconnect(); }, []);
  useLayoutEffect(() => { const v = vpRef.current; if (!v) return; hRef.current = v.offsetHeight; const ro = new ResizeObserver(() => { hRef.current = v.offsetHeight; }); ro.observe(v); return () => ro.disconnect(); }, []);
  useLayoutEffect(() => {
    if (!view.id) return; const v = vpRef.current, p = paneRef.current, l = leaveRef.current, id = view.id, red = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const fin = () => setView(s => (s.id === id ? { ...s, prev: null } : s));
    [v, p, l].forEach(e => e?.getAnimations().forEach(a => a.cancel()));
    const from = hRef.current, to = v.offsetHeight, sp = ease();
    if (Math.abs(from - to) > 0.5) v.animate([{ height: from + 'px' }, { height: to + 'px' }], { duration: red ? 200 : 560, easing: red ? 'ease' : sp });
    const sh = red ? 0 : 36;
    if (p) { if (sh) p.animate([{ transform: `translateX(${view.dir * sh}px)` }, { transform: 'none' }], { duration: 560, easing: sp }); p.animate([{ opacity: 0 }, { opacity: 0, offset: 0.25 }, { opacity: 1 }], { duration: 420, easing: 'ease-out' }); }
    if (l) { l.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 140, fill: 'forwards' }); const x = l.animate([{ transform: 'none' }, { transform: `translateX(${-view.dir * sh}px)` }], { duration: 200, easing: 'cubic-bezier(0.4,0,1,1)', fill: 'forwards' }); x.onfinish = fin; } else fin();
  }, [view.id]);
  useLayoutEffect(() => {
    const t = trackRef.current, g = gliderRef.current; if (!t || !g) return;
    const place = anim => { const s = segs.current[cur - 1]; if (!s) return; const sp = ease();
      g.style.transition = anim ? `transform 560ms ${sp}, width 560ms ${sp}, opacity 200ms ease` : 'opacity 200ms ease';
      g.style.transform = `translate3d(${s.offsetLeft}px, ${s.offsetTop}px, 0)`; g.style.width = s.offsetWidth + 'px'; g.style.height = s.offsetHeight + 'px'; g.style.opacity = '1'; };
    place(placed.current && !matchMedia('(prefers-reduced-motion: reduce)').matches); placed.current = true;
    const ro = new ResizeObserver(() => place(false)); ro.observe(t); return () => ro.disconnect();
  }, [cur, total, narrow]);
  const last = cur === total;
  return h('div', { ref: rootRef, className: 'stp', 'data-narrow': narrow ? '' : undefined },
    h('div', { ref: trackRef, className: 'stp__track' }, h('span', { ref: gliderRef, className: 'stp__glider', 'aria-hidden': true }),
      steps.map((_, i) => { const n = i + 1, s = n < cur ? 'complete' : n === cur ? 'active' : 'upcoming';
        return h('button', { key: n, ref: el => { segs.current[i] = el; }, type: 'button', className: 'stp__seg', 'aria-current': n === cur ? 'step' : undefined, 'aria-label': `${n}단계: ${titles[i] || ''}`, 'data-tip': titles[i], disabled: n === cur, onClick: () => go(n) },
          h('span', { className: 'stp__badge', 'data-s': s }, s === 'complete' ? h(Check) : n), h('span', { className: 'stp__title', 'data-s': s }, titles[i]), counts[i] != null ? h('span', { className: 'stp__count' }, counts[i]) : null); })),
    h('div', { className: 'stp__body' },
      h('div', { ref: vpRef, className: 'stp__view', 'aria-live': 'polite' },
        view.prev !== null ? h('div', { key: view.id - 1, ref: leaveRef, className: 'stp__pane stp__pane--leaving', 'aria-hidden': true }, steps[view.prev - 1]) : null,
        h('div', { key: view.id, ref: paneRef, className: 'stp__pane', tabIndex: -1 }, steps[view.step - 1])),
      h('div', { className: 'stp__foot' },
        h('button', { type: 'button', className: 'stp__btn stp__btn--back', 'data-hidden': cur <= 1 ? '' : undefined, onClick: () => go(cur - 1) }, h(Arrow, { d: 'M15 6l-6 6 6 6' }), h('span', null, backText)),
        h('button', { type: 'button', className: 'stp__btn stp__btn--next', onClick: () => (last ? onDone?.() : go(cur + 1)) }, h('span', null, last ? doneText : nextText), h(Arrow, { d: last ? 'M5 12.5l4.5 4.5L19 7.5' : 'M9 6l6 6-6 6' })))));
}
module.exports = { Stepper };
