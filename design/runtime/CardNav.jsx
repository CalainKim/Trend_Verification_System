// Adapted from React Bits CardNav (JS + CSS): bar that springs open into staggered rising cards, rolling Open/Close label, unroll intro. Light design-system theme; cards are the template children.
const { useEffect, useLayoutEffect, useRef, useState } = React;
if (!document.getElementById('card-nav-css')) {
  const st = document.createElement('style'); st.id = 'card-nav-css';
  st.textContent = `.cnv{position:relative;width:100%;font-size:14px;line-height:1.4}
.cnv__panel{position:relative;height:56px;border-radius:14px;overflow:hidden;background:var(--color-surface-card);box-shadow:inset 0 0 0 1px var(--color-hairline)}
.cnv__bar{position:relative;z-index:2;display:flex;align-items:center;gap:10px;height:56px;padding:0 8px;box-sizing:border-box}
.cnv__menu{display:inline-flex;align-items:center;gap:10px;height:40px;padding:0 14px;border:0;border-radius:10px;background:none;color:var(--color-ink);font:inherit;font-weight:600;cursor:pointer;transition:background-color 200ms ease}
.cnv__menu:hover{background:var(--color-canvas-soft)}
.cnv__menu:focus-visible,.cnv__cta:focus-visible{outline:2px solid var(--color-ink);outline-offset:2px}
.cnv__burger{position:relative;width:16px;height:12px}
.cnv__line{position:absolute;left:0;width:100%;height:1.5px;border-radius:2px;background:currentColor;transition:transform 500ms cubic-bezier(0.22,1,0.36,1),top 500ms cubic-bezier(0.22,1,0.36,1)}
.cnv__line--t{top:2.25px}.cnv__line--b{top:8.25px}
.cnv[data-open] .cnv__line--t{top:5.25px;transform:rotate(45deg)}.cnv[data-open] .cnv__line--b{top:5.25px;transform:rotate(-45deg)}
.cnv__label{position:relative;display:inline-grid;overflow:hidden}
.cnv__word{grid-area:1/1;transition:transform 500ms cubic-bezier(0.22,1,0.36,1)}
.cnv__word--c{transform:translateY(110%)}.cnv[data-open] .cnv__word--o{transform:translateY(-110%)}.cnv[data-open] .cnv__word--c{transform:none}
.cnv__sum{flex:1;min-width:0;display:flex;gap:6px;flex-wrap:wrap;overflow:hidden;max-height:24px}
.cnv__chip{display:inline-flex;align-items:center;height:24px;padding:0 10px;border-radius:999px;background:var(--color-canvas-soft);color:var(--color-body);font-size:12px;white-space:nowrap}
.cnv__cta{display:inline-flex;align-items:center;gap:6px;height:40px;padding:0 16px;border:0;border-radius:10px;background:var(--color-ink);color:var(--color-canvas);font:inherit;font-size:13px;font-weight:600;white-space:nowrap;cursor:pointer;transition:filter 200ms ease}
.cnv__cta:hover{filter:brightness(1.25)}
.cnv__content{position:absolute;top:56px;left:0;right:0;padding:0 8px 8px;box-sizing:border-box;visibility:hidden}
.cnv[data-shown] .cnv__content{visibility:visible}
.cnv__cards{display:flex;gap:8px;align-items:stretch}
.cnv[data-narrow] .cnv__cards{flex-direction:column}
.cnv[data-narrow] .cnv__card{flex:none}
.cnv__card{position:relative;flex:1 1 0;min-width:0;box-sizing:border-box;border-radius:10px;background:var(--color-canvas);box-shadow:inset 0 0 0 1px var(--color-hairline-soft);overflow:hidden;transform-origin:50% 0;will-change:transform,opacity}
@media (prefers-reduced-motion:reduce){.cnv__line,.cnv__word{transition:none}}`;
  document.head.appendChild(st);
}
const clamp = (v, a, b) => Math.min(b, Math.max(a, v)), easeOut = t => 1 - (1 - t) ** 3;
function CardNav({ title = '설정', closeLabel = '닫기', chips = [], ctaLabel, ctaIcon, onCta, defaultOpen = false, stagger = 0.12, bounce = 0.2, speed = 1, children }) {
  const rootRef = useRef(null), panelRef = useRef(null), contentRef = useRef(null), barRef = useRef(null), cardRefs = useRef([]), eng = useRef(null), introRef = useRef(true);
  const [open, setOpen] = useState(defaultOpen), [shown, setShown] = useState(defaultOpen), [narrow, setNarrow] = useState(false);
  const openRef = useRef(open); openRef.current = open;
  const kids = React.Children.toArray(children).filter(c => c && typeof c === 'object');
  useEffect(() => {
    const panel = panelRef.current, content = contentRef.current; if (!panel || !content) return;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const s = { p: openRef.current ? 1 : 0, v: 0, h: content.offsetHeight }; let raf = 0, last = 0;
    const render = () => {
      panel.style.height = 56 + Math.max(0, s.p) * s.h + 'px';
      const cards = cardRefs.current.filter(Boolean), n = cards.length, lag = n > 1 ? Math.min(stagger, 0.7 / (n - 1)) : 0, span = 1 - lag * (n - 1);
      cards.forEach((c, i) => { const l = clamp((s.p - i * lag) / Math.max(span, 0.05), 0, 1), e = easeOut(l); c.style.transform = `translateY(${(1 - e) * 26}px) scale(${0.97 + 0.03 * e})`; c.style.opacity = e; });
    };
    const tick = now => {
      raf = 0; const dt = last ? Math.min(0.05, (now - last) / 1000) : 1 / 60; last = now; const t = openRef.current ? 1 : 0;
      if (reduce) { s.p = t; s.v = 0; } else { const k = 160 * speed * speed, z = t ? 1 - 0.68 * bounce : 1, n = Math.ceil(dt * 240), hh = dt / n; for (let i = 0; i < n; i++) { s.v += (-k * (s.p - t) - 2 * z * Math.sqrt(k) * s.v) * hh; s.p += s.v * hh; } }
      const done = Math.abs(s.p - t) < 0.0005 && Math.abs(s.v) < 0.002; if (done) { s.p = t; s.v = 0; }
      render(); if (done && !t) setShown(false); if (!done) raf = requestAnimationFrame(tick);
    };
    eng.current = { wake: () => { if (!raf) { last = 0; raf = requestAnimationFrame(tick); } }, refresh: () => { s.h = content.offsetHeight; render(); } };
    render();
    const ro = new ResizeObserver(() => { s.h = content.offsetHeight; render(); }); ro.observe(content);
    return () => { cancelAnimationFrame(raf); ro.disconnect(); };
  }, [kids.length, narrow]);
  useLayoutEffect(() => { if (open) setShown(true); eng.current?.refresh(); eng.current?.wake(); }, [open]);
  useLayoutEffect(() => { const r = rootRef.current; if (!r) return; const m = () => setNarrow(r.offsetWidth < 560); m(); const ro = new ResizeObserver(m); ro.observe(r); return () => ro.disconnect(); }, []);
  useEffect(() => { if (!open) return; const k = e => { if (e.key === 'Escape') setOpen(false); }; document.addEventListener('keydown', k); return () => document.removeEventListener('keydown', k); }, [open]);
  useLayoutEffect(() => {
    const p = panelRef.current, b = barRef.current; if (!p || !b || !introRef.current) return; introRef.current = false;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const w = p.offsetWidth, h = p.offsetHeight;
    p.animate([{ clipPath: `inset(0px ${Math.max(0, (w - h) / 2)}px round ${h / 2}px)`, opacity: 0 }, { clipPath: 'inset(0px 0px round 14px)', opacity: 1 }], { duration: 820, easing: 'cubic-bezier(0.22,1,0.36,1)', fill: 'backwards' });
    Array.from(b.children).forEach((c, i) => c.animate([{ opacity: 0, transform: 'translateY(8px)' }, { opacity: 1, transform: 'none' }], { duration: 560, delay: 220 + i * 70, easing: 'cubic-bezier(0.22,1,0.36,1)', fill: 'backwards' }));
  }, []);
  const h = React.createElement;
  return h('div', { ref: rootRef, className: 'cnv', 'data-open': open ? '' : undefined, 'data-shown': shown || open ? '' : undefined, 'data-narrow': narrow ? '' : undefined },
    h('div', { ref: panelRef, className: 'cnv__panel' },
      h('div', { ref: barRef, className: 'cnv__bar' },
        h('button', { type: 'button', className: 'cnv__menu', 'aria-expanded': open, onClick: () => setOpen(!open) },
          h('span', { className: 'cnv__burger', 'aria-hidden': true }, h('span', { className: 'cnv__line cnv__line--t' }), h('span', { className: 'cnv__line cnv__line--b' })),
          h('span', { className: 'cnv__label' }, h('span', { className: 'cnv__word cnv__word--o', 'aria-hidden': open }, title), h('span', { className: 'cnv__word cnv__word--c', 'aria-hidden': !open }, closeLabel))),
        h('span', { className: 'cnv__sum' }, chips.map((c, i) => h('span', { key: i, className: 'cnv__chip' }, c))),
        ctaLabel ? h('button', { type: 'button', className: 'cnv__cta', onClick: onCta }, ctaIcon, ctaLabel) : null),
      h('div', { ref: contentRef, className: 'cnv__content', 'aria-hidden': !open, inert: open ? undefined : '' },
        h('div', { className: 'cnv__cards' }, kids.map((c, i) => h('div', { key: i, ref: el => { cardRefs.current[i] = el; }, className: 'cnv__card' }, c))))));
}
module.exports = { CardNav };
