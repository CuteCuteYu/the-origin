// 微信配色体系下的 NPC 识别色（无紫色）
const ACCENTS = {
  npc_01: "#fa9d3b",
  npc_02: "#10aeff",
  npc_03: "#ffc300",
};

export default function NPCList({ npcs, activeId, onSelect, onOpenMoments, histories }) {
  return (
    <section className="panel roster">
      <div className="panel-head">
        <h2>访谈名单</h2>
        <span className="count">{npcs.length} 人</span>
      </div>
      <ul>
        {npcs.map((npc, i) => {
          const asked = (histories[npc.id] || []).filter((m) => m.role === "user").length;
          const active = npc.id === activeId;
          return (
            <li key={npc.id} className="roster-item-wrap" style={{ animationDelay: `${i * 90}ms` }}>
              <button
                type="button"
                className={`roster-item ${active ? "active" : ""}`}
                style={{ "--accent": ACCENTS[npc.id] || "#07c160" }}
                onClick={() => onSelect(npc.id)}
              >
                <span className="avatar">{npc.emoji}</span>
                <span className="meta">
                  <span className="name-line">
                    <b>{npc.display_name}</b>
                    <i>{npc.title}</i>
                  </span>
                  <span className="oneliner">{npc.one_liner}</span>
                  <span className="slot">
                    {npc.interaction_slot}
                    {asked > 0 ? ` · 已记录 ${asked} 问` : ""}
                  </span>
                </span>
              </button>
              <button
                type="button"
                className="moments-chip"
                onClick={() => onOpenMoments(npc)}
              >
                朋友圈
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
