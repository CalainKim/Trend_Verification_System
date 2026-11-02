/* @ds-bundle: {"format":4,"namespace":"TrendCheckDesignSystem_f78377","components":[{"name":"Button","sourcePath":"components/actions/Button.jsx"},{"name":"ComparisonCard","sourcePath":"components/cards/ComparisonCard.jsx"},{"name":"FeatureCard","sourcePath":"components/cards/FeatureCard.jsx"},{"name":"PricingTierCard","sourcePath":"components/cards/PricingTierCard.jsx"},{"name":"TestimonialCard","sourcePath":"components/cards/TestimonialCard.jsx"},{"name":"Badge","sourcePath":"components/display/Badge.jsx"},{"name":"CodeBlock","sourcePath":"components/display/CodeBlock.jsx"},{"name":"TimelinePill","sourcePath":"components/display/TimelinePill.jsx"},{"name":"TextInput","sourcePath":"components/forms/TextInput.jsx"},{"name":"Footer","sourcePath":"components/navigation/Footer.jsx"},{"name":"FooterLink","sourcePath":"components/navigation/FooterLink.jsx"},{"name":"TopNav","sourcePath":"components/navigation/TopNav.jsx"},{"name":"IdeMockupCard","sourcePath":"components/product/IdeMockupCard.jsx"},{"name":"IdePane","sourcePath":"components/product/IdePane.jsx"},{"name":"CtaBand","sourcePath":"components/sections/CtaBand.jsx"},{"name":"HeroBand","sourcePath":"components/sections/HeroBand.jsx"}],"sourceHashes":{"components/actions/Button.jsx":"85a6a67352f4","components/cards/ComparisonCard.jsx":"699f19b1c141","components/cards/FeatureCard.jsx":"5ffe30b3e56d","components/cards/PricingTierCard.jsx":"5faa883adb27","components/cards/TestimonialCard.jsx":"b2403bedc110","components/display/Badge.jsx":"2d3aa226b38f","components/display/CodeBlock.jsx":"2ec0c37de12b","components/display/TimelinePill.jsx":"6cd3b3580d3a","components/forms/TextInput.jsx":"21edcfd9b037","components/navigation/Footer.jsx":"67cd5518414c","components/navigation/FooterLink.jsx":"7191ce889224","components/navigation/TopNav.jsx":"a51f25162694","components/product/IdeMockupCard.jsx":"ec5ce0c3b6b2","components/product/IdePane.jsx":"32bade91b873","components/sections/CtaBand.jsx":"5dc052d20651","components/sections/HeroBand.jsx":"a4dbc98be91c","ui_kits/web/HomeScreen.jsx":"8a87a0aef401","ui_kits/web/MethodScreen.jsx":"56ced0fffdea","ui_kits/web/VerifyScreen.jsx":"aca60eb65cc1"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.TrendCheckDesignSystem_f78377 = window.TrendCheckDesignSystem_f78377 || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/actions/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const base = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 8,
  font: 'var(--type-button)',
  borderRadius: 'var(--radius-md)',
  border: '1px solid transparent',
  cursor: 'pointer',
  textDecoration: 'none',
  whiteSpace: 'nowrap',
  transition: 'background-color 120ms ease, color 120ms ease, border-color 120ms ease'
};
const variants = {
  primary: {
    background: 'var(--color-primary)',
    color: 'var(--color-on-primary)',
    height: 40,
    padding: '10px 18px'
  },
  secondary: {
    background: 'var(--color-surface-card)',
    color: 'var(--color-ink)',
    borderColor: 'var(--color-hairline-strong)',
    height: 40,
    padding: '10px 18px'
  },
  tertiary: {
    background: 'transparent',
    color: 'var(--color-ink)',
    height: 40,
    padding: '10px 4px'
  },
  download: {
    background: 'var(--color-ink)',
    color: 'var(--color-canvas)',
    height: 44,
    padding: '12px 20px'
  }
};
const pressed = {
  primary: {
    background: 'var(--color-primary-active)'
  },
  secondary: {
    background: 'var(--color-canvas)'
  },
  tertiary: {
    color: 'var(--color-primary)'
  },
  download: {
    background: '#000000'
  }
};
function Button({
  variant = 'primary',
  icon,
  iconRight,
  disabled = false,
  href,
  onClick,
  children,
  style,
  type = 'button',
  ...rest
}) {
  const [down, setDown] = React.useState(false);
  const s = {
    ...base,
    ...variants[variant],
    ...(down && !disabled ? pressed[variant] : null),
    ...(disabled ? {
      opacity: 0.45,
      cursor: 'not-allowed'
    } : null),
    ...style
  };
  const handlers = {
    onMouseDown: () => setDown(true),
    onMouseUp: () => setDown(false),
    onMouseLeave: () => setDown(false)
  };
  const content = [icon, children, variant === 'tertiary' && iconRight === undefined ? /*#__PURE__*/React.createElement("span", {
    key: "arr",
    "aria-hidden": "true"
  }, "\u2192") : iconRight].filter(Boolean).map((c, i) => /*#__PURE__*/React.createElement(React.Fragment, {
    key: i
  }, c));
  if (href && !disabled) return /*#__PURE__*/React.createElement("a", _extends({
    href: href,
    style: s,
    onClick: onClick
  }, handlers, rest), content);
  return /*#__PURE__*/React.createElement("button", _extends({
    type: type,
    style: s,
    disabled: disabled,
    onClick: onClick
  }, handlers, rest), content);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/actions/Button.jsx", error: String((e && e.message) || e) }); }

// components/cards/ComparisonCard.jsx
try { (() => {
function ComparisonCard({
  leftTitle,
  rightTitle,
  rows = [],
  style
}) {
  const head = {
    font: 'var(--type-caption-upper)',
    letterSpacing: 'var(--caption-upper-ls)',
    textTransform: 'uppercase',
    padding: '16px 24px'
  };
  const cell = {
    font: 'var(--type-body-sm)',
    padding: '14px 24px',
    borderTop: '1px solid var(--color-hairline-soft)'
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--color-surface-card)',
      border: '1px solid var(--color-hairline)',
      borderRadius: 'var(--radius-lg)',
      overflow: 'hidden',
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      ...head,
      color: 'var(--color-muted)'
    }
  }, leftTitle), /*#__PURE__*/React.createElement("div", {
    style: {
      ...head,
      color: 'var(--color-ink)',
      borderLeft: '1px solid var(--color-hairline)'
    }
  }, rightTitle), rows.map((r, i) => /*#__PURE__*/React.createElement(React.Fragment, {
    key: i
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      ...cell,
      color: 'var(--color-muted)'
    }
  }, r.left), /*#__PURE__*/React.createElement("div", {
    style: {
      ...cell,
      color: 'var(--color-ink)',
      borderLeft: '1px solid var(--color-hairline)'
    }
  }, r.right))));
}
Object.assign(__ds_scope, { ComparisonCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/cards/ComparisonCard.jsx", error: String((e && e.message) || e) }); }

// components/cards/FeatureCard.jsx
try { (() => {
function FeatureCard({
  eyebrow,
  title,
  children,
  media,
  footer,
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--color-surface-card)',
      border: '1px solid var(--color-hairline)',
      borderRadius: 'var(--radius-lg)',
      padding: 24,
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
      color: 'var(--color-ink)',
      ...style
    }
  }, media, eyebrow && /*#__PURE__*/React.createElement("div", {
    style: {
      font: 'var(--type-caption-upper)',
      letterSpacing: 'var(--caption-upper-ls)',
      textTransform: 'uppercase',
      color: 'var(--color-muted)'
    }
  }, eyebrow), title && /*#__PURE__*/React.createElement("div", {
    style: {
      font: 'var(--type-title-md)',
      color: 'var(--color-ink)'
    }
  }, title), children && /*#__PURE__*/React.createElement("div", {
    style: {
      font: 'var(--type-body-md)',
      color: 'var(--color-body)',
      textWrap: 'pretty'
    }
  }, children), footer && /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 'auto',
      paddingTop: 8
    }
  }, footer));
}
Object.assign(__ds_scope, { FeatureCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/cards/FeatureCard.jsx", error: String((e && e.message) || e) }); }

// components/cards/PricingTierCard.jsx
try { (() => {
function PricingTierCard({
  name,
  price,
  period,
  description,
  features = [],
  action,
  featured = false,
  style
}) {
  const fg = featured ? 'var(--color-canvas)' : 'var(--color-ink)';
  const sub = featured ? 'var(--color-muted-soft)' : 'var(--color-muted)';
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: featured ? 'var(--color-ink)' : 'var(--color-surface-card)',
      border: '1px solid ' + (featured ? 'var(--color-ink)' : 'var(--color-hairline)'),
      borderRadius: 'var(--radius-lg)',
      padding: 32,
      display: 'flex',
      flexDirection: 'column',
      gap: 20,
      color: fg,
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      font: 'var(--type-title-md)'
    }
  }, name), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'baseline',
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-display-lg)',
      letterSpacing: 'var(--display-lg-ls)'
    }
  }, price), period && /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-body-sm)',
      color: sub
    }
  }, period)), description && /*#__PURE__*/React.createElement("div", {
    style: {
      font: 'var(--type-body-sm)',
      color: sub
    }
  }, description)), action, /*#__PURE__*/React.createElement("ul", {
    style: {
      listStyle: 'none',
      margin: 0,
      padding: 0,
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
      borderTop: '1px solid ' + (featured ? 'rgba(247,247,244,0.16)' : 'var(--color-hairline-soft)'),
      paddingTop: 20
    }
  }, features.map((f, i) => /*#__PURE__*/React.createElement("li", {
    key: i,
    style: {
      font: 'var(--type-body-sm)',
      display: 'flex',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      color: sub
    }
  }, "\u2713"), /*#__PURE__*/React.createElement("span", null, f)))));
}
Object.assign(__ds_scope, { PricingTierCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/cards/PricingTierCard.jsx", error: String((e && e.message) || e) }); }

// components/cards/TestimonialCard.jsx
try { (() => {
function TestimonialCard({
  quote,
  name,
  role,
  style
}) {
  return /*#__PURE__*/React.createElement("figure", {
    style: {
      margin: 0,
      background: 'var(--color-surface-card)',
      border: '1px solid var(--color-hairline)',
      borderRadius: 'var(--radius-lg)',
      padding: 24,
      display: 'flex',
      flexDirection: 'column',
      gap: 20,
      ...style
    }
  }, /*#__PURE__*/React.createElement("blockquote", {
    style: {
      margin: 0,
      font: 'var(--type-body-md)',
      letterSpacing: 'var(--body-tracked-ls)',
      color: 'var(--color-body)',
      textWrap: 'pretty'
    }
  }, quote), /*#__PURE__*/React.createElement("figcaption", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 2
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-title-sm)',
      color: 'var(--color-ink)'
    }
  }, name), role && /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-caption)',
      color: 'var(--color-muted)'
    }
  }, role)));
}
Object.assign(__ds_scope, { TestimonialCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/cards/TestimonialCard.jsx", error: String((e && e.message) || e) }); }

// components/display/Badge.jsx
try { (() => {
const tones = {
  neutral: {
    background: 'var(--color-surface-strong)',
    color: 'var(--color-ink)'
  },
  outline: {
    background: 'transparent',
    color: 'var(--color-body)',
    boxShadow: 'inset 0 0 0 1px var(--color-hairline-strong)'
  },
  ink: {
    background: 'var(--color-ink)',
    color: 'var(--color-canvas)'
  },
  success: {
    background: 'transparent',
    color: 'var(--color-semantic-success)',
    boxShadow: 'inset 0 0 0 1px currentColor'
  },
  error: {
    background: 'transparent',
    color: 'var(--color-semantic-error)',
    boxShadow: 'inset 0 0 0 1px currentColor'
  }
};
function Badge({
  tone = 'neutral',
  shape = 'pill',
  children,
  style
}) {
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      padding: '4px 10px',
      borderRadius: shape === 'tag' ? 'var(--radius-xs)' : 'var(--radius-pill)',
      font: 'var(--type-caption-upper)',
      letterSpacing: 'var(--caption-upper-ls)',
      textTransform: 'uppercase',
      whiteSpace: 'nowrap',
      ...tones[tone],
      ...style
    }
  }, children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/display/Badge.jsx", error: String((e && e.message) || e) }); }

// components/display/CodeBlock.jsx
try { (() => {
function CodeBlock({
  code,
  title,
  lines,
  style
}) {
  const rows = lines || String(code ?? '').split('\n').map(t => ({
    text: t
  }));
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--color-surface-card)',
      border: '1px solid var(--color-hairline)',
      borderRadius: 'var(--radius-lg)',
      overflow: 'hidden',
      ...style
    }
  }, title && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '10px 20px',
      borderBottom: '1px solid var(--color-hairline-soft)',
      font: 'var(--type-code)',
      fontSize: 12,
      color: 'var(--color-muted)'
    }
  }, title), /*#__PURE__*/React.createElement("pre", {
    style: {
      margin: 0,
      padding: 20,
      font: 'var(--type-code)',
      color: 'var(--color-ink)',
      overflowX: 'auto'
    }
  }, rows.map((r, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      color: r.tone === 'muted' ? 'var(--color-muted)' : r.tone === 'success' ? 'var(--color-semantic-success)' : r.tone === 'error' ? 'var(--color-semantic-error)' : r.tone === 'body' ? 'var(--color-body)' : undefined,
      minHeight: '1.5em'
    }
  }, r.text))));
}
Object.assign(__ds_scope, { CodeBlock });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/display/CodeBlock.jsx", error: String((e && e.message) || e) }); }

// components/display/TimelinePill.jsx
try { (() => {
const stages = {
  collect: {
    bg: 'var(--color-timeline-thinking)',
    fg: 'var(--color-ink)',
    label: '수집'
  },
  search: {
    bg: 'var(--color-timeline-grep)',
    fg: 'var(--color-ink)',
    label: '탐색'
  },
  analyze: {
    bg: 'var(--color-timeline-read)',
    fg: 'var(--color-ink)',
    label: '분석'
  },
  verify: {
    bg: 'var(--color-timeline-edit)',
    fg: 'var(--color-ink)',
    label: '검증'
  },
  verdict: {
    bg: 'var(--color-timeline-done)',
    fg: 'var(--color-on-primary)',
    label: '판정'
  }
};
const aliases = {
  thinking: 'collect',
  grep: 'search',
  read: 'analyze',
  edit: 'verify',
  done: 'verdict'
};
function TimelinePill({
  stage = 'collect',
  children,
  pending = false,
  style
}) {
  const s = stages[aliases[stage] || stage] || stages.collect;
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      padding: '4px 10px',
      borderRadius: 'var(--radius-pill)',
      background: pending ? 'transparent' : s.bg,
      color: pending ? 'var(--color-muted)' : s.fg,
      boxShadow: pending ? 'inset 0 0 0 1px var(--color-hairline-strong)' : 'none',
      font: 'var(--type-caption-upper)',
      letterSpacing: 'var(--caption-upper-ls)',
      textTransform: 'uppercase',
      whiteSpace: 'nowrap',
      ...style
    }
  }, children ?? s.label);
}
Object.assign(__ds_scope, { TimelinePill });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/display/TimelinePill.jsx", error: String((e && e.message) || e) }); }

// components/forms/TextInput.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function TextInput({
  label,
  hint,
  error,
  mono = false,
  prefix,
  value,
  defaultValue,
  onChange,
  placeholder,
  disabled = false,
  style,
  inputStyle,
  ...rest
}) {
  const [focus, setFocus] = React.useState(false);
  const id = React.useId();
  const border = error ? 'var(--color-semantic-error)' : focus ? 'var(--color-ink)' : 'var(--color-hairline-strong)';
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      ...style
    }
  }, label && /*#__PURE__*/React.createElement("label", {
    htmlFor: id,
    style: {
      font: 'var(--type-caption)',
      fontWeight: 500,
      color: 'var(--color-ink)'
    }
  }, label), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      height: 44,
      padding: '0 16px',
      background: disabled ? 'var(--color-canvas)' : 'var(--color-surface-card)',
      border: '1px solid ' + border,
      borderRadius: 'var(--radius-md)',
      transition: 'border-color 120ms ease'
    }
  }, prefix && /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--color-muted)',
      display: 'inline-flex'
    }
  }, prefix), /*#__PURE__*/React.createElement("input", _extends({
    id: id,
    value: value,
    defaultValue: defaultValue,
    onChange: onChange,
    placeholder: placeholder,
    disabled: disabled,
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false),
    style: {
      flex: 1,
      minWidth: 0,
      border: 0,
      outline: 0,
      background: 'transparent',
      padding: '12px 0',
      font: mono ? 'var(--type-code)' : 'var(--type-body-md)',
      color: disabled ? 'var(--color-muted-soft)' : 'var(--color-ink)',
      ...inputStyle
    }
  }, rest))), (error || hint) && /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-caption)',
      color: error ? 'var(--color-semantic-error)' : 'var(--color-muted)'
    }
  }, error || hint));
}
Object.assign(__ds_scope, { TextInput });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/TextInput.jsx", error: String((e && e.message) || e) }); }

// components/navigation/FooterLink.jsx
try { (() => {
function FooterLink({
  href = '#',
  children,
  onClick
}) {
  return /*#__PURE__*/React.createElement("a", {
    href: href,
    onClick: onClick,
    style: {
      font: 'var(--type-body-sm)',
      color: 'var(--color-body)',
      textDecoration: 'none',
      background: 'transparent'
    }
  }, children);
}
Object.assign(__ds_scope, { FooterLink });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/FooterLink.jsx", error: String((e && e.message) || e) }); }

// components/navigation/Footer.jsx
try { (() => {
function Footer({
  brand = 'TrendCheck',
  columns = [],
  note,
  style
}) {
  return /*#__PURE__*/React.createElement("footer", {
    style: {
      background: 'var(--color-canvas)',
      color: 'var(--color-body)',
      borderTop: '1px solid var(--color-hairline)',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 'var(--container-max)',
      margin: '0 auto',
      padding: '64px 48px',
      display: 'grid',
      gridTemplateColumns: 'repeat(5, minmax(0, 1fr))',
      gap: 32
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: '400 18px/1 var(--font-sans)',
      letterSpacing: '-0.4px',
      color: 'var(--color-ink)'
    }
  }, brand), note && /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-caption)',
      color: 'var(--color-muted)'
    }
  }, note)), columns.slice(0, 4).map((c, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-caption-upper)',
      letterSpacing: 'var(--caption-upper-ls)',
      textTransform: 'uppercase',
      color: 'var(--color-muted)',
      marginBottom: 4
    }
  }, c.title), c.links.map((l, j) => /*#__PURE__*/React.createElement(__ds_scope.FooterLink, {
    key: j,
    href: l.href
  }, l.label))))));
}
Object.assign(__ds_scope, { Footer });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/Footer.jsx", error: String((e && e.message) || e) }); }

// components/navigation/TopNav.jsx
try { (() => {
function TopNav({
  brand = 'TrendCheck',
  links = [],
  active,
  onNavigate,
  secondaryAction,
  primaryAction,
  style
}) {
  return /*#__PURE__*/React.createElement("header", {
    style: {
      height: 'var(--nav-height)',
      background: 'var(--color-canvas)',
      borderBottom: '1px solid var(--color-hairline-soft)',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 'var(--container-max)',
      margin: '0 auto',
      height: '100%',
      padding: '0 24px',
      display: 'flex',
      alignItems: 'center',
      gap: 32
    }
  }, /*#__PURE__*/React.createElement("a", {
    href: "#",
    onClick: e => {
      e.preventDefault();
      onNavigate && onNavigate('home');
    },
    style: {
      font: '400 20px/1 var(--font-sans)',
      letterSpacing: '-0.5px',
      color: 'var(--color-ink)',
      textDecoration: 'none'
    }
  }, brand), /*#__PURE__*/React.createElement("nav", {
    style: {
      display: 'flex',
      gap: 24,
      flex: 1
    }
  }, links.map(l => {
    const key = l.key || l.label;
    return /*#__PURE__*/React.createElement("a", {
      key: key,
      href: l.href || '#',
      onClick: e => {
        if (onNavigate) {
          e.preventDefault();
          onNavigate(key);
        }
      },
      style: {
        font: 'var(--type-nav-link)',
        color: active === key ? 'var(--color-ink)' : 'var(--color-body)',
        textDecoration: 'none'
      }
    }, l.label);
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8,
      alignItems: 'center'
    }
  }, secondaryAction && /*#__PURE__*/React.createElement(__ds_scope.Button, {
    variant: "tertiary",
    iconRight: null,
    onClick: secondaryAction.onClick
  }, secondaryAction.label), primaryAction && /*#__PURE__*/React.createElement(__ds_scope.Button, {
    onClick: primaryAction.onClick
  }, primaryAction.label))));
}
Object.assign(__ds_scope, { TopNav });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/TopNav.jsx", error: String((e && e.message) || e) }); }

// components/product/IdeMockupCard.jsx
try { (() => {
function IdeMockupCard({
  title = 'TrendCheck — console',
  sidebar,
  main,
  chat,
  terminal,
  height = 460,
  style
}) {
  const cols = [sidebar ? '200px' : null, 'minmax(0,1fr)', chat ? '300px' : null].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--color-surface-card)',
      border: '1px solid var(--color-hairline)',
      borderRadius: 'var(--radius-lg)',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: 36,
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '0 14px',
      borderBottom: '1px solid var(--color-hairline)'
    }
  }, [0, 1, 2].map(i => /*#__PURE__*/React.createElement("span", {
    key: i,
    style: {
      width: 10,
      height: 10,
      borderRadius: '50%',
      background: 'var(--color-hairline-strong)'
    }
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      textAlign: 'center',
      font: 'var(--type-caption)',
      color: 'var(--color-muted)'
    }
  }, title), /*#__PURE__*/React.createElement("span", {
    style: {
      width: 46
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: cols,
      gap: 6,
      padding: 6,
      height
    }
  }, sidebar, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateRows: terminal ? 'minmax(0,1fr) 140px' : 'minmax(0,1fr)',
      gap: 6,
      minHeight: 0,
      minWidth: 0
    }
  }, main, terminal), chat));
}
Object.assign(__ds_scope, { IdeMockupCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/product/IdeMockupCard.jsx", error: String((e && e.message) || e) }); }

// components/product/IdePane.jsx
try { (() => {
function IdePane({
  title,
  actions,
  children,
  padded = true,
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--color-canvas-soft)',
      border: '1px solid var(--color-hairline-soft)',
      borderRadius: 'var(--radius-md)',
      display: 'flex',
      flexDirection: 'column',
      minWidth: 0,
      minHeight: 0,
      overflow: 'hidden',
      ...style
    }
  }, title && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 8,
      padding: '8px 16px',
      borderBottom: '1px solid var(--color-hairline-soft)',
      font: 'var(--type-code)',
      fontSize: 12,
      color: 'var(--color-muted)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap'
    }
  }, title), actions), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: padded ? 16 : 0,
      font: 'var(--type-code)',
      color: 'var(--color-body)',
      flex: 1,
      minHeight: 0,
      overflow: 'auto'
    }
  }, children));
}
Object.assign(__ds_scope, { IdePane });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/product/IdePane.jsx", error: String((e && e.message) || e) }); }

// components/sections/CtaBand.jsx
try { (() => {
function CtaBand({
  title,
  subtitle,
  action,
  style
}) {
  return /*#__PURE__*/React.createElement("section", {
    style: {
      background: 'var(--color-canvas)',
      padding: '96px 24px',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 'var(--container-max)',
      margin: '0 auto',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      textAlign: 'center',
      gap: 24
    }
  }, /*#__PURE__*/React.createElement("h2", {
    style: {
      margin: 0,
      font: 'var(--type-display-lg)',
      letterSpacing: 'var(--display-lg-ls)',
      color: 'var(--color-ink)',
      textWrap: 'balance'
    }
  }, title), subtitle && /*#__PURE__*/React.createElement("p", {
    style: {
      margin: 0,
      font: 'var(--type-body-md)',
      color: 'var(--color-body)'
    }
  }, subtitle), action));
}
Object.assign(__ds_scope, { CtaBand });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/sections/CtaBand.jsx", error: String((e && e.message) || e) }); }

// components/sections/HeroBand.jsx
try { (() => {
function HeroBand({
  eyebrow,
  title,
  subtitle,
  actions,
  children,
  align = 'center',
  style
}) {
  const center = align === 'center';
  return /*#__PURE__*/React.createElement("section", {
    style: {
      background: 'var(--color-canvas)',
      padding: '80px 24px',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 'var(--container-max)',
      margin: '0 auto',
      display: 'flex',
      flexDirection: 'column',
      alignItems: center ? 'center' : 'flex-start',
      textAlign: center ? 'center' : 'left',
      gap: 24
    }
  }, eyebrow, /*#__PURE__*/React.createElement("h1", {
    style: {
      margin: 0,
      font: 'var(--type-display-mega)',
      fontSize: 'clamp(32px, 6vw, 72px)',
      letterSpacing: 'var(--display-mega-ls)',
      color: 'var(--color-ink)',
      maxWidth: 900,
      textWrap: 'balance'
    }
  }, title), subtitle && /*#__PURE__*/React.createElement("p", {
    style: {
      margin: 0,
      font: 'var(--type-body-md)',
      color: 'var(--color-body)',
      maxWidth: 560,
      textWrap: 'pretty'
    }
  }, subtitle), actions && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 16,
      alignItems: 'center',
      flexWrap: 'wrap',
      justifyContent: center ? 'center' : 'flex-start'
    }
  }, actions), children && /*#__PURE__*/React.createElement("div", {
    style: {
      width: '100%',
      marginTop: 32
    }
  }, children)));
}
Object.assign(__ds_scope, { HeroBand });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/sections/HeroBand.jsx", error: String((e && e.message) || e) }); }

// ui_kits/web/HomeScreen.jsx
try { (() => {
const {
  HeroBand,
  Button,
  IdeMockupCard,
  IdePane,
  TimelinePill,
  FeatureCard,
  ComparisonCard,
  TestimonialCard,
  PricingTierCard,
  CtaBand,
  Badge,
  CodeBlock
} = window.TrendCheckDesignSystem_f78377;
const homeSection = {
  maxWidth: 1200,
  margin: '0 auto',
  padding: '80px 24px',
  display: 'flex',
  flexDirection: 'column',
  gap: 32
};
const homeEyebrow = {
  font: 'var(--type-caption-upper)',
  letterSpacing: '0.88px',
  textTransform: 'uppercase',
  color: 'var(--color-muted)'
};
const homeH2 = {
  margin: 0,
  font: 'var(--type-display-lg)',
  letterSpacing: '-0.72px',
  color: 'var(--color-ink)',
  maxWidth: 720
};
function HomeMockup() {
  const kws = ['고프코어 바람막이', '발레코어 플랫', '카고 스커트', '바시티 재킷', '스웨이드 로퍼'];
  return /*#__PURE__*/React.createElement(IdeMockupCard, {
    title: "TrendCheck \u2014 \uACE0\uD504\uCF54\uC5B4 \uBC14\uB78C\uB9C9\uC774",
    height: 380,
    sidebar: /*#__PURE__*/React.createElement(IdePane, {
      title: "\uD0A4\uC6CC\uB4DC \xB7 5"
    }, kws.map((k, i) => /*#__PURE__*/React.createElement("div", {
      key: k,
      style: {
        padding: '5px 0',
        color: i === 0 ? 'var(--color-ink)' : undefined
      }
    }, i === 0 ? '› ' : '  ', k))),
    main: /*#__PURE__*/React.createElement(IdePane, {
      title: "report / \uACE0\uD504\uCF54\uC5B4-\uBC14\uB78C\uB9C9\uC774.md",
      style: {
        textAlign: 'left'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        color: 'var(--color-ink)'
      }
    }, "# \uD310\uC815: REAL"), /*#__PURE__*/React.createElement("div", null, "\xA0"), /*#__PURE__*/React.createElement("div", null, "## \uC2E0\uD638"), /*#__PURE__*/React.createElement("div", null, "\uAC80\uC0C9\uB7C9      +184%   \uAE30\uC900\uC120 \uB300\uBE44, 12\uC8FC"), /*#__PURE__*/React.createElement("div", null, "\uD310\uB9E4        +62%    \uC544\uC6B0\uD130 \uCE74\uD14C\uACE0\uB9AC"), /*#__PURE__*/React.createElement("div", null, "\uC18C\uC15C \uC5B8\uAE09   +3.1\u03C3   \uC2A4\uB0C5 \xB7 \uCEE4\uBBA4\uB2C8\uD2F0"), /*#__PURE__*/React.createElement("div", null, "\xA0"), /*#__PURE__*/React.createElement("div", {
      style: {
        color: 'var(--color-muted)'
      }
    }, "// \uC138 \uC2E0\uD638 \uBAA8\uB450 \uAC19\uC740 \uBC29\uD5A5. \uACC4\uC808\uC131 \uBCF4\uC815 \uD6C4\uC5D0\uB3C4 \uC720\uC9C0.")),
    terminal: /*#__PURE__*/React.createElement(IdePane, {
      title: "terminal",
      style: {
        textAlign: 'left'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        color: 'var(--color-muted)'
      }
    }, "$ trendcheck verify \"\uACE0\uD504\uCF54\uC5B4 \uBC14\uB78C\uB9C9\uC774\" --window 12w"), /*#__PURE__*/React.createElement("div", {
      style: {
        color: 'var(--color-semantic-success)'
      }
    }, "\u2713 verdict: REAL \u2014 3/3 signals agree")),
    chat: /*#__PURE__*/React.createElement(IdePane, {
      title: "Agent",
      style: {
        textAlign: 'left'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        alignItems: 'flex-start'
      }
    }, /*#__PURE__*/React.createElement(TimelinePill, {
      stage: "collect"
    }, "\uC218\uC9D1 \xB7 4,210\uAC74"), /*#__PURE__*/React.createElement(TimelinePill, {
      stage: "search"
    }, "\uD0D0\uC0C9 \xB7 3 sources"), /*#__PURE__*/React.createElement(TimelinePill, {
      stage: "analyze"
    }, "\uBD84\uC11D \xB7 12\uC8FC"), /*#__PURE__*/React.createElement(TimelinePill, {
      stage: "verify"
    }, "\uAC80\uC99D \xB7 \uACC4\uC808\uC131 \uBCF4\uC815"), /*#__PURE__*/React.createElement(TimelinePill, {
      stage: "verdict"
    }, "\uD310\uC815 \xB7 REAL"), /*#__PURE__*/React.createElement("div", {
      style: {
        marginTop: 6,
        color: 'var(--color-ink)'
      }
    }, "\uC138 \uC2E0\uD638\uAC00 \uBAA8\uB450 \uAE30\uC900\uC120\uC744 \uB118\uC5C8\uC2B5\uB2C8\uB2E4. \uC77C\uC2DC\uC801 \uC720\uD589\uC77C \uAC00\uB2A5\uC131\uC740 \uB0AE\uC2B5\uB2C8\uB2E4.")))
  });
}
function HomeScreen({
  onNavigate
}) {
  return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(HeroBand, {
    eyebrow: /*#__PURE__*/React.createElement(Badge, {
      tone: "outline"
    }, "\uBB34\uC2E0\uC0AC \uC790\uAE30\uC8FC\uB3C4\uD504\uB85C\uC81D\uD2B8"),
    title: "\uBC1C\uACAC\uD55C \uD2B8\uB80C\uB4DC, \uC9C4\uC9DC\uC778\uC9C0 \uD655\uC778\uD558\uC138\uC694",
    subtitle: "\uAC80\uC0C9\uB7C9, \uD310\uB9E4, \uC18C\uC15C \uC5B8\uAE09. \uC138 \uAC00\uC9C0 \uC2E0\uD638\uAC00 \uAC19\uC740 \uBC29\uD5A5\uC744 \uAC00\uB9AC\uD0AC \uB54C\uB9CC \uD2B8\uB80C\uB4DC\uB77C\uACE0 \uBD80\uB985\uB2C8\uB2E4.",
    actions: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
      variant: "download",
      onClick: () => onNavigate('verify')
    }, "\uD0A4\uC6CC\uB4DC \uAC80\uC99D\uD558\uAE30"), /*#__PURE__*/React.createElement(Button, {
      variant: "tertiary",
      onClick: () => onNavigate('method')
    }, "\uBC29\uBC95\uB860 \uBCF4\uAE30"))
  }, /*#__PURE__*/React.createElement(HomeMockup, null)), /*#__PURE__*/React.createElement("section", {
    style: homeSection
  }, /*#__PURE__*/React.createElement("div", {
    style: homeEyebrow
  }, "\uC138 \uAC00\uC9C0 \uC2E0\uD638"), /*#__PURE__*/React.createElement("h2", {
    style: homeH2
  }, "\uD558\uB098\uC758 \uC2E0\uD638\uB294 \uC18C\uBB38\uC785\uB2C8\uB2E4. \uC138 \uAC1C\uAC00 \uACB9\uCE58\uBA74 \uADFC\uAC70\uAC00 \uB429\uB2C8\uB2E4."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
      gap: 16
    }
  }, /*#__PURE__*/React.createElement(FeatureCard, {
    eyebrow: "Signal 01",
    title: "\uAC80\uC0C9\uB7C9"
  }, "\uB124\uC774\uBC84\uC640 \uBB34\uC2E0\uC0AC \uAC80\uC0C9\uC5B4\uC758 12\uC8FC \uCD94\uC138\uB97C \uC791\uB144 \uAC19\uC740 \uAE30\uAC04 \uAE30\uC900\uC120\uACFC \uBE44\uAD50\uD569\uB2C8\uB2E4."), /*#__PURE__*/React.createElement(FeatureCard, {
    eyebrow: "Signal 02",
    title: "\uD310\uB9E4"
  }, "\uCE74\uD14C\uACE0\uB9AC \uC548\uC5D0\uC11C \uD574\uB2F9 \uD0A4\uC6CC\uB4DC \uC0C1\uD488\uC758 \uD310\uB9E4 \uC0C1\uC2B9\uB960\uACFC \uC7AC\uAD6C\uB9E4\uC728\uC744 \uBD05\uB2C8\uB2E4."), /*#__PURE__*/React.createElement(FeatureCard, {
    eyebrow: "Signal 03",
    title: "\uC18C\uC15C \uC5B8\uAE09"
  }, "\uC2A4\uB0C5, \uCEE4\uBBA4\uB2C8\uD2F0 \uC5B8\uAE09\uB7C9\uC744 \uD45C\uC900\uD3B8\uCC28\uB85C \uD658\uC0B0\uD574 \uAC11\uC791\uC2A4\uB7EC\uC6B4 \uAE09\uB4F1\uC744 \uAC78\uB7EC\uB0C5\uB2C8\uB2E4."))), /*#__PURE__*/React.createElement("section", {
    style: {
      ...homeSection,
      paddingTop: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
      gap: 24,
      alignItems: 'start'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: homeEyebrow
  }, "\uAE30\uC874 \uBC29\uC2DD\uACFC \uBE44\uAD50"), /*#__PURE__*/React.createElement("h2", {
    style: homeH2
  }, "\uAC10\uC774 \uC544\uB2C8\uB77C \uAE30\uC900\uC120\uC73C\uB85C"), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: 0,
      color: 'var(--color-body)',
      maxWidth: 440
    }
  }, "\uBAA8\uB4E0 \uD310\uC815\uC740 \uAC19\uC740 \uADDC\uCE59\uC73C\uB85C \uACC4\uC0B0\uB418\uACE0, \uADFC\uAC70 \uB370\uC774\uD130\uC640 \uCFFC\uB9AC\uB97C \uD568\uAED8 \uB0A8\uAE41\uB2C8\uB2E4."), /*#__PURE__*/React.createElement(CodeBlock, {
    title: "rule.yaml",
    code: 'verdict: REAL\nwhen:\n  search_lift: ">= 50%"\n  sales_lift: ">= 20%"\n  social_z: ">= 2.0"\nwindow: 12w'
  })), /*#__PURE__*/React.createElement(ComparisonCard, {
    leftTitle: "\uAC10\uC73C\uB85C \uD310\uB2E8",
    rightTitle: "TrendCheck",
    rows: [{
      left: 'SNS 스크랩 몇 장',
      right: '검색 · 판매 · 소셜 3개 신호'
    }, {
      left: '"요즘 많이 보여요"',
      right: '기준선 대비 +184%'
    }, {
      left: '시즌 효과와 구분 어려움',
      right: '계절성 보정 후 판정'
    }, {
      left: '회의마다 다른 결론',
      right: '같은 규칙, 같은 결과'
    }]
  }))), /*#__PURE__*/React.createElement("section", {
    style: {
      ...homeSection,
      paddingTop: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: homeEyebrow
  }, "\uC0AC\uC6A9 \uD6C4\uAE30"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
      gap: 16
    }
  }, /*#__PURE__*/React.createElement(TestimonialCard, {
    quote: "\uAE30\uD68D \uD68C\uC758\uC5D0\uC11C '\uB290\uB08C'\uC774 \uC544\uB2C8\uB77C \uC22B\uC790\uB85C \uC774\uC57C\uAE30\uD558\uAC8C \uB410\uC5B4\uC694.",
    name: "\uAE40OO",
    role: "MD, \uC544\uC6B0\uD130"
  }), /*#__PURE__*/React.createElement(TestimonialCard, {
    quote: "\uAE09\uB4F1\uD55C \uD0A4\uC6CC\uB4DC\uC758 \uC808\uBC18\uC774 2\uC8FC \uB9CC\uC5D0 \uAEBC\uC9C4\uB2E4\uB294 \uAC78 \uCC98\uC74C \uC54C\uC558\uC2B5\uB2C8\uB2E4.",
    name: "\uC774OO",
    role: "\uB9C8\uCF00\uD130"
  }), /*#__PURE__*/React.createElement(TestimonialCard, {
    quote: "\uB9AC\uD3EC\uD2B8\uC5D0 \uCFFC\uB9AC\uAC00 \uD568\uAED8 \uB0A8\uC544\uC11C \uB2E4\uC2DC \uD655\uC778\uD558\uAE30 \uC27D\uC2B5\uB2C8\uB2E4.",
    name: "\uBC15OO",
    role: "\uB370\uC774\uD130 \uBD84\uC11D"
  }))), /*#__PURE__*/React.createElement("section", {
    style: {
      ...homeSection,
      paddingTop: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: homeEyebrow
  }, "\uC774\uC6A9 \uBC94\uC704"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
      gap: 16
    }
  }, /*#__PURE__*/React.createElement(PricingTierCard, {
    name: "Explorer",
    price: "5\uAC74",
    period: "/ \uC8FC",
    description: "\uAC1C\uC778 \uD0D0\uC0C9\uC6A9",
    features: ['키워드 검증', '기본 리포트'],
    action: /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      onClick: () => onNavigate('verify')
    }, "\uC2DC\uC791\uD558\uAE30")
  }), /*#__PURE__*/React.createElement(PricingTierCard, {
    featured: true,
    name: "Team",
    price: "\uBB34\uC81C\uD55C",
    description: "\uD300 \uACF5\uC720\uC640 \uC8FC\uAC04 \uB9AC\uD3EC\uD2B8",
    features: ['무제한 검증', '리포트 공유', '판정 변경 알림'],
    action: /*#__PURE__*/React.createElement(Button, {
      onClick: () => onNavigate('verify')
    }, "\uD300\uC73C\uB85C \uC2DC\uC791")
  }), /*#__PURE__*/React.createElement(PricingTierCard, {
    name: "Data",
    price: "API",
    description: "\uC0AC\uB0B4 \uB300\uC2DC\uBCF4\uB4DC \uC5F0\uB3D9",
    features: ['원천 데이터 접근', '커스텀 규칙'],
    action: /*#__PURE__*/React.createElement(Button, {
      variant: "secondary"
    }, "\uBB38\uC758\uD558\uAE30")
  }))), /*#__PURE__*/React.createElement(CtaBand, {
    title: "\uB2E4\uC74C \uD2B8\uB80C\uB4DC, \uAC80\uC99D\uBD80\uD130 \uC2DC\uC791\uD558\uC138\uC694",
    action: /*#__PURE__*/React.createElement(Button, {
      onClick: () => onNavigate('verify')
    }, "\uAC80\uC99D \uC2DC\uC791\uD558\uAE30")
  }));
}
window.HomeScreen = HomeScreen;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/web/HomeScreen.jsx", error: String((e && e.message) || e) }); }

// ui_kits/web/MethodScreen.jsx
try { (() => {
const {
  FeatureCard: MFeature,
  CodeBlock: MCode,
  TimelinePill: MPill
} = window.TrendCheckDesignSystem_f78377;
function MethodScreen() {
  const steps = [['collect', '수집', '검색어, 판매, 소셜 언급 원천 데이터를 같은 주 단위로 모읍니다.'], ['search', '탐색', '표기가 다른 유사 키워드와 관련 상품군을 묶습니다.'], ['analyze', '분석', '최근 12주 값을 작년 같은 기간 기준선과 비교합니다.'], ['verify', '검증', '계절성, 프로모션, 단발성 이벤트의 영향을 보정합니다.'], ['verdict', '판정', '세 신호의 통과 여부로 REAL · WATCH · FAD를 정합니다.']];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 1200,
      margin: '0 auto',
      padding: '80px 24px',
      display: 'flex',
      flexDirection: 'column',
      gap: 48
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 16,
      maxWidth: 720
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      font: 'var(--type-caption-upper)',
      letterSpacing: '0.88px',
      textTransform: 'uppercase',
      color: 'var(--color-muted)'
    }
  }, "\uBC29\uBC95\uB860"), /*#__PURE__*/React.createElement("h1", {
    style: {
      margin: 0,
      font: 'var(--type-display-lg)',
      fontSize: 48,
      letterSpacing: '-1.2px',
      lineHeight: 1.15,
      color: 'var(--color-ink)'
    }
  }, "\uBAA8\uB4E0 \uD310\uC815\uC740 \uB2E4\uC12F \uB2E8\uACC4\uB97C \uAC70\uCE69\uB2C8\uB2E4"), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: 0,
      color: 'var(--color-body)',
      letterSpacing: '0.08px'
    }
  }, "\uAC19\uC740 \uD0A4\uC6CC\uB4DC\uB294 \uC5B8\uC81C \uAC80\uC99D\uD574\uB3C4 \uAC19\uC740 \uADDC\uCE59\uC73C\uB85C \uACC4\uC0B0\uB429\uB2C8\uB2E4. \uB2E8\uACC4\uBCC4 \uC911\uAC04 \uACB0\uACFC\uB294 \uB9AC\uD3EC\uD2B8\uC5D0 \uD568\uAED8 \uAE30\uB85D\uB429\uB2C8\uB2E4.")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column'
    }
  }, steps.map(([s, t, d], i) => /*#__PURE__*/React.createElement("div", {
    key: s,
    style: {
      display: 'grid',
      gridTemplateColumns: '48px 140px minmax(0,1fr)',
      gap: 24,
      alignItems: 'center',
      padding: '20px 0',
      borderTop: '1px solid var(--color-hairline)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-code)',
      color: 'var(--color-muted)'
    }
  }, "0", i + 1), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement(MPill, {
    stage: s
  }, t)), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--color-body)'
    }
  }, d)))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
      gap: 16
    }
  }, /*#__PURE__*/React.createElement(MFeature, {
    eyebrow: "\uD310\uC815 \uADDC\uCE59",
    title: "\uC138 \uC2E0\uD638 \uBAA8\uB450 \uD1B5\uACFC\uD558\uBA74 REAL"
  }, "\uB450 \uAC1C\uB9CC \uD1B5\uACFC\uD558\uBA74 WATCH\uB85C \uB450\uACE0 4\uC8FC \uB4A4 \uB2E4\uC2DC \uAC80\uC99D\uD569\uB2C8\uB2E4. \uD558\uB098 \uC774\uD558\uB294 FAD\uC785\uB2C8\uB2E4."), /*#__PURE__*/React.createElement(MCode, {
    title: "rule.yaml",
    code: 'verdict: REAL\nwhen:\n  search_lift: ">= 50%"\n  sales_lift: ">= 20%"\n  social_z: ">= 2.0"\nwindow: 12w\nbaseline: same_period_last_year'
  })));
}
window.MethodScreen = MethodScreen;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/web/MethodScreen.jsx", error: String((e && e.message) || e) }); }

// ui_kits/web/VerifyScreen.jsx
try { (() => {
const {
  TextInput: VTextInput,
  Button: VButton,
  IdeMockupCard: VMockup,
  IdePane: VPane,
  TimelinePill: VPill,
  Badge: VBadge
} = window.TrendCheckDesignSystem_f78377;
const verifyStages = [{
  stage: 'collect',
  label: '수집',
  detail: '검색 · 판매 · 소셜 원천 데이터 수집'
}, {
  stage: 'search',
  label: '탐색',
  detail: '유사 키워드와 상품군 매칭'
}, {
  stage: 'analyze',
  label: '분석',
  detail: '12주 추세와 기준선 비교'
}, {
  stage: 'verify',
  label: '검증',
  detail: '계절성 · 이벤트 효과 보정'
}, {
  stage: 'verdict',
  label: '판정',
  detail: '규칙 적용'
}];
function fakeResult(kw) {
  let h = 0;
  for (const c of kw) h = h * 31 + c.charCodeAt(0) >>> 0;
  const s = 20 + h % 180,
    p = (h >> 3) % 90,
    z = (h >> 5) % 40 / 10;
  const pass = [s >= 50, p >= 20, z >= 2];
  const n = pass.filter(Boolean).length;
  return {
    s,
    p,
    z,
    pass,
    n,
    verdict: n === 3 ? 'REAL' : n === 2 ? 'WATCH' : 'FAD'
  };
}
function VerifyScreen() {
  const [kw, setKw] = React.useState('고프코어 바람막이');
  const [step, setStep] = React.useState(-1);
  const [run, setRun] = React.useState(null);
  const [history, setHistory] = React.useState([{
    kw: '발레코어 플랫',
    verdict: 'REAL'
  }, {
    kw: 'Y2K 미니백',
    verdict: 'FAD'
  }]);
  React.useEffect(() => {
    if (!run || step >= verifyStages.length) return;
    const t = setTimeout(() => setStep(s => s + 1), 650);
    return () => clearTimeout(t);
  }, [run, step]);
  React.useEffect(() => {
    if (run && step === verifyStages.length) setHistory(h => [{
      kw: run.kw,
      verdict: run.r.verdict
    }, ...h].slice(0, 6));
  }, [step]);
  const start = () => {
    if (!kw.trim()) return;
    setRun({
      kw: kw.trim(),
      r: fakeResult(kw.trim())
    });
    setStep(0);
  };
  const done = run && step >= verifyStages.length;
  const r = run && run.r;
  const tone = v => v === 'REAL' ? 'success' : v === 'FAD' ? 'error' : 'outline';
  return /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 1200,
      margin: '0 auto',
      padding: '48px 24px 80px',
      display: 'flex',
      flexDirection: 'column',
      gap: 32
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("h1", {
    style: {
      margin: 0,
      font: 'var(--type-display-lg)',
      letterSpacing: '-0.72px',
      color: 'var(--color-ink)'
    }
  }, "\uD0A4\uC6CC\uB4DC \uAC80\uC99D"), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: 0,
      color: 'var(--color-body)'
    }
  }, "\uBC1C\uACAC\uD55C \uD2B8\uB80C\uB4DC \uD0A4\uC6CC\uB4DC\uB97C \uC785\uB825\uD558\uBA74 \uC138 \uAC00\uC9C0 \uC2E0\uD638\uB85C \uD310\uC815\uD569\uB2C8\uB2E4.")), /*#__PURE__*/React.createElement("form", {
    onSubmit: e => {
      e.preventDefault();
      start();
    },
    style: {
      display: 'flex',
      gap: 12,
      alignItems: 'flex-end',
      flexWrap: 'wrap'
    }
  }, /*#__PURE__*/React.createElement(VTextInput, {
    label: "\uD2B8\uB80C\uB4DC \uD0A4\uC6CC\uB4DC",
    value: kw,
    onChange: e => setKw(e.target.value),
    placeholder: "\uC608: \uACE0\uD504\uCF54\uC5B4 \uBC14\uB78C\uB9C9\uC774",
    style: {
      flex: '1 1 320px'
    }
  }), /*#__PURE__*/React.createElement(VTextInput, {
    label: "\uAD00\uCC30 \uAE30\uAC04",
    defaultValue: "12\uC8FC",
    style: {
      width: 140
    }
  }), /*#__PURE__*/React.createElement(VButton, {
    type: "submit",
    variant: "download",
    disabled: run && !done
  }, "\uAC80\uC99D \uC2DC\uC791")), /*#__PURE__*/React.createElement(VMockup, {
    title: run ? 'TrendCheck — ' + run.kw : 'TrendCheck — 대기 중',
    height: 360,
    sidebar: /*#__PURE__*/React.createElement(VPane, {
      title: "\uCD5C\uADFC \uAC80\uC99D"
    }, history.map((h, i) => /*#__PURE__*/React.createElement("div", {
      key: i,
      style: {
        display: 'flex',
        justifyContent: 'space-between',
        gap: 8,
        padding: '5px 0'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap'
      }
    }, h.kw), /*#__PURE__*/React.createElement("span", {
      style: {
        color: h.verdict === 'REAL' ? 'var(--color-semantic-success)' : h.verdict === 'FAD' ? 'var(--color-semantic-error)' : 'var(--color-muted)'
      }
    }, h.verdict)))),
    main: /*#__PURE__*/React.createElement(VPane, {
      title: run ? 'report / ' + run.kw.replace(/\s+/g, '-') + '.md' : 'report'
    }, !run && /*#__PURE__*/React.createElement("div", {
      style: {
        color: 'var(--color-muted)'
      }
    }, "// \uD0A4\uC6CC\uB4DC\uB97C \uC785\uB825\uD558\uACE0 \uAC80\uC99D\uC744 \uC2DC\uC791\uD558\uC138\uC694."), run && !done && /*#__PURE__*/React.createElement("div", {
      style: {
        color: 'var(--color-muted)'
      }
    }, "// ", verifyStages[Math.min(step, 4)].detail, "\u2026"), done && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      style: {
        color: 'var(--color-ink)'
      }
    }, "# \uD310\uC815: ", r.verdict), /*#__PURE__*/React.createElement("div", null, "\xA0"), /*#__PURE__*/React.createElement("div", null, "\uAC80\uC0C9\uB7C9      +", r.s, "%   ", r.pass[0] ? '✓' : '✗', " \uAE30\uC900 50%"), /*#__PURE__*/React.createElement("div", null, "\uD310\uB9E4        +", r.p, "%    ", r.pass[1] ? '✓' : '✗', " \uAE30\uC900 20%"), /*#__PURE__*/React.createElement("div", null, "\uC18C\uC15C \uC5B8\uAE09   +", r.z.toFixed(1), "\u03C3   ", r.pass[2] ? '✓' : '✗', " \uAE30\uC900 2.0\u03C3"), /*#__PURE__*/React.createElement("div", null, "\xA0"), /*#__PURE__*/React.createElement("div", {
      style: {
        color: 'var(--color-muted)'
      }
    }, "// ", r.n, "/3 \uC2E0\uD638 \uD1B5\uACFC"))),
    terminal: /*#__PURE__*/React.createElement(VPane, {
      title: "terminal"
    }, run && /*#__PURE__*/React.createElement("div", {
      style: {
        color: 'var(--color-muted)'
      }
    }, "$ trendcheck verify \"", run.kw, "\" --window 12w"), done && /*#__PURE__*/React.createElement("div", {
      style: {
        color: r.verdict === 'REAL' ? 'var(--color-semantic-success)' : r.verdict === 'FAD' ? 'var(--color-semantic-error)' : 'var(--color-body)'
      }
    }, r.verdict === 'REAL' ? '✓' : r.verdict === 'FAD' ? '✗' : '•', " verdict: ", r.verdict, " \u2014 ", r.n, "/3 signals agree")),
    chat: /*#__PURE__*/React.createElement(VPane, {
      title: "Agent"
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        alignItems: 'flex-start'
      }
    }, verifyStages.map((s, i) => /*#__PURE__*/React.createElement(VPill, {
      key: s.stage,
      stage: s.stage,
      pending: !run || step < i
    }, s.label, run && step > i && i < 4 ? ' · 완료' : '', done && i === 4 ? ' · ' + r.verdict : '')), done && /*#__PURE__*/React.createElement("div", {
      style: {
        marginTop: 6,
        color: 'var(--color-ink)'
      }
    }, r.verdict === 'REAL' ? '세 신호가 모두 기준선을 넘었습니다.' : r.verdict === 'WATCH' ? '두 신호만 통과했습니다. 4주 뒤 다시 확인하세요.' : '일시적 유행일 가능성이 높습니다.')))
  }), done && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement(VBadge, {
    tone: tone(r.verdict)
  }, r.verdict), /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--type-caption)',
      color: 'var(--color-muted)'
    }
  }, "\uD310\uC815 \uACB0\uACFC\uB294 \uC608\uC2DC \uB370\uC774\uD130\uB85C \uC0DD\uC131\uB429\uB2C8\uB2E4.")));
}
window.VerifyScreen = VerifyScreen;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/web/VerifyScreen.jsx", error: String((e && e.message) || e) }); }

__ds_ns.Button = __ds_scope.Button;

__ds_ns.ComparisonCard = __ds_scope.ComparisonCard;

__ds_ns.FeatureCard = __ds_scope.FeatureCard;

__ds_ns.PricingTierCard = __ds_scope.PricingTierCard;

__ds_ns.TestimonialCard = __ds_scope.TestimonialCard;

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.CodeBlock = __ds_scope.CodeBlock;

__ds_ns.TimelinePill = __ds_scope.TimelinePill;

__ds_ns.TextInput = __ds_scope.TextInput;

__ds_ns.Footer = __ds_scope.Footer;

__ds_ns.FooterLink = __ds_scope.FooterLink;

__ds_ns.TopNav = __ds_scope.TopNav;

__ds_ns.IdeMockupCard = __ds_scope.IdeMockupCard;

__ds_ns.IdePane = __ds_scope.IdePane;

__ds_ns.CtaBand = __ds_scope.CtaBand;

__ds_ns.HeroBand = __ds_scope.HeroBand;

})();
