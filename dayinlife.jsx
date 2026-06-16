/*
 * dayinlife.jsx — optional POV "day in the life" stimulus at the Phase B→C handoff.
 * Generation was kicked off when the career was locked in (app.jsx). Here we poll
 * until the job resolves, then:
 *   - if video clips rendered → play morning → afternoon → evening as one edit;
 *   - otherwise (no key, disabled, or every clip filtered) → fall back to a
 *     rotating-text montage that describes the same working day/place.
 * Always skippable; any error falls straight through to the conversation.
 */
const DIL_ORDER = ['morning', 'afternoon', 'evening'];
const DIL_LABELS = { morning: 'Morning', afternoon: 'Afternoon', evening: 'Evening' };

function DayInLife({ jobId, onDone }) {
  const { useState, useEffect, useRef } = React;
  const [phase, setPhase] = useState('loading'); // loading | video | text | error
  const [clips, setClips] = useState([]);
  const [scenes, setScenes] = useState(null);
  const [vIdx, setVIdx] = useState(0); // current video clip
  const [tIdx, setTIdx] = useState(0); // current rotating-text scene
  const pollRef = useRef(null);
  const API = (typeof window !== 'undefined' && window.THESIS_API_BASE) || '';

  // Poll the job until it resolves into video clips or a text montage.
  useEffect(() => {
    let alive = true;
    const resolve = (d) => {
      const ready = (d.segments || []).filter((s) => s.ready && s.url);
      if (ready.length) { setClips(ready); setScenes(d.scenes || null); setPhase('video'); return; }
      if (d.scenes) { setScenes(d.scenes); setPhase('text'); return; }
      setPhase('error');
    };
    const poll = async () => {
      try {
        const r = await fetch(API + '/api/day-in-life/' + jobId);
        const d = await r.json();
        if (!alive) return;
        if (d.status === 'ready') { clearInterval(pollRef.current); resolve(d); }
        else if (d.status === 'error') { clearInterval(pollRef.current); setScenes(d.scenes || null); setPhase(d.scenes ? 'text' : 'error'); }
      } catch (e) { /* keep polling — the backend has its own timeout */ }
    };
    poll();
    pollRef.current = setInterval(poll, 4000);
    return () => { alive = false; clearInterval(pollRef.current); };
  }, [jobId]);

  // Rotating-text montage: auto-advance through the scenes that exist.
  const textScenes = scenes ? DIL_ORDER.filter((k) => scenes[k]).map((k) => ({ label: k, text: scenes[k] })) : [];
  useEffect(() => {
    if (phase !== 'text' || textScenes.length < 2) return undefined;
    const t = setTimeout(() => setTIdx((i) => (i + 1) % textScenes.length), 7000);
    return () => clearTimeout(t);
  }, [phase, tIdx, textScenes.length]);

  const onClipEnded = () => { if (vIdx < clips.length - 1) setVIdx(vIdx + 1); else setPhase('done'); };
  const cur = clips[vIdx];
  const tScene = textScenes[tIdx];

  return (
    <div className="flow">
      <div className="flow-body dil-wrap">
        {phase === 'loading' && (
          <div className="dil-stage">
            <div className="dil-eyebrow">A glimpse of that life</div>
            <h2 className="dil-title">Picturing an ordinary day, ten years on…</h2>
            <p className="dil-sub">Your future self is putting together a short look at a morning, an afternoon, and an evening. It takes a moment.</p>
            <div className="dil-spinner" aria-hidden="true" />
            <button className="link-btn dil-skip" onClick={onDone}>Skip and go straight in →</button>
          </div>
        )}

        {phase === 'video' && cur && (
          <div className="dil-stage">
            <div className="dil-eyebrow">{DIL_LABELS[cur.label] || cur.label} · {vIdx + 1} of {clips.length}</div>
            <div className="dil-frame">
              <video key={cur.label} className="dil-video" src={API + cur.url}
                autoPlay playsInline controls onEnded={onClipEnded} onError={onClipEnded} />
            </div>
            <p className="dil-sub">A day in the life — as your future self.</p>
            <div className="dil-actions">
              <button className="btn ghost sm" onClick={onDone}>Skip</button>
              {vIdx === clips.length - 1 && <button className="btn accent" onClick={onDone}>Step into the conversation →</button>}
            </div>
          </div>
        )}

        {phase === 'text' && tScene && (
          <div className="dil-stage">
            <div className="dil-eyebrow">A day in the life</div>
            <div className="dil-rot">
              <div className="dil-rot-label">{DIL_LABELS[tScene.label] || tScene.label}</div>
              <p key={tIdx} className="dil-rot-text fade-in">{tScene.text}</p>
            </div>
            <div className="dil-dots" aria-hidden="true">
              {textScenes.map((s, i) => (
                <button key={s.label} className={`dil-dot ${i === tIdx ? 'on' : ''}`} onClick={() => setTIdx(i)} aria-label={DIL_LABELS[s.label]} />
              ))}
            </div>
            <p className="dil-sub">Take a moment to picture it — then step in.</p>
            <div className="dil-actions">
              <button className="btn ghost sm" onClick={onDone}>Skip</button>
              <button className="btn accent" onClick={onDone}>Step into the conversation →</button>
            </div>
          </div>
        )}

        {(phase === 'done' || phase === 'error') && (
          <div className="dil-stage">
            <h2 className="dil-title">{phase === 'done' ? 'That was a glimpse — now talk to them.' : "Let's go straight in."}</h2>
            <p className="dil-sub">{phase === 'done' ? 'Hold that day in mind. Your future self is ready when you are.' : 'Your future self is ready to talk.'}</p>
            <button className="btn accent" onClick={onDone}>Step into the conversation →</button>
          </div>
        )}
      </div>
    </div>
  );
}
