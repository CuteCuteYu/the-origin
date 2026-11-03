import { useEffect, useState } from "react";
import {
  fetchBriefing,
  fetchGameState,
  fetchNpcs,
  fetchHistory,
  fetchOaDocs,
  openOaDoc,
  unlockOaDoc,
  saveNotes,
  sendChatStream,
  resetGame,
} from "./api";
import BriefingPanel from "./components/BriefingPanel";
import NPCList from "./components/NPCList";
import ChatWindow from "./components/ChatWindow";
import OAWindow from "./components/OAWindow";
import NotebookPanel from "./components/NotebookPanel";
import MomentsModal from "./components/MomentsModal";

const INTEL_STORAGE_KEY = "viganex_intel_progress";

export default function App() {
  const [briefing, setBriefing] = useState(null);
  const [npcs, setNpcs] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [histories, setHistories] = useState({});
  const [pending, setPending] = useState(false);
  const [bootError, setBootError] = useState(null);
  // 视图切换：访谈室 / OA 模拟系统 / 笔记本
  const [view, setView] = useState("chat");
  const [oaDocs, setOaDocs] = useState(null);
  const [oaLoading, setOaLoading] = useState(false);
  const [oaError, setOaError] = useState(null);
  // 聚合游戏状态：虚拟时钟 / NPC 可用性与心理数值 / 口径 / 笔记 / OA 解锁
  const [gameState, setGameState] = useState(null);
  // 当前打开朋友圈的 NPC（null = 未打开）
  const [momentsNpc, setMomentsNpc] = useState(null);
  const [intel, setIntel] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(INTEL_STORAGE_KEY)) || {};
    } catch {
      return {};
    }
  });

  const refreshGameState = () => {
    fetchGameState()
      .then(setGameState)
      .catch(() => {
        /* 状态拉取失败不打断主流程，下一轮对话后会再刷新 */
      });
  };

  // 开局：拉取简报、NPC 名单、全部历史记录与聚合状态
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
        refreshGameState();
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

  // 打开一份 OA 文档：首次打开会让虚拟时钟走 2 分钟
  const handleOaOpen = async (docId) => {
    try {
      const res = await openOaDoc(docId);
      setGameState((prev) =>
        prev
          ? { ...prev, clock: res.clock, minutes: res.minutes, day_over: res.day_over }
          : prev
      );
    } catch {
      /* 打开失败不阻塞阅读（后端仍会在下次状态刷新时对齐） */
    }
  };

  // 口令解锁受限文档：解锁 = 首次阅读，后端已把时钟走了 2 分钟，
  // 这里用返回值同步顶栏时钟，并用净化文档替换列表项
  const handleOaUnlock = async (docId, passphrase) => {
    const res = await unlockOaDoc(docId, passphrase);
    setOaDocs((prev) => (prev || []).map((d) => (d.id === docId ? res.doc : d)));
    setGameState((prev) =>
      prev && res.clock
        ? { ...prev, clock: res.clock, minutes: res.minutes, day_over: res.day_over }
        : prev
    );
    refreshGameState();
    return res;
  };

  // 保存笔记本内容（口径备忘会自动汇总，这里只存玩家手记）
  const handleSaveNotes = async (notes) => {
    await saveNotes(notes);
  };

  // 流式发送一句话：乐观插入用户消息 → 追加打字中的助手气泡 →
  // 逐段渲染 delta → done 后用后端剥好 <state> 的干净全文替换并刷新状态
  const handleSend = async (text) => {
    if (!activeId || pending) return;
    const id = activeId;
    // 气泡时间用游戏内时钟（发送那一刻）；done 后回复时间用推进后的时钟
    const sendTs = gameState?.clock || new Date().toISOString();
    setHistories((prev) => ({
      ...prev,
      [id]: [
        ...(prev[id] || []),
        { role: "user", content: text, ts: sendTs },
        { role: "assistant", content: "", streaming: true, ts: sendTs },
      ],
    }));
    setPending(true);
    try {
      const done = await sendChatStream(id, text, (delta) => {
        setHistories((prev) => {
          const list = prev[id] || [];
          if (!list.length || list[list.length - 1].role !== "assistant") return prev;
          const last = list[list.length - 1];
          return {
            ...prev,
            [id]: [...list.slice(0, -1), { ...last, content: last.content + delta }],
          };
        });
      });
      setHistories((prev) => {
        const list = prev[id] || [];
        if (!list.length || list[list.length - 1].role !== "assistant") return prev;
        return {
          ...prev,
          [id]: [...list.slice(0, -1), { role: "assistant", content: done.reply, ts: done.clock || sendTs }],
        };
      });
      // 时钟 / 心理数值 / 可用性以聚合接口为准（含其他 NPC 的传话与口径变化）
      refreshGameState();
    } catch (e) {
      setHistories((prev) => {
        const list = prev[id] || [];
        const trimmed = list.filter((m) => !(m.streaming && !m.content));
        return {
          ...prev,
          [id]: [
            ...trimmed,
            { role: "error", content: `通讯中断：${e.message}`, ts: new Date().toISOString() },
          ],
        };
      });
      refreshGameState();
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
      // 重置全部记忆：对话存档、心理状态、时钟、OA 解锁由后端删除；
      // 前端本地已读状态一并清空，回到访谈室
      localStorage.removeItem("viganex_oa_read");
      setOaDocs(null);
      setGameState(null);
      setView("chat");
      setMomentsNpc(null);
      refreshGameState();
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
  const clock = gameState?.clock;
  const clockEnd = gameState?.end || "19:00";
  const dayOver = !!gameState?.day_over;

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
          <button
            type="button"
            className={view === "notebook" ? "active" : ""}
            onClick={() => setView("notebook")}
          >
            笔记本
          </button>
        </nav>
        <div className="topbar-right">
          {clock && (
            <span className={`clock-chip ${dayOver ? "over" : ""}`} title={`闭园时间 ${clockEnd}`}>
              ⏱ {clock} / {clockEnd}
            </span>
          )}
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
            gameState={gameState}
          />
        </aside>
        <main className="main">
          {view === "chat" ? (
            activeNpc && (
              <ChatWindow
                npc={activeNpc}
                messages={histories[activeId] || []}
                pending={pending}
                onSend={handleSend}
                status={gameState?.npcs?.[activeId]}
                dayOver={dayOver}
              />
            )
          ) : view === "oa" ? (
            <OAWindow
              docs={oaDocs}
              loading={oaLoading}
              error={oaError}
              onOpenDoc={handleOaOpen}
              onUnlock={handleOaUnlock}
              gameState={gameState}
            />
          ) : (
            <NotebookPanel
              npcs={npcs}
              gameState={gameState}
              onSave={handleSaveNotes}
            />
          )}
        </main>
      </div>

      {momentsNpc && (
        <MomentsModal npc={momentsNpc} onClose={() => setMomentsNpc(null)} />
      )}

      <footer className="footnote">
        微芒之下 · 社会工程学模拟沙盘 · 公司、人物与事件均为虚构 · 对话由大模型实时生成
      </footer>
    </div>
  );
}
