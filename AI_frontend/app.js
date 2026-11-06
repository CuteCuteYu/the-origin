/* ============================================================
   the-origin // AUTONOMOUS OPERATOR
   纯前端（无构建）控制台：只做三件事
   1. 把用户最初的要求交给后端自主代理；
   2. 渲染代理的思考 / 动作 / 观察 / 鉴定 / 时钟 / 进度事件；
   3. 在系统判定通关时展示最终报告。
   ============================================================ */

const API = location.protocol === "file:" ? "http://127.0.0.1:8000" : "";
const OBJ_KEY = "the_origin_ai_objective";

const $ = (id) => document.getElementById(id);

const els = {
  brandSub: $("brandSub"),
  statusPill: $("statusPill"),
  statusText: $("statusText"),
  modelBadge: $("modelBadge"),
  gameModelBadge: $("gameModelBadge"),
  protocolBadge: $("protocolBadge"),
  clockText: $("clockText"),
  clockRemaining: $("clockRemaining"),
  stepStat: $("stepStat"),
  objective: $("objective"),
  maxTurns: $("maxTurns"),
  resetFirst: $("resetFirst"),
  startBtn: $("startBtn"),
  stopBtn: $("stopBtn"),
  configBanner: $("configBanner"),
  configBannerText: $("configBannerText"),
  npcRoster: $("npcRoster"),
  historyList: $("historyList"),
  filters: $("filters"),
  feed: $("feed"),
  emptyState: $("emptyState"),
  thinkingDot: $("thinkingDot"),
  thinkingText: $("thinkingText"),
  feedMeta: $("feedMeta"),
  stageLabel: $("stageLabel"),
  stageRail: $("stageRail"),
  coverageText: $("coverageText"),
  partialText: $("partialText"),
  targetCards: $("targetCards"),
  memoryList: $("memoryList"),
  reportBox: $("reportBox"),
  reportText: $("reportText"),
  copyReport: $("copyReport"),
  openView: $("openView"),
  viewSheet: $("viewSheet"),
  kindToggles: $("kindToggles"),
  densitySelect: $("densitySelect"),
  reverseToggle: $("reverseToggle"),
  autoScrollToggle: $("autoScrollToggle"),
  collapseThoughtToggle: $("collapseThoughtToggle"),
  collapseDocToggle: $("collapseDocToggle"),
  presetEditor: $("presetEditor"),
  addPreset: $("addPreset"),
  resetView: $("resetView"),
  closeView: $("closeView"),
  scenarioStatus: $("scenarioStatus"),
  reloadScenario: $("reloadScenario"),
  showKeys: $("showKeys"),
  agentKey: $("agentKey"),
  agentBase: $("agentBase"),
  agentModel: $("agentModel"),
  gameKey: $("gameKey"),
  gameBase: $("gameBase"),
  gameModel: $("gameModel"),
  agentEnvHint: $("agentEnvHint"),
  gameEnvHint: $("gameEnvHint"),
  agentTest: $("agentTest"),
  gameTest: $("gameTest"),
  agentTestResult: $("agentTestResult"),
  gameTestResult: $("gameTestResult"),
};

const STATUS_TEXT = { unknown: "未获取", partial: "部分线索", confirmed: "已确认" };

/* ---------- 行动链显示偏好 ---------- */

const VIEW_KEY = "the_origin_ai_view_v1";
const LLM_STORE_KEY = "the_origin_ai_llm_v1";
const LLM_SESSION_KEY = "the_origin_ai_llm_keys_v1";

const EVENT_KINDS = [
  ["thought", "思考"],
  ["action", "动作"],
  ["obs", "观察"],
  ["chat", "对话"],
  ["doc", "文档"],
  ["intel", "情报鉴定"],
  ["stage", "阶段推进"],
  ["system", "系统"],
  ["notice", "通知"],
  ["error", "错误"],
  ["done", "结算"],
];
const KIND_LABEL = Object.fromEntries(EVENT_KINDS);

function defaultPresets() {
  return [
    { id: "all", name: "全部", kinds: ["*"], locked: true },
    { id: "thought", name: "思考", kinds: ["thought"] },
    { id: "intel", name: "情报", kinds: ["intel", "stage", "done"] },
    { id: "chat", name: "对话", kinds: ["chat"] },
    { id: "action", name: "动作", kinds: ["action", "obs"] },
    { id: "doc", name: "文档", kinds: ["doc"] },
  ];
}

function normalizePresets(presets) {
  const valid = new Set(EVENT_KINDS.map(([id]) => id));
  const list = [];
  if (Array.isArray(presets)) {
    for (const item of presets) {
      if (!item || typeof item !== "object") continue;
      const kinds = Array.isArray(item.kinds)
        ? item.kinds.filter((k) => k === "*" || valid.has(k))
        : [];
      list.push({
        id: String(item.id || `p_${Math.random().toString(36).slice(2, 8)}`),
        name: String(item.name || "未命名").slice(0, 12),
        kinds,
        locked: !!item.locked,
      });
    }
  }
  if (!list.some((p) => p.id === "all")) {
    list.unshift({ id: "all", name: "全部", kinds: ["*"], locked: true });
  }
  for (const preset of list) {
    if (preset.id === "all") {
      preset.name = "全部";
      preset.kinds = ["*"];
      preset.locked = true;
    }
  }
  return list;
}

function defaultView() {
  return {
    hiddenKinds: [],
    density: "cozy",
    reverse: false,
    autoScroll: true,
    collapseThought: false,
    collapseDoc: false,
    presets: defaultPresets(),
    activePreset: "all",
  };
}

function loadView() {
  const view = defaultView();
  try {
    const saved = JSON.parse(localStorage.getItem(VIEW_KEY) || "null");
    if (!saved || typeof saved !== "object") return view;
    view.hiddenKinds = Array.isArray(saved.hiddenKinds)
      ? saved.hiddenKinds.filter((id) => KIND_LABEL[id])
      : [];
    view.density = saved.density === "compact" ? "compact" : "cozy";
    view.reverse = !!saved.reverse;
    view.autoScroll = saved.autoScroll !== false;
    view.collapseThought = !!saved.collapseThought;
    view.collapseDoc = !!saved.collapseDoc;
    view.presets = normalizePresets(saved.presets);
    view.activePreset = view.presets.some((p) => p.id === saved.activePreset)
      ? saved.activePreset
      : view.presets[0]?.id || "all";
  } catch {
    /* localStorage 不可用时使用默认值 */
  }
  return view;
}

function saveView() {
  try {
    localStorage.setItem(VIEW_KEY, JSON.stringify(state.view));
  } catch {
    /* ignore */
  }
}

/* ---------- 双模型配置（密钥只进 sessionStorage） ---------- */

function defaultLlmState() {
  return {
    agent: { key: "", base: "", model: "" },
    game: { key: "", base: "", model: "" },
  };
}

function loadLlmState() {
  const out = defaultLlmState();
  try {
    const saved = JSON.parse(localStorage.getItem(LLM_STORE_KEY) || "null");
    if (saved && typeof saved === "object") {
      for (const kind of ["agent", "game"]) {
        const item = saved[kind] || {};
        out[kind].base = String(item.base || "");
        out[kind].model = String(item.model || "");
      }
    }
  } catch {
    /* ignore */
  }
  try {
    const keys = JSON.parse(sessionStorage.getItem(LLM_SESSION_KEY) || "null");
    if (keys && typeof keys === "object") {
      for (const kind of ["agent", "game"]) {
        out[kind].key = String(keys[kind] || "");
      }
    }
  } catch {
    /* ignore */
  }
  return out;
}

function saveLlmState() {
  try {
    localStorage.setItem(
      LLM_STORE_KEY,
      JSON.stringify({
        agent: { base: state.llm.agent.base, model: state.llm.agent.model },
        game: { base: state.llm.game.base, model: state.llm.game.model },
      })
    );
  } catch {
    /* ignore */
  }
  try {
    sessionStorage.setItem(
      LLM_SESSION_KEY,
      JSON.stringify({
        agent: state.llm.agent.key,
        game: state.llm.game.key,
      })
    );
  } catch {
    /* ignore */
  }
}

const state = {
  config: null,
  briefing: null,
  running: false,
  runId: null,
  abort: null,
  progress: null,
  notes: {},
  npcStates: {},
  targetNames: {},
  targetOrder: [],
  cards: [],
  view: loadView(),
  llm: loadLlmState(),
  envProfiles: null,
  eventCount: 0,
  clock: null,
  maxTurns: 40,
  sawDone: false,
};

/* ---------- 基础工具 ---------- */

function h(tag, opts = {}) {
  const node = document.createElement(tag);
  if (opts.class) node.className = opts.class;
  if (opts.text != null) node.textContent = String(opts.text);
  if (opts.attrs) {
    for (const [key, value] of Object.entries(opts.attrs)) {
      node.setAttribute(key, String(value));
    }
  }
  return node;
}

function clampPct(v) {
  const n = Number(v);
  return Math.max(0, Math.min(100, Number.isFinite(n) ? n : 0));
}

async function getJSON(path) {
  const res = await fetch(API + path, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

async function errorMessage(res) {
  try {
    const data = await res.json();
    if (data && data.detail) return data.detail;
  } catch {
    /* ignore */
  }
  return `请求失败（${res.status}）`;
}

/* ---------- 顶栏 / 状态 ---------- */

function setStatus(kind, text) {
  els.statusPill.className = `pill pill--${kind}`;
  els.statusText.textContent = text;
}

function setThinking(live, label) {
  els.thinkingDot.classList.toggle("is-live", !!live);
  els.thinkingText.textContent = label || (live ? "代理运行中" : "代理待命");
}

function updateClock(clock) {
  if (!clock) return;
  state.clock = clock;
  els.clockText.textContent = clock.clock || "--:--";
  const remain = clock.remaining_minutes != null ? clock.remaining_minutes : 0;
  els.clockRemaining.textContent = `${remain}m`;
  const over = !!clock.day_over;
  els.clockText.parentElement.classList.toggle("is-over", over);
  els.clockRemaining.parentElement.classList.toggle("is-over", over);
  if (clock.per_chat) els.clockRemaining.title = `每轮对话 ${clock.per_chat} 分钟`;
}

/* ---------- 名册 ---------- */

function meter(label, value, susp) {
  const row = h("div", { class: "meter" + (susp ? " meter--susp" : "") });
  row.appendChild(h("span", { class: "meter__label", text: label }));
  const bar = h("div", { class: "meter__bar" });
  const fill = h("i");
  fill.style.width = `${clampPct(value)}%`;
  bar.appendChild(fill);
  row.appendChild(bar);
  row.appendChild(h("span", { class: "meter__val", text: String(value ?? 0) }));
  return row;
}

function renderRoster(npcs, snapshot) {
  const list = npcs || state.briefing?.npcs || [];
  els.npcRoster.textContent = "";
  for (const npc of list) {
    const s = (snapshot || {})[npc.id] || {};
    const card = h("div", { class: "npc" });
    card.dataset.npcId = npc.id;
    card.dataset.available = String(s.available !== false);

    const top = h("div", { class: "npc__top" });
    top.appendChild(h("span", { class: "npc__emoji", text: npc.emoji || "🧑" }));
    const idBox = h("div", { class: "npc__id" });
    idBox.appendChild(
      h("b", { class: "npc__name", text: npc.display_name || npc.name || npc.id })
    );
    idBox.appendChild(h("span", { class: "npc__title", text: npc.title || "" }));
    top.appendChild(idBox);
    top.appendChild(
      h("span", { class: "npc__until", text: npc.available_until || s.until || "" })
    );
    card.appendChild(top);

    card.appendChild(meter("TRUST", s.trust ?? 0, false));
    card.appendChild(meter("SUSP", s.suspicion ?? 0, true));
    els.npcRoster.appendChild(card);
  }
}

function updateRoster(snapshot) {
  if (!snapshot) return;
  state.npcStates = snapshot;
  for (const [id, s] of Object.entries(snapshot)) {
    const card = els.npcRoster.querySelector(
      `[data-npc-id="${window.CSS && CSS.escape ? CSS.escape(id) : id}"]`
    );
    if (!card) continue;
    card.dataset.available = String(s.available !== false);
    const fills = card.querySelectorAll(".meter__bar i");
    if (fills[0]) fills[0].style.width = `${clampPct(s.trust)}%`;
    if (fills[1]) fills[1].style.width = `${clampPct(s.suspicion)}%`;
    const vals = card.querySelectorAll(".meter__val");
    if (vals[0]) vals[0].textContent = String(s.trust ?? 0);
    if (vals[1]) vals[1].textContent = String(s.suspicion ?? 0);
    const until = card.querySelector(".npc__until");
    if (until && s.until) until.textContent = s.until;
  }
}

/* ---------- 情报板 ---------- */

function renderProgress(progress, notes, npcSnapshot) {
  if (!progress) return;
  state.progress = progress;
  if (notes) state.notes = notes;
  if (npcSnapshot) updateRoster(npcSnapshot);

  const stage = Number(progress.stage || 0);
  els.stageLabel.textContent = progress.stage_label || "";
  const nodes = [...els.stageRail.children];
  nodes.forEach((node, i) => {
    node.classList.toggle("is-on", i < stage);
    node.classList.toggle("is-current", i === stage - 1 && !progress.success);
  });

  els.coverageText.textContent = `${progress.confirmed_count || 0}/${progress.total_count || 3} 已确认`;
  els.partialText.textContent = `${progress.partial_count || 0} 条线索`;

  els.targetCards.textContent = "";
  const targets = progress.targets || {};
  const order = [];
  for (const tid of state.targetOrder || []) {
    if (targets[tid]) order.push(tid);
  }
  for (const tid of Object.keys(targets)) {
    if (!order.includes(tid)) order.push(tid);
  }
  for (const tid of order) {
    const entry = targets[tid] || {};
    const status = entry.status || "unknown";
    const card = h("div", { class: "target" });
    card.dataset.status = status;

    const head = h("div", { class: "target__head" });
    head.appendChild(
      h("span", { class: "target__name", text: state.targetNames[tid] || tid })
    );
    head.appendChild(
      h("span", { class: "target__status", text: STATUS_TEXT[status] || status })
    );
    card.appendChild(head);

    for (const evidence of (entry.evidence || []).slice(-2)) {
      card.appendChild(h("p", { class: "target__evidence", text: evidence }));
    }
    if (status !== "confirmed" && entry.gap) {
      card.appendChild(h("p", { class: "target__gap", text: `缺口：${entry.gap}` }));
    }
    els.targetCards.appendChild(card);
  }

  renderMemory(state.notes);
}

function renderMemory(notes) {
  state.notes = notes || {};
  const entries = Object.entries(state.notes);
  els.memoryList.textContent = "";
  if (!entries.length) {
    els.memoryList.appendChild(h("p", { class: "muted", text: "暂无笔记。" }));
    return;
  }
  for (const [key, value] of entries.slice(-12).reverse()) {
    const item = h("div", { class: "memory-item" });
    item.appendChild(h("b", { text: key }));
    item.appendChild(h("span", { text: String(value) }));
    els.memoryList.appendChild(item);
  }
}

function showReport(text) {
  els.reportBox.hidden = !text;
  els.reportText.textContent = text || "";
  els.copyReport.textContent = "复制";
}

/* ---------- 视图设置 ---------- */

function syncViewControls() {
  els.densitySelect.value = state.view.density;
  els.reverseToggle.checked = state.view.reverse;
  els.autoScrollToggle.checked = state.view.autoScroll;
  els.collapseThoughtToggle.checked = state.view.collapseThought;
  els.collapseDocToggle.checked = state.view.collapseDoc;
}

function renderKindToggles() {
  els.kindToggles.textContent = "";
  for (const [id, label] of EVENT_KINDS) {
    const on = !state.view.hiddenKinds.includes(id);
    const row = h("label", { class: "kind-toggle" + (on ? " is-on" : "") });
    const input = h("input");
    input.type = "checkbox";
    input.checked = on;
    input.addEventListener("change", () => {
      const hidden = new Set(state.view.hiddenKinds);
      if (input.checked) hidden.delete(id);
      else hidden.add(id);
      state.view.hiddenKinds = [...hidden];
      row.classList.toggle("is-on", input.checked);
      saveView();
      for (const card of state.cards) applyFilterTo(card);
    });
    row.appendChild(input);
    row.appendChild(h("span", { text: label }));
    els.kindToggles.appendChild(row);
  }
}

function renderPresetEditor() {
  els.presetEditor.textContent = "";
  for (const preset of state.view.presets) {
    const row = h("div", { class: "preset-row" });

    const top = h("div", { class: "preset-row__top" });
    const name = h("input", { class: "preset-row__name" });
    name.type = "text";
    name.maxLength = 12;
    name.value = preset.name;
    name.disabled = !!preset.locked;
    name.addEventListener("input", () => {
      preset.name = name.value.trim() || "未命名";
      saveView();
      renderPresetChips();
    });
    top.appendChild(name);

    if (preset.locked) {
      top.appendChild(h("span", { class: "preset-row__tag", text: "内置" }));
    } else {
      const del = h("button", { class: "preset-row__del", text: "删除" });
      del.type = "button";
      del.addEventListener("click", () => {
        state.view.presets = state.view.presets.filter((p) => p.id !== preset.id);
        if (state.view.activePreset === preset.id) state.view.activePreset = "all";
        saveView();
        renderPresetEditor();
        renderPresetChips();
        for (const card of state.cards) applyFilterTo(card);
      });
      top.appendChild(del);
    }
    row.appendChild(top);

    const kinds = h("div", { class: "preset-kinds" });
    if (preset.locked) {
      kinds.appendChild(
        h("span", {
          class: "preset-row__tag",
          text: "包含全部未被关闭的事件类型",
        })
      );
    } else {
      for (const [id, label] of EVENT_KINDS) {
        const on = preset.kinds.includes(id);
        const chip = h("button", {
          class: "preset-kind" + (on ? " is-on" : ""),
          text: label,
        });
        chip.type = "button";
        chip.addEventListener("click", () => {
          const set = new Set(preset.kinds);
          if (set.has(id)) set.delete(id);
          else set.add(id);
          preset.kinds = [...set];
          saveView();
          renderPresetEditor();
          renderPresetChips();
          for (const card of state.cards) applyFilterTo(card);
        });
        kinds.appendChild(chip);
      }
    }
    row.appendChild(kinds);
    els.presetEditor.appendChild(row);
  }
}

function openViewSheet() {
  syncViewControls();
  syncLlmControls();
  renderKindToggles();
  renderPresetEditor();
  loadScenarioStatus();
  els.viewSheet.hidden = false;
  els.viewSheet.setAttribute("aria-hidden", "false");
  document.body.classList.add("sheet-open");
}

function closeViewSheet() {
  els.viewSheet.hidden = true;
  els.viewSheet.setAttribute("aria-hidden", "true");
  document.body.classList.remove("sheet-open");
}

/* ---------- 场景配置状态 ---------- */

async function loadScenarioStatus() {
  els.scenarioStatus.dataset.state = "loading";
  els.scenarioStatus.textContent = "正在读取配置状态…";
  try {
    const info = await getJSON("/api/scenario/status");
    const lines = [
      `文件：${info.path || "backend/data/scenario.json"}`,
      `状态：${
        info.errors?.length
          ? "校验失败"
          : info.up_to_date
            ? "已是最新"
            : "有待导入的修改"
      }`,
      `上次导入：${info.last_import || "尚未导入"}`,
      `规模：${info.npc_count || 0} 个 NPC · ${info.doc_count || 0} 份 OA 文档`,
    ];
    if (info.errors?.length) {
      lines.push("错误：");
      for (const err of info.errors) lines.push(`- ${err}`);
    }
    els.scenarioStatus.textContent = lines.join("\n");
    els.scenarioStatus.dataset.state = info.errors?.length
      ? "error"
      : info.up_to_date
        ? "ok"
        : "stale";
  } catch (err) {
    els.scenarioStatus.textContent = `无法读取配置状态：${err.message}`;
    els.scenarioStatus.dataset.state = "error";
  }
}

async function reloadScenario() {
  if (state.running) return;
  els.reloadScenario.disabled = true;
  els.scenarioStatus.dataset.state = "loading";
  els.scenarioStatus.textContent = "正在重新导入场景…";
  try {
    const res = await fetch(API + "/api/scenario/reload", {
      method: "POST",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) throw new Error(await errorMessage(res));
    const result = await res.json();

    const briefing = await getJSON("/api/ai/briefing");
    state.briefing = briefing;
    state.targetNames = Object.fromEntries(
      (briefing.intel_targets || []).map((t) => [t.target_id, t.name])
    );
    state.targetOrder = (briefing.intel_targets || [])
      .map((t) => String(t.target_id || ""))
      .filter(Boolean);
    const gameTitle = briefing.meta?.game_title || "the-origin";
    document.title = `${gameTitle} // AUTONOMOUS OPERATOR`;
    els.brandSub.textContent = `${gameTitle} · AUTONOMOUS OPERATOR`;
    renderRoster(briefing.npcs, briefing.npc_states);
    renderProgress(briefing.progress_seed, {}, briefing.npc_states);
    updateClock(briefing.clock);
    const saved = localStorage.getItem(OBJ_KEY);
    if (!saved) els.objective.value = briefing.default_objective || "";

    addCard("notice", (card) => {
      evTop(card, "SCENARIO RELOADED");
      card.appendChild(
        h("div", {
          class: "ev__body",
          text: `已重新导入场景：${result.npc_count} 个 NPC，${result.doc_count} 份 OA 文档。`,
        })
      );
    });
    await loadScenarioStatus();
    loadHistory();
  } catch (err) {
    els.scenarioStatus.textContent = `导入失败：${err.message}`;
    els.scenarioStatus.dataset.state = "error";
  } finally {
    els.reloadScenario.disabled = false;
  }
}

/* ---------- 事件流 ---------- */

function evTop(card, tag, time) {
  const top = h("div", { class: "ev__top" });
  top.appendChild(h("span", { class: "ev__tag", text: tag }));
  top.appendChild(
    h("span", { class: "ev__time", text: time || state.clock?.clock || "" })
  );
  card.appendChild(top);
  return top;
}

function addCard(kind, build) {
  if (state.emptyState && state.emptyState.parentNode) state.emptyState.remove();
  const card = h("article", { class: `ev ev--${kind}` });
  card.dataset.kind = kind;
  build(card);
  state.cards.push(card);
  if (state.view.reverse) {
    els.feed.insertBefore(card, els.feed.firstChild);
  } else {
    els.feed.appendChild(card);
  }
  state.eventCount += 1;
  els.feedMeta.textContent = `${state.eventCount} events`;
  applyFilterTo(card);
  if (state.view.autoScroll) {
    els.feed.scrollTop = state.view.reverse ? 0 : els.feed.scrollHeight;
  }
  return card;
}

function kindVisible(kind) {
  const view = state.view;
  if (view.hiddenKinds.includes(kind)) return false;
  const preset =
    view.presets.find((p) => p.id === view.activePreset) || view.presets[0];
  if (!preset) return true;
  return preset.kinds.includes("*") || preset.kinds.includes(kind);
}

function applyFilterTo(card) {
  card.hidden = !kindVisible(card.dataset.kind);
}

function renderOrder() {
  if (!state.cards.length) return;
  const ordered = state.view.reverse ? [...state.cards].reverse() : state.cards;
  for (const card of ordered) els.feed.appendChild(card);
  if (state.view.autoScroll) {
    els.feed.scrollTop = state.view.reverse ? 0 : els.feed.scrollHeight;
  }
}

function renderPresetChips() {
  els.filters.textContent = "";
  for (const preset of state.view.presets) {
    const chip = h("button", {
      class: "chip" + (preset.id === state.view.activePreset ? " is-active" : ""),
      text: preset.name,
    });
    chip.type = "button";
    chip.dataset.preset = preset.id;
    chip.addEventListener("click", () => {
      state.view.activePreset = preset.id;
      saveView();
      renderPresetChips();
      for (const card of state.cards) applyFilterTo(card);
    });
    els.filters.appendChild(chip);
  }
}

function applyViewChrome() {
  const view = state.view;
  document.body.classList.toggle("density-compact", view.density === "compact");
  document.body.classList.toggle("collapse-thought", view.collapseThought);
  document.body.classList.toggle("collapse-doc", view.collapseDoc);
  renderPresetChips();
  for (const card of state.cards) applyFilterTo(card);
}

function actionArgsSummary(tool, args) {
  if (!args || typeof args !== "object") return "";
  if (tool === "chat_with_npc") {
    const msg = String(args.message || "").trim();
    return `${args.npc_id || ""} ← 说：${msg}`;
  }
  if (tool === "read_oa_document") return `doc_id: ${args.doc_id || ""}`;
  if (tool === "unlock_oa_document") {
    return `doc_id: ${args.doc_id || ""}\npassphrase: ${args.passphrase || ""}`;
  }
  if (tool === "save_note") {
    return `key: ${args.key || ""}\ncontent: ${String(args.content || "").slice(0, 400)}`;
  }
  if (tool === "finish") {
    return `report: ${String(args.report || "").slice(0, 500)}`;
  }
  return JSON.stringify(args);
}

function handleEvent(ev) {
  if (!ev || !ev.type) return;

  switch (ev.type) {
    case "run": {
      state.runId = ev.run_id || null;
      state.sawDone = false;
      state.maxTurns = ev.max_turns || state.maxTurns;
      els.stepStat.textContent = `0/${state.maxTurns}`;
      if (ev.llm) updateModelBadges(ev.llm);
      else if (ev.model) els.modelBadge.textContent = `AGENT ${ev.model}`;
      if (ev.briefing?.intel_targets?.length) {
        state.targetNames = Object.fromEntries(
          ev.briefing.intel_targets.map((t) => [t.target_id, t.name])
        );
        state.targetOrder = ev.briefing.intel_targets
          .map((t) => String(t.target_id || ""))
          .filter(Boolean);
      }

      addCard("system", (card) => {
        evTop(card, "RUN STARTED", ev.started_at ? String(ev.started_at).slice(11, 19) : "");
        const body = h("div", { class: "ev__body" });
        body.appendChild(h("p", { class: "ev__quote", text: ev.objective || "" }));
        const llm = ev.llm || {};
        const llmText = [
          `run_id  ${ev.run_id || ""}`,
          `budget  ${ev.max_turns || 0} steps`,
          `agent   ${llm.agent?.model || ev.model || "-"} @ ${
            llm.agent?.base_url || "-"
          }`,
          `game    ${llm.game?.model || "-"} @ ${llm.game?.base_url || "-"}`,
        ].join("\n");
        body.appendChild(h("div", { class: "ev__args", text: llmText }));
        card.appendChild(body);
      });

      setStatus("running", "RUNNING");
      setThinking(true, "代理启动 · 正在建立信息优势");
      showReport("");
      if (ev.briefing?.clock) updateClock(ev.briefing.clock);
      if (ev.progress) renderProgress(ev.progress, ev.notes || {});
      break;
    }

    case "thought": {
      addCard("thought", (card) => {
        evTop(card, `THOUGHT · STEP ${ev.step || ""}`);
        const hint = h("span", {
          class: "ev__fold-hint",
          text: "思考已折叠 · 点击展开",
        });
        hint.addEventListener("click", () => card.classList.toggle("is-open"));
        card.appendChild(hint);
        card.appendChild(h("p", { class: "ev__quote", text: ev.text || "" }));
      });
      setThinking(true, "代理推演中");
      break;
    }

    case "action": {
      addCard("action", (card) => {
        evTop(card, `ACTION · STEP ${ev.step || ""}`);
        const body = h("div", { class: "ev__body" });
        const line = h("div");
        line.appendChild(h("span", { class: "ev__code", text: ev.tool || "" }));
        line.appendChild(document.createTextNode(`  ${ev.label || ""}`));
        body.appendChild(line);
        const summary = actionArgsSummary(ev.tool, ev.args || {});
        if (summary) body.appendChild(h("div", { class: "ev__args", text: summary }));
        card.appendChild(body);
      });
      els.stepStat.textContent = `${ev.step || 0}/${state.maxTurns}`;
      setThinking(true, `正在执行：${ev.label || ev.tool}`);
      break;
    }

    case "observation": {
      if (ev.ok && ["chat_with_npc", "read_oa_document", "unlock_oa_document"].includes(ev.tool)) {
        setThinking(true, "正在阅读反馈");
        break;
      }
      const kind = ev.ok ? "obs" : "error";
      addCard(kind, (card) => {
        evTop(card, ev.ok ? "OBSERVATION" : "OBSERVATION · FAILED");
        const body = h("div", { class: "ev__body" });
        body.appendChild(h("p", { text: ev.summary || "" }));
        if (ev.detail) {
          body.appendChild(
            h("div", { class: "ev__args", text: String(ev.detail).slice(0, 2400) })
          );
        }
        card.appendChild(body);
      });
      if (!ev.ok) setStatus("warn", "RETRYING");
      setThinking(true, ev.ok ? "正在分析反馈" : "动作失败 · 重新规划");
      break;
    }

    case "chat": {
      addCard("chat", (card) => {
        const top = evTop(card, "NPC DIALOGUE", ev.clock);
        const chips = h("span", { class: "npc-chips" });
        chips.appendChild(
          h("span", { class: "npc-chip npc-chip--trust", text: `TRUST ${ev.trust ?? "-"}` })
        );
        chips.appendChild(
          h("span", {
            class: "npc-chip npc-chip--susp",
            text: `SUSP ${ev.suspicion ?? "-"}`,
          })
        );
        top.appendChild(chips);

        const body = h("div", { class: "ev__body" });
        const userRow = h("div", { class: "bubble-row bubble-row--user" });
        userRow.appendChild(
          h("div", { class: "bubble bubble--user", text: ev.user_message || "" })
        );
        body.appendChild(userRow);

        const npcRow = h("div", { class: "bubble-row" });
        const npcBubble = h("div", { class: "bubble bubble--npc" });
        npcBubble.appendChild(
          h("div", {
            class: "bubble-label",
            text: `${ev.npc_name || ev.npc_id || "NPC"} · ${ev.clock || ""}`,
          })
        );
        npcBubble.appendChild(document.createTextNode(ev.reply || ""));
        npcRow.appendChild(npcBubble);
        body.appendChild(npcRow);
        card.appendChild(body);
      });
      setThinking(true, "等待情报鉴定");
      break;
    }

    case "doc": {
      addCard("doc", (card) => {
        evTop(card, "OA DOCUMENT", ev.clock);
        const head = h("div", { class: "doc__head" });
        head.appendChild(h("span", { class: "doc__title", text: ev.title || ev.doc_id }));
        head.appendChild(
          h("span", {
            class: "doc__meta",
            text: `${ev.date || ""}${ev.first_time ? " · 首次打开 −2min" : ""}`,
          })
        );
        card.appendChild(head);

        const wrap = h("div", {
          class: "doc" + ((ev.content || "").length > 700 ? " doc--long" : ""),
        });
        wrap.appendChild(h("pre", { class: "doc__text", text: ev.content || "" }));
        card.appendChild(wrap);

        if ((ev.content || "").length > 700) {
          const btn = h("button", { class: "doc__toggle", text: "展开全文" });
          btn.type = "button";
          btn.addEventListener("click", () => {
            wrap.classList.toggle("is-open");
            btn.textContent = wrap.classList.contains("is-open") ? "收起" : "展开全文";
          });
          card.appendChild(btn);
        }
      });
      setThinking(true, "正在阅读文档");
      break;
    }

    case "feedback": {
      addCard("intel", (card) => {
        if (!ev.valid_info) card.classList.add("is-empty");
        const top = evTop(card, ev.valid_info ? "INTEL · VALID" : "INTEL · NO SIGNAL");
        if (ev.risk) {
          top.appendChild(
            h("span", {
              class: `risk risk--${ev.risk}`,
              text: `RISK ${String(ev.risk).toUpperCase()}`,
            })
          );
        }

        const body = h("div", { class: "ev__body" });
        if (ev.note) body.appendChild(h("p", { class: "ev__quote", text: ev.note }));
        body.appendChild(
          h("div", {
            class: "ev__args",
            text: `${ev.stage_label || ""} · confirmed ${ev.confirmed_count ?? 0}/3 · engine ${
              ev.engine || "-"
            }`,
          })
        );

        const findings = ev.findings || [];
        if (findings.length) {
          const box = h("div", { class: "findings" });
          for (const finding of findings) {
            const row = h("div", { class: "finding" });
            const name = h("div", {
              class: "finding__name",
              text: finding.name || finding.target_id,
            });
            name.appendChild(
              h("span", {
                class: `level level--${finding.level}`,
                text: String(finding.level || "").toUpperCase(),
              })
            );
            row.appendChild(name);
            if (finding.evidence) {
              row.appendChild(
                h("p", { class: "finding__evidence", text: `“${finding.evidence}”` })
              );
            }
            if (finding.gap && finding.level !== "confirmed") {
              row.appendChild(h("div", { class: "finding__gap", text: `缺口：${finding.gap}` }));
            }
            box.appendChild(row);
          }
          body.appendChild(box);
        }
        card.appendChild(body);
      });
      setThinking(true, ev.valid_info ? "已获取有效情报" : "本轮无有效情报");
      break;
    }

    case "clock": {
      updateClock(ev.clock);
      updateRoster(ev.npcs);
      if (ev.notes) renderMemory(ev.notes);
      break;
    }

    case "progress": {
      const prevStage = state.progress ? Number(state.progress.stage || 0) : null;
      renderProgress(ev.progress, ev.notes, ev.npcs || null);
      if (ev.clock) updateClock(ev.clock);
      if (
        prevStage !== null &&
        ev.progress &&
        Number(ev.progress.stage || 0) !== prevStage
      ) {
        addCard("stage", (card) => {
          evTop(card, "STAGE ADVANCE");
          card.appendChild(
            h("p", { class: "ev__quote", text: ev.progress.stage_label || "" })
          );
        });
      }
      break;
    }

    case "notice": {
      addCard("notice", (card) => {
        evTop(card, "SYSTEM NOTICE");
        card.appendChild(h("div", { class: "ev__body", text: ev.text || "" }));
      });
      break;
    }

    case "error": {
      addCard("error", (card) => {
        evTop(card, "ERROR");
        card.appendChild(h("div", { class: "ev__body", text: ev.message || "未知错误" }));
      });
      setStatus("error", "ERROR");
      setThinking(false, "运行出错");
      break;
    }

    case "done": {
      state.sawDone = true;
      setThinking(false);
      updateClock(ev.clock);
      if (ev.progress) renderProgress(ev.progress, ev.notes || {});
      if (ev.report) showReport(ev.report);
      els.stepStat.textContent = `${ev.steps || 0}/${state.maxTurns}`;

      addCard("done", (card) => {
        if (ev.success) card.classList.add("is-success");
        evTop(
          card,
          `RUN ${ev.status === "error" ? "FAILED" : "FINISHED"} · ${ev.status_text || ev.status || ""}`
        );
        const body = h("div", { class: "ev__body" });
        body.appendChild(
          h("p", {
            class: "ev__quote",
            text: ev.success
            ? `全部 ${ev.progress?.total_count || 3} 块情报 confirmed，系统判定通关。`
              : `本次未达成全部目标：${ev.progress?.stage_label || "任务未完成"}。`,
          })
        );
        body.appendChild(
          h("div", {
            class: "ev__args",
            text: `steps ${ev.steps || 0} · chats ${ev.chat_rounds || 0} · confirmed ${
              ev.progress?.confirmed_count || 0
            }/${ev.progress?.total_count || 3} · clock ${ev.clock?.clock || "-"}`,
          })
        );
        card.appendChild(body);
      });

      if (ev.status === "error") {
        setStatus("error", "FAILED");
      } else if (ev.success) {
        setStatus("success", "MISSION COMPLETE");
      } else if (ev.status === "stopped") {
        setStatus("warn", "STOPPED");
      } else {
        setStatus("idle", String(ev.status || "FINISHED").toUpperCase());
      }
      break;
    }

    default:
      break;
  }
}

/* ---------- SSE ---------- */

async function consumeSSE(response, onEvent) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let index;
    while ((index = buffer.indexOf("\n\n")) >= 0) {
      const frame = buffer.slice(0, index);
      buffer = buffer.slice(index + 2);
      for (const rawLine of frame.split("\n")) {
        const line = rawLine.trim();
        if (!line.startsWith("data:")) continue;
        try {
          onEvent(JSON.parse(line.slice(5).trim()));
        } catch (err) {
          console.warn("bad SSE frame", line, err);
        }
      }
    }
  }
}

/* ---------- 启动 / 中止 ---------- */

function setRunning(running) {
  state.running = running;
  els.startBtn.disabled = running;
  els.stopBtn.disabled = !running;
  els.objective.disabled = running;
  els.maxTurns.disabled = running;
  els.resetFirst.disabled = running;
}

function clearFeed() {
  for (const card of [...els.feed.querySelectorAll(".ev")]) card.remove();
  state.cards = [];
  state.eventCount = 0;
  els.feedMeta.textContent = "0 events";
}

function resetPanel() {
  state.progress = null;
  state.notes = {};
  const seed = state.briefing?.progress_seed;
  if (seed) renderProgress(seed, {}, null);
  renderMemory({});
  showReport("");
  els.stepStat.textContent = `0/${state.maxTurns}`;
}

async function start() {
  if (state.running) return;

  const objective = els.objective.value.trim();
  if (!objective) {
    els.objective.focus();
    els.objective.classList.add("shake");
    setTimeout(() => els.objective.classList.remove("shake"), 500);
    return;
  }
  localStorage.setItem(OBJ_KEY, objective);

  const maxTurns = Math.max(1, Math.min(80, Number.parseInt(els.maxTurns.value, 10) || 40));
  els.maxTurns.value = String(maxTurns);
  state.maxTurns = maxTurns;

  clearFeed();
  resetPanel();
  setRunning(true);
  setStatus("running", "CONNECTING");
  setThinking(true, "正在连接自主代理");
  state.runId = null;
  state.abort = new AbortController();
  state.sawDone = false;

  try {
    const res = await fetch(API + "/api/ai/play", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({
        objective,
        max_turns: maxTurns,
        reset: els.resetFirst.checked,
        ...buildLlmOverrides(),
      }),
      signal: state.abort.signal,
    });

    if (!res.ok) throw new Error(await errorMessage(res));

    await consumeSSE(res, handleEvent);

    if (!state.sawDone) {
      addCard("notice", (card) => {
        evTop(card, "STREAM CLOSED");
        card.appendChild(
          h("div", { class: "ev__body", text: "事件流已结束，但未收到终态事件。" })
        );
      });
      setStatus("warn", "INCOMPLETE");
    }
  } catch (err) {
    if (err.name === "AbortError") {
      addCard("notice", (card) => {
        evTop(card, "ABORTED");
        card.appendChild(h("div", { class: "ev__body", text: "连接已断开。" }));
      });
    } else {
      addCard("error", (card) => {
        evTop(card, "FATAL");
        card.appendChild(h("div", { class: "ev__body", text: err.message || String(err) }));
      });
      setStatus("error", "ERROR");
    }
  } finally {
    setRunning(false);
    setThinking(false);
    loadHistory();
  }
}

async function stop() {
  if (!state.running) return;
  setStatus("warn", "STOPPING");
  setThinking(true, "正在收束当前动作");
  if (!state.runId) {
    state.abort?.abort();
    return;
  }
  const runId = state.runId;
  try {
    await fetch(API + "/api/ai/stop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: runId }),
    });
  } catch (err) {
    console.warn(err);
  }
  // 兜底：30 秒内后端仍未收束，则强制断开连接
  setTimeout(() => {
    if (state.running && state.runId === runId) state.abort?.abort();
  }, 30000);
}

/* ---------- 历史对局 ---------- */

async function loadHistory() {
  try {
    const data = await getJSON("/api/ai/runs?limit=8");
    const runs = data.runs || [];
    els.historyList.textContent = "";
    if (!runs.length) {
      els.historyList.appendChild(h("p", { class: "muted", text: "暂无记录。" }));
      return;
    }
    for (const run of runs) {
      const btn = h("button", { class: "history-item" });
      btn.type = "button";
      btn.dataset.success = String(!!run.success);
      btn.dataset.status = run.status || "";
      btn.appendChild(h("span", { class: "history-item__dot" }));
      btn.appendChild(
        h("span", {
          class: "history-item__obj",
          text: run.objective || run.id,
        })
      );
      btn.appendChild(
        h("span", {
          class: "history-item__meta",
          text: `${run.confirmed_count || 0}/${run.total_count || 3} · ${run.steps || 0}步`,
        })
      );
      btn.title = `${run.id} · ${run.status || ""} · ${run.created_at || ""}`;
      btn.addEventListener("click", () => openRun(run.id));
      els.historyList.appendChild(btn);
    }
  } catch {
    /* 历史加载失败不影响主流程 */
  }
}

async function openRun(runId) {
  if (state.running) return;
  try {
    const run = await getJSON(`/api/ai/runs/${encodeURIComponent(runId)}`);
    clearFeed();
    state.progress = null;
    state.notes = {};
    state.runId = run.id;
    state.maxTurns = run.max_turns || 40;
    state.sawDone = false;
    const seed = state.briefing?.progress_seed;
    if (seed) renderProgress(seed, {}, null);
    renderMemory({});
    showReport("");

    for (const ev of run.events || []) handleEvent(ev);

    if (!state.sawDone) {
      if (run.report) showReport(run.report);
      setStatus(run.status === "error" ? "error" : "idle", `ARCHIVED · ${String(run.status || "").toUpperCase()}`);
      setThinking(false);
    }
    setRunning(false);
  } catch (err) {
    addCard("error", (card) => {
      evTop(card, "ARCHIVE ERROR");
      card.appendChild(h("div", { class: "ev__body", text: err.message || String(err) }));
    });
  }
}

/* ---------- 配置 ---------- */

function updateModelBadges(profiles) {
  const agent = profiles?.agent || {};
  const game = profiles?.game || {};
  els.modelBadge.textContent = `AGENT ${agent.model || "—"}`;
  els.gameModelBadge.textContent = `GAME ${game.model || "—"}`;
  els.protocolBadge.textContent = `PROTOCOL ${String(
    agent.protocol || "auto"
  ).toUpperCase()}`;
}

function previewModelBadges(profiles) {
  const env = profiles || {};
  const agentModel = state.llm.agent.model.trim() || env.agent?.model || "—";
  const gameModel = state.llm.game.model.trim() || env.game?.model || "—";
  const agentBase = state.llm.agent.base.trim().replace(/\/+$/, "");
  const envBase = String(env.agent?.base_url || "").trim().replace(/\/+$/, "");
  const customBase = agentBase && agentBase !== envBase;
  const protocol = customBase
    ? "auto"
    : state.config?.protocol_in_use || env.agent?.protocol || "auto";
  els.modelBadge.textContent = `AGENT ${agentModel}`;
  els.gameModelBadge.textContent = `GAME ${gameModel}`;
  els.protocolBadge.textContent = `PROTOCOL ${String(protocol).toUpperCase()}`;
}

function applyLlmEnv(profiles) {
  state.envProfiles = profiles || {};
  const agent = profiles?.agent || {};
  const game = profiles?.game || {};
  els.agentKey.placeholder = agent.key_present
    ? "已检测到系统密钥（留空使用）"
    : "未检测到，请填写";
  els.agentBase.placeholder = agent.base_url || "https://...";
  els.agentModel.placeholder = agent.model || "glm-5.3";
  els.gameKey.placeholder = game.key_present
    ? "已检测到系统密钥（留空使用）"
    : "未检测到，请填写";
  els.gameBase.placeholder = game.base_url || "https://...";
  els.gameModel.placeholder = game.model || "glm-5.3";
  els.agentEnvHint.textContent = `环境默认：${agent.model || "—"} @ ${
    agent.base_url || "—"
  }`;
  els.gameEnvHint.textContent = `环境默认：${game.model || "—"} @ ${
    game.base_url || "—"
  }`;
}

function syncLlmControls() {
  els.agentKey.value = state.llm.agent.key;
  els.agentBase.value = state.llm.agent.base;
  els.agentModel.value = state.llm.agent.model;
  els.gameKey.value = state.llm.game.key;
  els.gameBase.value = state.llm.game.base;
  els.gameModel.value = state.llm.game.model;
  els.showKeys.checked = false;
  els.agentKey.type = "password";
  els.gameKey.type = "password";
}

function buildLlmOverrides() {
  const out = {};
  for (const kind of ["agent", "game"]) {
    const item = state.llm[kind] || {};
    const data = {};
    if (String(item.key || "").trim()) data.api_key = String(item.key).trim();
    if (String(item.base || "").trim()) data.base_url = String(item.base).trim();
    if (String(item.model || "").trim()) data.model = String(item.model).trim();
    if (Object.keys(data).length) out[`${kind}_llm`] = data;
  }
  return out;
}

function hasKeyFor(profile, kind) {
  return !!state.llm[kind]?.key?.trim() || !!profile?.key_present;
}

function applyConfig(config) {
  state.config = config || {};
  const profiles = state.config.profiles || {};
  applyLlmEnv(profiles);
  syncLlmControls();
  previewModelBadges(profiles);
  refreshConfigBanner();
}

function refreshConfigBanner() {
  const profiles = state.config?.profiles || {};
  const missing = [];
  if (!hasKeyFor(profiles.agent, "agent")) missing.push("AI 玩家（进攻）");
  if (!hasKeyFor(profiles.game, "game")) missing.push("游戏 / NPC");
  if (missing.length) {
    els.configBanner.hidden = false;
    els.configBannerText.textContent =
      `以下模型未配置 API Key：${missing.join("、")}。` +
      "可在右上角 ⚙ → 模型配置 中填写，或设置系统环境变量 ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN 后重启后端。";
  } else {
    els.configBanner.hidden = true;
  }
}

/* ---------- 启动 ---------- */

async function boot() {
  applyViewChrome();
  syncViewControls();
  try {
    const [status, briefing] = await Promise.all([
      getJSON("/api/ai/status"),
      getJSON("/api/ai/briefing"),
    ]);

    state.briefing = briefing;
    state.targetNames = Object.fromEntries(
      (briefing.intel_targets || []).map((t) => [t.target_id, t.name])
    );
    state.targetOrder = (briefing.intel_targets || [])
      .map((t) => String(t.target_id || ""))
      .filter(Boolean);

    const gameTitle = briefing.meta?.game_title || "the-origin";
    document.title = `${gameTitle} // AUTONOMOUS OPERATOR`;
    els.brandSub.textContent = `${gameTitle} · AUTONOMOUS OPERATOR`;

    applyConfig(status.config);
    updateClock(status.clock || briefing.clock);
    renderRoster(briefing.npcs, briefing.npc_states);
    renderProgress(briefing.progress_seed, {}, null);
    renderMemory({});

    const saved = localStorage.getItem(OBJ_KEY);
    els.objective.value = saved || briefing.default_objective || "";
    state.maxTurns = Number.parseInt(els.maxTurns.value, 10) || 40;

    loadHistory();
  } catch (err) {
    els.configBanner.hidden = false;
    els.configBannerText.textContent = `无法连接后端：${err.message}。请先启动 FastAPI（端口 8000），再刷新本页。`;
    setStatus("error", "OFFLINE");
    els.modelBadge.textContent = "MODEL —";
  }
}

/* ---------- 绑定 ---------- */

els.startBtn.addEventListener("click", start);
els.stopBtn.addEventListener("click", stop);

els.openView.addEventListener("click", openViewSheet);
els.closeView.addEventListener("click", closeViewSheet);
for (const closer of document.querySelectorAll("[data-close-sheet]")) {
  closer.addEventListener("click", closeViewSheet);
}
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !els.viewSheet.hidden) closeViewSheet();
});

els.densitySelect.addEventListener("change", () => {
  state.view.density = els.densitySelect.value === "compact" ? "compact" : "cozy";
  saveView();
  applyViewChrome();
});

els.reverseToggle.addEventListener("change", () => {
  state.view.reverse = els.reverseToggle.checked;
  saveView();
  renderOrder();
});

els.autoScrollToggle.addEventListener("change", () => {
  state.view.autoScroll = els.autoScrollToggle.checked;
  saveView();
  if (state.view.autoScroll) {
    els.feed.scrollTop = state.view.reverse ? 0 : els.feed.scrollHeight;
  }
});

els.collapseThoughtToggle.addEventListener("change", () => {
  state.view.collapseThought = els.collapseThoughtToggle.checked;
  saveView();
  applyViewChrome();
});

els.collapseDocToggle.addEventListener("change", () => {
  state.view.collapseDoc = els.collapseDocToggle.checked;
  saveView();
  applyViewChrome();
});

els.addPreset.addEventListener("click", () => {
  const id = `p_${Math.random().toString(36).slice(2, 8)}`;
  state.view.presets.push({
    id,
    name: `预设 ${state.view.presets.length}`,
    kinds: ["intel", "stage", "done", "chat", "doc"],
    locked: false,
  });
  state.view.activePreset = id;
  saveView();
  renderPresetEditor();
  renderPresetChips();
  for (const card of state.cards) applyFilterTo(card);
});

els.resetView.addEventListener("click", () => {
  state.view = defaultView();
  saveView();
  syncViewControls();
  renderKindToggles();
  renderPresetEditor();
  applyViewChrome();
  renderOrder();
});

function bindLlmInput(kind, field, el) {
  el.addEventListener("input", () => {
    state.llm[kind][field] = el.value;
    saveLlmState();
    refreshConfigBanner();
    if (!state.running) previewModelBadges(state.envProfiles);
    const result = kind === "agent" ? els.agentTestResult : els.gameTestResult;
    if (result) {
      result.textContent = "";
      result.className = "llm-test__result";
    }
  });
}

async function testLlm(kind) {
  const button = kind === "agent" ? els.agentTest : els.gameTest;
  const result = kind === "agent" ? els.agentTestResult : els.gameTestResult;
  const item = state.llm[kind] || {};
  if (!button || !result) return;
  button.disabled = true;
  result.className = "llm-test__result";
  result.textContent = "连接中…";
  try {
    const body = { kind };
    if (String(item.key || "").trim()) body.api_key = String(item.key).trim();
    if (String(item.base || "").trim()) body.base_url = String(item.base).trim();
    if (String(item.model || "").trim()) body.model = String(item.model).trim();
    const res = await fetch(API + "/api/ai/test-llm", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(await errorMessage(res));
    const data = await res.json();
    const reply = String(data.reply || "").trim().slice(0, 24) || "OK";
    result.className = "llm-test__result is-ok";
    result.textContent = `✓ ${data.model} · ${String(data.protocol || "").toUpperCase()} · ${reply}`;
  } catch (err) {
    result.className = "llm-test__result is-err";
    result.textContent = `✗ ${err.message || "连接失败"}`;
  } finally {
    button.disabled = false;
  }
}

bindLlmInput("agent", "key", els.agentKey);
bindLlmInput("agent", "base", els.agentBase);
bindLlmInput("agent", "model", els.agentModel);
bindLlmInput("game", "key", els.gameKey);
bindLlmInput("game", "base", els.gameBase);
bindLlmInput("game", "model", els.gameModel);

els.agentTest.addEventListener("click", () => testLlm("agent"));
els.gameTest.addEventListener("click", () => testLlm("game"));

els.showKeys.addEventListener("change", () => {
  const type = els.showKeys.checked ? "text" : "password";
  els.agentKey.type = type;
  els.gameKey.type = type;
});

els.reloadScenario.addEventListener("click", reloadScenario);

els.copyReport.addEventListener("click", async () => {
  const text = els.reportText.textContent || "";
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    els.copyReport.textContent = "已复制";
    setTimeout(() => {
      els.copyReport.textContent = "复制";
    }, 1600);
  } catch {
    els.copyReport.textContent = "复制失败";
  }
});

els.objective.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    event.preventDefault();
    start();
  }
});

boot();
