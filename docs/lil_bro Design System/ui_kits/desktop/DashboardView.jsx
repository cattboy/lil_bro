/* global React */
const { useState, useEffect, useMemo } = React;

// ── Dashboard ───────────────────────────────────────────────────
window.DashboardView = function DashboardView() {
  return (
    <div className="main-area">
      <div className="main-header">
        <div className="main-title">System Dashboard</div>
        <window.StatusPill tone="ok">LHM Active &nbsp;·&nbsp; 12:34:56</window.StatusPill>
      </div>

      <div className="stat-grid">
        <window.StatCard label="CPU Usage" value="45" unit="%"  tone="norm" meta="Ryzen 7 5800X" />
        <window.StatCard label="CPU Temp"  value="68" unit="°C" tone="warn" meta="All Cores" />
        <window.StatCard label="GPU Temp"  value="72" unit="°C" tone="ok"   meta="RTX 3080" />
        <window.StatCard label="RAM Used"  value="16.2" unit=" GB" tone="cyan" meta="of 32.0 GB" />
      </div>

      <div className="chart-wrap">
        <div className="chart-hdr">
          <div className="chart-title">Temperature History — Last 60s</div>
          <div className="chart-legend">
            <div className="leg-item"><div className="leg-line" style={{ background: 'var(--accent)' }}></div>CPU</div>
            <div className="leg-item"><div className="leg-line" style={{ background: 'var(--magenta)' }}></div>GPU</div>
          </div>
        </div>
        <svg width="100%" height="160" viewBox="0 0 900 160" preserveAspectRatio="none" style={{ display: 'block', position: 'relative', zIndex: 1 }}>
          <rect x="0" y="0"   width="900" height="40" fill="rgba(255,107,107,0.055)"/>
          <rect x="0" y="40"  width="900" height="40" fill="rgba(255,181,71,0.045)"/>
          <rect x="0" y="80"  width="900" height="80" fill="rgba(74,222,128,0.03)"/>
          <line x1="0" y1="40" x2="900" y2="40" stroke="rgba(255,107,107,0.22)" strokeWidth="1" strokeDasharray="4 4"/>
          <line x1="0" y1="80" x2="900" y2="80" stroke="rgba(255,181,71,0.22)" strokeWidth="1" strokeDasharray="4 4"/>
          <text x="896" y="14" textAnchor="end" fontFamily="JetBrains Mono,monospace" fontSize="10" fill="rgba(255,107,107,0.5)">85°C</text>
          <text x="896" y="74" textAnchor="end" fontFamily="JetBrains Mono,monospace" fontSize="10" fill="rgba(255,181,71,0.5)">70°C</text>
          <polyline points="0,92 60,88 120,78 180,68 240,58 300,64 360,70 420,76 480,82 540,72 600,78 660,84 720,76 780,68 840,78 900,86" stroke="rgba(0,229,204,0.22)" strokeWidth="6" fill="none" strokeLinejoin="round"/>
          <polyline points="0,92 60,88 120,78 180,68 240,58 300,64 360,70 420,76 480,82 540,72 600,78 660,84 720,76 780,68 840,78 900,86" stroke="#00E5CC" strokeWidth="2" fill="none" strokeLinejoin="round"/>
          <polyline points="0,106 60,100 120,92 180,84 240,74 300,80 360,86 420,92 480,98 540,90 600,96 660,100 720,92 780,86 840,96 900,104" stroke="rgba(209,131,232,0.22)" strokeWidth="6" fill="none" strokeLinejoin="round"/>
          <polyline points="0,106 60,100 120,92 180,84 240,74 300,80 360,86 420,92 480,98 540,90 600,96 660,100 720,92 780,86 840,96 900,104" stroke="#D183E8" strokeWidth="2" fill="none" strokeLinejoin="round"/>
          <circle cx="900" cy="86" r="4" fill="#00E5CC"/>
          <circle cx="900" cy="104" r="4" fill="#D183E8"/>
        </svg>
      </div>

      <div className="poll-widget">
        <div style={{ position: 'relative', zIndex: 1 }}>
          <div className="poll-label">USB Polling Rate</div>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: '6px', marginBottom: '4px' }}>
            <div className="poll-val">1000</div>
            <div className="poll-unit">Hz</div>
          </div>
          <div className="poll-status"><div className="s-dot ok"></div>Excellent</div>
        </div>
        <div style={{ position: 'relative', zIndex: 1, marginLeft: 'auto' }}>
          <button className="btn btn-s" style={{ fontSize: '0.78rem', padding: '7px 14px' }}>Test Polling</button>
        </div>
      </div>
    </div>
  );
};
