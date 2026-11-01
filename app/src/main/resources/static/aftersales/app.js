const CLIENT_ID = "e5cd7e4891bf95d1d19206ce24a7b32e";
const TOKEN_KEY = "aftersales_access_token";
const views = { overview: "工作台总览", documents: "资料管理", retrieval: "检索测试", ask: "溯源问答" };
let token = sessionStorage.getItem(TOKEN_KEY) || "";
const $ = (selector) => document.querySelector(selector);

function parseJson(text) {
  let result = "";
  let quoted = false;
  let escaped = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      result += ch;
      if (escaped) escaped = false;
      else if (ch === "\\") escaped = true;
      else if (ch === '"') quoted = false;
      continue;
    }
    if (ch === '"') {
      quoted = true;
      result += ch;
      continue;
    }
    if (ch >= "0" && ch <= "9") {
      let end = i + 1;
      while (end < text.length && /[0-9.eE+-]/.test(text[end])) end++;
      const value = text.slice(i, end);
      result += /^\d{16,}$/.test(value) ? '"' + value + '"' : value;
      i = end - 1;
      continue;
    }
    result += ch;
  }
  return JSON.parse(result);
}

function notify(message, error = false) {
  const box = $("#notice");
  box.textContent = message;
  box.className = error ? "notice error" : "notice";
  box.hidden = false;
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function setBusy(form, busy) {
  const button = form.querySelector('button[type="submit"]');
  if (!button) return;
  if (busy) {
    button.dataset.label = button.textContent;
    button.textContent = "处理中…";
    button.disabled = true;
  } else {
    button.textContent = button.dataset.label || button.textContent;
    button.disabled = false;
  }
}

async function api(path, options = {}) {
  const headers = { clientid: CLIENT_ID, ...(options.headers || {}) };
  if (token) headers.Authorization = "Bearer " + token;
  const response = await fetch(path, { ...options, headers });
  const text = await response.text();
  let payload;
  try { payload = text ? parseJson(text) : null; }
  catch { throw new Error("服务器返回了无法解析的数据"); }
  if (!response.ok || (payload && typeof payload.code === "number" && payload.code !== 200)) {
    const message = payload?.msg || payload?.message || `请求失败（HTTP ${response.status}）`;
    if (response.status === 401 || payload?.code === 401) clearSession();
    throw new Error(message);
  }
  return payload?.data ?? payload;
}

function jsonOptions(body) {
  return { method: "POST", headers: { "Content-Type": "application/json" }, body };
}

function knowledgeId() {
  const value = $("#knowledge-id").value.trim();
  if (!/^\d{1,19}$/.test(value)) throw new Error("请输入有效的知识库 ID");
  return value;
}

function questionBody(id, question, topK, extra = "") {
  return `{"knowledgeId":${id},"query":${JSON.stringify(question)},"topK":${topK}${extra}}`;
}

function make(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined && content !== null) node.textContent = String(content);
  return node;
}

function clearSession() {
  token = "";
  sessionStorage.removeItem(TOKEN_KEY);
  $("#workspace").hidden = true;
  $("#login-panel").hidden = false;
  $("#logout").hidden = true;
  $("#session-label").textContent = "尚未登录";
  $(".sidebar-foot").classList.remove("signed");
  $("#password").value = "";
}

function showSession() {
  $("#workspace").hidden = false;
  $("#login-panel").hidden = true;
  $("#logout").hidden = false;
  $("#session-label").textContent = "已登录 · 权限由后端校验";
  $(".sidebar-foot").classList.add("signed");
}

function setView() {
  const key = location.hash.replace("#", "");
  const view = Object.hasOwn(views, key) ? key : "overview";
  $("#page-title").textContent = views[view];
  document.querySelectorAll(".view").forEach((node) => node.classList.toggle("active", node.id === "view-" + view));
  document.querySelectorAll(".nav a").forEach((node) => {
    const active = node.dataset.view === view;
    node.classList.toggle("active", active);
    if (active) node.setAttribute("aria-current", "page");
    else node.removeAttribute("aria-current");
  });
  if (view === "documents" && token) loadDocuments();
}

function knowledgeRow(item) {
  const row = make("div", "knowledge-item");
  const details = make("div");
  details.append(make("div", "knowledge-name", item.name || "未命名知识库"));
  details.append(make("p", "knowledge-desc", item.description || `ID ${item.id}`));
  const button = make("button", "button outline small", "使用此库");
  button.type = "button";
  button.addEventListener("click", () => {
    $("#knowledge-id").value = String(item.id);
    $("#knowledge-select").value = String(item.id);
    notify(`已切换到 ${item.name || item.id}`);
    if (location.hash === "#documents") loadDocuments();
  });
  row.append(details, button);
  return row;
}

async function loadKnowledge() {
  try {
    const result = await api("/system/info/list?pageNum=1&pageSize=100");
    const rows = result?.rows || [];
    const list = $("#knowledge-list");
    const select = $("#knowledge-select");
    list.replaceChildren();
    select.replaceChildren(new Option("选择知识库", ""));
    if (!rows.length) list.append(make("div", "empty-state", "暂无知识库。可以在右侧创建，或输入已知 ID。"));
    rows.forEach((item) => {
      list.append(knowledgeRow(item));
      select.add(new Option(item.name || String(item.id), String(item.id)));
    });
    $("#knowledge-total").textContent = `共 ${result?.total ?? rows.length} 个`;
    select.value = $("#knowledge-id").value.trim();
  } catch (error) {
    notify(`知识库列表加载失败：${error.message}`, true);
  }
}

function statusLabel(value) {
  return { 0: ["待解析", "waiting"], 1: ["解析中", "parsing"], 2: ["已完成", ""], 3: ["解析失败", "failed"] }[value] || ["未知", "waiting"];
}

async function loadDocuments() {
  let id;
  try { id = knowledgeId(); }
  catch (error) { notify(error.message, true); return; }
  const body = $("#document-rows");
  body.replaceChildren();
  const loading = make("tr");
  const cell = make("td", "table-empty", "正在加载资料…");
  cell.colSpan = 6;
  loading.append(cell);
  body.append(loading);
  try {
    const result = await api(`/system/attach/list?knowledgeId=${encodeURIComponent(id)}&pageNum=1&pageSize=100`);
    const rows = result?.rows || [];
    body.replaceChildren();
    $("#document-total").textContent = `共 ${result?.total ?? rows.length} 份`;
    if (!rows.length) {
      const tr = make("tr");
      const td = make("td", "table-empty", "当前知识库还没有资料。");
      td.colSpan = 6;
      tr.append(td);
      body.append(tr);
      return;
    }
    rows.forEach((item) => {
      const tr = make("tr");
      tr.append(make("td", "", item.name || "—"), make("td", "", item.type?.toUpperCase() || "—"));
      const statusCell = make("td");
      const [label, className] = statusLabel(item.status);
      statusCell.append(make("span", "status-pill " + className, label));
      tr.append(statusCell, make("td", "", item.fragmentCount ?? "—"), make("td", "", item.createTime ? new Date(item.createTime).toLocaleString("zh-CN") : "—"));
      const actionCell = make("td");
      if (item.status !== 1) {
        const button = make("button", "button outline small", item.status === 3 ? "重试解析" : "重新解析");
        button.type = "button";
        button.addEventListener("click", async () => {
          button.disabled = true;
          try {
            await api(`/system/attach/parse/${encodeURIComponent(String(item.id))}`, { method: "POST" });
            notify("解析任务已提交，请稍后刷新状态。");
            loadDocuments();
          } catch (error) { notify(error.message, true); button.disabled = false; }
        });
        actionCell.append(button);
      }
      tr.append(actionCell);
      body.append(tr);
    });
  } catch (error) {
    body.replaceChildren();
    const tr = make("tr");
    const td = make("td", "table-empty", `资料加载失败：${error.message}`);
    td.colSpan = 6;
    tr.append(td);
    body.append(tr);
  }
}

function resultCard(item, index, source = false) {
  const card = make("article", "card result-card");
  const top = make("div", "result-top");
  top.append(make("div", "result-title", `${index + 1}. ${item.sourceName || "未命名来源"}`));
  top.append(make("div", "result-score", typeof item.score === "number" ? `分数 ${item.score.toFixed(4)}` : ""));
  const meta = make("div", "result-meta");
  meta.append(make("span", "", `文档 ID：${item.docId || "—"}`));
  meta.append(make("span", "", `片段 ID：${source ? item.fragmentId || "—" : item.id || "—"}`));
  card.append(top, meta, make("p", "result-content", source ? item.excerpt || "" : item.content || ""));
  return card;
}

$("#today").textContent = new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "long", day: "numeric" }).format(new Date());
window.addEventListener("hashchange", setView);
setView();
if (token) { showSession(); loadKnowledge(); }

$("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  setBusy(form, true);
  try {
    const body = JSON.stringify({ clientId: CLIENT_ID, grantType: "password", tenantId: "000000", username: $("#username").value.trim(), password: $("#password").value });
    const data = await api("/auth/login", jsonOptions(body));
    if (!data?.access_token) throw new Error("登录响应中没有访问令牌");
    token = data.access_token;
    sessionStorage.setItem(TOKEN_KEY, token);
    showSession();
    notify("登录成功。请选择知识库开始使用。");
    await loadKnowledge();
    setView();
  } catch (error) { notify(error.message, true); }
  finally { setBusy(form, false); }
});

$("#logout").addEventListener("click", async () => {
  try { await api("/auth/logout", { method: "POST" }); }
  catch { }
  clearSession();
  notify("已退出登录。");
});

$("#knowledge-select").addEventListener("change", (event) => {
  if (event.target.value) $("#knowledge-id").value = event.target.value;
  if (location.hash === "#documents") loadDocuments();
});
$("#knowledge-id").addEventListener("input", () => { $("#knowledge-select").value = ""; });
$("#refresh-knowledge").addEventListener("click", loadKnowledge);
$("#refresh-documents").addEventListener("click", loadDocuments);
$("#upload-file").addEventListener("change", (event) => { $("#file-name").textContent = event.target.files[0]?.name || "选择文件或拖入资料"; });

$("#create-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const values = new FormData(form);
  setBusy(form, true);
  try {
    await api("/system/info", jsonOptions(JSON.stringify({ name: String(values.get("name") || "").trim(), description: String(values.get("description") || "").trim(), vectorModel: values.get("vectorModel"), embeddingModel: String(values.get("embeddingModel") || "").trim(), share: 0, retrieveLimit: 5, similarityThreshold: 0, textBlockSize: 2000, overlapChar: 100, enableHybrid: 1, hybridAlpha: 0.3 })));
    notify("知识库已创建，刷新列表后选择它。");
    form.reset();
    await loadKnowledge();
  } catch (error) { notify(error.message, true); }
  finally { setBusy(form, false); }
});

$("#upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  setBusy(form, true);
  try {
    const data = new FormData(form);
    data.set("knowledgeId", knowledgeId());
    data.set("autoParse", form.elements.autoParse.checked ? "true" : "false");
    await api("/system/attach/upload", { method: "POST", body: data });
    notify("上传成功。解析可能需要一些时间，请刷新状态。");
    form.reset();
    $("#file-name").textContent = "选择文件或拖入资料";
    await loadDocuments();
  } catch (error) { notify(error.message, true); }
  finally { setBusy(form, false); }
});

$("#retrieval-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  setBusy(form, true);
  try {
    const id = knowledgeId();
    const question = form.elements.query.value.trim();
    const topK = Math.max(1, Math.min(20, Number(form.elements.topK.value) || 5));
    const extra = `,"threshold":0,"enableHybrid":${form.elements.enableHybrid.checked},"hybridAlpha":0.3`;
    const rows = await api("/system/fragment/retrieval", jsonOptions(questionBody(id, question, topK, extra)));
    const results = $("#retrieval-results");
    results.replaceChildren();
    (rows || []).forEach((item, index) => results.append(resultCard(item, index)));
    if (!rows?.length) results.append(make("div", "card empty-state", "没有命中片段。请核对知识库 ID、资料解析状态和查询内容。"));
    $("#retrieval-count").textContent = `${rows?.length || 0} 个片段`;
  } catch (error) { notify(error.message, true); }
  finally { setBusy(form, false); }
});

$("#ask-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  setBusy(form, true);
  try {
    const id = knowledgeId();
    const question = form.elements.question.value.trim();
    const body = `{"knowledgeId":${id},"question":${JSON.stringify(question)},"topK":3}`;
    const data = await api("/system/aftersales/ask", jsonOptions(body));
    $("#answer-area").hidden = false;
    $("#answer-text").textContent = data.answer || "没有返回回答。";
    $("#answer-model").textContent = data.model ? `模型：${data.model}` : "";
    const status = $("#answer-status");
    status.textContent = { GENERATED: "已生成", NO_EVIDENCE: "证据不足", MODEL_UNAVAILABLE: "模型不可用" }[data.status] || data.status || "未知状态";
    status.className = "status-pill " + (data.status === "GENERATED" ? "" : "failed");
    const sources = $("#source-results");
    sources.replaceChildren();
    (data.sources || []).forEach((item, index) => sources.append(resultCard(item, index, true)));
    if (!data.sources?.length) sources.append(make("div", "card empty-state", "本次回答没有可展示的来源片段。"));
    $("#source-count").textContent = `${data.sources?.length || 0} 个来源`;
    $("#answer-area").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) { notify(error.message, true); }
  finally { setBusy(form, false); }
});

document.querySelectorAll("[data-question]").forEach((button) => button.addEventListener("click", () => {
  $("#ask-form textarea").value = button.dataset.question;
  $("#ask-form textarea").focus();
}));
