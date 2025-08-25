const DEFAULT_SETTINGS = {
  serverUrl: "http://127.0.0.1:8766",
  jpegQuality: 0.85,
  autoRetryMinutes: 1,
  schemaEndpoint: ""  // 可自定义分类 Schema 路径（相对或绝对）
};

// -------- helpers --------
function normalizeBase(base){
  base = (base||"").trim();
  if (!/^https?:\/\//i.test(base)) base = "http://" + base;
  // remove trailing slashes
  base = base.replace(/\/+$/,"");
  return base;
}
function normalizePath(p){
  if (!p) return "/";
  // allow absolute url
  if (/^https?:\/\//i.test(p)) return p;
  // ensure single leading slash
  return "/" + p.replace(/^\/+/, "");
}
function cleanJoin(base, path){
  base = normalizeBase(base);
  path = normalizePath(path);
  return base + path;
}

async function getSettings() {
  const res = await chrome.storage.local.get({ settings: DEFAULT_SETTINGS, outbox: [], cachedSchema: null });
  const settings = Object.assign({}, DEFAULT_SETTINGS, res.settings || {});
  return { settings, outbox: res.outbox || [], cachedSchema: res.cachedSchema || null };
}
async function saveSettings(settings) { await chrome.storage.local.set({ settings }); }
async function setCachedSchema(schema){ await chrome.storage.local.set({ cachedSchema: schema }); }
async function clearCachedSchema(){ await chrome.storage.local.remove("cachedSchema"); }

async function pushOutbox(item) {
  const { outbox } = await getSettings();
  outbox.push(item);
  await chrome.storage.local.set({ outbox });
  scheduleRetry();
}
function scheduleRetry() {
  chrome.storage.local.get({ settings: DEFAULT_SETTINGS }, ({ settings }) => {
    const minutes = Math.max(1, settings.autoRetryMinutes || 1);
    chrome.alarms.create("outboxRetry", { periodInMinutes: minutes });
  });
}
async function processOutbox() {
  const { settings, outbox } = await getSettings();
  if (!outbox?.length) return;
  const remain = [];
  for (const item of outbox) {
    try {
      // 与实时发送逻辑保持一致：优先 /api/push，失败再 /tag/add
      const pushUrl = cleanJoin(settings.serverUrl, "/api/push");
      const pushResp = await fetch(pushUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(item)
      });
      if (pushResp.ok) {
        continue;
      }
      const tagUrl = cleanJoin(settings.serverUrl, "/tag/add");
      const tagResp = await fetch(tagUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(item)
      });
      if (!tagResp.ok) throw new Error("HTTP " + tagResp.status);
    } catch (e) {
      remain.push(item);
    }
  }
  await chrome.storage.local.set({ outbox: remain });
  if (!remain.length) chrome.alarms.clear("outboxRetry");
}
chrome.alarms.onAlarm.addListener(a=>{ if (a.name==="outboxRetry") processOutbox(); });

// 创建右键菜单
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "createMJTag",
    title: "新建MJ标签",
    contexts: ["image"]
  });
});

// 处理右键菜单点击
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "createMJTag" && info.srcUrl) {
    // 向content script发送消息，传递图片URL
    chrome.tabs.sendMessage(tab.id, {
      type: "CREATE_TAG_FROM_IMAGE",
      imageUrl: info.srcUrl,
      pageUrl: info.pageUrl,
      pageTitle: tab.title
    });
  }
});

async function tryFetchSchema(settings) {
  const endpoints = [];
  if (settings.schemaEndpoint && settings.schemaEndpoint.trim()) endpoints.push(settings.schemaEndpoint.trim());
  endpoints.push("/tag/schema", "/schema", "/tags/schema", "/sync/schema");
  let lastErr = null;
  for (const ep of endpoints) {
    try {
      const url = /^https?:\/\//i.test(ep) ? ep : cleanJoin(settings.serverUrl, ep);
      const resp = await fetch(url, { method: "GET" });
      if (!resp.ok) { lastErr = "HTTP " + resp.status; continue; }
      const data = await resp.json();
      if (data && (data.head || data.tail || data.headTabs || data.tailTabs)) {
        const schema = { head: data.head || data.headTabs || [], tail: data.tail || data.tailTabs || [] };
        await setCachedSchema(schema);
        return { ok: true, schema, endpoint: ep };
      }
    } catch (e) { lastErr = String(e); }
  }
  // fallback to cached
  const { cachedSchema } = await getSettings();
  if (cachedSchema) return { ok: true, schema: cachedSchema, endpoint: "(cached)" };
  return { ok: false, error: lastErr || "未找到可用的 Schema 接口，且无缓存可用" };
}

async function pingServer(settings) {
  const candidates = ["/health", "/ping", "/"];
  let last = null;
  for (const ep of candidates) {
    try {
      const url = cleanJoin(settings.serverUrl, ep);
      const resp = await fetch(url, { method: "GET" });
      if (resp.ok) return { ok: true, status: resp.status };
      last = "HTTP " + resp.status;
    } catch (e) { last = String(e); }
  }
  return { ok: false, error: last || "连接失败" };
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    try {
      if (msg.type === "GET_SETTINGS") {
        const state = await getSettings(); sendResponse({ ok: true, settings: state.settings, cachedSchema: state.cachedSchema });
      } else if (msg.type === "SET_SETTINGS") {
        // normalize base at save time to reduce错误
        const s = Object.assign({}, msg.settings);
        s.serverUrl = normalizeBase(s.serverUrl||"");
        await saveSettings(s); sendResponse({ ok: true });
      } else if (msg.type === "CLEAR_SCHEMA_CACHE") {
        await clearCachedSchema(); sendResponse({ ok: true });
      } else if (msg.type === "CAPTURE") {
        const { settings } = await getSettings();
        try {
          const winId = (sender && sender.tab && sender.tab.windowId) || chrome.windows && chrome.windows.WINDOW_ID_CURRENT;
          chrome.tabs.captureVisibleTab(winId, {
            format: "jpeg",
            quality: Math.round((settings.jpegQuality ?? 0.85) * 100)
          }, (dataUrl) => {
            if (chrome.runtime.lastError || !dataUrl) {
              sendResponse({ ok: false, error: (chrome.runtime.lastError && chrome.runtime.lastError.message) || 'captureVisibleTab 失败' });
            } else {
              sendResponse({ ok: true, dataUrl });
            }
          });
        } catch (e) {
          sendResponse({ ok: false, error: String(e) });
        }
        return true;
      } else if (msg.type === "TRANSLATE") {
        const { settings } = await getSettings();
        const url = cleanJoin(settings.serverUrl, "/translate");
        try {
          const resp = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: msg.text, to: "zh" }) });
          if (!resp.ok) throw new Error("HTTP " + resp.status);
          const data = await resp.json();
          const zh = data.zh || data.translated || data.text || data.result || "";
          sendResponse({ ok: true, zh, raw: data });
        } catch (e) {
          sendResponse({ ok: false, error: String(e) + "。请检查本地程序是否开启，且已设置 CORS（Access-Control-Allow-Origin: *）。" });
        }
      } else if (msg.type === "SAVE_TAG") {
        const { settings } = await getSettings();
        // 关键改动：将包含截图和中文名的完整 payload 直接发给服务器
        const payload = Object.assign({}, msg.payload, { _ts: Date.now() });
        
        try {
          // 优先使用 /api/push 端点，服务器会处理截图和文件名
          const pushUrl = cleanJoin(settings.serverUrl, "/api/push");
          const pushResp = await fetch(pushUrl, { 
            method: "POST", 
            headers: { "Content-Type": "application/json" }, 
            body: JSON.stringify(payload) // 直接发送完整 payload
          });
          
          if (pushResp.ok) {
            console.log("[Background] 完整标签数据（含截图）已通过 /api/push 发送成功");
            sendResponse({ ok: true, data: { message: "数据已发送到主程序" } });
            return;
          }
          
          // 如果 /api/push 失败，尝试使用 /tag/add 端点（作为备用）
          const tagUrl = cleanJoin(settings.serverUrl, "/tag/add");
          const tagResp = await fetch(tagUrl, { 
            method: "POST", 
            headers: { "Content-Type": "application/json" }, 
            body: JSON.stringify(payload) 
          });
          
          if (!tagResp.ok) throw new Error("HTTP " + tagResp.status);
          const data = await tagResp.json().catch(()=>({}));
          sendResponse({ ok: true, data });
          
        } catch (e) {
          console.error("[Background] 标签保存失败:", String(e));
          // 将完整数据加入离线队列
          await pushOutbox(payload);
          sendResponse({ ok: false, queued: true, error: String(e) + "。已加入离线队列，待网络恢复或主程序可用后自动重试。" });
        }
      } else if (msg.type === "FETCH_SCHEMA") {
        const { settings } = await getSettings();
        const r = await tryFetchSchema(settings); sendResponse(r);
      } else if (msg.type === "PING_SERVER") {
        const { settings } = await getSettings();
        const r = await pingServer(settings); sendResponse(r);
      } else if (msg.type === "REQUEST_DESKTOP_CAPTURE") {
        // 直接返回成功，让content script使用标准API
        // 这样可以避免额外的权限弹窗
        sendResponse({ ok: true, useStandardAPI: true });
        return true;
      }
    } catch (err) {
      sendResponse({ ok: false, error: String(err) });
    }
  })();
  return true;
});