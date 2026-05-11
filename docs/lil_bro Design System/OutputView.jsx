/* global React */
const { useState, useEffect, useRef } = React;

// Full pipeline log lines. Color-tagged using log mini-classes.
const LOG = [
{ c: 'm', text: '══ Phase 1: Bootstrap ══', bold: true },
{ c: 'g', tag: '[OK]  ', text: 'System Restore Point created' },
{ c: 'g', tag: '[OK]  ', text: 'LHM sidecar started on port 8085' },
{ c: 'm', text: '══ Phase 2: System Scan ══', bold: true },
{ c: 'c', tag: '[INFO]', text: 'Collecting hardware specs...' },
{ c: 'g', tag: '[OK]  ', text: 'nvidia-smi found — Driver 552.44' },
{ c: 'g', tag: '[OK]  ', text: 'Monitor: ASUS VG27AQ1A @ 165Hz' },
{ c: 'y', tag: '[WARN]', text: 'Power Plan: Balanced — not optimal' },
{ c: 'y', tag: '[WARN]', text: 'XMP not enabled — RAM at 2133 MHz' },
{ c: 'g', tag: '[OK]  ', text: 'Mouse polling at 1000Hz' },
{ c: 'm', text: '══ Phase 3: AI Analysis ══', bold: true },
{ c: 'c', tag: '[INFO]', text: 'LLM model loaded — Qwen2.5-7B-Instruct' },
{ c: 'c', tag: '[INFO]', text: 'Generating recommendations (6.2s)...' },
{ c: 'g', tag: '[OK]  ', text: '3 fixes: 1 HIGH, 1 MEDIUM, 1 LOW' },
{ c: 'm', text: '══ Phase 4: Apply Fixes ══', bold: true },
{ c: 'c', tag: '[INFO]', text: 'Applying: Ultimate Performance power plan...' },
{ c: 'g', tag: '[OK]  ', text: 'Power plan switched' },
{ c: 'c', tag: '[INFO]', text: 'Cleaning temp folders (12.4 GB)', live: true }];


window.OutputView = function OutputView() {
  return (
    <div className="main-area">
      <div className="main-header">
        <div className="main-title">Pipeline</div>
        <window.StatusPill tone="run">Phase 4 — Applying Fixes</window.StatusPill>
      </div>

      <div className="phase-row">
        <window.PhaseCard num={1} name="Bootstrap" state="done" />
        <window.PhaseCard num={2} name="System Scan" state="done" />
        <window.PhaseCard num={3} name="AI Analysis" state="done" />
        <window.PhaseCard num={4} name="Apply Fixes" state="running" pct={62} />
        <window.PhaseCard num={5} name="Verify" state="pending" />
      </div>

      <div className="log-panel">
        <div className="log-toolbar">
          <div className="log-tb-title">Pipeline Log</div>
          <div className="log-tb-btns">
            <button className="log-btn">Clear</button>
            <button className="log-btn">Copy</button>
          </div>
        </div>
        <div className="log-body">
          {LOG.map((l, i) =>
          <span className="ll" key={i}>
              {l.tag && <span className={'l' + l.c}>{l.tag}</span>}
              <span className={l.bold ? 'l' + l.c : 'lw'} style={l.bold ? { fontWeight: 700 } : null}>
                {l.tag ? ' ' + l.text : l.text}
              </span>
              {l.live && <span className="blink lc"> █</span>}
            </span>
          )}
        </div>
      </div>
    </div>);

};

// ── Approval dialog ─────────────────────────────────────────────
window.ApprovalDialog = function ApprovalDialog({ onApply, onSkip }) {
  const [sel, setSel] = useState({ a: true, b: false, c: true });
  const fixes = [
  { id: 'a', sev: 'high', tag: 'POWER PLAN', title: 'Switch to Ultimate Performance',
    desc: 'Your PC is in Balanced mode which throttles CPU clocks mid-game.', mode: 'AUTO' },
  { id: 'b', sev: 'medium', tag: 'XMP/EXPO', title: 'Enable XMP in BIOS',
    desc: 'RAM at base 2133 MHz. Requires BIOS access and restart.', mode: 'MANUAL' },
  { id: 'c', sev: 'low', tag: 'TEMP FOLDERS', title: 'Clean Shader Cache',
    desc: '12.4 GB across 3 temp locations. Safe to remove.', mode: 'AUTO' }];

  const count = Object.values(sel).filter(Boolean).length;
  return (
    <div className="dlg-backdrop">
      <div className="dlg" style={{ width: 540 }}>
        <div className="dlg-head">
          <div className="dlg-title">Apply These Fixes?</div>
          <button className="dlg-x" onClick={onSkip}>✕</button>
        </div>
        <div className="dlg-body">
          <div className="dlg-sub">lil_bro identified 3 improvements. Select which to apply:</div>
          <div className="fix-list">
            {fixes.map((f) => {
              const isSel = sel[f.id];
              const sevCls = f.sev === 'high' ? 'sev-h' : f.sev === 'medium' ? 'sev-m' : 'sev-l';
              return (
                <div key={f.id}
                className={'fix-item' + (isSel ? ' sel' : '')}
                style={!isSel ? { opacity: 0.7 } : null}
                onClick={() => setSel((s) => ({ ...s, [f.id]: !s[f.id] }))}>
                  <div className="fix-cb">{isSel ? '✓' : ''}</div>
                  <div style={{ flex: 1 }}>
                    <div className={'fix-sev ' + sevCls}>{f.sev.toUpperCase()} · {f.tag}</div>
                    <div className="fix-title">{f.title}</div>
                    <div className="fix-desc">{f.desc}</div>
                  </div>
                  <div className={'fix-badge ' + (f.mode === 'AUTO' ? 'badge-a' : 'badge-m')}>{f.mode}</div>
                </div>);

            })}
          </div>
        </div>
        <div className="dlg-foot">
          <window.Btn variant="g" onClick={onSkip}>Skip All</window.Btn>
          <window.Btn variant="p" onClick={() => onApply(count)}>
            Apply {count} Selected
          </window.Btn>
        </div>
      </div>
    </div>);

};

// ── Confirm dialog ──────────────────────────────────────────────
window.ConfirmDialog = function ConfirmDialog({ onYes, onNo }) {
  return (
    <div className="dlg-backdrop">
      <div className="dlg" style={{ width: 420 }}>
        <div className="dlg-head">
          <div className="dlg-title">Create Restore Point?</div>
          <button className="dlg-x" onClick={onNo}>✕</button>
        </div>
        <div className="dlg-body" style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
          <div style={{ fontSize: '1.6rem', color: 'var(--accent)', marginTop: 2, flexShrink: 0,
            textShadow: '0 0 20px var(--accent-glow)' }}>⚡</div>
          <div>
            <div style={{ fontSize: '0.9rem', fontWeight: 500, color: 'var(--text-primary)', marginBottom: 6 }}>
              lil_bro will create a Windows System Restore Point
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
              Takes ~30 seconds. Lets you roll back any changes if needed. Strongly recommended before applying fixes.
            </div>
          </div>
        </div>
        <div className="dlg-foot">
          <window.Btn variant="g" onClick={onNo}>Skip</window.Btn>
          <window.Btn variant="p" onClick={onYes}>Yes, Continue</window.Btn>
        </div>
      </div>
    </div>);

};

// ── Splash screen ───────────────────────────────────────────────
window.Splash = function Splash({ onContinue }) {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => setStep((s) => s + 1), 1000);
    return () => clearTimeout(t);
  }, [step]);
  useEffect(() => {
    if (step >= 3) {
      const t = setTimeout(onContinue, 600);
      return () => clearTimeout(t);
    }
  }, [step, onContinue]);
  return (
    <div className="splash-bg">
      <div className="splash-brand">lil<span>_</span>bro</div>
      <div className="splash-sub">Your Local AI PC<br />Optimization Agent</div>
      <div className="splash-badge">100% Offline · Privacy First</div>
      <div className="splash-steps">
        <SplashStep done={step >= 1} running={step === 0} label="LHM Monitor" />
        <SplashStep done={step >= 2} running={step === 1} label="Loading fonts" />
        <SplashStep done={step >= 3} running={step === 2} label="Checking system" />
      </div>
    </div>);

};

function SplashStep({ done, running, label }) {
  let cls = 'splash-step';
  if (done) cls += ' done';else
  if (running) cls += ' run';
  return (
    <div className={cls}>
      <span className={'si' + (running ? ' blink' : '')}>
        {done ? '✓' : running ? '●' : '○'}
      </span>
      <span>{label}</span>
      <span className="step-r">{done ? 'OK' : running ? '...' : ''}</span>
    </div>);

}