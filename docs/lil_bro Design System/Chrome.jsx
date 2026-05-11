/* global React */
const { useState, useEffect } = React;

// ── Title bar (window chrome) ───────────────────────────────────
window.TitleBar = function TitleBar({ title = 'lil_bro v1.0 — Optimization' }) {
  return (
    <div className="titlebar">
      <div className="tb-dots">
        <span className="tb-dot" style={{ background: '#FF6B6B' }}></span>
        <span className="tb-dot" style={{ background: '#FFB547' }}></span>
        <span className="tb-dot" style={{ background: '#4ADE80', color: "rgb(232, 230, 227)" }}></span>
      </div>
      <div className="tb-title">{title}</div>
      <div className="tb-controls">
        <button className="tb-btn" aria-label="minimize">−</button>
        <button className="tb-btn" aria-label="maximize">▢</button>
        <button className="tb-btn" style={{ color: 'var(--error)' }} aria-label="close">✕</button>
      </div>
    </div>);

};

// ── Sidebar ─────────────────────────────────────────────────────
window.Sidebar = function Sidebar({ view, onChange, running = false }) {
  const items = [
  { id: 'dashboard', icon: '◆', label: 'Dashboard' },
  {
    id: 'start',
    icon: running ? '▣' : '▶',
    label: running ? 'Working' : 'Start Optimization',
    accent: true,
    pulsing: running
  }];

  const utility = [
  { id: 'debug', icon: '📄', label: 'View Debug Log', muted: true },
  { id: 'revert', icon: '↩', label: 'Revert Changes', color: 'var(--warning)' },
  { id: 'exit', icon: '✕', label: 'Exit', color: 'var(--error)' }];

  return (
    <aside className="sidebar">
      <div className="sb-brand">lil<span>_</span>menu</div>
      {items.map((it) => {
        const isActive = it.id === 'start' ?
        running && view === 'output' :
        view === it.id;
        const cls = [
        'nav-item',
        isActive ? 'active' : '',
        it.accent ? 'nav-accent' : '',
        it.pulsing ? 'pulsing' : ''].
        filter(Boolean).join(' ');
        return (
          <button key={it.id} className={cls} onClick={() => onChange(it.id)}>
            <span className="nav-icon">{it.icon}</span>{it.label}
          </button>);

      })}
      <div className="nav-spacer"></div>
      <div className="nav-divider"></div>
      {utility.map((it) =>
      <button
        key={it.id}
        className="nav-item"
        style={{
          color: it.color || (it.muted ? 'var(--text-muted)' : undefined),
          fontSize: it.muted ? '0.75rem' : undefined
        }}
        onClick={() => onChange(it.id)}>
        
          <span className="nav-icon">{it.icon}</span>{it.label}
        </button>
      )}
    </aside>);

};

// ── Status bar (bottom) ─────────────────────────────────────────
window.StatusBar = function StatusBar({ state = 'idle', model = 'Qwen2.5-7B', session, extra }) {
  const dot = state === 'running' ? 'run' : 'ok';
  const label = state === 'running' ? 'Running — Phase 4/5' : 'Idle';
  return (
    <div className="statusbar">
      <div className="sb-item"><span className={'s-dot ' + dot}></span>{label}</div>
      <div className="sb-sep"></div>
      <div className="sb-item">Model: {model}</div>
      <div className="sb-sep"></div>
      {extra && <><div className="sb-item">{extra}</div><div className="sb-sep"></div></>}
      <div className="sb-item">Session: {session}</div>
    </div>);

};

// ── Stat card ───────────────────────────────────────────────────
window.StatCard = function StatCard({ label, value, unit, tone = 'norm', meta }) {
  return (
    <div className={'stat-card ' + tone}>
      <div className="sc-label">{label}</div>
      <div className="sc-val">{value}<span className="sc-unit-inline">{unit}</span></div>
      <div className="sc-unit">{meta}</div>
    </div>);

};

// ── Phase card ──────────────────────────────────────────────────
window.PhaseCard = function PhaseCard({ num, name, state, pct }) {
  const statusLabel = {
    done: '✓ COMPLETE',
    running: '● RUNNING',
    pending: '○ PENDING'
  }[state];
  return (
    <div className={'phase-card ' + state}>
      <div className="pc-num">Phase {String(num).padStart(2, '0')}</div>
      <div className="pc-name">{name}</div>
      <div className="pc-status">{statusLabel}</div>
      {state === 'running' &&
      <div className="pc-bar-bg"><div className="pc-bar-fill" style={{ width: (pct || 60) + '%' }}></div></div>
      }
    </div>);

};

// ── Button ──────────────────────────────────────────────────────
window.Btn = function Btn({ variant = 'p', children, onClick, style }) {
  return <button className={'btn btn-' + variant} onClick={onClick} style={style}>{children}</button>;
};

// ── Severity badge / chip ───────────────────────────────────────
window.SevBadge = function SevBadge({ level }) {
  const cls = { high: 'sev-h', medium: 'sev-m', low: 'sev-l' }[level];
  return <span className={'fix-sev ' + cls}>{level.toUpperCase()}</span>;
};

window.StatusPill = function StatusPill({ tone = 'ok', children }) {
  return (
    <div className="status-pill">
      <span className={'s-dot ' + tone}></span>
      {children}
    </div>);

};