import { useEffect, useState } from "react";
import { fetchMoments, refreshMoments } from "../api";

// 微信配色体系下的 NPC 识别色
const ACCENTS = {
  npc_01: "#fa9d3b",
  npc_02: "#10aeff",
  npc_03: "#ffc300",
};

const NAME_COLORS = {
  陈静: "#fa9d3b",
  周明远: "#10aeff",
  方雨桐: "#ffc300",
  李星: "#07c160",
  赵雯: "#35c7a5",
  孙哥: "#fa5151",
  何姐: "#7d90a9",
  许总: "#c8c8c8",
};

export default function MomentsModal({ npc, onClose }) {
  const [feed, setFeed] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [mode, setMode] = useState("load"); // load | refresh

  const load = async (force = false) => {
    setLoading(true);
    setError(null);
    setMode(force ? "refresh" : "load");
    try {
      const data = force ? await refreshMoments(npc.id) : await fetchMoments(npc.id);
      setFeed(data);
    } catch (e) {
      setError(e.message || "加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [npc.id]);

  // Esc 关闭
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const accent = ACCENTS[npc.id] || "#07c160";

  return (
    <div className="moments-overlay" onClick={onClose}>
      <div
        className="moments-panel"
        style={{ "--m-accent": accent }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="moments-topbar">
          <button type="button" className="moments-back" onClick={onClose}>
            ‹ 返回
          </button>
          <span className="moments-title">{npc.display_name} 的朋友圈</span>
          <button
            type="button"
            className="moments-refresh"
            onClick={() => load(true)}
            disabled={loading}
          >
            {loading && mode === "refresh" ? "生成中…" : "刷新动态"}
          </button>
        </div>

        <div className="moments-cover">
          <span className="moments-cover-emoji" aria-hidden="true">
            {npc.emoji}
          </span>
        </div>
        <div className="moments-id">
          <span className="moments-avatar">{npc.emoji}</span>
          <div className="moments-id-text">
            <b>{npc.display_name}</b>
            <span>{npc.one_liner}</span>
          </div>
        </div>

        <div className="moments-feed">
          {loading && (
            <div className="moments-loading">
              <span className="dots">
                <i />
                <i />
                <i />
              </span>
              <p>{mode === "refresh" ? "正在重新生成朋友圈……" : "正在读取朋友圈……"}</p>
              <p className="moments-loading-sub">
                动态由 AI 依据人设现场生成，首次约需 10~30 秒；生成后会缓存，下次秒开
              </p>
            </div>
          )}

          {!loading && error && (
            <div className="moments-error">
              <span>{error}</span>
              <button type="button" className="moments-retry" onClick={() => load(false)}>
                重试
              </button>
            </div>
          )}

          {!loading &&
            !error &&
            feed &&
            (feed.posts || []).map((post, i) => (
              <article className="moment" key={i} style={{ animationDelay: `${i * 60}ms` }}>
                <p className="moment-content">{post.content}</p>
                <div className="moment-time">{post.time}</div>
                {((post.likes && post.likes.length > 0) ||
                  (post.comments && post.comments.length > 0)) && (
                  <div className="moment-social">
                    {post.likes && post.likes.length > 0 && (
                      <div className="moment-likes">
                        <span className="heart">♡</span>
                        <span>{post.likes.join("、")}</span>
                      </div>
                    )}
                    {(post.comments || []).map((c, j) => (
                      <div className="moment-comment" key={j}>
                        <b style={{ "--c": NAME_COLORS[c.from] || "var(--accent)" }}>{c.from}</b>
                        <span>：{c.text}</span>
                      </div>
                    ))}
                  </div>
                )}
              </article>
            ))}

          {!loading && !error && feed && (!feed.posts || feed.posts.length === 0) && (
            <div className="moments-loading">
              <p>这个人最近什么都没发——或者，你还没有权限看。</p>
            </div>
          )}
        </div>

        <div className="moments-foot">
          朋友圈内容由 AI 依据人设实时生成 · 仅供游戏体验
          {feed?.generated_at ? ` · 生成于 ${String(feed.generated_at).replace("T", " ").slice(0, 16)}` : ""}
        </div>
      </div>
    </div>
  );
}
