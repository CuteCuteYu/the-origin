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

function Message({ m, npc }) {
  if (m.role === "error") {
    return <div className="msg error">{m.content}</div>;
  }
  const isUser = m.role === "user";
  const time = m.ts
    ? new Date(m.ts).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
    : "";
  return (
    <div className={`msg ${isUser ? "user" : "npc"}`}>
      {!isUser && <span className="msg-avatar">{npc.emoji}</span>}
      <div className="bubble-wrap">
        <div className="bubble">{renderRich(m.content)}</div>
        <span className="msg-time">{isUser ? `你 · ${time}` : `${npc.display_name} · ${time}`}</span>
      </div>
    </div>
  );
}

export default function ChatWindow({ npc, messages, pending, onSend }) {
  const [draft, setDraft] = useState("");
  const bodyRef = useRef(null);

  // 新消息或等待回复时自动滚到底部
  useEffect(() => {
    const el = bodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, pending, npc.id]);

  const submit = () => {
    const t = draft.trim();
    if (!t || pending) return;
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
      </header>

      <div className="chat-body" ref={bodyRef}>
        {messages.length === 0 && !pending && (
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

        {pending && (
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
          placeholder={`以「睿析咨询顾问」的身份，对${npc.display_name}说……（Enter 发送 / Shift+Enter 换行）`}
          rows={2}
          disabled={pending}
        />
        <button className="btn-send" onClick={submit} disabled={pending || !draft.trim()}>
          提交提问
        </button>
      </div>
    </section>
  );
}
