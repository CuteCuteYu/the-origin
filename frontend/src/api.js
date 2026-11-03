// 与后端交互的极简封装（经 Vite 代理转发到 FastAPI）
async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = `请求失败（${res.status}）`;
    try {
      const data = await res.json();
      if (data.detail) detail = data.detail;
    } catch {
      /* 忽略解析失败 */
    }
    throw new Error(detail);
  }
  return res.json();
}

export const fetchBriefing = () => request("/api/game/briefing");

export const fetchGameState = () => request("/api/game/state");

export const saveNotes = (notes) =>
  request("/api/game/notes", { method: "PUT", body: JSON.stringify({ notes }) });

export const fetchNpcs = () => request("/api/npcs");

export const fetchHistory = (npcId) => request(`/api/npcs/${npcId}/history`);

export const fetchOaDocs = () => request("/api/oa/documents");

export const openOaDoc = (docId) =>
  request("/api/oa/open", { method: "POST", body: JSON.stringify({ doc_id: docId }) });

export const unlockOaDoc = (docId, passphrase) =>
  request("/api/oa/unlock", {
    method: "POST",
    body: JSON.stringify({ doc_id: docId, passphrase }),
  });

export const fetchMoments = (npcId) => request(`/api/npcs/${npcId}/moments`);

export const refreshMoments = (npcId) =>
  request(`/api/npcs/${npcId}/moments/refresh`, { method: "POST" });

export const resetGame = () => request("/api/game/reset", { method: "POST" });

/**
 * 流式对话：POST SSE，逐段回调 onDelta，结束时 resolve done 事件负载。
 * 后端事件类型：delta / done / error；HTTP 层错误（如 409 下班）直接 throw。
 */
export async function sendChatStream(npcId, message, onDelta) {
  const res = await fetch(`/api/npcs/${npcId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) {
    let detail = `请求失败（${res.status}）`;
    try {
      const data = await res.json();
      if (data.detail) detail = data.detail;
    } catch {
      /* 忽略解析失败 */
    }
    throw new Error(detail);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let donePayload = null;

  const handleFrame = (frame) => {
    const line = frame.split("\n").find((l) => l.startsWith("data:"));
    if (!line) return;
    let payload;
    try {
      payload = JSON.parse(line.slice(5).trim());
    } catch {
      return;
    }
    if (payload.type === "delta" && onDelta) {
      onDelta(payload.text);
    } else if (payload.type === "done") {
      donePayload = payload;
    } else if (payload.type === "error") {
      throw new Error(payload.message || "模型调用失败");
    }
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      handleFrame(frame);
    }
  }
  if (!donePayload) throw new Error("连接中断，未收到完整回复。");
  return donePayload;
}
