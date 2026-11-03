import { useEffect, useState } from "react";

const GENERAL_KEY = "general";
const npcKey = (id) => `npc:${id}`;

// 口径时间显示：新存档是游戏内时钟（"16:05"），旧存档是真实时间戳
const fmtClaimTime = (ts) => {
  if (!ts) return "";
  return /^\d{1,2}:\d{2}$/.test(ts) ? ts : String(ts).slice(11, 16);
};

/**
 * 调查笔记本：左侧是「口径档案」（你在各人面前说过的、被记录下来的话，
 * 后端会把它注入其他 NPC 的提示词做比对），右侧是玩家自己的手记
 * （按人物分栏 + 一页通用备忘，PUT /api/game/notes 持久化到存档）。
 */
export default function NotebookPanel({ npcs, gameState, onSave }) {
  const claims = gameState?.claims || [];
  // 本地草稿只在首次拿到后端笔记时初始化，之后的刷新不会覆盖正在编辑的内容
  const [drafts, setDrafts] = useState(null);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (drafts === null && gameState) {
      setDrafts({ ...(gameState.notes || {}) });
    }
  }, [gameState, drafts]);

  const dirty =
    drafts !== null &&
    JSON.stringify(drafts) !== JSON.stringify(gameState?.notes || {});

  const setDraft = (key, value) => {
    setDrafts((prev) => ({ ...(prev || {}), [key]: value }));
  };

  const save = async () => {
    if (!drafts || saving) return;
    setSaving(true);
    setError(null);
    try {
      await onSave(drafts);
      setSavedAt(new Date());
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const generalDraft = drafts?.[GENERAL_KEY] || "";

  return (
    <section className="notebook">
      <header className="notebook-head">
        <div>
          <h2>调查笔记本</h2>
          <p className="notebook-sub">
            口径档案自动记录你说过的话——换人之前，先核对自己没说漏。手记会随存档保存。
          </p>
        </div>
        <div className="notebook-actions">
          {error && <span className="notebook-error">保存失败：{error}</span>}
          {savedAt && !dirty && !error && (
            <span className="notebook-saved">已保存 ✓</span>
          )}
          <button
            type="button"
            className="btn-send notebook-save"
            onClick={save}
            disabled={saving || !dirty}
          >
            {saving ? "保存中…" : dirty ? "保存手记" : "无改动"}
          </button>
        </div>
      </header>

      <div className="notebook-grid">
        <div className="notebook-claims">
          <h3>
            口径档案 <span className="count">{claims.length} 条</span>
          </h3>
          <p className="notebook-hint">
            这些是你对 NPC 说过、并被对方记下的话。员工之间会传话——
            如果你在两个人面前说法对不上，他们的警觉会一起升高。
          </p>
          {claims.length === 0 ? (
            <p className="notebook-empty">还没有记录。去访谈室聊几句吧。</p>
          ) : (
            <ul className="claims-list">
              {claims.map((c, i) => (
                <li key={i} className="claim-item">
                  <p className="claim-text">「{c.text}」</p>
                  <p className="claim-meta">
                    <b>{c.heard_by}</b> 记住的说法
                    {c.ts ? ` · ${fmtClaimTime(c.ts)}` : ""}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="notebook-notes">
          <h3>通用备忘</h3>
          <textarea
            value={generalDraft}
            onChange={(e) => setDraft(GENERAL_KEY, e.target.value)}
            placeholder="时间线、口令线索、下一步要验证的疑点……"
            rows={6}
          />
          {npcs.map((npc) => (
            <div className="notebook-npc" key={npc.id}>
              <h4>
                {npc.emoji} {npc.display_name}
                <i>{npc.title}</i>
              </h4>
              <textarea
                value={drafts?.[npcKey(npc.id)] || ""}
                onChange={(e) => setDraft(npcKey(npc.id), e.target.value)}
                placeholder={`对${npc.display_name}的观察：性格、在意什么、说漏过什么……`}
                rows={4}
              />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
