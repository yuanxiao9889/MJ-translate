function log(msg){ const pre=document.getElementById("log"); pre.textContent=(new Date().toLocaleTimeString())+"  "+msg+"\n"+pre.textContent; }
async function rpc(type, payload){ return await chrome.runtime.sendMessage(Object.assign({type}, payload||{})); }

(async ()=>{
  const serverUrl=document.getElementById("serverUrl");
  const jpegQuality=document.getElementById("jpegQuality");
  const autoRetryMinutes=document.getElementById("autoRetryMinutes");
  const schemaEndpoint=document.getElementById("schemaEndpoint");
  const saveBtn=document.getElementById("saveBtn");
  const pingBtn=document.getElementById("pingBtn");
  const schemaBtn=document.getElementById("schemaBtn");
  const translateBtn=document.getElementById("translateBtn");
  const saveTagBtn=document.getElementById("saveTagBtn");
  const clearSchemaBtn=document.getElementById("clearSchemaBtn");

  const res = await rpc("GET_SETTINGS");
  if (res?.ok) {
    serverUrl.value = res.settings.serverUrl || "http://127.0.0.1:8766";
    jpegQuality.value = res.settings.jpegQuality ?? 0.85;
    autoRetryMinutes.value = res.settings.autoRetryMinutes ?? 1;
    schemaEndpoint.value = res.settings.schemaEndpoint || "";
    if (res.cachedSchema) log("当前缓存 Schema: " + JSON.stringify(res.cachedSchema));
  }

  saveBtn.addEventListener("click", async ()=>{
    const settings = {
      serverUrl: (serverUrl.value||"").trim(),
      jpegQuality: Math.max(0.5, Math.min(0.95, Number(jpegQuality.value)||0.85)),
      autoRetryMinutes: Math.max(1, parseInt(autoRetryMinutes.value||"1")),
      schemaEndpoint: (schemaEndpoint.value||"").trim()
    };
    const ok = await rpc("SET_SETTINGS", { settings });
    log(ok?.ok? "✅ 设置已保存（已规范化 serverUrl）" : "❌ 设置保存失败");
  });
  clearSchemaBtn.addEventListener("click", async ()=>{
    const r = await rpc("CLEAR_SCHEMA_CACHE");
    log(r?.ok ? "✅ 已清空缓存 Schema" : "❌ 清空缓存 Schema 失败");
  });
  pingBtn.addEventListener("click", async ()=>{
    const r = await rpc("PING_SERVER");
    if(r?.ok) log("✅ 连接成功，状态码 "+r.status);
    else log("❌ 连接失败："+ (r?.error||""));
  });
  schemaBtn.addEventListener("click", async ()=>{
    const r = await rpc("FETCH_SCHEMA");
    if(r?.ok) log("✅ 分类接口可用："+ JSON.stringify(r));
    else log("❌ 分类接口不可用："+ (r?.error||""));
  });
  translateBtn.addEventListener("click", async ()=>{
    const r = await rpc("TRANSLATE", { text: "dreamy lighting" });
    if(r?.ok) log("✅ 翻译成功："+ (r.zh||JSON.stringify(r.raw)));
    else log("❌ 翻译失败："+ (r?.error||""));
  });
  saveTagBtn.addEventListener("click", async ()=>{
    const sample = { type:"head", subcategory:"基础", english:"sample english", chinese:"示例中文", pageUrl:"about:blank", pageTitle:"Test", screenshot:"" };
    const r = await rpc("SAVE_TAG", { payload: sample });
    if(r?.ok) log("✅ 保存成功："+ JSON.stringify(r.data||{}));
    else if(r?.queued) log("⚠️ 保存失败，已入队等待重试："+ (r?.error||""));
    else log("❌ 保存失败："+ (r?.error||""));
  });
})();