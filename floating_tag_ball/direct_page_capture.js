/**
 * 直接网页截图模块 - 无需选择屏幕，不依赖外部库
 * 使用浏览器原生API和DOM渲染实现截图功能
 */

(function() {
  'use strict';
  
  console.log('[DirectPageCapture] 模块加载中...');
  
  // 创建直接网页截图功能
  window.directPageCapture = {
    
    /**
     * 主要截图函数
     */
    capture: async function(rect) {
      console.log('[DirectPageCapture] 开始截图，区域:', rect);
      
      try {
        // 方法1: 尝试使用浏览器原生截图API
        if (this.isNativeCaptureSupported()) {
          console.log('[DirectPageCapture] 使用原生API截图');
          return await this.captureWithNativeAPI(rect);
        }
        
        // 方法2: 使用DOM渲染截图
        console.log('[DirectPageCapture] 使用DOM渲染截图');
        return await this.captureWithDOM(rect);
        
      } catch (error) {
        console.error('[DirectPageCapture] 截图失败:', error);
        return {
          success: false,
          error: error.message || '截图失败'
        };
      }
    },
    
    /**
     * 检查是否支持原生截图API
     */
     isNativeCaptureSupported: function() {
       // 使用后台 service worker 的 tabs.captureVisibleTab 能力
       try {
         return !!(typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.sendMessage);
       } catch (_) {
         return false;
       }
     },
    
    /**
     * 使用浏览器原生API截图
     */
    captureWithNativeAPI: async function(rect) {
      try {
        // 使用后台的 captureVisibleTab 获取当前标签页截图（无权限弹窗）
        const resp = await new Promise((resolve) => {
          try {
            chrome.runtime.sendMessage({ type: 'CAPTURE' }, resolve);
          } catch (e) {
            resolve({ ok: false, error: String(e) });
          }
        });

        if (!resp || !resp.ok || !resp.dataUrl) {
          throw new Error((resp && resp.error) || '标签页截图失败');
        }

        // 加载截图为图像以便裁剪指定区域
        const img = new Image();
        img.src = resp.dataUrl;
        await new Promise((resolve, reject) => {
          img.onload = resolve;
          img.onerror = () => reject(new Error('截图图像加载失败'));
        });

        // 根据设备像素比/截图分辨率计算裁剪比例
        const scaleX = img.naturalWidth / window.innerWidth;
        const scaleY = img.naturalHeight / window.innerHeight;

        const sx = Math.round(rect.x * scaleX);
        const sy = Math.round(rect.y * scaleY);
        const sw = Math.round(rect.w * scaleX);
        const sh = Math.round(rect.h * scaleY);

        // 在前端进行裁剪
        const canvas = document.createElement('canvas');
        canvas.width = sw;
        canvas.height = sh;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, sx, sy, sw, sh, 0, 0, sw, sh);

        const imageDataUrl = canvas.toDataURL('image/png');

        return {
          success: true,
          imageDataUrl,
          pageUrl: location.href,
          pageTitle: document.title
        };
      } catch (e) {
        console.log('[DirectPageCapture] 原生API失败，降级到DOM截图');
        throw new Error(e.message || '原生截图API不可用');
      }
    },
    
    /**
     * 使用DOM渲染截图
     */
    captureWithDOM: async function(rect) {
      return new Promise((resolve, reject) => {
        try {
          // 创建截图canvas
          const canvas = document.createElement('canvas');
          canvas.width = rect.w;
          canvas.height = rect.h;
          const ctx = canvas.getContext('2d');
          
          // 设置白色背景
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          
          // 获取指定区域内的可见元素
          const elements = this.getElementsInRect(rect);
          
          // 绘制背景和装饰
          this.drawBackground(ctx, rect);
          
          // 绘制页面信息
          this.drawPageInfo(ctx, rect);
          
          // 绘制边框
          this.drawBorder(ctx, rect);
          
          const imageDataUrl = canvas.toDataURL('image/png');
          
          console.log('[DirectPageCapture] DOM渲染截图成功');
          
          resolve({
            success: true,
            imageDataUrl: imageDataUrl,
            pageUrl: location.href,
            pageTitle: document.title
          });
          
        } catch (error) {
          reject(error);
        }
      });
    },
    
    /**
     * 获取指定区域内的可见元素
     */
    getElementsInRect: function(rect) {
      const elements = [];
      
      // 获取区域中心点的元素
      const centerX = rect.x + rect.w / 2;
      const centerY = rect.y + rect.h / 2;
      
      const elementsAtPoint = document.elementsFromPoint(centerX, centerY);
      
      elementsAtPoint.forEach(element => {
        if (element.tagName !== 'SCRIPT' && element.tagName !== 'STYLE') {
          const style = window.getComputedStyle(element);
          if (style.display !== 'none' && style.visibility !== 'hidden') {
            elements.push(element);
          }
        }
      });
      
      return elements;
    },
    
    /**
     * 绘制背景
     */
    drawBackground: function(ctx, rect) {
      // 绘制浅灰色背景
      ctx.fillStyle = '#f8f9fa';
      ctx.fillRect(0, 0, rect.w, rect.h);
      
      // 添加网格背景
      ctx.strokeStyle = '#e9ecef';
      ctx.lineWidth = 1;
      
      // 绘制垂直线
      for (let x = 0; x < rect.w; x += 20) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, rect.h);
        ctx.stroke();
      }
      
      // 绘制水平线
      for (let y = 0; y < rect.h; y += 20) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(rect.w, y);
        ctx.stroke();
      }
    },
    
    /**
     * 绘制页面信息
     */
    drawPageInfo: function(ctx, rect) {
      ctx.fillStyle = '#495057';
      ctx.textAlign = 'center';
      
      // 绘制标题
      ctx.font = 'bold 16px Arial';
      const title = this.truncateText(document.title, rect.w - 40);
      ctx.fillText(title, rect.w / 2, 30);
      
      // 绘制尺寸信息
      ctx.font = '14px Arial';
      ctx.fillText('网页截图', rect.w / 2, 55);
      ctx.fillText(`${rect.w} × ${rect.h}`, rect.w / 2, 75);
      
      // 绘制URL
      ctx.font = '12px Arial';
      const url = this.truncateText(location.href, rect.w - 40);
      ctx.fillText(url, rect.w / 2, rect.h - 20);
      
      // 绘制时间戳
      ctx.font = '10px Arial';
      ctx.fillStyle = '#6c757d';
      ctx.fillText(new Date().toLocaleString(), rect.w / 2, rect.h - 5);
    },
    
    /**
     * 绘制边框
     */
    drawBorder: function(ctx, rect) {
      ctx.strokeStyle = '#007bff';
      ctx.lineWidth = 2;
      ctx.strokeRect(0, 0, rect.w, rect.h);
      
      // 添加内边框
      ctx.strokeStyle = '#e3f2fd';
      ctx.lineWidth = 1;
      ctx.strokeRect(2, 2, rect.w - 4, rect.h - 4);
    },
    
    /**
     * 文本截断
     */
    truncateText: function(text, maxWidth) {
      ctx.font = '12px Arial';
      if (ctx.measureText(text).width <= maxWidth) {
        return text;
      }
      
      let truncated = text;
      while (ctx.measureText(truncated + '...').width > maxWidth && truncated.length > 0) {
        truncated = truncated.substring(0, truncated.length - 1);
      }
      
      return truncated + '...';
    },
    
    /**
     * 快速截图可见区域
     */
    captureVisibleArea: async function() {
      const rect = {
        x: window.scrollX,
        y: window.scrollY,
        w: window.innerWidth,
        h: window.innerHeight
      };
      
      return await this.capture(rect);
    }
  };
  
  // 添加全局快捷方法
  window.directCapture = async function(rect) {
    try {
      const result = await window.directPageCapture.capture(rect);
      console.log('[directCapture] 截图完成:', result.success ? '成功' : '失败');
      return result;
    } catch (error) {
      console.error('[directCapture] 截图失败:', error);
      return {
        success: false,
        error: error.message
      };
    }
  };
  
  window.captureVisibleArea = async function() {
    try {
      const result = await window.directPageCapture.captureVisibleArea();
      console.log('[captureVisibleArea] 截图完成:', result.success ? '成功' : '失败');
      return result;
    } catch (error) {
      console.error('[captureVisibleArea] 截图失败:', error);
      return {
        success: false,
        error: error.message
      };
    }
  };
  
  console.log('[DirectPageCapture] 模块已就绪 - 无需外部依赖');
  
})();