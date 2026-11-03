import { useEffect, useRef, useState } from "react";

const TYPING_CAPTIONS = {
  npc_01: "陈静正在把奶茶挪到一边……",
  npc_02: "周明远低头敲了两下键盘，让你等一下……",
  npc_03: "方雨桐正在评估你的问题……",
};

const STARTERS = [
  "你好，我是睿析咨询的顾问，今天想跟你聊几句。",
  "最近工作忙吗？",
  "方便介绍一下你在公司负责什么工作吗？",
];

// 气泡时间显示：优先游戏内虚拟时钟（"16:05"），旧存档的真实时间戳兜底
function fmtTime(ts) {
  if (!ts) return "";
  if (/^\d{1,2}:\d{2}$/.test(ts)) return ts;
  const d = new Date(ts);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

// 把 NPC 文本中的（动作/神态描写）渲染为斜体样式，让"表演"更可见
function renderRich(text) {
  const parts = String(text).split(/(（[^）]*）)/g);
  return parts.map((p, i) =>
    p.startsWith("（") ? (
      <em key={i} className="action">
        {p}
      </em>
    ) : (
      <span key={i}>{p}</span>
    )
  );
}

// 流式期间 <state> 块还在路上，先按可见文本截断展示，done 后由后端给的干净全文替换
function displayText(text, streaming) {
  if (!streaming) return text;
  const idx = text.indexOf("<state");
  return idx >= 0 ? text.slice(0, idx) : text;
}

function Meter({ label, value, tone }) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div className={`meter ${tone}`} title={`${label} ${pct}/100`}>
      <span className="meter-label">{label}</span>
      <span className="meter-track">
        <i style={{ width: `${pct}%` }} />
      </span>
      <span className="meter-num">{pct}</span>
    </div>
  );
}

function Message({ m, npc }) {
  if (m.role === "error") {
    return <div className="msg error">{m.content}</div>;
  }
  const isUser = m.role === "user";
  const streaming = !!m.streaming;
  const time = fmtTime(m.ts);
  return (
    <div className={`msg ${isUser ? "user" : "npc"}`}>
      {!isUser && <span className="msg-avatar">{npc.emoji}</span>}
      <div className="bubble-wrap">
        <div className="bubble">
          {renderRich(displayText(m.content, streaming))}
          {streaming && <span className="stream-cursor" aria-hidden="true">▍</span>}
        </div>
        <span className="msg-time">
          {isUser ? `你 · ${time}` : `${npc.display_name} · ${time}`}
        </span>
      </div>
    </div>
  );
}

export default function ChatWindow({ npc, messages, pending, onSend, status, dayOver }) {
  const [draft, setDraft] = useState("");
  const bodyRef = useRef(null);

  const st = status || {};
  const blocked = dayOver || st.off_work === true;
  const lastMsg = messages[messages.length - 1];
  const showTyping = pending && !(lastMsg && lastMsg.streaming && lastMsg.content);

  // 新消息或等待回复时自动滚到底部
  useEffect(() => {
    const el = bodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, pending, npc.id]);

  const submit = () => {
    const t = draft.trim();
    if (!t || pending || blocked) return;
    setDraft("");
    onSend(t);
  };

  return (
    <section className="chat">
      <header className="chat-head">
        <span className="chat-avatar">{npc.emoji}</span>
        <div className="chat-title">
          <h2>
            {npc.display_name}
            <i>{npc.title}{npc.department ? ` · ${npc.department}` : ""}</i>
          </h2>
          <p className="scene">{npc.scene_hint}</p>
        </div>
        {st.trust !== undefined && (
          <div className="chat-meters">
            <Meter label="信任" value={st.trust} tone="trust" />
            <Meter label="警觉" value={st.suspicion} tone="suspicion" />
          </div>
        )}
      </header>

      {blocked && (
        <div className="chat-banner">
          {dayOver
            ? "19:00 已到，楼里的人陆续走了——今天的访谈全部结束。若想再来一局，请右上角「销毁记录 · 重新开始」。"
            : st.reason || `${npc.display_name}已经下班。`}
        </div>
      )}

      <div className="chat-body" ref={bodyRef}>
        {messages.length === 0 && !pending && !blocked && (
          <div className="empty">
            <p className="empty-scene">{npc.scene_hint}</p>
            <p className="empty-tip">挑一句开场白，或者直接写下你想说的话——</p>
            <div className="chips">
              {STARTERS.map((s) => (
                <button key={s} type="button" className="chip" onClick={() => onSend(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <Message key={`${npc.id}-${i}`} m={m} npc={npc} />
        ))}

        {showTyping && (
          <div className="msg npc typing">
            <span className="msg-avatar">{npc.emoji}</span>
            <div className="bubble-wrap">
              <div className="bubble typing-bubble">
                <span className="dots">
                  <i />
                  <i />
                  <i />
                </span>
                <span className="typing-caption">
                  {TYPING_CAPTIONS[npc.id] || "对方正在斟酌措辞……"}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="chat-input">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder={
            blocked
              ? dayOver
                ? "今天已经闭园，访谈全部结束——右上角「销毁记录 · 重新开始」可再来一局。"
                : `${npc.display_name}已经下班了。看看名单里还有谁在。`
              : `以「睿析咨询顾问」的身份，对${npc.display_name}说……（Enter 发送 / Shift+Enter 换行）`
          }
          rows={2}
          disabled={pending || blocked}
        />
        <button className="btn-send" onClick={submit} disabled={pending || blocked || !draft.trim()}>
          提交提问
        </button>
      </div>
    </section>
  );
}
