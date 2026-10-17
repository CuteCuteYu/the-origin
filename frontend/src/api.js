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

export const fetchNpcs = () => request("/api/npcs");

export const fetchHistory = (npcId) => request(`/api/npcs/${npcId}/history`);

export const fetchOaDocs = () => request("/api/oa/documents");

export const fetchMoments = (npcId) => request(`/api/npcs/${npcId}/moments`);

export const refreshMoments = (npcId) =>
  request(`/api/npcs/${npcId}/moments/refresh`, { method: "POST" });

export const sendChat = (npcId, message) =>
  request(`/api/npcs/${npcId}/chat`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });

export const resetGame = () => request("/api/game/reset", { method: "POST" });
