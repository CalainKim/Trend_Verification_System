// Port of React Bits AnimatedList (JS + CSS). Hugeicons removed (icons are passed in). Added a "ds" theme using design-system tokens.
const { useEffect, useId, useLayoutEffect, useRef, useState } = React;
if (!document.getElementById('animated-list-css')) {
  const st = document.createElement('style'); st.id = 'animated-list-css';
  st.textContent = `.animated-list{position:relative;width:min(100%,var(--al-width));min-width:0;max-width:100%;box-sizing:border-box;border-radius:calc(var(--al-radius) + 12px);color:var(--al-ink)}
.animated-list--framed{padding:6px;background:var(--al-frame);box-shadow:var(--al-frame-shadow)}
.animated-list:has(> .animated-list__viewport:focus-visible){outline:2px solid var(--al-accent);outline-offset:3px}
.animated-list__frame-rim{position:absolute;inset:0;z-index:3;border-radius:inherit;box-shadow:inset 0 0 0 1px var(--al-frame-edge);pointer-events:none}
.animated-list__viewport{--al-fade-top:0px;--al-fade-bottom:0px;position:relative;box-sizing:border-box;padding:4px 2px;overflow-x:hidden;overflow-y:auto;overscroll-behavior:contain;outline:none;scrollbar-width:thin;scrollbar-color:var(--al-thumb) transparent}
.animated-list__viewport--bare{scrollbar-width:none}.animated-list__viewport--bare::-webkit-scrollbar{display:none}
.animated-list__track{position:relative;display:flex;flex-direction:column;gap:var(--al-gap)}
.animated-list__item{position:relative;display:flex;align-items:center;gap:10px;min-width:0;padding:8px 10px;box-sizing:border-box;border-radius:var(--al-radius);background:var(--al-tile);box-shadow:var(--al-tile-shadow);color:var(--al-ink);cursor:pointer;user-select:none}
.animated-list[data-animated] .animated-list__item:not([data-state]){opacity:0}
@media (hover:hover){.animated-list__item:hover{filter:var(--al-hover)}}
.animated-list__item[data-selected]:not(:active){filter:var(--al-active)}
.animated-list__item:active{filter:var(--al-press)}
.animated-list__lead{display:grid;place-items:center;flex:none;width:24px;height:24px;overflow:hidden;border-radius:6px;background:var(--al-well);color:var(--al-ink)}
.animated-list__lead img{display:block;width:100%;height:100%;object-fit:cover}
.animated-list__text{display:flex;flex:1;flex-direction:column;gap:1px;min-width:0}
.animated-list__title{overflow:hidden;font-size:13px;font-weight:600;line-height:1.3;text-overflow:ellipsis;white-space:nowrap}
.animated-list__description{overflow:hidden;font-size:11px;line-height:1.35;color:var(--al-muted);text-overflow:ellipsis;white-space:nowrap}
.animated-list__meta{flex:none;font-family:var(--font-mono);font-size:11px;font-variant-numeric:tabular-nums;color:var(--al-muted)}
.animated-list__rim{position:absolute;inset:0;border-radius:inherit;box-shadow:inset 0 0 0 1px var(--al-tile-edge);pointer-events:none}
.animated-list__indicator{position:absolute;top:0;left:0;right:0;z-index:2;height:0;opacity:0;pointer-events:none;transition:opacity 0.2s ease}
.animated-list__ring{position:absolute;inset:0;border-radius:var(--al-radius);background:var(--al-ring-fill);box-shadow:inset 0 0 0 1.5px var(--al-ring)}`;
  document.head.appendChild(st);
}
const THEMES = {
  ds: { '--al-frame': 'var(--color-canvas-soft)', '--al-frame-edge': 'var(--color-hairline)', '--al-frame-shadow': 'none', '--al-tile': 'var(--color-surface-card)', '--al-tile-edge': 'var(--color-hairline)', '--al-tile-shadow': 'none', '--al-well': 'var(--color-canvas-soft)', '--al-ink': 'var(--color-ink)', '--al-muted': 'var(--color-muted)', '--al-thumb': 'var(--color-hairline-strong)', '--al-ring': 'var(--color-ink)', '--al-ring-fill': 'transparent', '--al-hover': 'brightness(0.98)', '--al-press': 'brightness(0.95)', '--al-active': 'none' }
};
const HIDDEN = { pop: { above: 'translate3d(0,-12px,0) scale(0.8)', below: 'translate3d(0,12px,0) scale(0.8)' }, slide: { above: 'translate3d(0,-28px,0) scale(0.98)', below: 'translate3d(0,28px,0) scale(0.98)' }, fade: { above: 'translate3d(0,-4px,0)', below: 'translate3d(0,4px,0)' } };
const SPRING = 'linear(0, 0.0603, 0.2033, 0.3821, 0.5633, 0.7258, 0.8584, 0.9574, 1.0242, 1.0634, 1.0809, 1.0828, 1.0747, 1.0613, 1.046, 1.0313, 1.0186, 1.0085, 1.0012, 0.9965, 0.994, 0.9931, 0.9933, 0.9941, 0.9953, 0.9966, 0.9978, 0.9988, 1)';
const ss = t => t * t * t * (t * (t * 6 - 15) + 10);
const FADE_MASK = (() => { const st = [0, 0.15, 0.3, 0.45, 0.6, 0.75, 0.9, 1]; const top = st.map(t => `rgba(0,0,0,${ss(t).toFixed(3)}) calc(var(--al-fade-top) * ${t})`); const bot = [...st].reverse().map(t => `rgba(0,0,0,${ss(t).toFixed(3)}) calc(100% - var(--al-fade-bottom) * ${t})`); return `linear-gradient(to bottom, ${[...top, ...bot].join(', ')})`; })();
const size = v => (typeof v === 'number' ? `${v}px` : v);

function AnimatedList({ items = [], onItemSelect, initialSelectedIndex = -1, selectOnHover = true, enableArrowNavigation = true, loop = false, animation = 'pop', animateOnce = false, stagger = 0.05, showGradients = true, fadeSize = 56, displayScrollbar = true, frame = true, theme = 'ds', accentColor, radius = 14, gap = 8, width = 420, maxHeight = 440, className = '', itemClassName = '', style }) {
  const rootRef = useRef(null), viewportRef = useRef(null), trackRef = useRef(null), indicatorRef = useRef(null), ringRef = useRef(null), itemRefs = useRef([]), engineRef = useRef(null), keyboardRef = useRef(false), navigatingRef = useRef(false);
  const [selected, setSelected] = useState(initialSelectedIndex);
  const baseId = useId();
  const settingsRef = useRef({}); settingsRef.current = { items, onItemSelect, selected, selectOnHover, enableArrowNavigation, loop, animation, animateOnce, stagger, showGradients, fadeSize };
  useLayoutEffect(() => {
    const root = rootRef.current, viewport = viewportRef.current, track = trackRef.current, indicator = indicatorRef.current, ring = ringRef.current;
    if (!root || !viewport || !track || !indicator || !ring) return;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const ease = CSS.supports?.('transition-timing-function', 'linear(0, 1)') ? SPRING : 'cubic-bezier(0.34, 1.4, 0.64, 1)';
    const transition = `transform 620ms ${ease}, opacity 300ms cubic-bezier(0.22, 1, 0.36, 1), filter 200ms ease`;
    const motion = { y: 0, h: 0, vy: 0, vh: 0, ty: 0, th: 0, ready: false }, fades = { top: '', bottom: '' };
    let boxes = [], current = null, entered = false, engaged = false, pointer = [0, 0], raf = 0, last = 0;
    const mode = () => { const c = settingsRef.current.animation; if (c === 'none' || !HIDDEN[c]) return 'none'; return reduced ? 'fade' : c; };
    const apply = (el, state) => { el.dataset.state = state; const pose = current && current !== 'none' && state !== 'in' ? HIDDEN[current][state] : ''; el.style.transform = pose; el.style.opacity = pose ? '0' : ''; };
    const syncRing = () => { const it = itemRefs.current[settingsRef.current.selected]; if (!it) return; const state = it.dataset.state || 'in'; if (state === ring.dataset.state) return; ring.style.transitionDelay = it.style.transitionDelay; apply(ring, state); };
    const write = () => { indicator.style.transform = `translate3d(0, ${motion.y.toFixed(2)}px, 0)`; indicator.style.height = `${motion.h.toFixed(2)}px`; };
    const tick = now => { raf = 0; const dt = Math.min(0.05, (now - last) / 1000 || 0); last = now; const om = 30, ze = 0.78, n = Math.max(1, Math.ceil(dt / (1 / 240))), hh = dt / n;
      for (let i = 0; i < n; i++) { motion.vy += (om * om * (motion.ty - motion.y) - 2 * ze * om * motion.vy) * hh; motion.vh += (om * om * (motion.th - motion.h) - 2 * ze * om * motion.vh) * hh; motion.y += motion.vy * hh; motion.h += motion.vh * hh; }
      const moving = Math.abs(motion.ty - motion.y) > 0.05 || Math.abs(motion.th - motion.h) > 0.05 || Math.abs(motion.vy) + Math.abs(motion.vh) > 0.5;
      if (!moving) { motion.y = motion.ty; motion.h = motion.th; motion.vy = motion.vh = 0; } write(); if (moving) raf = requestAnimationFrame(tick); };
    const place = snap => { const it = itemRefs.current[settingsRef.current.selected]; if (!it) { indicator.style.opacity = '0'; motion.ready = false; return; } indicator.style.opacity = '1'; motion.ty = it.offsetTop; motion.th = it.offsetHeight;
      if (snap || reduced || !motion.ready) { motion.y = motion.ty; motion.h = motion.th; motion.vy = motion.vh = 0; motion.ready = true; write(); return; } if (!raf) { last = performance.now(); raf = requestAnimationFrame(tick); } };
    const updateFades = () => { const s = settingsRef.current, span = Math.max(1, s.fadeSize), { scrollTop, scrollHeight, clientHeight } = viewport;
      const t = s.showGradients ? Math.min(span, Math.max(0, scrollTop)) : 0, b = s.showGradients ? Math.min(span, Math.max(0, scrollHeight - clientHeight - scrollTop)) : 0;
      const nt = `${t.toFixed(1)}px`, nb = `${b.toFixed(1)}px`; if (nt !== fades.top) { fades.top = nt; viewport.style.setProperty('--al-fade-top', nt); } if (nb !== fades.bottom) { fades.bottom = nb; viewport.style.setProperty('--al-fade-bottom', nb); } };
    const measure = () => { const off = track.offsetTop; boxes = itemRefs.current.map(it => (it ? [off + it.offsetTop, it.offsetHeight] : null)); };
    const reveal = entrance => { if (!entered) return; const s = settingsRef.current, top = viewport.scrollTop, view = viewport.clientHeight; let order = 0;
      itemRefs.current.forEach((it, i) => { const box = boxes[i]; if (!it || !box) return; const start = box[0] - top, overlap = Math.min(view, start + box[1]) - Math.max(0, start);
        const hidden = current !== 'none' && overlap < Math.min(box[1], view) * 0.5 && !(s.animateOnce && it.dataset.seen);
        const state = hidden ? (start + box[1] / 2 < view / 2 ? 'above' : 'below') : 'in'; if (state === it.dataset.state) return;
        const delay = entrance && !hidden ? (order++ * Math.max(0, s.stagger)).toFixed(3) : 0; it.style.transitionDelay = delay ? `${delay}s, ${delay}s, 0s` : ''; if (!hidden) it.dataset.seen = 'true'; apply(it, state); });
      syncRing(); };
    const sync = () => { const s = settingsRef.current; itemRefs.current.length = s.items.length; const els = itemRefs.current.filter(Boolean), next = mode(), changed = next !== current, restyle = changed ? els : els.filter(it => !it.dataset.state);
      current = next; if (current === 'none') entered = true;
      if (restyle.length) { const all = changed ? [...restyle, ring] : restyle; for (const e of all) e.style.transition = 'none'; for (const it of restyle) apply(it, current === 'none' ? 'in' : it.dataset.state || 'below');
        if (changed) apply(ring, itemRefs.current[s.selected]?.dataset.state || 'in'); void root.offsetHeight; for (const e of all) e.style.transition = transition; }
      measure(); reveal(restyle.length > 0); };
    sync();
    const gate = typeof IntersectionObserver === 'undefined' ? null : new IntersectionObserver((en, ob) => { if (!en.some(e => e.isIntersecting)) return; ob.disconnect(); if (entered) return; entered = true; measure(); reveal(true); }, { rootMargin: '0px 0px -10% 0px' });
    if (!entered) { if (gate) gate.observe(root); else { entered = true; reveal(true); } }
    const ro = new ResizeObserver(() => { place(true); updateFades(); measure(); reveal(false); }); ro.observe(viewport); ro.observe(track);
    const onScroll = () => { updateFades(); reveal(false); };
    const onKey = e => { const s = settingsRef.current; if (!s.enableArrowNavigation || e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
      const a = document.activeElement, focused = a === viewport, idle = !a || a === document.body || a === document.documentElement; if (!focused && !(engaged && idle)) return;
      const n = s.items.length; if (!n) return; const i = s.selected; let next = null;
      if (e.key === 'ArrowDown') next = i < 0 ? 0 : i + 1; else if (e.key === 'ArrowUp') next = i < 0 ? n - 1 : i - 1; else if (e.key === 'Home') next = 0; else if (e.key === 'End') next = n - 1;
      else if ((e.key === 'Enter' || (focused && e.key === ' ')) && i >= 0 && i < n) { e.preventDefault(); s.onItemSelect?.(s.items[i], i); return; }
      if (next === null) return; e.preventDefault(); next = s.loop ? (next + n) % n : Math.min(n - 1, Math.max(0, next)); keyboardRef.current = true; navigatingRef.current = true; setSelected(next); };
    const onMove = e => { const moved = e.clientX !== pointer[0] || e.clientY !== pointer[1]; pointer = [e.clientX, e.clientY]; if (!navigatingRef.current || !moved) return; navigatingRef.current = false;
      const it = e.target instanceof Element ? e.target.closest('[data-index]') : null; if (it && root.contains(it) && settingsRef.current.selectOnHover) setSelected(Number(it.dataset.index)); };
    const onEnter = () => { engaged = true; }, onLeave = () => { engaged = false; };
    viewport.addEventListener('scroll', onScroll, { passive: true }); window.addEventListener('keydown', onKey); root.addEventListener('pointerenter', onEnter); root.addEventListener('pointerleave', onLeave); root.addEventListener('pointermove', onMove);
    updateFades(); place(true); syncRing(); engineRef.current = { place, syncRing, updateFades, sync };
    return () => { cancelAnimationFrame(raf); gate?.disconnect(); ro.disconnect(); viewport.removeEventListener('scroll', onScroll); window.removeEventListener('keydown', onKey); root.removeEventListener('pointerenter', onEnter); root.removeEventListener('pointerleave', onLeave); root.removeEventListener('pointermove', onMove); engineRef.current = null; };
  }, []);
  useLayoutEffect(() => { engineRef.current?.sync(); }, [items, animation]);
  useEffect(() => { const eng = engineRef.current; if (!eng) return; eng.place(false); eng.syncRing(); if (!keyboardRef.current) return; keyboardRef.current = false;
    const vp = viewportRef.current, tr = trackRef.current, it = itemRefs.current[selected]; if (!vp || !tr || !it) return;
    const top = tr.offsetTop + it.offsetTop, bottom = top + it.offsetHeight, room = Math.max(0, (vp.clientHeight - it.offsetHeight) / 2), m = Math.min(showGradients ? Math.max(12, fadeSize) : 12, room);
    if (top < vp.scrollTop + m) vp.scrollTo({ top: Math.max(0, top - m), behavior: 'smooth' }); else if (bottom > vp.scrollTop + vp.clientHeight - m) vp.scrollTo({ top: bottom - vp.clientHeight + m, behavior: 'smooth' }); }, [selected, fadeSize, showGradients]);
  useEffect(() => { engineRef.current?.updateFades(); }, [showGradients, fadeSize, maxHeight, gap]);
  const hover = i => { if (!navigatingRef.current) setSelected(i); };
  const choose = (item, i) => { setSelected(i); onItemSelect?.(item, i); };
  const h = React.createElement;
  return h('div', { ref: rootRef, className: `animated-list${frame ? ' animated-list--framed' : ''} ${className}`.trim(), 'data-animated': animation !== 'none' ? '' : undefined,
    style: { ...(THEMES[theme] ?? THEMES.ds), '--al-radius': `${Math.max(0, radius)}px`, '--al-gap': `${Math.max(0, gap)}px`, '--al-width': size(width), '--al-accent': accentColor || 'var(--al-ink)', ...(accentColor ? { '--al-ring': accentColor } : {}), ...style } },
    h('div', { ref: viewportRef, className: `animated-list__viewport${displayScrollbar ? '' : ' animated-list__viewport--bare'}`, role: 'listbox', tabIndex: 0, 'aria-activedescendant': selected >= 0 && selected < items.length ? `${baseId}-${selected}` : undefined,
      style: { maxHeight: size(maxHeight), maskImage: showGradients ? FADE_MASK : undefined, WebkitMaskImage: showGradients ? FADE_MASK : undefined } },
      h('div', { ref: trackRef, className: 'animated-list__track' },
        items.map((item, i) => { const e = item !== null && typeof item === 'object' ? item : { title: item }, on = i === selected;
          return h('div', { key: e.id ?? i, ref: el => { itemRefs.current[i] = el; }, id: `${baseId}-${i}`, className: `animated-list__item ${itemClassName}`.trim(), role: 'option', 'aria-selected': on, 'data-index': i, 'data-selected': on ? '' : undefined, 'data-tip': e.tip, onPointerEnter: selectOnHover ? () => hover(i) : undefined, onClick: () => choose(item, i) },
            (e.image || e.icon) ? h('span', { className: 'animated-list__lead' }, e.image ? h('img', { src: e.image, alt: '', draggable: false }) : e.icon) : null,
            h('span', { className: 'animated-list__text' }, h('span', { className: 'animated-list__title' }, e.title), e.description ? h('span', { className: 'animated-list__description' }, e.description) : null),
            e.meta ? h('span', { className: 'animated-list__meta' }, e.meta) : null,
            e.help ? h('span', { 'data-tip': e.help, role: 'button', tabIndex: 0, 'aria-label': '도움말', onClick: ev => ev.stopPropagation(), style: { flex: 'none', width: 16, height: 16, borderRadius: 8, border: '1px solid var(--color-hairline-strong)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, color: 'var(--color-muted)', cursor: 'help' } }, '?') : null,
            h('span', { className: 'animated-list__rim', 'aria-hidden': true })); }),
        h('span', { ref: indicatorRef, className: 'animated-list__indicator', 'aria-hidden': true }, h('span', { ref: ringRef, className: 'animated-list__ring' })))),
    frame ? h('span', { className: 'animated-list__frame-rim', 'aria-hidden': true }) : null);
}
module.exports = { AnimatedList };
