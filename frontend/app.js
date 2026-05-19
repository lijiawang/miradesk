const state = {
  sessions: [],
  activeSessionId: null,
  tasks: [],
  runs: [],
  selectedTaskId: null,
  currentStreamController: null,
  streamingSessionId: null,
};

const SESSION_STORAGE_KEY = "miradesk.sessions.v1";
const LEGACY_SESSION_STORAGE_KEY = "claude-web.sessions.v1";
const API_BASE_URL = (
  window.__CLAUDE_WEB_API_BASE_URL__ ||
  import.meta.env?.VITE_API_BASE_URL ||
  ""
).replace(/\/$/, "");

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function apiUrl(path) {
  return `${API_BASE_URL}${path}`;
}

const elements = {
  apiStatus: $("#apiStatus"),
  schedulerStatus: $("#schedulerStatus"),
  sectionTitle: $("#sectionTitle"),
  sectionMeta: $("#sectionMeta"),
  messageList: $("#messageList"),
  chatWindow: $(".chat-window"),
  messageCount: $("#messageCount"),
  sessionList: $("#sessionList"),
  newSessionButton: $("#newSessionButton"),
  activeSessionTitle: $("#activeSessionTitle"),
  outputConsole: $("#outputConsole"),
  runState: $("#runState"),
  chatForm: $("#chatForm"),
  promptInput: $("#promptInput"),
  commandInput: $("#commandInput"),
  timeoutInput: $("#timeoutInput"),
  cliPathInput: $("#cliPathInput"),
  stopStreamButton: $("#stopStreamButton"),
  saveAsTaskButton: $("#saveAsTaskButton"),
  taskForm: $("#taskForm"),
  taskNameInput: $("#taskNameInput"),
  taskPromptInput: $("#taskPromptInput"),
  taskCommandInput: $("#taskCommandInput"),
  taskIntervalInput: $("#taskIntervalInput"),
  taskNextRunInput: $("#taskNextRunInput"),
  taskTimeoutInput: $("#taskTimeoutInput"),
  taskEnabledInput: $("#taskEnabledInput"),
  taskList: $("#taskList"),
  taskCount: $("#taskCount"),
  runTaskSelect: $("#runTaskSelect"),
  runList: $("#runList"),
  runDetailConsole: $("#runDetailConsole"),
  selectedRunState: $("#selectedRunState"),
  refreshButton: $("#refreshButton"),
  clearConsoleButton: $("#clearConsoleButton"),
  copyOutputButton: $("#copyOutputButton"),
  toastHost: $("#toastHost"),
};

const sectionCopy = {
  chat: ["会话", "本机 Claude CLI 执行工作台"],
  tasks: ["定时任务", "创建、触发、启停本机 Claude 任务"],
  runs: ["运行记录", "查看定时任务的历史输出"],
};

function formatDate(value) {
  if (!value) return "未设置";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function toDatetimeLocalValue(date = new Date(Date.now() + 60_000)) {
  const offset = date.getTimezoneOffset();
  const local = new Date(date.getTime() - offset * 60_000);
  return local.toISOString().slice(0, 16);
}

function fromDatetimeLocal(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function createSession(title = null) {
  const index = state.sessions.length + 1;
  return {
    id: crypto.randomUUID(),
    title: title || `窗口 ${index}`,
    messages: [],
    lastOutput: "",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
}

function loadSessions() {
  try {
    const rawSessions =
      localStorage.getItem(SESSION_STORAGE_KEY) ||
      localStorage.getItem(LEGACY_SESSION_STORAGE_KEY) ||
      "[]";
    const saved = JSON.parse(rawSessions);
    if (Array.isArray(saved) && saved.length > 0) {
      state.sessions = saved.map((session, index) => ({
        id: session.id || crypto.randomUUID(),
        title: session.title || `窗口 ${index + 1}`,
        messages: Array.isArray(session.messages) ? session.messages : [],
        lastOutput: session.lastOutput || "",
        createdAt: session.createdAt || new Date().toISOString(),
        updatedAt: session.updatedAt || new Date().toISOString(),
      }));
      state.activeSessionId = state.sessions[0].id;
      saveSessions();
      return;
    }
  } catch {
    localStorage.removeItem(SESSION_STORAGE_KEY);
  }

  const session = createSession("窗口 1");
  state.sessions = [session];
  state.activeSessionId = session.id;
  saveSessions();
}

function saveSessions() {
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(state.sessions));
}

function getActiveSession() {
  return state.sessions.find((session) => session.id === state.activeSessionId) || state.sessions[0];
}

function getSession(sessionId) {
  return state.sessions.find((session) => session.id === sessionId);
}

function setActiveSession(sessionId) {
  if (!getSession(sessionId)) return;
  state.activeSessionId = sessionId;
  switchSection("chat");
  renderSessions();
  renderMessages();
  renderOutput();
}

function addSession() {
  const session = createSession();
  state.sessions.unshift(session);
  state.activeSessionId = session.id;
  saveSessions();
  switchSection("chat");
  renderSessions();
  renderMessages();
  renderOutput();
}

function deleteSession(sessionId) {
  if (state.streamingSessionId === sessionId) {
    toast("这个窗口正在输出，停止后再删除", "error");
    return;
  }
  if (state.sessions.length === 1) {
    toast("至少保留一个会话窗口", "error");
    return;
  }
  state.sessions = state.sessions.filter((session) => session.id !== sessionId);
  if (state.activeSessionId === sessionId) {
    state.activeSessionId = state.sessions[0].id;
  }
  saveSessions();
  renderSessions();
  renderMessages();
  renderOutput();
}

function updateSessionTitle(session, prompt) {
  if (!session || session.messages.length > 1) return;
  const title = prompt.replace(/\s+/g, " ").slice(0, 22).trim();
  if (title) {
    session.title = title;
  }
}

function setRunState(label, mode = "") {
  elements.runState.textContent = label;
  elements.runState.className = `state-pill ${mode}`.trim();
}

function toast(message, mode = "") {
  const node = document.createElement("div");
  node.className = `toast ${mode}`.trim();
  node.textContent = message;
  elements.toastHost.appendChild(node);
  setTimeout(() => node.remove(), 3600);
}

async function request(path, options = {}) {
  const response = await fetch(apiUrl(path), {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (response.status === 204) {
    return null;
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail || response.statusText || "请求失败";
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

async function loadHealth() {
  try {
    const data = await request("/health");
    elements.apiStatus.textContent = data.status === "healthy" ? "在线" : data.status;
    elements.schedulerStatus.textContent = data.scheduler_running ? "运行中" : "停止";
  } catch (error) {
    elements.apiStatus.textContent = "离线";
    elements.schedulerStatus.textContent = "未知";
  }
}

async function loadTasks() {
  try {
    state.tasks = await request("/tasks");
    renderTasks();
    renderTaskSelect();
  } catch (error) {
    toast(error.message, "error");
  }
}

function addMessage(role, body, sessionId = state.activeSessionId) {
  const session = getSession(sessionId);
  if (!session) return null;
  const message = {
    id: crypto.randomUUID(),
    role,
    body,
    at: new Date().toISOString(),
  };
  session.messages.unshift(message);
  session.updatedAt = new Date().toISOString();
  saveSessions();
  if (session.id === state.activeSessionId) {
    renderSessions();
    renderMessages();
  }
  return message;
}

function renderSessions() {
  elements.sessionList.innerHTML = state.sessions
    .map(
      (session) => `
        <button class="session-item ${session.id === state.activeSessionId ? "active" : ""}" data-session-id="${session.id}">
          <span class="session-main">
            <span class="session-title">${escapeHtml(session.title)}</span>
            <span class="session-meta">${session.messages.length} 条 · ${formatDate(session.updatedAt)}</span>
          </span>
          <span class="session-delete" data-delete-session="${session.id}" title="删除">×</span>
        </button>
      `,
    )
    .join("");
}

function renderMessages() {
  const session = getActiveSession();
  const messages = session?.messages || [];
  elements.activeSessionTitle.textContent = session?.title || "会话窗口";
  elements.messageCount.textContent = String(messages.length);
  elements.messageList.dataset.empty = messages.length === 0 ? "true" : "false";
  elements.chatWindow.classList.toggle("empty", messages.length === 0);
  if (messages.length === 0) {
    elements.messageList.innerHTML = `
      <article class="empty-chat">
        <div class="empty-title">你在忙什么？</div>
      </article>
    `;
    return;
  }
  elements.messageList.innerHTML = messages
    .slice()
    .reverse()
    .map(
      (message, index) => `
        <article class="message ${message.role}">
          <div class="message-meta">${message.role === "user" ? "You" : "Claude"} · ${formatDate(message.at)}</div>
          ${renderMessageContent(message, index)}
        </article>
      `,
    )
    .join("");
  elements.messageList.scrollTop = elements.messageList.scrollHeight;
}

function renderOutput() {
  const session = getActiveSession();
  elements.outputConsole.textContent = session?.lastOutput || "";
}

function renderMessageContent(message, index) {
  const body = message.body || "";
  if (!body) {
    return `<div class="message-body muted-body">正在输出...</div>`;
  }
  if (message.role === "assistant") {
    return `
      <div class="assistant-output-card">
        <div class="output-card-toolbar">
          <span>text</span>
          <button class="copy-message-button" type="button" data-copy-message="${index}" title="复制">⧉</button>
        </div>
        <pre class="message-code">${escapeHtml(body)}</pre>
      </div>
    `;
  }
  return `<div class="message-body">${escapeHtml(body)}</div>`;
}

function buildContextPrompt(session, prompt) {
  const history = (session?.messages || [])
    .slice()
    .reverse()
    .filter((message) => message.body)
    .slice(-16);

  if (history.length === 0) {
    return prompt;
  }

  const context = history
    .map((message) => `${message.role === "user" ? "User" : "Assistant"}: ${message.body}`)
    .join("\n\n");

  return [
    "请只基于当前会话窗口的上下文继续回答。",
    "以下是该窗口已有上下文：",
    context,
    "当前用户输入：",
    prompt,
  ].join("\n\n");
}

function renderTasks() {
  elements.taskCount.textContent = String(state.tasks.length);
  if (state.tasks.length === 0) {
    elements.taskList.innerHTML = `<div class="task-item"><div class="task-name">暂无任务</div><div class="task-meta">创建后会保存在本机 SQLite。</div></div>`;
    return;
  }

  elements.taskList.innerHTML = state.tasks
    .map(
      (task) => `
        <article class="task-item" data-task-id="${task.id}">
          <div class="task-title-row">
            <div class="task-name">${escapeHtml(task.name)}</div>
            <span class="state-pill ${task.enabled ? "ok" : ""}">${task.enabled ? "启用" : "暂停"}</span>
          </div>
          <div class="task-meta">
            ${escapeHtml(task.command)} · 每 ${task.interval_seconds || "单次"} 秒 · 下次 ${formatDate(task.next_run_at)}
          </div>
          <div class="task-actions">
            <button data-action="run" data-id="${task.id}">立即运行</button>
            <button data-action="toggle" data-id="${task.id}">${task.enabled ? "暂停" : "启用"}</button>
            <button data-action="runs" data-id="${task.id}">记录</button>
            <button class="danger" data-action="delete" data-id="${task.id}">删除</button>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderTaskSelect() {
  elements.runTaskSelect.innerHTML = state.tasks
    .map((task) => `<option value="${task.id}">${escapeHtml(task.name)}</option>`)
    .join("");
  if (!state.selectedTaskId && state.tasks[0]) {
    state.selectedTaskId = state.tasks[0].id;
  }
  if (state.selectedTaskId) {
    elements.runTaskSelect.value = String(state.selectedTaskId);
  }
}

async function runClaude(payload, sessionId) {
  const session = getSession(sessionId);
  if (!session) return;

  setRunState("流式输出", "busy");
  session.lastOutput = "";
  if (session.id === state.activeSessionId) {
    elements.outputConsole.textContent = "";
  }
  const assistantMessage = addMessage("assistant", "", session.id);
  const controller = new AbortController();
  state.currentStreamController = controller;
  state.streamingSessionId = session.id;
  elements.stopStreamButton.disabled = false;

  try {
    const response = await fetch(apiUrl("/claude/stream"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    if (!response.ok || !response.body) {
      throw new Error(`流式请求失败: ${response.status}`);
    }

    await readEventStream(response.body, (event, data) => {
      if (event === "chunk") {
        const text = data.text || "";
        session.lastOutput += data.stream === "stderr" ? text : text;
        assistantMessage.body = session.lastOutput || "(streaming...)";
        session.updatedAt = new Date().toISOString();
        saveSessions();
        if (session.id === state.activeSessionId) {
          elements.outputConsole.textContent = session.lastOutput;
          elements.outputConsole.scrollTop = elements.outputConsole.scrollHeight;
          renderMessages();
          renderSessions();
        }
      }

      if (event === "error") {
        const message = data.message || "流式输出失败";
        session.lastOutput += `\n${message}`;
        assistantMessage.body = session.lastOutput;
        session.updatedAt = new Date().toISOString();
        saveSessions();
        if (session.id === state.activeSessionId) {
          elements.outputConsole.textContent = session.lastOutput;
          renderMessages();
          renderSessions();
        }
        setRunState("失败", "error");
        toast(message, "error");
      }

      if (event === "done") {
        const success = Boolean(data.success);
        assistantMessage.body = session.lastOutput || "(no output)";
        session.updatedAt = new Date().toISOString();
        saveSessions();
        if (session.id === state.activeSessionId) {
          renderMessages();
          renderSessions();
        }
        setRunState(success ? "完成" : "失败", success ? "ok" : "error");
      }
    });
  } catch (error) {
    if (error.name === "AbortError") {
      session.lastOutput += "\n[已停止]";
      assistantMessage.body = session.lastOutput;
      session.updatedAt = new Date().toISOString();
      saveSessions();
      if (session.id === state.activeSessionId) {
        elements.outputConsole.textContent = session.lastOutput;
        renderMessages();
        renderSessions();
      }
      setRunState("已停止", "error");
      return;
    }
    session.lastOutput = error.message;
    assistantMessage.body = error.message;
    session.updatedAt = new Date().toISOString();
    saveSessions();
    if (session.id === state.activeSessionId) {
      elements.outputConsole.textContent = session.lastOutput;
      renderMessages();
      renderSessions();
    }
    setRunState("失败", "error");
    toast(error.message, "error");
  } finally {
    state.currentStreamController = null;
    state.streamingSessionId = null;
    elements.stopStreamButton.disabled = true;
  }
}

async function readEventStream(body, onEvent) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      dispatchEventBlock(rawEvent, onEvent);
      boundary = buffer.indexOf("\n\n");
    }
  }

  if (buffer.trim()) {
    dispatchEventBlock(buffer, onEvent);
  }
}

function dispatchEventBlock(rawEvent, onEvent) {
  const lines = rawEvent.split("\n");
  let event = "message";
  const dataLines = [];

  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }

  if (dataLines.length === 0) return;
  const dataText = dataLines.join("\n");
  try {
    onEvent(event, JSON.parse(dataText));
  } catch {
    onEvent(event, { text: dataText });
  }
}

function buildChatPayload() {
  const session = getActiveSession();
  const prompt = elements.promptInput.value.trim();
  if (!prompt) {
    throw new Error("请输入 Prompt");
  }
  return {
    prompt,
    session,
    payload: {
      command: elements.commandInput.value,
      timeout: Number(elements.timeoutInput.value || 300),
      cli_path: elements.cliPathInput.value.trim() || null,
      args: {
        message: buildContextPrompt(session, prompt),
      },
    },
  };
}

function buildTaskPayload() {
  const name = elements.taskNameInput.value.trim();
  const prompt = elements.taskPromptInput.value.trim();
  if (!name) throw new Error("请输入任务名称");
  if (!prompt) throw new Error("请输入任务 Prompt");

  return {
    name,
    command: elements.taskCommandInput.value,
    args: {
      message: prompt,
    },
    interval_seconds: Number(elements.taskIntervalInput.value || 3600),
    next_run_at: fromDatetimeLocal(elements.taskNextRunInput.value),
    timeout: Number(elements.taskTimeoutInput.value || 300),
    enabled: elements.taskEnabledInput.checked,
  };
}

async function createTask(payload) {
  await request("/tasks", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  toast("任务已创建");
  await loadTasks();
}

async function showRuns(taskId) {
  state.selectedTaskId = Number(taskId);
  switchSection("runs");
  renderTaskSelect();
  await loadRuns(taskId);
}

async function loadRuns(taskId) {
  if (!taskId) {
    elements.runList.innerHTML = `<div class="run-item"><div class="run-name">暂无任务</div></div>`;
    return;
  }
  state.runs = await request(`/tasks/${taskId}/runs`);
  if (state.runs.length === 0) {
    elements.runList.innerHTML = `<div class="run-item"><div class="run-name">暂无运行记录</div><div class="run-meta">任务触发后会出现在这里。</div></div>`;
    return;
  }
  elements.runList.innerHTML = state.runs
    .map(
      (run) => `
        <article class="run-item" data-run-id="${run.id}">
          <div class="run-title-row">
            <div class="run-name">Run #${run.id}</div>
            <span class="state-pill ${run.status === "success" ? "ok" : run.status === "failed" ? "error" : "busy"}">${run.status}</span>
          </div>
          <div class="run-meta">${formatDate(run.started_at)} → ${formatDate(run.finished_at)}</div>
          <button class="mini-button" data-run-detail="${run.id}">查看输出</button>
        </article>
      `,
    )
    .join("");
}

function switchSection(name) {
  document.body.dataset.section = name;
  $$(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.section === name));
  elements.newSessionButton.classList.toggle("active", name === "chat");
  $$("[data-view]").forEach((view) => view.classList.toggle("hidden", view.dataset.view !== name));
  elements.sectionTitle.textContent = sectionCopy[name][0];
  elements.sectionMeta.textContent = sectionCopy[name][1];
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function bindEvents() {
  $$(".nav-item").forEach((button) => {
    button.addEventListener("click", () => switchSection(button.dataset.section));
  });

  elements.newSessionButton.addEventListener("click", () => {
    addSession();
  });

  elements.sessionList.addEventListener("click", (event) => {
    const deleteTarget = event.target.closest("[data-delete-session]");
    if (deleteTarget) {
      event.stopPropagation();
      deleteSession(deleteTarget.dataset.deleteSession);
      return;
    }

    const sessionTarget = event.target.closest("[data-session-id]");
    if (sessionTarget) {
      setActiveSession(sessionTarget.dataset.sessionId);
    }
  });

  elements.messageList.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-copy-message]");
    if (!button) return;
    const messages = (getActiveSession()?.messages || []).slice().reverse();
    const message = messages[Number(button.dataset.copyMessage)];
    if (!message) return;
    await navigator.clipboard.writeText(message.body || "");
    toast("消息已复制");
  });

  elements.promptInput.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing) {
      return;
    }
    event.preventDefault();
    elements.chatForm.requestSubmit();
  });

  elements.chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      if (state.currentStreamController) {
        toast("当前会话正在输出，请先停止或等待完成", "error");
        return;
      }
      const { payload, prompt, session } = buildChatPayload();
      addMessage("user", prompt, session.id);
      updateSessionTitle(session, prompt);
      saveSessions();
      renderSessions();
      renderMessages();
      elements.promptInput.value = "";
      await runClaude(payload, session.id);
    } catch (error) {
      toast(error.message, "error");
    }
  });

  elements.saveAsTaskButton.addEventListener("click", () => {
    const prompt = elements.promptInput.value.trim();
    if (prompt) {
      elements.taskPromptInput.value = prompt;
      elements.taskNameInput.value = `task-${new Date().toISOString().slice(0, 16).replace(/[-:T]/g, "")}`;
      elements.taskCommandInput.value = elements.commandInput.value;
      elements.taskTimeoutInput.value = elements.timeoutInput.value;
      switchSection("tasks");
    } else {
      toast("先输入 Prompt，再保存为定时任务", "error");
    }
  });

  elements.stopStreamButton.addEventListener("click", () => {
    state.currentStreamController?.abort();
  });

  elements.taskForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await createTask(buildTaskPayload());
      elements.taskForm.reset();
      elements.taskNextRunInput.value = toDatetimeLocalValue();
      elements.taskEnabledInput.checked = true;
    } catch (error) {
      toast(error.message, "error");
    }
  });

  elements.taskList.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const id = Number(button.dataset.id);
    const action = button.dataset.action;
    const task = state.tasks.find((item) => item.id === id);
    try {
      if (action === "run") {
        await request(`/tasks/${id}/run-now`, { method: "POST" });
        toast("任务已加入执行队列");
      }
      if (action === "toggle") {
        await request(`/tasks/${id}`, {
          method: "PATCH",
          body: JSON.stringify({
            enabled: !task.enabled,
            next_run_at: !task.enabled ? new Date().toISOString() : null,
          }),
        });
        toast(task.enabled ? "任务已暂停" : "任务已启用");
      }
      if (action === "runs") {
        await showRuns(id);
        return;
      }
      if (action === "delete") {
        await request(`/tasks/${id}`, { method: "DELETE" });
        toast("任务已删除");
      }
      await loadTasks();
    } catch (error) {
      toast(error.message, "error");
    }
  });

  elements.runTaskSelect.addEventListener("change", async () => {
    await loadRuns(elements.runTaskSelect.value);
  });

  elements.runList.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-run-detail]");
    if (!button) return;
    const run = state.runs.find((item) => String(item.id) === String(button.dataset.runDetail));
    if (!run) return;
    elements.selectedRunState.textContent = run.status;
    elements.selectedRunState.className = `state-pill ${run.status === "success" ? "ok" : run.status === "failed" ? "error" : "busy"}`;
    elements.runDetailConsole.textContent = run.output || run.error || "";
  });

  elements.refreshButton.addEventListener("click", async () => {
    await Promise.all([loadHealth(), loadTasks()]);
    if (state.selectedTaskId) {
      await loadRuns(state.selectedTaskId);
    }
    toast("已刷新");
  });

  elements.clearConsoleButton.addEventListener("click", () => {
    const session = getActiveSession();
    if (session) {
      session.lastOutput = "";
      saveSessions();
    }
    elements.outputConsole.textContent = "";
    elements.runDetailConsole.textContent = "";
  });

  elements.copyOutputButton.addEventListener("click", async () => {
    await navigator.clipboard.writeText(elements.outputConsole.textContent || "");
    toast("输出已复制");
  });
}

async function boot() {
  loadSessions();
  bindEvents();
  switchSection("chat");
  renderSessions();
  renderMessages();
  renderOutput();
  elements.taskNextRunInput.value = toDatetimeLocalValue();
  await Promise.all([loadHealth(), loadTasks()]);
  setInterval(loadHealth, 8000);
  setInterval(loadTasks, 12000);
}

boot();
