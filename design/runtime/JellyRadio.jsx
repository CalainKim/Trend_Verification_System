// Port of React Bits JellyRadio (JS + CSS). The `motion` springs are replaced by a small rAF spring solver (no npm here).
const { useEffect, useLayoutEffect, useRef, useState } = React;
if (!document.getElementById('jelly-radio-css')) {
  const st = document.createElement('style'); st.id = 'jelly-radio-css';
  st.textContent = `.jelly-radio{--jr-ease-out:cubic-bezier(0.23,1,0.32,1);flex:none;display:inline-flex;align-items:center;gap:var(--jr-gap);padding:var(--jr-pad-y) var(--jr-pad-x);user-select:none;-webkit-user-select:none}
.jelly-radio[data-disabled]{opacity:0.5;pointer-events:none}
.jelly-radio__chip{position:relative;margin:0;padding:0;border:0;background:none;color:inherit;font:inherit;cursor:pointer;outline:none;transform-origin:50% 50%;touch-action:manipulation;-webkit-tap-highlight-color:transparent}
.jelly-radio__chip[data-on='true']{cursor:default}
.jelly-radio__chip:focus-visible .jelly-radio__skin{box-shadow:0 0 0 2px var(--jr-active)}
.jelly-radio:not([data-disabled]) .jelly-radio__chip:disabled{cursor:default;opacity:0.4}
.jelly-radio__skin{position:relative;display:inline-flex;align-items:center;justify-content:center;gap:0.4em;height:var(--jr-h);padding:0 var(--jr-px);border-radius:var(--jr-radius);overflow:hidden;background:var(--jr-chip);color:var(--jr-text);font-size:var(--jr-font);font-weight:500;line-height:1;white-space:nowrap;transition:transform 160ms var(--jr-ease-out),background-color 200ms ease,color 200ms ease}
.jelly-radio__skin::before{content:'';position:absolute;inset:0;background:var(--jr-text);opacity:0;pointer-events:none;transition:opacity 160ms ease}
@media (hover:hover) and (pointer:fine){.jelly-radio__chip[data-on='false']:not(:disabled):hover .jelly-radio__skin::before{opacity:0.11}}
.jelly-radio__chip:active .jelly-radio__skin{transform:scale(0.97)}
.jelly-radio__chip[data-on='true'] .jelly-radio__skin{background:var(--jr-active);color:var(--jr-active-text)}
.jelly-radio__icon{display:inline-flex}
@media (prefers-reduced-motion:reduce){.jelly-radio__chip:active .jelly-radio__skin{transform:none}}`;
  document.head.appendChild(st);
}
const SIZES = { sm: [28, 12, 12], md: [36, 13, 16], lg: [44, 14, 20] };
const reduceMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

// minimal spring value: v, vel; animate(target, {k, c, m, delay})
function makeVal(v0, onTick) {
  const o = { v: v0, vel: 0, tgt: v0, k: 500, c: 30, m: 1, start: 0, live: false };
  o.jump = x => { o.v = o.tgt = x; o.vel = 0; o.live = false; onTick(); };
  o.to = (x, { stiffness, damping, mass }, delay) => { o.tgt = x; o.k = stiffness; o.c = damping; o.m = mass; o.start = performance.now() + delay * 1000; o.live = true; };
  o.step = (now, dt) => {
    if (!o.live || now < o.start) return o.live;
    const a = (-o.k * (o.v - o.tgt) - o.c * o.vel) / o.m;
    o.vel += a * dt; o.v += o.vel * dt;
    if (Math.abs(o.vel) < 0.002 && Math.abs(o.v - o.tgt) < 0.0005) { o.v = o.tgt; o.vel = 0; o.live = false; }
    return true;
  };
  return o;
}
const spring = (k, m, bounce) => ({ stiffness: k, damping: 2 * Math.sqrt(k * m) * (1 - bounce), mass: m });

function JellyRadio({ items = ['Off', 'Low', 'Medium', 'High', 'Max'], value, defaultValue, onChange, chipColor = '#27272a', activeColor = '#f5f5f5', textColor = '#f5f5f5', activeTextColor = '#18181b', size = 'md', gap = 8, radius = 18, swell = 0.2, barge = 6, shrink = 0.05, jelly = 1, bounce = 0.25, stagger = 22, stiffness = 580, disabled = false, ariaLabel = 'Options', className = '' }) {
  const list = items.map(it => (typeof it === 'string' ? { value: it, label: it } : it));
  const [inner, setInner] = useState(() => defaultValue ?? list[0]?.value);
  const current = value ?? inner;
  const at = Math.max(0, list.findIndex(it => it.value === current));
  const groupRef = useRef(null), chipRefs = useRef([]), widths = useRef([]), mvs = useRef([]), applied = useRef(at), cfg = useRef({}), raf = useRef(0);
  cfg.current = { swell, barge, shrink, jelly, bounce, stagger, stiffness, count: list.length };
  const [hgt, font, px] = SIZES[size] ?? SIZES.md;
  const itemsKey = list.map(it => it.value).join('|');

  const paint = i => { const el = chipRefs.current[i], mv = mvs.current[i]; if (el && mv) el.style.transform = `translateX(${mv.x.v}px) scale(${mv.sx.v}, ${mv.sy.v})`; };
  const mvFor = i => { if (!mvs.current[i]) { const t = () => paint(i); mvs.current[i] = { x: makeVal(0, t), sx: makeVal(1, t), sy: makeVal(1, t) }; } return mvs.current[i]; };
  const loop = () => {
    let last = performance.now();
    cancelAnimationFrame(raf.current);
    const tick = now => {
      const dt = Math.min(0.032, (now - last) / 1000); last = now; let any = false;
      mvs.current.forEach((mv, i) => { if (!mv) return; let a = false; for (let s = 0; s < 4; s++) { a = mv.x.step(now, dt / 4) | mv.sx.step(now, dt / 4) | mv.sy.step(now, dt / 4) || a; } paint(i); any = any || a; });
      if (any) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
  };
  const apply = (sel, instant) => {
    const C = cfg.current, rtl = groupRef.current ? getComputedStyle(groupRef.current).direction === 'rtl' : false;
    const push = ((widths.current[sel] ?? 0) * C.swell) / 2 + C.barge;
    for (let i = 0; i < C.count; i++) {
      const mv = mvFor(i), far = Math.abs(i - sel), x = Math.sign(i - sel) * (rtl ? -1 : 1) * push, s = i === sel ? 1 + C.swell : 1 - C.shrink;
      if (instant || reduceMotion()) { mv.x.jump(x); mv.sx.jump(s); mv.sy.jump(s); continue; }
      const k = C.stiffness * (1 - 0.12 * Math.min(far, 3)), inFlight = mv.x.live || mv.sx.live || mv.sy.live, delay = inFlight ? 0 : (far * C.stagger) / 1000, j = C.jelly;
      mv.x.to(x, spring(k, 0.9, C.bounce), delay);
      mv.sx.to(s, spring(k * (1 + 0.24 * j), 0.9 - 0.1 * j, Math.min(0.85, C.bounce + 0.3 * j)), delay);
      mv.sy.to(s, spring(k * (1 - 0.14 * j), 0.9 + 0.05 * j, C.bounce), delay + 0.05 * j);
    }
    if (!instant) loop();
  };
  const measure = () => {
    const g = groupRef.current; if (!g) return;
    widths.current = chipRefs.current.map(el => el?.offsetWidth ?? 0);
    const chipH = chipRefs.current[0]?.offsetHeight ?? 0, maxW = Math.max(0, ...widths.current);
    g.style.setProperty('--jr-pad-x', `${Math.ceil((maxW * swell * 1.3) / 2 + barge) + 2}px`);
    g.style.setProperty('--jr-pad-y', `${Math.ceil((chipH * swell) / 2) + 2}px`);
  };
  useLayoutEffect(() => {
    const settle = () => { measure(); apply(applied.current, true); };
    settle();
    const ob = new ResizeObserver(settle); if (groupRef.current) ob.observe(groupRef.current);
    document.fonts?.ready.then(settle);
    return () => ob.disconnect();
  }, [itemsKey, size, gap, swell, barge, shrink]);
  useEffect(() => { if (applied.current === at) return; applied.current = at; apply(at, false); }, [at]);
  useEffect(() => () => cancelAnimationFrame(raf.current), []);

  const commit = (i, instant) => {
    if (disabled || !list[i] || list[i].disabled) return;
    if (i === at) { onChange?.(list[i].value, i, true); return; }
    applied.current = i; apply(i, instant);
    if (value === undefined) setInner(list[i].value);
    onChange?.(list[i].value, i);
  };
  const stepFrom = (i, dir) => { const n = list.length; let j = i; for (let t = 0; t < n; t++) { j = (j + dir + n) % n; if (!list[j].disabled) return j; } return i; };
  const onKeyDown = (e, i) => {
    let next = null;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = stepFrom(i, 1);
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = stepFrom(i, -1);
    else if (e.key === 'Home') next = stepFrom(-1, 1);
    else if (e.key === 'End') next = stepFrom(list.length, -1);
    else if (e.key === ' ' || e.key === 'Enter') next = i;
    if (next === null) return;
    e.preventDefault(); commit(next, true); chipRefs.current[next]?.focus();
  };
  const h = React.createElement;
  return h('div', { ref: groupRef, role: 'radiogroup', 'aria-label': ariaLabel, 'data-disabled': disabled ? '' : undefined, className: 'jelly-radio' + (className ? ' ' + className : ''),
    style: { '--jr-chip': chipColor, '--jr-active': activeColor, '--jr-text': textColor, '--jr-active-text': activeTextColor, '--jr-gap': `${gap}px`, '--jr-radius': `${radius}px`, '--jr-h': `${hgt}px`, '--jr-font': `${font}px`, '--jr-px': `${px}px` } },
    list.map((it, i) => { mvFor(i); return h('button', { key: it.value, ref: el => { chipRefs.current[i] = el; }, type: 'button', role: 'radio', 'aria-checked': i === at, tabIndex: i === at ? 0 : -1, disabled: disabled || !!it.disabled, className: 'jelly-radio__chip', 'data-on': i === at ? 'true' : 'false', onClick: e => commit(i, e.detail === 0), onKeyDown: e => onKeyDown(e, i) },
      h('span', { className: 'jelly-radio__skin' }, it.icon ? h('span', { className: 'jelly-radio__icon' }, it.icon) : null, h('span', { className: 'jelly-radio__label' }, it.label))); }));
}
module.exports = { JellyRadio };
