// Vertical adaptation of React Bits PillNav (JS + CSS): glide pill with spring + stretch, hover fill, intro unroll. Light design-system theme.
const { useEffect, useLayoutEffect, useRef } = React;
if (!document.getElementById('pill-nav-v-css')) {
  const st = document.createElement('style'); st.id = 'pill-nav-v-css';
  st.textContent = `.pnv{position:relative;display:flex;flex-direction:column;align-items:center;gap:10px}
.pnv__bar{position:relative;box-sizing:border-box;padding:4px;border-radius:999px;background:var(--color-surface-card);box-shadow:inset 0 0 0 1px var(--color-hairline)}
.pnv__list{position:relative;z-index:1;display:flex;flex-direction:column;gap:3px;margin:0;padding:0;list-style:none}
.pnv__list>li{position:relative}
.pnv__sep{height:1px;margin:4px 8px;background:var(--color-hairline)}
.pnv__grp{display:block;padding:4px 0 1px;font-size:9.5px;font-weight:600;letter-spacing:0.02em;line-height:1.2;color:var(--color-muted);text-align:center;white-space:nowrap}
.pnv__item{position:relative;display:grid;place-items:center;width:40px;height:40px;border:0;border-radius:999px;background:transparent;color:var(--color-body);cursor:pointer;overflow:hidden;isolation:isolate;outline:none;transition:color 220ms ease}
.pnv__item:focus-visible{box-shadow:0 0 0 2px var(--color-ink)}
.pnv__item[aria-current]{color:var(--color-canvas)}
.pnv__fill{position:absolute;left:50%;top:100%;z-index:-1;width:92px;height:92px;margin:-46px 0 0 -46px;border-radius:50%;background:var(--color-surface-strong);transform:scale(0);transition:transform 340ms cubic-bezier(0.4,0,0.2,1);pointer-events:none}
.pnv__item:hover:not([aria-current]) .pnv__fill{transform:scale(1);transition:transform 520ms cubic-bezier(0.22,1,0.36,1)}
.pnv__item:hover:not([aria-current]){color:var(--color-ink)}
.pnv__face{display:grid;place-items:center;transition:transform 360ms cubic-bezier(0.34,1.4,0.64,1)}
.pnv__item:active .pnv__face{transform:scale(0.88)}
.pnv__badge{position:absolute;top:-3px;right:-5px;pointer-events:none;z-index:2;min-width:15px;height:15px;box-sizing:border-box;padding:0 4px;border-radius:8px;background:var(--color-primary,#f54e00);color:#fff;font-size:9px;font-weight:600;line-height:15px;text-align:center;font-variant-numeric:tabular-nums;box-shadow:0 0 0 2px var(--color-surface-card)}
.pnv__glide{position:absolute;left:4px;right:4px;top:0;z-index:0;border-radius:999px;background:var(--color-ink);opacity:0;pointer-events:none;will-change:transform,height}
@media (prefers-reduced-motion:reduce){.pnv__fill,.pnv__face,.pnv__item{transition:none}}`;
  document.head.appendChild(st);
}
const ICONS = {
  trend: ['M3 17l6-6 4 4 8-8', 'M14 7h7v7'], rise: ['M12 19V5', 'M5 12l7-7 7 7'], layers: ['M12 3l9 5-9 5-9-5z', 'M3 13l9 5 9-5'],
  check: ['M9 11l3 3 8-8', 'M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9'], bell: ['M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9', 'M10.3 21a1.9 1.9 0 0 0 3.4 0'],
  doc: ['M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z', 'M14 3v5h5', 'M9 13h6M9 17h4'], settings: ['M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0', 'M16 4v4M10 10v4M18 16v4']
};
const h = React.createElement;
const Ico = ({ k }) => h('svg', { width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true }, (ICONS[k] || []).map((d, i) => h('path', { key: i, d })));
function PillNavV({ groups = [], active, onSelect, bounce = 0.3, stretch = 0.5, intro = true }) {
  const barRef = useRef(null), glideRef = useRef(null), slots = useRef({}), eng = useRef(null), first = useRef(intro);
  const flat = groups.flatMap(g => g.children || []);
  useEffect(() => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const s = { y0: 0, y1: 0, v0: 0, v1: 0, a: 0, init: false }; let raf = 0, last = 0;
    const target = () => { const el = slots.current[eng.current.active]; if (!el) return null; const o = el.offsetTop + el.parentElement.offsetTop; return { t: o, b: o + el.offsetHeight }; };
    const tick = now => {
      raf = 0; const dt = last ? Math.min(0.05, (now - last) / 1000) : 1 / 60; last = now; const tg = target(), g = glideRef.current; let busy = false;
      if (tg) {
        if (!s.init || reduce) { s.y0 = tg.t; s.y1 = tg.b; s.v0 = s.v1 = 0; s.init = true; }
        const dir = Math.sign((tg.t + tg.b) / 2 - (s.y0 + s.y1) / 2), base = 520, lead = base * (1 + 0.9 * stretch), trail = base * (1 - 0.5 * stretch), z = 1 - 0.55 * bounce;
        const k0 = dir < 0 ? lead : dir > 0 ? trail : base, k1 = dir > 0 ? lead : dir < 0 ? trail : base, n = Math.ceil(dt * 240), st = dt / n;
        for (let i = 0; i < n; i++) { s.v0 += (-k0 * (s.y0 - tg.t) - 2 * z * Math.sqrt(k0) * s.v0) * st; s.y0 += s.v0 * st; s.v1 += (-k1 * (s.y1 - tg.b) - 2 * z * Math.sqrt(k1) * s.v1) * st; s.y1 += s.v1 * st; }
        s.a += (1 - s.a) * (reduce ? 1 : 1 - Math.exp(-dt / 0.08));
        busy = Math.abs(s.y0 - tg.t) > 0.05 || Math.abs(s.y1 - tg.b) > 0.05 || Math.abs(s.v0) + Math.abs(s.v1) > 0.5 || s.a < 0.999;
      } else { s.a += -s.a * (1 - Math.exp(-dt / 0.08)); busy = s.a > 0.002; }
      if (g) { const ht = Math.max(0, s.y1 - s.y0), sq = 1 - Math.min(0.14, Math.max(0, (ht / 40 - 1) * 0.3)); g.style.height = ht + 'px'; g.style.transform = `translate3d(0, ${s.y0}px, 0) scaleX(${sq})`; g.style.opacity = s.a; }
      if (busy) raf = requestAnimationFrame(tick);
    };
    eng.current = { active, wake: () => { if (!raf) { last = 0; raf = requestAnimationFrame(tick); } } };
    const delay = first.current && !reduce ? setTimeout(() => eng.current.wake(), 520) : (eng.current.wake(), 0);
    const ro = new ResizeObserver(() => { s.init = false; eng.current.wake(); }); if (barRef.current) ro.observe(barRef.current);
    return () => { cancelAnimationFrame(raf); clearTimeout(delay); ro.disconnect(); };
  }, []);
  useEffect(() => { if (eng.current) { eng.current.active = active; eng.current.wake(); } }, [active]);
  useLayoutEffect(() => {
    if (!first.current) return; first.current = false; const bar = barRef.current;
    if (!bar || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const H = bar.offsetHeight, W = bar.offsetWidth;
    bar.animate([{ clipPath: `inset(0 0 ${Math.max(0, H - W)}px 0 round ${W / 2}px)` }, { clipPath: `inset(0 0 0 0 round ${W / 2}px)` }], { duration: 760, delay: 60, easing: 'cubic-bezier(0.22,1,0.36,1)', fill: 'backwards' });
    flat.forEach((it, i) => slots.current[it.value]?.animate([{ opacity: 0, transform: 'translateY(-10px)' }, { opacity: 1, transform: 'none' }], { duration: 520, delay: 180 + i * 50, easing: 'cubic-bezier(0.22,1,0.36,1)', fill: 'backwards' }));
  }, []);
  return h('nav', { className: 'pnv', 'aria-label': '메뉴' },
    h('div', { ref: barRef, className: 'pnv__bar' },
      h('span', { ref: glideRef, className: 'pnv__glide', 'aria-hidden': true }),
      h('ul', { className: 'pnv__list' }, groups.map((g, gi) => [gi ? h('li', { key: 'sep' + gi, className: 'pnv__sep', role: 'presentation' }) : null, g.label ? h('li', { key: 'grp' + gi, className: 'pnv__grp', role: 'presentation', 'aria-hidden': true }, g.label) : null,
        ...(g.children || []).map(it => h('li', { key: it.value, ref: el => { slots.current[it.value] = el; } },
          h('button', { type: 'button', className: 'pnv__item', 'aria-current': it.value === active ? 'page' : undefined, 'aria-label': it.label, 'data-tip': it.label + (it.desc ? ': ' + it.desc : ''), onClick: () => onSelect?.(it.value) },
            h('span', { className: 'pnv__fill', 'aria-hidden': true }), h('span', { className: 'pnv__face' }, h(Ico, { k: it.icon }))),
            it.badge ? h('span', { className: 'pnv__badge', 'aria-hidden': true }, it.badge > 99 ? '99+' : it.badge) : null))]))));
}
module.exports = { PillNavV };
