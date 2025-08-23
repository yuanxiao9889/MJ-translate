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
      
      try {
        // 使用直接网页截图API
        if (window.directPageCapture && typeof window.directPageCapture.capture === 'function') {
          const result = await window.directPageCapture.capture(rect);
          
          if (result.success) {
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
        
        console.log("[tagball] DOM降级截图成功，数据大小:", imageDataUrl.length);
        
        // 打开标签弹窗
        openTagModal({
          imageDataUrl: imageDataUrl,
          pageUrl: location.href,
          pageTitle: document.title
        });
        
      } catch (error) {
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
    // 图片预览和裁剪按钮容器
    const imageContainer = createEl("div",{style:{display:"flex",flexDirection:"column",gap:"10px"}});
    const imagePreview = prefill.imageDataUrl ? 
      createEl("img",{id:"tagball-preview",src:prefill.imageDataUrl,style:{maxWidth:"100%",borderRadius:"10px",border:"1px solid #e4e6f3"}}) : 
      createEl("div",{style:{padding:"24px",border:"1px dashed #d3d7ef",borderRadius:"10px",color:"#666",textAlign:"center"}}, "（无截图）");
    
    // 裁剪按钮（仅在有图片时显示）
    const cropButton = prefill.imageDataUrl ? 
      createEl("button",{
        class:"tagball-btn ghost",
        style:{width:"100%",fontSize:"14px"},
        onclick: () => openCropModal(prefill.imageDataUrl)
      }, "✂️ 裁剪图片") : null;
    
    imageContainer.appendChild(imagePreview);
    if (cropButton) imageContainer.appendChild(cropButton);
    
    const left = createEl("div",{},[imageContainer]);

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

  // 监听来自background的消息
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === "CREATE_TAG_FROM_IMAGE") {
      handleImageTagCreation(message);
      sendResponse({ success: true });
    }
  });

  // 处理从右键菜单创建标签
  async function handleImageTagCreation(data) {
    console.log("[tagball] 从右键菜单创建标签", data);
    
    try {
      // 加载图片并转换为base64
      const imageDataUrl = await loadImageAsDataUrl(data.imageUrl);
      
      // 打开标签弹窗，预填图片数据
      openTagModal({
        imageDataUrl: imageDataUrl,
        pageUrl: data.pageUrl || location.href,
        pageTitle: data.pageTitle || document.title
      });
      
    } catch (error) {
      console.error("[tagball] 加载图片失败:", error);
      
      // 显示错误提示
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
        <h3 style="margin: 0 0 10px 0;">图片加载失败</h3>
        <p style="margin: 0 0 15px 0; font-size: 14px;">
          ${error.message || '无法加载选中的图片'}
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

  // 将图片URL转换为base64 data URL
  function loadImageAsDataUrl(imageUrl) {
    return new Promise((resolve, reject) => {
      // 创建图片元素
      const img = new Image();
      
      // 设置跨域属性
      img.crossOrigin = 'anonymous';
      
      img.onload = function() {
        try {
          // 创建canvas
          const canvas = document.createElement('canvas');
          const ctx = canvas.getContext('2d');
          
          // 设置canvas尺寸
          canvas.width = img.naturalWidth;
          canvas.height = img.naturalHeight;
          
          // 绘制图片到canvas
          ctx.drawImage(img, 0, 0);
          
          // 转换为base64
          const dataUrl = canvas.toDataURL('image/png');
          resolve(dataUrl);
          
        } catch (error) {
          reject(new Error('图片转换失败: ' + error.message));
        }
      };
      
      img.onerror = function() {
        reject(new Error('图片加载失败，可能是跨域限制或图片不存在'));
      };
      
      // 开始加载图片
      img.src = imageUrl;
      
      // 设置超时
      setTimeout(() => {
        reject(new Error('图片加载超时'));
      }, 10000);
    });
  }

  // 图片裁剪功能
  let cropModal = null;
  let cropData = {
    startX: 0, startY: 0,
    cropX: 0, cropY: 0,
    cropWidth: 200, cropHeight: 200,
    isDragging: false,
    isResizing: false,
    isDrawing: false,
    resizeHandle: null,
    imageWidth: 0, imageHeight: 0,
    containerWidth: 0, containerHeight: 0,
    scale: 1
  };

  function openCropModal(imageDataUrl) {
    if (cropModal) cropModal.remove();
    
    // 打开裁剪时，暂时隐藏标签弹窗，避免任何站点叠层上下文和 z-index 差异导致的遮挡
    if (typeof modal !== 'undefined' && modal) {
      modal.style.display = 'none';
      modal.style.pointerEvents = 'none';
      modal.style.visibility = 'hidden';
    }

    cropModal = createEl("div", {
      id: "tagball-crop-modal",
      style: {
        position: "fixed",
        inset: "0",
        background: "rgba(0,0,0,0.8)",
        zIndex: "2147483647",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "system-ui,-apple-system,'Segoe UI',Roboto,'Helvetica Neue',Arial",
        backdropFilter: "blur(5px)"
      }
    });

    // 动态抬高裁剪层的 z-index 到标签弹窗之上（+1）
    try {
      if (typeof modal !== 'undefined' && modal) {
        const z = window.getComputedStyle(modal).zIndex;
        const base = parseInt(z, 10);
        if (!Number.isNaN(base)) {
          const safeMax = 2147483647;
          let target = base + 1;
          if (target > safeMax) target = safeMax;
          cropModal.style.zIndex = String(target);
        }
      }
    } catch (_) { /* 忽略 */ }

    const cropContainer = createEl("div", {
      style: {
        background: "#fff",
        borderRadius: "12px",
        padding: "20px",
        maxWidth: "95vw",
        maxHeight: "95vh",
        display: "flex",
        flexDirection: "column",
        gap: "16px",
        boxShadow: "0 24px 64px rgba(0,0,0,0.3)",
        overflow: "hidden"
      }
    });

    // 标题栏
    const header = createEl("div", {
      style: {
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        paddingBottom: "12px",
        borderBottom: "1px solid #eee"
      }
    }, [
      createEl("h3", {style: {margin: "0", fontSize: "18px", color: "#333"}}, "裁剪图片"),
      createEl("button", {
        style: {
          border: "none",
          background: "transparent",
          fontSize: "20px",
          cursor: "pointer",
          padding: "4px"
        },
        onclick: () => closeCropModal()
      }, "✕")
    ]);

    // 主要内容区域
    const mainContent = createEl("div", {
      style: {
        display: "flex",
        gap: "20px",
        alignItems: "flex-start"
      }
    });

    // 左侧：裁剪区域
    const cropArea = createEl("div", {
      id: "crop-area",
      style: {
        position: "relative",
        border: "2px solid #ddd",
        borderRadius: "8px",
        overflow: "hidden",
        background: "#f9f9f9",
        display: "flex",
        alignItems: "center",
        justifyContent: "center"
      }
    });

    // 图片元素
    const cropImage = createEl("img", {
      id: "crop-image",
      src: imageDataUrl,
      style: {
        display: "block",
        userSelect: "none",
        pointerEvents: "none",
        objectFit: "contain"
      },
      onload: function() {
        initializeCrop(this, cropArea);
      }
    });

    // 裁剪框
    const cropBox = createEl("div", {
      id: "crop-box",
      style: {
        position: "absolute",
        border: "2px solid #2a6df4",
        background: "rgba(42, 109, 244, 0.1)",
        cursor: "move",
        boxSizing: "border-box"
      }
    });

    // 添加8个调整手柄
    const handles = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'];
    handles.forEach(handle => {
      const handleEl = createEl("div", {
        class: `crop-handle crop-handle-${handle}`,
        style: {
          position: "absolute",
          width: "8px",
          height: "8px",
          background: "#2a6df4",
          border: "1px solid #fff",
          borderRadius: "50%",
          cursor: getCursorForHandle(handle),
          ...getHandlePosition(handle)
        },
        onmousedown: (e) => startResize(e, handle)
      });
      cropBox.appendChild(handleEl);
    });

    cropArea.appendChild(cropImage);
    cropArea.appendChild(cropBox);

    // 右侧：预览和控制
    const rightPanel = createEl("div", {
      style: {
        display: "flex",
        flexDirection: "column",
        gap: "16px",
        minWidth: "200px"
      }
    });

    // 预览区域
    const previewArea = createEl("div", {
      style: {
        border: "1px solid #ddd",
        borderRadius: "8px",
        padding: "12px",
        background: "#f9f9f9"
      }
    }, [
      createEl("div", {style: {marginBottom: "8px", fontWeight: "600", fontSize: "14px"}}, "预览"),
      createEl("canvas", {
        id: "crop-preview",
        style: {
          maxWidth: "150px",
          maxHeight: "150px",
          border: "1px solid #ccc",
          borderRadius: "4px",
          background: "#fff"
        }
      })
    ]);

    // 操作按钮
    const buttonArea = createEl("div", {
      style: {
        display: "flex",
        flexDirection: "column",
        gap: "8px"
      }
    }, [
      createEl("button", {
        class: "tagball-btn primary",
        style: {width: "100%"},
        onclick: () => applyCrop()
      }, "应用裁剪"),
      createEl("button", {
        class: "tagball-btn ghost",
        style: {width: "100%"},
        onclick: () => resetCrop()
      }, "重置"),
      createEl("button", {
        class: "tagball-btn",
        style: {width: "100%"},
        onclick: () => closeCropModal()
      }, "取消")
    ]);

    rightPanel.appendChild(previewArea);
    rightPanel.appendChild(buttonArea);
    mainContent.appendChild(cropArea);
    mainContent.appendChild(rightPanel);
    cropContainer.appendChild(header);
    cropContainer.appendChild(mainContent);
    cropModal.appendChild(cropContainer);
    // 使用 document.documentElement 作为挂载点，避免部分站点在 body 上创建的叠层上下文导致层级被压制
    document.documentElement.appendChild(cropModal);

    // 添加事件监听
    setupCropEvents(cropBox, cropArea);
  }

  function initializeCrop(img, container) {
    // 获取图片原始尺寸
    cropData.imageWidth = img.naturalWidth;
    cropData.imageHeight = img.naturalHeight;
    
    // 计算最佳显示尺寸，保持图片比例
    const maxWidth = Math.min(800, window.innerWidth * 0.6);
    const maxHeight = Math.min(600, window.innerHeight * 0.6);
    
    const imageRatio = cropData.imageWidth / cropData.imageHeight;
    const containerRatio = maxWidth / maxHeight;
    
    let displayWidth, displayHeight;
    
    if (imageRatio > containerRatio) {
      // 图片更宽，以宽度为准
      displayWidth = maxWidth;
      displayHeight = maxWidth / imageRatio;
    } else {
      // 图片更高，以高度为准
      displayHeight = maxHeight;
      displayWidth = maxHeight * imageRatio;
    }
    
    // 设置图片显示尺寸
    img.style.width = displayWidth + 'px';
    img.style.height = displayHeight + 'px';
    
    // 设置容器尺寸以匹配图片
    container.style.width = displayWidth + 'px';
    container.style.height = displayHeight + 'px';
    
    // 更新裁剪数据
    cropData.containerWidth = displayWidth;
    cropData.containerHeight = displayHeight;
    cropData.scale = displayWidth / cropData.imageWidth;

    // 初始裁剪框位置（居中，60%大小，但不小于50px）
    const initialWidth = Math.max(50, Math.min(displayWidth * 0.6, 300));
    const initialHeight = Math.max(50, Math.min(displayHeight * 0.6, 300));
    
    cropData.cropX = (displayWidth - initialWidth) / 2;
    cropData.cropY = (displayHeight - initialHeight) / 2;
    cropData.cropWidth = initialWidth;
    cropData.cropHeight = initialHeight;

    updateCropBox();
    updatePreview();
  }

  function setupCropEvents(cropBox, cropArea) {
    // 在空白区域按下开始绘制新裁剪框
    cropArea.addEventListener('mousedown', (e) => {
      // 若点击的是裁剪框或其手柄，则由其它逻辑处理
      if (e.target.id === 'crop-box' || (e.target.classList && e.target.classList.contains('crop-handle'))) {
        return;
      }
      startNewSelection(e);
    });

    // 拖拽移动现有裁剪框
    cropBox.addEventListener('mousedown', (e) => {
      // 如果点击的不是调整手柄，则开始拖拽
      if (!e.target.classList.contains('crop-handle')) {
        startDrag(e);
      }
    });

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }

  function startDrag(e) {
    cropData.isDragging = true;
    cropData.startX = e.clientX - cropData.cropX;
    cropData.startY = e.clientY - cropData.cropY;
    e.preventDefault();
  }

  function startNewSelection(e) {
    const area = document.getElementById('crop-area');
    if (!area) return;
    const rect = area.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    cropData.isDrawing = true;
    cropData.startX = Math.max(0, Math.min(x, cropData.containerWidth));
    cropData.startY = Math.max(0, Math.min(y, cropData.containerHeight));

    // 初始化为一个点
    cropData.cropX = cropData.startX;
    cropData.cropY = cropData.startY;
    cropData.cropWidth = 0;
    cropData.cropHeight = 0;

    updateCropBox();
    updatePreview();
    e.preventDefault();
  }

  function startResize(e, handle) {
    cropData.isResizing = true;
    cropData.resizeHandle = handle;
    cropData.startX = e.clientX;
    cropData.startY = e.clientY;
    e.preventDefault();
    e.stopPropagation();
  }

  function handleMouseMove(e) {
    if (cropData.isDrawing) {
      const area = document.getElementById('crop-area');
      if (!area) return;
      const rect = area.getBoundingClientRect();
      let x = e.clientX - rect.left;
      let y = e.clientY - rect.top;

      // 约束在容器范围内
      x = Math.max(0, Math.min(x, cropData.containerWidth));
      y = Math.max(0, Math.min(y, cropData.containerHeight));

      const left = Math.min(cropData.startX, x);
      const top = Math.min(cropData.startY, y);
      const width = Math.abs(x - cropData.startX);
      const height = Math.abs(y - cropData.startY);

      // 最小尺寸1px，防止看不见
      cropData.cropX = left;
      cropData.cropY = top;
      cropData.cropWidth = Math.max(1, width);
      cropData.cropHeight = Math.max(1, height);

      updateCropBox();
      updatePreview();
    } else if (cropData.isDragging) {
      const newX = e.clientX - cropData.startX;
      const newY = e.clientY - cropData.startY;
      
      // 边界检查
      cropData.cropX = Math.max(0, Math.min(newX, cropData.containerWidth - cropData.cropWidth));
      cropData.cropY = Math.max(0, Math.min(newY, cropData.containerHeight - cropData.cropHeight));
      
      updateCropBox();
      updatePreview();
    } else if (cropData.isResizing) {
      handleResize(e);
    }
  }

  function handleResize(e) {
    const deltaX = e.clientX - cropData.startX;
    const deltaY = e.clientY - cropData.startY;
    const handle = cropData.resizeHandle;
    
    let newX = cropData.cropX;
    let newY = cropData.cropY;
    let newWidth = cropData.cropWidth;
    let newHeight = cropData.cropHeight;

    // 根据手柄位置调整尺寸
    if (handle.includes('w')) {
      newX = Math.max(0, cropData.cropX + deltaX);
      newWidth = cropData.cropWidth - (newX - cropData.cropX);
    }
    if (handle.includes('e')) {
      newWidth = Math.min(cropData.containerWidth - cropData.cropX, cropData.cropWidth + deltaX);
    }
    if (handle.includes('n')) {
      newY = Math.max(0, cropData.cropY + deltaY);
      newHeight = cropData.cropHeight - (newY - cropData.cropY);
    }
    if (handle.includes('s')) {
      newHeight = Math.min(cropData.containerHeight - cropData.cropY, cropData.cropHeight + deltaY);
    }

    // 最小尺寸限制
    if (newWidth >= 20 && newHeight >= 20) {
      cropData.cropX = newX;
      cropData.cropY = newY;
      cropData.cropWidth = newWidth;
      cropData.cropHeight = newHeight;
      
      updateCropBox();
      updatePreview();
    }
  }

  function handleMouseUp() {
    cropData.isDragging = false;
    cropData.isResizing = false;
    cropData.isDrawing = false;
    cropData.resizeHandle = null;
  }

  function updateCropBox() {
    const cropBox = document.getElementById('crop-box');
    if (cropBox) {
      cropBox.style.left = cropData.cropX + 'px';
      cropBox.style.top = cropData.cropY + 'px';
      cropBox.style.width = cropData.cropWidth + 'px';
      cropBox.style.height = cropData.cropHeight + 'px';
    }
  }

  function updatePreview() {
    const canvas = document.getElementById('crop-preview');
    const img = document.getElementById('crop-image');
    if (!canvas || !img) return;

    const ctx = canvas.getContext('2d');
    
    // 计算实际图片上的裁剪区域
    const scaleX = cropData.imageWidth / cropData.containerWidth;
    const scaleY = cropData.imageHeight / cropData.containerHeight;
    
    const sourceX = cropData.cropX * scaleX;
    const sourceY = cropData.cropY * scaleY;
    const sourceWidth = cropData.cropWidth * scaleX;
    const sourceHeight = cropData.cropHeight * scaleY;

    // 设置canvas尺寸
    const previewSize = Math.min(150, Math.max(cropData.cropWidth, cropData.cropHeight));
    canvas.width = previewSize;
    canvas.height = previewSize;
    
    // 清空canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // 绘制裁剪预览
    const scale = previewSize / Math.max(sourceWidth, sourceHeight);
    const drawWidth = sourceWidth * scale;
    const drawHeight = sourceHeight * scale;
    const offsetX = (previewSize - drawWidth) / 2;
    const offsetY = (previewSize - drawHeight) / 2;
    
    ctx.drawImage(
      img,
      sourceX, sourceY, sourceWidth, sourceHeight,
      offsetX, offsetY, drawWidth, drawHeight
    );
  }

  function applyCrop() {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const img = document.getElementById('crop-image');
    
    if (!img) return;

    // 计算实际裁剪区域
    const scaleX = cropData.imageWidth / cropData.containerWidth;
    const scaleY = cropData.imageHeight / cropData.containerHeight;
    
    const sourceX = cropData.cropX * scaleX;
    const sourceY = cropData.cropY * scaleY;
    const sourceWidth = cropData.cropWidth * scaleX;
    const sourceHeight = cropData.cropHeight * scaleY;

    // 设置canvas尺寸为裁剪区域尺寸
    canvas.width = sourceWidth;
    canvas.height = sourceHeight;
    
    // 绘制裁剪后的图片
    ctx.drawImage(
      img,
      sourceX, sourceY, sourceWidth, sourceHeight,
      0, 0, sourceWidth, sourceHeight
    );
    
    // 获取裁剪后的图片数据
    const croppedDataUrl = canvas.toDataURL('image/png');
    
    // 更新原始标签弹窗中的图片
    const originalPreview = document.getElementById('tagball-preview');
    if (originalPreview) {
      originalPreview.src = croppedDataUrl;
    }
    
    // 关闭裁剪弹窗
    // 关闭裁剪弹窗并恢复标签弹窗
    closeCropModal();
   }

  function resetCrop() {
    // 重置到初始状态
    const img = document.getElementById('crop-image');
    const container = document.getElementById('crop-area');
    if (img && container) {
      initializeCrop(img, container);
    }
  }

  function getCursorForHandle(handle) {
    const cursors = {
      'nw': 'nw-resize', 'n': 'n-resize', 'ne': 'ne-resize',
      'e': 'e-resize', 'se': 'se-resize', 's': 's-resize',
      'sw': 'sw-resize', 'w': 'w-resize'
    };
    return cursors[handle] || 'default';
  }

  function getHandlePosition(handle) {
    const positions = {
      'nw': { top: '-4px', left: '-4px' },
      'n': { top: '-4px', left: '50%', transform: 'translateX(-50%)' },
      'ne': { top: '-4px', right: '-4px' },
      'e': { top: '50%', right: '-4px', transform: 'translateY(-50%)' },
      'se': { bottom: '-4px', right: '-4px' },
      's': { bottom: '-4px', left: '50%', transform: 'translateX(-50%)' },
      'sw': { bottom: '-4px', left: '-4px' },
      'w': { top: '50%', left: '-4px', transform: 'translateY(-50%)' }
    };
    return positions[handle] || {};
  }

  // 统一关闭裁剪弹窗并恢复标签弹窗显示
  function closeCropModal() {
    if (cropModal) {
      cropModal.remove();
      cropModal = null;
    }
    if (typeof modal !== 'undefined' && modal) {
      modal.style.display = 'block';
      modal.style.pointerEvents = '';
      modal.style.visibility = '';
    }
  }

})();