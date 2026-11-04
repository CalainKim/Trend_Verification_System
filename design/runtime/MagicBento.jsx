// Adapted from React Bits MagicBento (JS + CSS): grid, spotlight, border glow, intro. Built-in demo visuals, stars, tilt, magnetism and click wave removed. Light design-system theme.
const { useLayoutEffect, useRef, useState } = React;
if (!document.getElementById('magic-bento-css')) {
  const st = document.createElement('style'); st.id = 'magic-bento-css';
  st.textContent = `.magic-bento{position:relative;box-sizing:border-box;display:grid;grid-auto-flow:row dense;width:100%;color:var(--color-ink)}
.magic-bento__cell{position:relative;min-width:0;min-height:0;--mb-delay:0ms}
.magic-bento[data-intro] .magic-bento__cell{opacity:0;transform:translate3d(0,16px,0) scale(0.97)}
.magic-bento[data-intro] .magic-bento__cell[data-state='in']{opacity:1;transform:none;transition:opacity 420ms cubic-bezier(0.22,1,0.36,1) var(--mb-delay),transform 760ms cubic-bezier(0.34,1.4,0.64,1) var(--mb-delay)}
.magic-bento__card{position:relative;box-sizing:border-box;display:flex;width:100%;height:100%;flex-direction:column;overflow:hidden;border-radius:var(--mb-radius);background:var(--color-surface-card);color:var(--color-ink);isolation:isolate;outline:none;text-align:left;border:0;padding:0;font:inherit}
.magic-bento__card[data-clickable]{cursor:pointer}
.magic-bento__card:focus-visible{box-shadow:0 0 0 2px var(--color-ink)}
.magic-bento__light{position:absolute;inset:0;z-index:1;border-radius:inherit;background:radial-gradient(var(--mb-spot) circle at var(--mb-x,-999px) var(--mb-y,-999px),rgba(38,37,30,calc(0.05 * var(--mb-hot,0))) 0%,rgba(38,37,30,0) 70%);pointer-events:none}
.magic-bento__rim{position:absolute;inset:0;z-index:3;border-radius:inherit;box-shadow:inset 0 0 0 1px var(--color-hairline);pointer-events:none}
.magic-bento__border{position:absolute;inset:0;z-index:4;box-sizing:border-box;padding:1px;border-radius:inherit;background:radial-gradient(var(--mb-bsize) circle at var(--mb-x,-999px) var(--mb-y,-999px),rgba(38,37,30,calc(0.55 * var(--mb-near,0))) 0%,rgba(38,37,30,0) 70%);-webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;mask:linear-gradient(#000 0 0) content-box exclude,linear-gradient(#000 0 0);pointer-events:none}
.magic-bento__content{position:relative;z-index:2;box-sizing:border-box;display:flex;min-height:0;flex:1;flex-direction:column;gap:10px;padding:16px 18px}
.magic-bento[data-intro] .mb-draw{clip-path:inset(-6px 100% -6px -6px)}
.magic-bento[data-intro] .magic-bento__cell[data-state='in'] .mb-draw{animation:mb-draw 1100ms cubic-bezier(0.65,0,0.35,1) calc(var(--mb-delay) + 220ms) forwards}
.magic-bento[data-intro] .mb-grow{transform:scaleX(0);transform-origin:left center}
.magic-bento[data-intro] .magic-bento__cell[data-state='in'] .mb-grow{animation:mb-grow 760ms cubic-bezier(0.34,1.4,0.64,1) calc(var(--mb-delay) + 200ms + var(--i,0) * 55ms) forwards}
@keyframes mb-draw{to{clip-path:inset(-6px -6px -6px -6px)}}@keyframes mb-grow{to{transform:scaleX(1)}}
.mb-flow{position:relative;display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));align-items:start;flex:1;min-height:0;padding-top:6px}
.mb-rail{position:absolute;top:15px;left:10%;right:10%;height:2px;z-index:0;border-radius:1px;background:var(--color-hairline)}
.mb-rail i{position:absolute;inset:0;border-radius:1px;background:var(--color-ink);transform-origin:left center;transform:scaleX(0)}
.mb-step{position:relative;display:flex;flex-direction:column;align-items:center;gap:6px;font-size:11px;color:var(--color-body);text-align:center}
.mb-st{position:relative;z-index:1;display:grid;width:20px;height:20px;place-items:center;border-radius:10px;background:var(--color-surface-card);box-shadow:0 0 0 4px var(--color-surface-card)}
.mb-st>*{grid-area:1/1}
.mb-pend{width:14px;height:14px;box-sizing:border-box;border:1.5px dashed var(--color-hairline-strong);border-radius:50%}
.mb-spin{width:16px;height:16px;box-sizing:border-box;border:2px solid var(--color-hairline);border-top-color:var(--color-ink);border-radius:50%;opacity:0}
.mb-done{display:grid;width:20px;height:20px;place-items:center;border-radius:50%;background:var(--color-ink);color:var(--color-canvas);opacity:0;scale:0.4}
.magic-bento__cell[data-state='in'] .mb-pend{animation:mb-hide 1ms linear calc(var(--mb-delay) + 400ms + var(--i) * 520ms) forwards}
.magic-bento__cell[data-state='in'] .mb-spin{animation:mb-run 520ms linear calc(var(--mb-delay) + 400ms + var(--i) * 520ms) both,mb-rot 700ms linear infinite}
.magic-bento__cell[data-state='in'] .mb-done{animation:mb-check 420ms cubic-bezier(0.34,1.4,0.64,1) calc(var(--mb-delay) + 920ms + var(--i) * 520ms) forwards}
.magic-bento__cell[data-state='in'] .mb-step>span:last-child{animation:mb-ink 300ms ease calc(var(--mb-delay) + 920ms + var(--i) * 520ms) forwards}
.magic-bento__cell[data-state='in'] .mb-rail i{animation:mb-fill calc(var(--n) * 520ms) linear calc(var(--mb-delay) + 400ms) forwards}
.mb-flowmsg{font-size:12px;color:var(--color-muted);opacity:0}
.magic-bento__cell[data-state='in'] .mb-flowmsg{animation:mb-fade 400ms ease calc(var(--mb-delay) + 400ms + var(--n) * 520ms + 400ms) forwards}
@keyframes mb-hide{to{opacity:0}}@keyframes mb-run{0%{opacity:0}1%,92%{opacity:1}100%{opacity:0}}@keyframes mb-rot{to{rotate:360deg}}
@keyframes mb-check{to{opacity:1;scale:1}}@keyframes mb-fill{to{transform:scaleX(1)}}@keyframes mb-ink{to{color:var(--color-ink)}}@keyframes mb-fade{to{opacity:1}}
@media (prefers-reduced-motion:reduce){.mb-pend,.mb-spin{display:none}.mb-done{opacity:1!important;scale:1!important;animation:none!important}.mb-rail i{transform:none!important;animation:none!important}.mb-flowmsg{opacity:1!important}}
@media (prefers-reduced-motion:reduce){.magic-bento .magic-bento__cell{opacity:1!important;transform:none!important}.magic-bento .mb-draw{clip-path:none!important;animation:none!important}.magic-bento .mb-grow{transform:none!important;animation:none!important}}`;
  document.head.appendChild(st);
}
const MIN_CELL = 150, MIN_PAIR = 200, STAGGER = 80;
function MagicBento({ items = [], columns = 4, rowHeight = 180, gap = 12, radius = 12, spotlightRadius = 300, intro = true, onItemClick, style }) {
  const rootRef = useRef(null), cardRefs = useRef([]), cellRefs = useRef([]);
  const [cols, setCols] = useState(columns);
  useLayoutEffect(() => {
    const root = rootRef.current; if (!root) return;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const pointer = { x: -1e5, y: -1e5, inside: false }, light = { x: -1e5, y: -1e5, near: 0 }, hot = [];
    let raf = 0, last = 0;
    const frame = now => {
      raf = 0; const dt = Math.min(0.05, (now - last) / 1000 || 0); last = now;
      const b = root.getBoundingClientRect(), m = spotlightRadius * 0.5;
      const near = pointer.inside && pointer.x > b.left - m && pointer.x < b.right + m && pointer.y > b.top - m && pointer.y < b.bottom + m ? 1 : 0;
      const f = 1 - Math.exp(-dt / 0.05); light.x += (pointer.x - light.x) * f; light.y += (pointer.y - light.y) * f;
      light.near += (near - light.near) * (1 - Math.exp(-dt / (near > light.near ? 0.12 : 0.4)));
      let busy = Math.abs(near - light.near) > 0.002 || Math.abs(pointer.x - light.x) + Math.abs(pointer.y - light.y) > 0.3;
      cardRefs.current.forEach((card, i) => {
        if (!card) return; const r = card.getBoundingClientRect(), lx = light.x - r.left, ly = light.y - r.top, px = pointer.x - r.left, py = pointer.y - r.top;
        const inside = pointer.inside && px >= 0 && py >= 0 && px <= r.width && py <= r.height, t = inside ? 1 : 0;
        hot[i] = (hot[i] || 0) + (t - (hot[i] || 0)) * (1 - Math.exp(-dt / (t ? 0.14 : 0.32))); if (Math.abs(t - hot[i]) > 0.002) busy = true;
        card.style.setProperty('--mb-x', lx.toFixed(1) + 'px'); card.style.setProperty('--mb-y', ly.toFixed(1) + 'px');
        card.style.setProperty('--mb-near', light.near.toFixed(3)); card.style.setProperty('--mb-hot', hot[i].toFixed(3));
      });
      if (busy) raf = requestAnimationFrame(frame);
    };
    const wake = () => { if (raf) return; last = performance.now(); raf = requestAnimationFrame(frame); };
    const move = e => { pointer.x = e.clientX; pointer.y = e.clientY; if (!light.near) { light.x = e.clientX; light.y = e.clientY; } pointer.inside = true; wake(); };
    const out = e => { if (e.relatedTarget) return; pointer.inside = false; wake(); };
    const ro = new ResizeObserver(() => { const w = root.clientWidth, cell = n => (w - gap * (n - 1)) / n; setCols(cell(columns) >= MIN_CELL ? columns : columns >= 2 && cell(2) >= MIN_PAIR ? 2 : 1); });
    ro.observe(root);
    if (intro && !reduced) { root.dataset.intro = ''; requestAnimationFrame(() => cellRefs.current.forEach((c, i) => { if (!c) return; c.style.setProperty('--mb-delay', i * STAGGER + 'ms'); c.dataset.state = 'in'; })); }
    window.addEventListener('pointermove', move, { passive: true }); document.addEventListener('pointerout', out);
    return () => { cancelAnimationFrame(raf); ro.disconnect(); window.removeEventListener('pointermove', move); document.removeEventListener('pointerout', out); };
  }, []);
  const h = React.createElement, span = Math.max(1, cols);
  return h('div', { ref: rootRef, className: 'magic-bento', style: { '--mb-radius': radius + 'px', '--mb-spot': spotlightRadius + 'px', '--mb-bsize': Math.round(spotlightRadius * 0.75) + 'px', gridTemplateColumns: `repeat(${span}, minmax(0, 1fr))`, gridAutoRows: span === 1 ? `minmax(${rowHeight}px, auto)` : rowHeight + 'px', gap: gap + 'px', ...style } },
    items.map((it, i) => h('div', { key: it.id ?? i, ref: el => { cellRefs.current[i] = el; }, className: 'magic-bento__cell', style: { gridColumn: `span ${Math.min(span, it.colSpan || 1)}`, gridRow: `span ${it.rowSpan || 1}` } },
      h(it.onClick || onItemClick ? 'button' : 'div', { ref: el => { cardRefs.current[i] = el; }, type: it.onClick || onItemClick ? 'button' : undefined, className: 'magic-bento__card', 'data-clickable': it.onClick || onItemClick ? '' : undefined, 'data-tip': it.tip, 'aria-label': it.title, onClick: () => { it.onClick?.(); onItemClick?.(it, i); } },
        h('span', { className: 'magic-bento__light' }), h('div', { className: 'magic-bento__content' }, it.content), h('span', { className: 'magic-bento__rim' }), h('span', { className: 'magic-bento__border' })))));
}
module.exports = { MagicBento };
