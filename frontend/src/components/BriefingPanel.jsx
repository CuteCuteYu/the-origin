export default function BriefingPanel({ briefing, intel, onToggleIntel }) {
  const { player, intel_targets = [] } = briefing;
  const doneCount = intel_targets.filter((t) => intel[t.target_id]).length;

  return (
    <section className="panel briefing">
      <div className="panel-head">
        <h2>任务简报</h2>
        <span className="stamp">机密</span>
      </div>

      <p className="brief-role">{player.role}</p>

      <details className="brief-block" open>
        <summary>背景掩护</summary>
        <p>{player.cover_story}</p>
      </details>

      <details className="brief-block" open>
        <summary>行动目标</summary>
        <p>{player.objective}</p>
      </details>

      <div className="brief-block">
        <div className="brief-subhead">
          情报拼图 <span className="count">{doneCount}/{intel_targets.length}</span>
        </div>
        <p className="hint">
          {player.objective_note || "系统不会判定输赢——什么时候算拿到手，由你自己确认。"}
        </p>
        <ul className="intel-list">
          {intel_targets.map((t) => {
            const checked = !!intel[t.target_id];
            return (
              <li key={t.target_id}>
                <button
                  type="button"
                  className={`intel-item ${checked ? "checked" : ""}`}
                  onClick={() => onToggleIntel(t.target_id)}
                >
                  <span className="box" aria-hidden="true">{checked ? "✓" : ""}</span>
                  <span className="label">{t.name}</span>
                </button>
              </li>
            );
          })}
        </ul>
        {doneCount === intel_targets.length && intel_targets.length > 0 && (
          <p className="intel-done">三份拼图已在手——该收网了。</p>
        )}
      </div>

      <details className="brief-block">
        <summary>随身资源</summary>
        <ul className="plain-list">
          {(player.resources || []).map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      </details>
    </section>
  );
}
