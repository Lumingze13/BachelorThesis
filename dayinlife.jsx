/*
 * dayinlife.jsx — optional POV "day in the life" stimulus shown at the Phase B→C
 * handoff. Generation was kicked off when the career was locked in (app.jsx); here
 * we poll until the clips are ready, then play morning → afternoon → evening as one
 * short edit. Always skippable, and any error/timeout falls straight through to the
 * conversation — it must never trap the participant. Only mounted when the feature
 * is enabled and a job exists.
 */
function DayInLife({ jobId, onDone }) {
  const { useState, useEffect, useRef } = React;
  const [status, setStatus] = useState('pending'); // pending | playing | done | error
  const [clips, setClips] = useState([]);
  const [idx, setIdx] = useState(0);
  const pollRef = useRef(null);
  const API = (typeof window !== 'undefined' && window.THESIS_API_BASE) || '';
  const LABELS = { morning: 'Morning', afternoon: 'Afternoon', evening: 'Evening' };

  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const r = await fetch(API + '/api/day-in-life/' + jobId);
        const d = await r.json();
        if (!alive) return;
        if (d.status === 'ready') {
          const ready = (d.segments || []).filter((s) => s.ready && s.url);
          clearInterval(pollRef.current);
          if (ready.length) { setClips(ready); setStatus('playing'); }
          else setStatus('error');
        } else if (d.status === 'error') {
          clearInterval(pollRef.current);
          setStatus('error');
        }
      } catch (e) { /* keep polling — the backend has its own timeout */ }
    };
    poll();
    pollRef.current = setInterval(poll, 4000);
    return () => { alive = false; clearInterval(pollRef.current); };
  }, [jobId]);

  const onEnded = () => { if (idx < clips.length - 1) setIdx(idx + 1); else setStatus('done'); };
  const cur = clips[idx];

  return (
    <div className="flow">
      <div className="flow-body dil-wrap">
        {status === 'pending' && (
          <div className="dil-stage">
            <div className="dil-eyebrow">A glimpse of that life</div>
            <h2 className="dil-title">Picturing an ordinary day, ten years on…</h2>
            <p className="dil-sub">Your future self is putting together a short look at a morning, an afternoon, and an evening. It takes a moment.</p>
            <div className="dil-spinner" aria-hidden="true" />
            <button className="link-btn dil-skip" onClick={onDone}>Skip and go straight in →</button>
          </div>
        )}

        {status === 'playing' && cur && (
          <div className="dil-stage">
            <div className="dil-eyebrow">{LABELS[cur.label] || cur.label} · {idx + 1} of {clips.length}</div>
            <div className="dil-frame">
              <video
                key={cur.label}
                className="dil-video"
                src={API + cur.url}
                autoPlay
                playsInline
                controls
                onEnded={onEnded}
                onError={onEnded}
              />
            </div>
            <p className="dil-sub">A day in the life — as your future self.</p>
            <div className="dil-actions">
              <button className="btn ghost sm" onClick={onDone}>Skip</button>
              {idx === clips.length - 1 && (
                <button className="btn accent" onClick={onDone}>Step into the conversation →</button>
              )}
            </div>
          </div>
        )}

        {(status === 'done' || status === 'error') && (
          <div className="dil-stage">
            <h2 className="dil-title">
              {status === 'done' ? 'That was a glimpse — now talk to them.' : "Let's go straight in."}
            </h2>
            <p className="dil-sub">
              {status === 'done'
                ? 'Hold that day in mind. Your future self is ready when you are.'
                : 'Your future self is ready to talk.'}
            </p>
            <button className="btn accent" onClick={onDone}>Step into the conversation →</button>
          </div>
        )}
      </div>
    </div>
  );
}
