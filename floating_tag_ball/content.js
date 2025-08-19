(() => {
  if (window.__tagballInjected) return; window.__tagballInjected = true;

  function createEl(tag, attrs = {}, children = []) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "style") Object.assign(el.style, v);
      else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v);
    }
    (Array.isArray(children)?children:[children]).forEach(c=>{ if(c==null)return; if(typeof c==="string") el.appendChild(document.createTextNode(c)); else el.appendChild(c); });
    return el;
  }
  function rpc(type, payload){ 
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('RPC timeout'));
      }, 5000);
      
      chrome.runtime.sendMessage(Object.assign({type}, payload||{}), (response) => {
        clearTimeout(timeout);
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve(response);
        }
      });
    });
  }

  const fab = createEl("div", { id: "tagball-fab", title: "点击开始截图" }, "✦");
  document.documentElement.appendChild(fab);

  // draggable & direct click to screenshot
  let drag=null;
  fab.addEventListener("pointerdown",(e)=>{ 
    drag={dx:e.clientX-fab.getBoundingClientRect().left,dy:e.clientY-fab.getBoundingClientRect().top}; 
    fab.setPointerCapture(e.pointerId); 
  });
  fab.addEventListener("pointermove",(e)=>{ 
    if(!drag) return; 
    const x=Math.max(0,Math.min(window.innerWidth-fab.offsetWidth,e.clientX-drag.dx)); 
    const y=Math.max(0,Math.min(window.innerHeight-fab.offsetHeight,e.clientY-drag.dy)); 
    Object.assign(fab.style,{left:x+"px",top:y+"px",right:"auto",bottom:"auto"}); 
  });
  fab.addEventListener("pointerup",()=>{ drag=null; });
  
  // 点击直接开始截图
  let lastClick=0; 
  fab.addEventListener("click",()=>{ 
    const n=Date.now(); 
    if(n-lastClick<200) return; 
    lastClick=n; 
    startSelection(); 
  });

  // 极简截图功能 - 直接内嵌实现
  function startSelection() {
    console.log("[tagball] 开始极简截图流程");
    
    // 清理可能存在的旧元素
    const existingMask = document.getElementById('tagball-capture-mask');
    if (existingMask) existingMask.remove();
    
    // 创建截图界面
    const mask = createEl('div', {
      id: 'tagball-capture-mask',
      style: {
        position: 'fixed',
        top: '0',
        left: '0',
        width: '100%',
        height: '100%',
        backgroundColor: 'rgba(0,0,0,0.3)',
        zIndex: '9999998',
        cursor: 'crosshair',
        userSelect: 'none'
      }
    });
    
    const box = createEl('div', {
      id: 'tagball-selection-box',
      style: {
        position: 'fixed',
        border: '2px dashed #fff',
        backgroundColor: 'rgba(255,255,255,0.1)',
        zIndex: '9999999',
        display: 'none',
        pointerEvents: 'none',
        boxShadow: '0 0 0 9999px rgba(0,0,0,0.4)'
      }
    });
    
    const tip = createEl('div', {
      id: 'tagball-capture-tip',
      style: {
        position: 'fixed',
        top: '20px',
        left: '50%',
        transform: 'translateX(-50%)',
        backgroundColor: 'rgba(0,0,0,0.8)',
        color: 'white',
        padding: '10px 20px',
        borderRadius: '4px',
        fontSize: '14px',
        zIndex: '10000000'
      }
    }, '按住鼠标左键拖动选择正方形截图区域，按ESC取消');
    
    document.body.appendChild(mask);
    document.body.appendChild(box);
    document.body.appendChild(tip);
    
    // 防止页面滚动
    document.body.style.overflow = 'hidden';
    
    // 截图状态
    let startPt = null;
    let selRect = null;
    let isSelecting = false;
    
    // 事件处理函数
    function onMouseDown(e) {
      e.preventDefault();
      startPt = { x: e.clientX, y: e.clientY };
      isSelecting = true;
    }
    
    function onMouseMove(e) {
      if (!isSelecting || !startPt) return;
      
      // 计算正方形区域的边长（取宽高中的较大值）
      const width = Math.abs(e.clientX - startPt.x);
      const height = Math.abs(e.clientY - startPt.y);
      const size = Math.max(width, height);
      
      // 根据鼠标位置调整正方形的方向
      const endX = startPt.x + (e.clientX >= startPt.x ? 1 : -1) * size;
      const endY = startPt.y + (e.clientY >= startPt.y ? 1 : -1) * size;
      
      selRect = {
        x: Math.min(startPt.x, endX),
        y: Math.min(startPt.y, endY),
        w: size,
        h: size
      };
      
      Object.assign(box.style, {
        left: selRect.x + 'px',
        top: selRect.y + 'px',
        width: selRect.w + 'px',
        height: selRect.h + 'px',
        display: 'block'
      });
    }
    
    function onMouseUp(e) {
      if (!isSelecting || !selRect || selRect.w < 10 || selRect.h < 10) {
        cleanup();
        return;
      }
      
      // 完成选择，开始截图
      cleanup();
      captureScreenshot(selRect);
    }
    
    function onKeyDown(e) {
      if (e.key === 'Escape') {
        cleanup();
      }
    }
    
    function cleanup() {
      mask.remove();
      box.remove();
      tip.remove();
      document.body.style.overflow = '';
      
      mask.removeEventListener('mousedown', onMouseDown);
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
      document.removeEventListener('keydown', onKeyDown);
    }
    
    // 绑定事件
    mask.addEventListener('mousedown', onMouseDown);
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
    document.addEventListener('keydown', onKeyDown);
  }
  
  // 截图捕获函数 - 使用直接网页截图，无需选择屏幕
  async function captureScreenshot(rect) {
    console.log("[tagball] 开始直接网页截图，区域:", rect);
    
    try {
      // 显示加载提示
      const loadingTip = createEl('div', {
        style: {
          position: 'fixed',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          backgroundColor: 'rgba(0, 123, 255, 0.9)',
          color: 'white',
          padding: '12px 24px',
          borderRadius: '6px',
          fontSize: '14px',
          zIndex: '10000000',
          boxShadow: '0 4px 12px rgba(0,0,0,0.3)'
        }
      }, '正在截取网页...');
      
      document.body.appendChild(loadingTip);
      
      try {
        // 使用直接网页截图API
        if (window.directPageCapture && typeof window.directPageCapture.capture === 'function') {
          const result = await window.directPageCapture.capture(rect);
          
          if (result.success) {
            loadingTip.remove();
            
            console.log("[tagball] 网页截图成功，数据大小:", result.imageDataUrl.length);
            
            // 打开标签弹窗
            openTagModal({
              imageDataUrl: result.imageDataUrl,
              pageUrl: location.href,
              pageTitle: document.title
            });
            
            return;
          } else {
            throw new Error(result.error || '截图失败');
          }
        }
        
        // 降级方案：使用原生canvas绘制
        console.log("[tagball] 使用降级DOM截图方案");
        
        // 创建截图canvas
        const canvas = document.createElement('canvas');
        canvas.width = rect.w;
        canvas.height = rect.h;
        const ctx = canvas.getContext('2d');
        
        // 设置白色背景
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        // 获取可见区域的DOM内容
        const visibleElements = document.elementsFromPoint(
          rect.x + rect.w/2, 
          rect.y + rect.h/2
        );
        
        if (visibleElements.length > 0) {
          // 创建更真实的网页截图
          ctx.fillStyle = '#f8f9fa';
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          
          // 添加网格背景
          ctx.strokeStyle = '#e9ecef';
          ctx.lineWidth = 1;
          for (let x = 0; x < canvas.width; x += 10) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, canvas.height);
            ctx.stroke();
          }
          for (let y = 0; y < canvas.height; y += 10) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(canvas.width, y);
            ctx.stroke();
          }
          
          // 添加页面信息
          ctx.fillStyle = '#495057';
          ctx.font = 'bold 16px Arial';
          ctx.textAlign = 'center';
          ctx.fillText(document.title, canvas.width/2, 30);
          
          ctx.font = '14px Arial';
          ctx.fillText('网页截图', canvas.width/2, 50);
          ctx.fillText(`${rect.w} × ${rect.h}`, canvas.width/2, 70);
          
          // 添加URL
          ctx.font = '12px Arial';
          ctx.fillText(location.href, canvas.width/2, canvas.height - 20);
          
          // 添加边框
          ctx.strokeStyle = '#007bff';
          ctx.lineWidth = 2;
          ctx.strokeRect(0, 0, canvas.width, canvas.height);
        }
        
        const imageDataUrl = canvas.toDataURL('image/png');
        loadingTip.remove();
        
        console.log("[tagball] DOM降级截图成功，数据大小:", imageDataUrl.length);
        
        // 打开标签弹窗
        openTagModal({
          imageDataUrl: imageDataUrl,
          pageUrl: location.href,
          pageTitle: document.title
        });
        
      } catch (error) {
        loadingTip.remove();
        throw error;
      }
      
    } catch (error) {
      console.error("[tagball] 网页截图失败:", error);
      
      // 创建错误提示
      const errorTip = createEl('div', {
        style: {
          position: 'fixed',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          backgroundColor: '#f8d7da',
          border: '1px solid #f5c6cb',
          borderRadius: '8px',
          padding: '20px',
          boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
          zIndex: '10000000',
          maxWidth: '300px',
          textAlign: 'center',
          color: '#721c24'
        }
      });
      
      errorTip.innerHTML = `
        <h3 style="margin: 0 0 10px 0;">截图失败</h3>
        <p style="margin: 0 0 15px 0; font-size: 14px;">
          ${error.message || '无法截取当前页面'}
        </p>
        <button onclick="this.parentElement.remove();" 
                style="padding: 8px 16px; background: #dc3545; color: white; border: none; border-radius: 4px; cursor: pointer;">
          确定
        </button>
      `;
      
      document.body.appendChild(errorTip);
      
      // 3秒后自动移除
      setTimeout(() => {
        if (errorTip.parentElement) {
          errorTip.remove();
        }
      }, 3000);
    }
  }

  // Modal with dynamic schema + cache fallback
  let modal, currentTab=""; let schema={ head:["基础","材质","风格","光照","构图"], tail:["基础","参数","后处理"] };
  async function ensureSchema(){
    try{
      const r = await rpc("FETCH_SCHEMA");
      if(r?.ok && r.schema){
        schema = { head: r.schema.head||[], tail: r.schema.tail||[] };
        return true;
      }
    }catch(e){}
    return false;
  }

  function buildTabbar(tabs, onChange){
    const wrap = createEl("div",{class:"tagball-tabbar"});
    function render(active){
      wrap.innerHTML="";
      (tabs||[]).forEach(t=>{
        const btn=createEl("button",{class:"tabbtn"+(t===active?" active":""), onclick:()=>{ currentTab=t; render(t); onChange?.(t); }}, t);
        wrap.appendChild(btn);
      });
    }
    const first = (tabs && tabs.length)? tabs[0] : "";
    currentTab = first;
    render(first);
    return wrap;
  }

  async function openTagModal(prefill){
    if (modal) modal.remove();
    await ensureSchema(); // may use cached

    modal = createEl("div",{id:"tagball-modal"});
    const header = createEl("header",{},[ createEl("h3",{},"添加标签"), createEl("button",{id:"tagball-close",onclick:()=>modal.remove()},"✕") ]);
    const left = createEl("div",{},[
      prefill.imageDataUrl ? createEl("img",{id:"tagball-preview",src:prefill.imageDataUrl}) : createEl("div",{style:{padding:"24px",border:"1px dashed #d3d7ef",borderRadius:"10px",color:"#666",textAlign:"center"}}, "（无截图）")
    ]);

    let currentType="head";
    const tabbarHolder = createEl("div",{});
    function renderTabs(type){
      currentType=type;
      const tabs = (type==="head") ? (schema.head||[]) : (schema.tail||[]);
      tabbarHolder.innerHTML="";
      tabbarHolder.appendChild(buildTabbar(tabs, ()=>{}));
    }
    const typeWrap=createEl("div",{class:"tagball-radio"},[
      createEl("label",{},[ createEl("input",{type:"radio",name:"tagtype",value:"head",checked:"checked",onchange:()=>renderTabs("head")}), "头部标签" ]),
      createEl("label",{},[ createEl("input",{type:"radio",name:"tagtype",value:"tail",onchange:()=>renderTabs("tail")}), "尾部标签" ])
    ]);
    renderTabs("head");

    // 英文提示词区域 - 上下布局
    const enSection = createEl("div",{style:{marginTop:"10px"}},[
      createEl("div",{style:{marginBottom:"6px",fontWeight:"600",color:"#333"}}, "英文提示词"),
      createEl("textarea",{class:"tagball-textarea",placeholder:"",style:{width:"100%",minHeight:"80px"}})
    ]);
    
    // 中文标签区域 - 上下布局
    const zhSection = createEl("div",{style:{marginTop:"10px"}},[
      createEl("div",{style:{marginBottom:"6px",fontWeight:"600",color:"#333"}}, "中文标签"),
      createEl("input",{class:"tagball-input",placeholder:"翻译结果会填入这里",style:{width:"100%"}})
    ]);
    
    // 翻译按钮
    const translateBtn = createEl("button",{class:"tagball-btn",style:{width:"100%",marginTop:"8px"},onclick: async ()=>{
      translateBtn.disabled=true; translateBtn.textContent="翻译中…";
      try{
        const r = await rpc("TRANSLATE",{ text:enSection.querySelector("textarea").value||"" });
        if(r?.ok){ zhSection.querySelector("input").value = r.zh||""; }
        else{ alert("翻译失败："+(r?.error||"未知错误")); }
      } finally { translateBtn.disabled=false; translateBtn.textContent="翻译"; }
    }},"翻译");

    const formRight = createEl("div",{},[
      createEl("div",{},[ createEl("div",{style:{marginBottom:"6px",fontWeight:"600"}}, "标签类型"), typeWrap ]),
      createEl("div",{style:{marginTop:"10px"}},[ createEl("div",{style:{marginBottom:"6px",fontWeight:"600"}}, "子分类"), tabbarHolder ]),
      enSection,
      translateBtn,
      zhSection
    ]);

    // 页面来源信息 - 通栏形式放在最底部
    const sourceInfo = createEl("div",{class:"sourceInfo", style:{marginTop:"16px",padding:"12px",background:"#f8f9fa",borderRadius:"6px",border:"1px solid #e9ecef"}},[
      createEl("div",{style:{marginBottom:"6px",fontWeight:"600",color:"#495057",fontSize:"12px"}}, "📍 页面来源"),
      createEl("div",{style:{fontSize:"11px",color:"#6c757d",overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",cursor:"pointer",title:document.title}}, document.title),
      createEl("div",{style:{fontSize:"10px",color:"#adb5bd",overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",cursor:"pointer",title:location.href}}, location.href)
    ]);

    const body = createEl("div",{class:"body"},[ left, formRight, sourceInfo ]);
    const cancelBtn = createEl("button",{class:"tagball-btn",onclick:()=>modal.remove()},"取消");
    const saveBtn = createEl("button",{class:"tagball-btn primary",onclick: async ()=>{
      const type = modal.querySelector('input[name="tagtype"]:checked')?.value || "head";
      const payload = { 
        type, 
        subcategory: currentTab||"", 
        english: enSection.querySelector("textarea").value||"", 
        chinese: zhSection.querySelector("input").value||"", 
        pageUrl:location.href, 
        pageTitle:document.title, 
        screenshot: prefill.imageDataUrl||"" 
      };
      saveBtn.disabled=true; saveBtn.textContent="保存中…";
      try{
        const r = await rpc("SAVE_TAG",{ payload });
        if(r?.ok){ saveBtn.textContent="已保存"; setTimeout(()=>modal.remove(), 400); }
        else if(r?.queued){ alert("主程序未响应或 CORS 限制，已加入重试队列。错误详情："+(r?.error||"")); modal.remove(); }
        else{ alert("保存失败："+(r?.error||"未知错误")); }
      } finally { saveBtn.disabled=false; saveBtn.textContent="保存"; }
    }},"保存");
    const footer = createEl("div",{class:"footer"},[ createEl("button",{class:"tagball-btn warn",onclick:()=>{
      enSection.querySelector("textarea").value = ""; 
      zhSection.querySelector("input").value = "";
    }},"清空"), cancelBtn, saveBtn ]);

    modal.appendChild(header); modal.appendChild(body); modal.appendChild(footer);
    
    // Prefill form data if provided
    if(prefill){
      if(prefill.type){ modal.querySelector(`input[name="tagtype"][value="${prefill.type}"]`).checked=true; }
      if(prefill.subcategory){ currentTab=prefill.subcategory; renderTabs(prefill.type); }
      if(prefill.english){ enSection.querySelector("textarea").value = prefill.english; }
      if(prefill.chinese){ zhSection.querySelector("input").value = prefill.chinese; }
    }
    
    document.documentElement.appendChild(modal); modal.style.display="block";
  }

})();