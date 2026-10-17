import { useEffect, useState } from "react";
import { fetchBriefing, fetchNpcs, fetchHistory, sendChat, resetGame, fetchOaDocs } from "./api";
import BriefingPanel from "./components/BriefingPanel";
import NPCList from "./components/NPCList";
import ChatWindow from "./components/ChatWindow";
import OAWindow from "./components/OAWindow";
import MomentsModal from "./components/MomentsModal";

const INTEL_STORAGE_KEY = "viganex_intel_progress";

export default function App() {
  const [briefing, setBriefing] = useState(null);
  const [npcs, setNpcs] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [histories, setHistories] = useState({});
  const [pending, setPending] = useState(false);
  const [bootError, setBootError] = useState(null);
  // 视图切换：访谈室 / OA 模拟系统
  const [view, setView] = useState("chat");
  const [oaDocs, setOaDocs] = useState(null);
  const [oaLoading, setOaLoading] = useState(false);
  const [oaError, setOaError] = useState(null);
  // 当前打开朋友圈的 NPC（null = 未打开）
  const [momentsNpc, setMomentsNpc] = useState(null);
  const [intel, setIntel] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(INTEL_STORAGE_KEY)) || {};
    } catch {
      return {};
    }
  });

  // 开局：拉取简报、NPC 名单与全部历史记录
  useEffect(() => {
    (async () => {
      try {
        const [b, n] = await Promise.all([fetchBriefing(), fetchNpcs()]);
        setBriefing(b);
        setNpcs(n.npcs);
        if (n.npcs.length) setActiveId(n.npcs[0].id);
        const entries = await Promise.all(
          n.npcs.map(async (npc) => [npc.id, (await fetchHistory(npc.id)).messages])
        );
        setHistories(Object.fromEntries(entries));
      } catch (e) {
        setBootError(e.message);
      }
    })();
  }, []);

  // 首次进入 OA 系统时懒加载文档数据
  const openOa = async () => {
    setView("oa");
    if (oaDocs !== null || oaLoading) return;
    setOaLoading(true);
    setOaError(null);
    try {
      const data = await fetchOaDocs();
      setOaDocs(data.documents || []);
    } catch (e) {
      setOaError(e.message);
      setOaDocs([]);
    } finally {
      setOaLoading(false);
    }
  };

  // 点击名单里的人物：切回访谈室并进行对话
  const openChatWith = (npcId) => {
    setActiveId(npcId);
    setView("chat");
  };

  const handleSend = async (text) => {
    if (!activeId || pending) return;
    const id = activeId;
    const optimistic = { role: "user", content: text, ts: new Date().toISOString() };
    setHistories((prev) => ({ ...prev, [id]: [...(prev[id] || []), optimistic] }));
    setPending(true);
    try {
      const res = await sendChat(id, text);
      setHistories((prev) => ({
        ...prev,
        [id]: [
          ...(prev[id] || []),
          { role: "assistant", content: res.reply, ts: new Date().toISOString() },
        ],
      }));
    } catch (e) {
      setHistories((prev) => ({
        ...prev,
        [id]: [
          ...(prev[id] || []),
          { role: "error", content: `通讯中断：${e.message}`, ts: new Date().toISOString() },
        ],
      }));
    } finally {
      setPending(false);
    }
  };

  const handleReset = async () => {
    if (!window.confirm("确定要销毁全部访谈记录，重新开始吗？")) return;
    try {
      await resetGame();
      setHistories(Object.fromEntries(npcs.map((n) => [n.id, []])));
      setIntel({});
      localStorage.removeItem(INTEL_STORAGE_KEY);
      // 重置全部记忆：对话存档与朋友圈缓存由后端删除；OA 已读状态一并清空，回到访谈室
      localStorage.removeItem("viganex_oa_read");
      setView("chat");
      setMomentsNpc(null);
    } catch (e) {
      window.alert(`重置失败：${e.message}`);
    }
  };

  const toggleIntel = (targetId) => {
    setIntel((prev) => {
      const next = { ...prev, [targetId]: !prev[targetId] };
      localStorage.setItem(INTEL_STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  };

  if (bootError) {
    return (
      <div className="boot-screen">
        <h1>微芒之下</h1>
        <p className="boot-error">无法连接后端：{bootError}</p>
        <p className="boot-hint">
          请先在终端启动 FastAPI 后端，再刷新本页面：
          <code>uv run --directory backend python -m uvicorn main:app --port 8000</code>
        </p>
      </div>
    );
  }

  if (!briefing || !npcs.length) {
    return (
      <div className="boot-screen">
        <h1>微芒之下</h1>
        <p className="boot-loading">正在调取档案……</p>
      </div>
    );
  }

  const activeNpc = npcs.find((n) => n.id === activeId);
  const dateTag = (briefing.meta?.current_date || "").replaceAll("-", "");

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">微芒之下</span>
          <span className="brand-sub">商业调查档案 · {briefing.meta?.scene}</span>
        </div>
        <nav className="view-tabs">
          <button
            type="button"
            className={view === "chat" ? "active" : ""}
            onClick={() => setView("chat")}
          >
            访谈室
          </button>
          <button
            type="button"
            className={view === "oa" ? "active" : ""}
            onClick={openOa}
          >
            OA 系统
          </button>
        </nav>
        <div className="topbar-right">
          <span className="case-no">档案编号 VX-{dateTag}</span>
          <button className="btn-ghost" onClick={handleReset}>
            销毁记录 · 重新开始
          </button>
        </div>
      </header>

      <div className="layout">
        <aside className="sidebar">
          <BriefingPanel briefing={briefing} intel={intel} onToggleIntel={toggleIntel} />
          <NPCList
            npcs={npcs}
            activeId={activeId}
            onSelect={openChatWith}
            onOpenMoments={setMomentsNpc}
            histories={histories}
          />
        </aside>
        <main className="main">
          {view === "chat"
            ? activeNpc && (
                <ChatWindow
                  npc={activeNpc}
                  messages={histories[activeId] || []}
                  pending={pending}
                  onSend={handleSend}
                />
              )
            : (
                <OAWindow docs={oaDocs} loading={oaLoading} error={oaError} />
              )}
        </main>
      </div>

      {momentsNpc && (
        <MomentsModal npc={momentsNpc} onClose={() => setMomentsNpc(null)} />
      )}

      <footer className="footnote">
        微芒之下 · 基础课第四课教学项目 · 公司、人物与事件均为虚构 · 对话由大模型实时生成
      </footer>
    </div>
  );
}
