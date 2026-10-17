import { useMemo, useState } from "react";
import OABlocks from "./OABlocks.jsx";

const CATEGORY_META = [
  { key: "announcements", label: "公告通知", icon: "📌" },
  { key: "meetings", label: "会议纪要", icon: "🗂️" },
  { key: "logs", label: "日志与周报", icon: "📓" },
  { key: "im", label: "通讯记录", icon: "💬" },
  { key: "projects", label: "项目档案", icon: "📦" },
];

const READ_KEY = "viganex_oa_read";

function loadRead() {
  try {
    return JSON.parse(localStorage.getItem(READ_KEY)) || {};
  } catch {
    return {};
  }
}

export default function OAWindow({ docs, loading, error }) {
  const [activeDocId, setActiveDocId] = useState(null);
  const [query, setQuery] = useState("");
  const [read, setRead] = useState(loadRead);

  const docList = docs || [];

  // 按分类分组 + 关键词过滤（标题 / 作者 / 标签）
  const grouped = useMemo(() => {
    const q = query.trim().toLowerCase();
    return CATEGORY_META.map((cat) => ({
      ...cat,
      docs: docList.filter(
        (d) =>
          d.category === cat.key &&
          (!q ||
            String(d.title).toLowerCase().includes(q) ||
            String(d.author).toLowerCase().includes(q) ||
            (d.tags || []).some((t) => String(t).toLowerCase().includes(q)))
      ),
    }));
  }, [docList, query]);

  const activeDoc = docList.find((d) => d.id === activeDocId) || null;
  const unreadCount = docList.filter((d) => !read[d.id]).length;

  const openDoc = (id) => {
    setActiveDocId(id);
    setRead((prev) => {
      if (prev[id]) return prev;
      const next = { ...prev, [id]: true };
      localStorage.setItem(READ_KEY, JSON.stringify(next));
      return next;
    });
  };

  if (loading) {
    return (
      <section className="oa">
        <div className="oa-status">正在接入内部系统……</div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="oa">
        <div className="oa-status error">OA 系统接入失败：{error}</div>
      </section>
    );
  }

  return (
    <section className="oa">
      <div className="oa-windowbar">
        <span className="oa-dots" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
        <span className="oa-title">微芒科技 · 智慧办公平台 VigaOA v2.4</span>
        <span className="oa-confidential">内部资料 · 请勿外传</span>
      </div>

      <div className="oa-grid">
        <aside className="oa-sidebar">
          <div className="oa-search">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索标题 / 作者 / 标签…"
            />
            <span className="oa-unread">未读 {unreadCount}</span>
          </div>
          <div className="oa-doclist">
            {grouped.map((cat) => (
              <div className="oa-cat" key={cat.key}>
                <div className="oa-cat-head">
                  {cat.icon} {cat.label}
                  <span>{cat.docs.length}</span>
                </div>
                <ul>
                  {cat.docs.map((d) => (
                    <li key={d.id}>
                      <button
                        type="button"
                        className={`oa-doc-item ${d.id === activeDocId ? "active" : ""}`}
                        onClick={() => openDoc(d.id)}
                      >
                        {!read[d.id] && <i className="dot" aria-hidden="true" />}
                        <span className="t">{d.title}</span>
                        <span className="d">
                          {d.date} · {d.author}
                        </span>
                      </button>
                    </li>
                  ))}
                  {cat.docs.length === 0 && <li className="oa-empty">无匹配文档</li>}
                </ul>
              </div>
            ))}
          </div>
        </aside>

        <div className="oa-content">
          {activeDoc ? (
            <article className="oa-doc" key={activeDoc.id}>
              <div className="oa-doc-head">
                <p className="oa-breadcrumb">
                  OA 首页 /{" "}
                  {CATEGORY_META.find((c) => c.key === activeDoc.category)?.label || "文档"} /{" "}
                  {activeDoc.title}
                </p>
                <h1>{activeDoc.title}</h1>
                <p className="oa-doc-meta">
                  <span>{activeDoc.date}</span>
                  <span>{activeDoc.author}</span>
                  {(activeDoc.tags || []).map((t) => (
                    <em key={t}>#{t}</em>
                  ))}
                </p>
              </div>
              <OABlocks blocks={activeDoc.blocks || []} />
              <div className="oa-watermark" aria-hidden="true">
                VIGANEX · 内部资料
              </div>
            </article>
          ) : (
            <div className="oa-welcome">
              <h2>企业内部办公系统</h2>
              <p>
                这里沉淀着公司的日常与历史：公告、会议纪要、工作周报、群聊归档、项目复盘……
                目前共 {docList.length} 份文档，{unreadCount} 份未读。
              </p>
              <p className="oa-tip">
                提示：这些材料里的细节，也许能在访谈中用得上——留意每份文字背后的人。
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
