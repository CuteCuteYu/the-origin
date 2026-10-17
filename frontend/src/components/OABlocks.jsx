// OA 文档内容块渲染器：把后端 JSON 的 blocks 渲染成类似办公系统的排版

// 微信配色体系下的发言人颜色（无紫色）
const NAME_COLORS = {
  周明远: "#10aeff",
  方雨桐: "#ffc300",
  陈静: "#fa9d3b",
  李星: "#07c160",
  赵雯: "#35c7a5",
  孙志强: "#fa5151",
  何丽萍: "#7d90a9",
};

const FALLBACK_COLORS = ["#10aeff", "#ffc300", "#fa9d3b", "#07c160", "#35c7a5"];

function colorFor(name) {
  if (NAME_COLORS[name]) return NAME_COLORS[name];
  let h = 0;
  for (const ch of String(name)) h = (h * 31 + ch.codePointAt(0)) % 997;
  return FALLBACK_COLORS[h % FALLBACK_COLORS.length];
}

function MetaBlock({ items }) {
  return (
    <div className="bl-meta">
      {(items || []).map(([k, v], i) => (
        <div className="meta-item" key={i}>
          <span>{k}</span>
          <p>{v}</p>
        </div>
      ))}
    </div>
  );
}

function IMBlock({ messages }) {
  return (
    <div className="bl-im">
      {(messages || []).map((m, i) =>
        m.from === "系统" ? (
          <div key={i} className="im-system">
            —— {m.text} ——
          </div>
        ) : (
          <div key={i} className="im-row">
            <span
              className="im-avatar"
              style={{
                background: `${colorFor(m.from)}22`,
                color: colorFor(m.from),
                borderColor: `${colorFor(m.from)}55`,
              }}
            >
              {String(m.from).slice(0, 1)}
            </span>
            <div className="im-body">
              <div className="im-head">
                <b>{m.from}</b>
                <span>{m.time}</span>
              </div>
              <div className="im-text">{m.text}</div>
            </div>
          </div>
        )
      )}
    </div>
  );
}

export default function OABlocks({ blocks }) {
  return (
    <div className="oa-blocks">
      {(blocks || []).map((b, i) => {
        switch (b.type) {
          case "meta":
            return <MetaBlock key={i} items={b.items} />;
          case "heading":
            return (
              <h3 key={i} className="bl-h">
                {b.text}
              </h3>
            );
          case "paragraph":
            return (
              <p key={i} className="bl-p">
                {b.text}
              </p>
            );
          case "list":
            return b.ordered ? (
              <ol key={i} className="bl-list">
                {(b.items || []).map((it, j) => (
                  <li key={j}>{it}</li>
                ))}
              </ol>
            ) : (
              <ul key={i} className="bl-list">
                {(b.items || []).map((it, j) => (
                  <li key={j}>{it}</li>
                ))}
              </ul>
            );
          case "quote":
            return (
              <blockquote key={i} className="bl-quote">
                {b.text}
                {b.source && <cite>{b.source}</cite>}
              </blockquote>
            );
          case "table":
            return (
              <table key={i} className="bl-table">
                <thead>
                  <tr>
                    {(b.headers || []).map((h, j) => (
                      <th key={j}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(b.rows || []).map((row, ri) => (
                    <tr key={ri}>
                      {row.map((cell, ci) => (
                        <td key={ci}>{cell}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            );
          case "im":
            return <IMBlock key={i} messages={b.messages} />;
          case "callout":
            return (
              <div key={i} className={`bl-callout ${b.tone === "warn" ? "warn" : "info"}`}>
                <b className="bl-callout-icon">{b.tone === "warn" ? "!" : "i"}</b>
                {b.text}
              </div>
            );
          default:
            return null;
        }
      })}
    </div>
  );
}
