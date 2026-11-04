// Scanning animation for 지금 유행 search: category columns with candidate chips swept by a scan line, pulled into a central collector.
if (!document.getElementById('trend-scan-css')) {
  const st = document.createElement('style'); st.id = 'trend-scan-css';
  st.textContent = `.tsc{position:relative;flex:1;display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));grid-template-rows:minmax(0,1fr) auto;gap:10px;padding:18px 20px 20px;overflow:hidden}
.tsc[data-part='core']{display:flex;flex-direction:column;justify-content:flex-end}
.tsc__col{position:relative;display:flex;flex-direction:column;gap:6px;min-width:0;min-height:0;overflow:hidden}
.tsc__cat{font-size:12px;font-weight:600;color:var(--color-body);display:flex;justify-content:space-between}
.tsc__chip{position:relative;overflow:hidden;padding:6px 9px;border-radius:7px;font-size:12px;color:var(--color-body);background:var(--color-canvas);box-shadow:inset 0 0 0 1px var(--color-hairline-soft);white-space:nowrap;text-overflow:ellipsis;animation:tsc-lit 2.4s ease-in-out infinite;animation-delay:calc(var(--c) * 0.35s + var(--i) * 0.12s)}
.tsc__chip::after{content:'';position:absolute;inset:0;background:linear-gradient(90deg,transparent,rgba(38,37,30,0.10),transparent);transform:translateX(-100%);animation:tsc-sheen 2.4s ease-in-out infinite;animation-delay:inherit}
.tsc__scan{position:absolute;top:0;bottom:0;width:80px;left:-80px;background:linear-gradient(90deg,transparent,rgba(38,37,30,0.05),transparent);border-right:1px solid rgba(38,37,30,0.18);animation:tsc-scan 2.6s cubic-bezier(.45,0,.55,1) infinite;pointer-events:none}
.tsc__core{grid-column:1/-1;display:flex;align-items:center;gap:12px;margin-top:6px;padding:12px 14px;border-radius:10px;background:var(--color-ink);color:var(--color-canvas)}
.tsc__ring{position:relative;width:26px;height:26px;flex:none}
.tsc__ring i{position:absolute;inset:0;border-radius:50%;border:2px solid rgba(255,255,255,0.18);border-top-color:#fff;animation:tsc-rot 0.9s linear infinite}
.tsc__ring b{position:absolute;inset:8px;border-radius:50%;background:#fff;animation:tsc-beat 1.2s ease-in-out infinite}
.tsc__msg{flex:1;min-width:0;font-size:13px;font-weight:600}
.tsc__msg span{display:inline-block;animation:tsc-in 420ms cubic-bezier(.2,.7,.2,1)}
.tsc__dots{display:flex;gap:4px}.tsc__dots i{width:6px;height:6px;border-radius:3px;background:rgba(255,255,255,0.25);transition:background 300ms ease}.tsc__dots i[data-on]{background:#fff}
@keyframes tsc-lit{0%,70%,100%{color:var(--color-body);box-shadow:inset 0 0 0 1px var(--color-hairline-soft);transform:none}12%,30%{color:var(--color-ink);box-shadow:inset 0 0 0 1.5px var(--color-ink);transform:translateY(-1px)}}
@keyframes tsc-sheen{0%,8%{transform:translateX(-100%)}30%,100%{transform:translateX(100%)}}
@keyframes tsc-scan{to{left:100%}}@keyframes tsc-rot{to{transform:rotate(360deg)}}@keyframes tsc-beat{0%,100%{transform:scale(.6);opacity:.6}50%{transform:scale(1);opacity:1}}
@keyframes tsc-in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.tco{flex:1;display:flex;flex-direction:column;gap:8px;min-height:0}
.tco__head{display:flex;align-items:center;gap:10px;font-size:13px;font-weight:600;color:var(--color-ink)}
.tco__spin{width:16px;height:16px;flex:none;border-radius:50%;border:2px solid var(--color-hairline);border-top-color:var(--color-ink);animation:tsc-rot 0.8s linear infinite}
.tco__card{position:relative;flex:1;min-height:44px;border-radius:8px;background:var(--color-canvas);box-shadow:inset 0 0 0 1px var(--color-hairline-soft);overflow:hidden;opacity:0;animation:tco-in 500ms cubic-bezier(.2,.7,.2,1) forwards;animation-delay:calc(var(--i) * 0.5s)}
.tco__card::after{content:'';position:absolute;inset:0;background:linear-gradient(90deg,transparent,rgba(38,37,30,0.07),transparent);transform:translateX(-100%);animation:tco-sh 1.4s ease-in-out infinite}
.tco__bar{position:absolute;left:12px;height:8px;border-radius:4px;background:var(--color-hairline)}
.tco__pulse{position:absolute;left:-4px;top:50%;width:8px;height:8px;margin-top:-4px;border-radius:4px;background:var(--color-ink);animation:tco-pl 1.6s ease-in-out infinite;animation-delay:calc(var(--i) * 0.5s)}
@keyframes tco-in{from{opacity:0;transform:translateX(14px) scale(.98)}to{opacity:1;transform:none}}
@keyframes tco-sh{to{transform:translateX(100%)}}
@keyframes tco-pl{0%{transform:translateX(0);opacity:0}20%{opacity:1}100%{transform:translateX(40px);opacity:0}}
@keyframes tsc-rot{to{transform:rotate(360deg)}}
@media (prefers-reduced-motion:reduce){.tco__spin,.tco__card::after,.tco__pulse{animation:none}.tco__card{opacity:1;animation:none}}
@media (prefers-reduced-motion:reduce){.tsc__chip,.tsc__chip::after,.tsc__scan,.tsc__ring i,.tsc__ring b{animation:none}}`;
  document.head.appendChild(st);
}
function TrendScan({ cats = [], msg = '', step = 0, total = 5, part = 'all' }) {
  const h = React.createElement;
  return h('div', { className: 'tsc', 'data-part': part, style: { '--n': Math.max(1, cats.length) } },
    part !== 'core' ? h('span', { className: 'tsc__scan', 'aria-hidden': true }) : null,
    part === 'core' ? null : cats.map((c, ci) => h('div', { key: c.name, className: 'tsc__col' },
      h('span', { className: 'tsc__cat' }, h('span', null, c.name), h('span', { style: { fontFamily: 'var(--font-mono)', fontWeight: 400, color: 'var(--color-muted)' } }, c.types.length)),
      c.types.map((t, ti) => h('span', { key: t, className: 'tsc__chip', style: { '--c': ci, '--i': ti } }, t)))),
    part === 'cols' ? null : h('div', { className: 'tsc__core', role: 'status', style: part === 'core' ? { marginTop: 'auto' } : undefined },
      h('span', { className: 'tsc__ring', 'aria-hidden': true }, h('i'), h('b')),
      h('span', { className: 'tsc__msg' }, h('span', { key: msg }, msg)),
      h('span', { className: 'tsc__dots', 'aria-hidden': true }, Array.from({ length: total }, (_, i) => h('i', { key: i, 'data-on': i <= step ? '' : undefined })))));
}
function TrendCollect({ msg = '유행을 묶는 중', n = 3 }) {
  const h = React.createElement;
  return h('div', { className: 'tco', role: 'status' },
    h('span', { className: 'tco__head' }, h('span', { className: 'tco__spin', 'aria-hidden': true }), msg),
    Array.from({ length: n }, (_, i) => h('div', { key: i, className: 'tco__card', style: { '--i': i }, 'aria-hidden': true },
      h('span', { className: 'tco__pulse' }), h('span', { className: 'tco__bar', style: { top: 12, width: (46 + i * 13) + '%' } }), h('span', { className: 'tco__bar', style: { top: 26, width: (28 + i * 9) + '%', opacity: 0.6 } }))));
}
module.exports = { TrendScan, TrendCollect };
