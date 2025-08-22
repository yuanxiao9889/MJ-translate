import http.server
import socketserver
import json
import threading
import os
import urllib.parse
import base64
import time
from http import HTTPStatus

# 定义暂存文件路径
PENDING_TAGS_FILE = 'pending_tags.json'
PENDING_IMAGES_FILE = 'pending_images.json'

class TagSyncHandler(http.server.BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        """处理CORS预检请求"""
        self.send_response(HTTPStatus.OK)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """处理GET请求"""
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        
        # 处理schema相关的端点
        if path in ['/tag/schema', '/schema', '/tags/schema', '/sync/schema']:
            result = self.handle_get_schema()
            self.send_json_response(result)
        elif path == '/api/pull':
            result = self.handle_api_pull()
            self.send_json_response(result)
        else:
            self.send_error(HTTPStatus.NOT_FOUND, 'Path not found')
    
    def do_POST(self):
        """处理POST请求"""
        # 解析请求路径
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        
        # 获取请求内容长度
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            # 解析JSON数据
            data = json.loads(post_data.decode('utf-8'))
            
            # 根据路径处理不同类型的请求
            if path == '/sync/tags' or path == '/tag/add':
                result = self.handle_tag_sync(data)
            elif path == '/sync/images':
                result = self.handle_image_sync(data)
            elif path == '/api/push':
                result = self.handle_api_push(data)
            elif path == '/translate':
                result = self.handle_translate(data)
            else:
                self.send_error(HTTPStatus.NOT_FOUND, 'Path not found')
                return
            
            # 发送成功响应
            self.send_json_response(result)
            
        except json.JSONDecodeError:
            self.send_error(HTTPStatus.BAD_REQUEST, 'Invalid JSON')
        except Exception as e:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(e))
    
    def send_json_response(self, data):
        """发送JSON响应"""
        self.send_response(HTTPStatus.OK)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        response_data = json.dumps(data).encode('utf-8')
        self.wfile.write(response_data)
    
    def handle_get_schema(self):
        """处理获取标签schema的请求"""
        try:
            tags_file = 'tags.json'
            
            if os.path.exists(tags_file):
                with open(tags_file, 'r', encoding='utf-8') as f:
                    tags_data = json.load(f)
                
                # 提取head和tail的分类（tab）名称
                head_tabs = list(tags_data.get('head', {}).keys())
                tail_tabs = list(tags_data.get('tail', {}).keys())
                
                return {
                    'ok': True,
                    'head': head_tabs,
                    'tail': tail_tabs,
                    'headTabs': head_tabs,  # 兼容性字段
                    'tailTabs': tail_tabs   # 兼容性字段
                }
            else:
                # 如果tags.json不存在，返回默认的分类结构
                return {
                    'ok': True,
                    'head': ['基础', '材质', '风格', '光照', '构图'],
                    'tail': ['基础', '参数', '后处理'],
                    'headTabs': ['基础', '材质', '风格', '光照', '构图'],
                    'tailTabs': ['基础', '参数', '后处理']
                }
        except Exception as e:
            return {
                'ok': False,
                'error': f'Failed to load schema: {str(e)}'
            }
    
    def handle_tag_sync(self, data):
        """处理标签同步请求"""
        # 检查主程序的tags.json是否存在
        tags_file = 'tags.json'
        
        # 主程序运行中，直接更新标签数据
        if os.path.exists(tags_file):
            with open(tags_file, 'r', encoding='utf-8') as f:
                tags_data = json.load(f)
            
            # 更新标签数据
            if 'head' in data:
                tags_data['head'] = data['head']
            if 'tail' in data:
                tags_data['tail'] = data['tail']
            
            # 保存更新后的标签数据
            with open(tags_file, 'w', encoding='utf-8') as f:
                json.dump(tags_data, f, ensure_ascii=False, indent=2)
            
            # 尝试触发主程序UI刷新
            try:
                import sys
                sys.path.append('.')
                
                # 尝试通过bridge.py触发UI刷新
                if hasattr(sys.modules.get('__main__'), 'refresh_tags_ui'):
                    sys.modules['__main__'].refresh_tags_ui(tags_file)
                    print(f"[Tag Sync] 已触发主程序UI刷新")
                else:
                    print(f"[Tag Sync] 主程序未运行UI刷新方法")
            except Exception as e:
                print(f"[Tag Sync] 触发UI刷新失败: {e}")
            
            return {'status': 'success', 'message': 'Tags synchronized successfully'}
        else:
            # 主程序未运行，将数据暂存到pending_tags.json
            if os.path.exists(PENDING_TAGS_FILE):
                with open(PENDING_TAGS_FILE, 'r', encoding='utf-8') as f:
                    pending_data = json.load(f)
            else:
                pending_data = {'head': {}, 'tail': {}}
            
            # 合并新数据
            if 'head' in data:
                pending_data['head'].update(data['head'])
            if 'tail' in data:
                pending_data['tail'].update(data['tail'])
            
            # 保存到暂存文件
            with open(PENDING_TAGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(pending_data, f, ensure_ascii=False, indent=2)
            
            return {'status': 'success', 'message': 'Tags saved to pending file'}
    
    def handle_image_sync(self, data):
        """处理图片同步请求"""
        try:
            # 添加日志记录
            print(f"收到图片同步请求: {data['fileName']}")
            print(f"图片数据长度: {len(data['imageData'])}")
            
            # 无论主程序是否运行，都直接保存图片到images目录
            images_dir = 'images'
            if not os.path.exists(images_dir):
                os.makedirs(images_dir)
            
            # 获取base64数据，处理dataURL格式
            image_data = data['imageData']
            if image_data.startswith('data:image/'):
                # 移除dataURL前缀，只保留base64部分
                base64_data = image_data.split(',')[1]
                print(f"检测到dataURL格式，移除前缀后数据长度: {len(base64_data)}")
            else:
                # 如果不是dataURL格式，直接使用原始数据
                base64_data = image_data
                print(f"使用原始base64数据，长度: {len(base64_data)}")
            
            # 使用标签名称作为文件名前缀，确保命名一致性
            tag_name = data.get('tagName', 'tag')
            timestamp = str(int(time.time()))
            filename = f"{tag_name}_{timestamp}.png"
            
            # 解码base64图片数据并保存
            file_path = os.path.join(images_dir, filename)
            print(f"保存图片到: {file_path}")
            
            with open(file_path, 'wb') as f:
                decoded_data = base64.b64decode(base64_data)
                f.write(decoded_data)
                print(f"图片保存成功，文件大小: {len(decoded_data)} 字节")
            
            # 返回与主程序本地创建时完全一致的相对路径
            print(f"图片保存成功，将返回相对路径: {file_path}")
            return {
                'status': 'success', 
                'message': 'Image saved successfully',
                'path': file_path,
                'filePath': file_path,
                'filename': filename
            }
        except Exception as e:
            error_msg = f'Failed to save image: {str(e)}'
            print(f"图片保存失败: {error_msg}")
            return {'status': 'error', 'message': error_msg}
    
    def handle_api_pull(self):
        """处理/api/pull端点的请求，用于bridge.py轮询数据"""
        try:
            # 检查是否有待处理的标签数据
            if os.path.exists(PENDING_TAGS_FILE):
                with open(PENDING_TAGS_FILE, 'r', encoding='utf-8') as f:
                    pending_data = json.load(f)
                
                # 如果有待处理数据，返回给bridge.py
                if pending_data and (pending_data.get('head') or pending_data.get('tail')):
                    print(f"[API Pull] 返回待处理标签数据")
                    return {
                        'items': [{
                            'type': 'tags',
                            'data': pending_data,
                            'timestamp': int(time.time())
                        }]
                    }
            
            # 检查是否有待处理的图片数据
            if os.path.exists(PENDING_IMAGES_FILE):
                with open(PENDING_IMAGES_FILE, 'r', encoding='utf-8') as f:
                    pending_images = json.load(f)
                
                # 如果有待处理图片，返回给bridge.py
                if pending_images:
                    print(f"[API Pull] 返回待处理图片数据")
                    return {
                        'items': [{
                            'type': 'images',
                            'data': pending_images,
                            'timestamp': int(time.time())
                        }]
                    }
            
            # 没有待处理数据
            return {'items': []}
            
        except Exception as e:
            error_msg = f"API pull failed: {str(e)}"
            print(f"[API Pull] 错误: {error_msg}")
            return {'items': [], 'error': str(e)}
    
    def handle_api_push(self, data):
        """处理/api/push端点的请求，用于接收浏览器扩展的数据"""
        try:
            print(f"[API Push] 收到数据: {data}")
            
            # 检查是否是标签数据（支持多种字段格式）
            if ('tagType' in data and 'zhTag' in data) or ('type' in data and 'chinese' in data):
                return self._handle_tag_push(data)
            
            # 检查是否是图片数据（包含imageDataUrl字段）
            if 'imageDataUrl' in data:
                return self._handle_image_push(data)
            
            # 其他类型的数据处理
            return {'status': 'success', 'message': 'Data received'}
        except Exception as e:
            error_msg = f"API push failed: {str(e)}"
            print(f"[API Push] 错误: {error_msg}")
            return {'status': 'error', 'message': str(e)}
    
    def _handle_tag_push(self, data):
        """处理标签数据的推送"""
        try:
            tags_file = 'tags.json'
            
            # 检查主程序是否运行（通过检查tags.json是否存在）
            if os.path.exists(tags_file):
                print(f"[API Push] 主程序运行中，直接更新tags.json")
                
                # 读取现有标签数据
                with open(tags_file, 'r', encoding='utf-8') as f:
                    tags_data = json.load(f)
                
                # 准备新标签数据（支持多种字段格式）
                tag_type = data.get('tagType') or data.get('type', 'head')
                sub_category = data.get('subCategory') or data.get('subcategory', '基础')
                zh_tag = data.get('zhTag') or data.get('chinese', '')
                en_tag = data.get('enTag') or data.get('english', '')
                
                # 确保分类结构存在
                if tag_type not in tags_data:
                    tags_data[tag_type] = {}
                if sub_category not in tags_data[tag_type]:
                    tags_data[tag_type][sub_category] = {}
                
                # 优先处理截图，以生成正确的图片路径
                saved_image_path = data.get('image', '') # 保留已有的图片路径（如果有）
                if data.get('screenshot') and data['screenshot'].startswith('data:image/'):
                    try:
                        import base64
                        
                        # 使用中文标签名生成与主程序一致的文件名
                        label_for_filename = zh_tag or f"浏览器截图_{int(time.time())}"
                        filename = f"{label_for_filename}_{int(time.time())}.png"
                        
                        images_dir = 'images'
                        if not os.path.exists(images_dir):
                            os.makedirs(images_dir)
                        
                        file_path = os.path.join(images_dir, filename)
                        
                        # 解码并保存图片
                        base64_data = data['screenshot'].split(',')[1]
                        with open(file_path, 'wb') as f:
                            f.write(base64.b64decode(base64_data))
                        
                        saved_image_path = file_path # 使用新生成的正确路径
                        print(f"[API Push] 截图已保存，名称为: {filename}")
                    except Exception as e:
                        print(f"[API Push] 保存截图失败: {e}")

                # 添加新标签（使用辞書形式，キーは中国語タグ名）
                new_tag = {
                    'en': en_tag or zh_tag,
                    'image': saved_image_path, # 使用新生成的图片路径
                    'usage_count': 0,
                    'url': data.get('pageUrl') or data.get('pageUrl', ''),
                    'title': data.get('pageTitle') or data.get('pageTitle', ''),
                    'timestamp': data.get('_ts') or data.get('_ts', int(time.time()))
                }
                
                # 检查是否已存在相同标签
                if zh_tag not in tags_data[tag_type][sub_category]:
                    tags_data[tag_type][sub_category][zh_tag] = new_tag
                    print(f"[API Push] 添加新标签: {zh_tag} -> {en_tag}")
                else:
                    print(f"[API Push] 标签已存在，跳过: {zh_tag}")
                
                # 保存更新后的标签数据
                with open(tags_file, 'w', encoding='utf-8') as f:
                    json.dump(tags_data, f, ensure_ascii=False, indent=2)
                
                # 尝试触发主程序UI刷新
                try:
                    import sys
                    sys.path.append('.')
                    
                    # 尝试通过bridge.py触发UI刷新
                    from services.bridge import poll_from_browser
                    if hasattr(sys.modules.get('__main__'), 'refresh_tags_ui'):
                        sys.modules['__main__'].refresh_tags_ui(tags_file)
                        print(f"[API Push] 已触发主程序UI刷新")
                    else:
                        print(f"[API Push] 主程序未运行UI刷新方法")
                except Exception as e:
                    print(f"[API Push] 触发UI刷新失败: {e}")
                
                return {
                    'status': 'success', 
                    'message': f'Tag saved to {tag_type}.{sub_category}',
                    'tagType': tag_type,
                    'subCategory': sub_category
                }
            else:
                print(f"[API Push] 主程序未运行，保存到pending_tags.json")
                
                # 主程序未运行，保存到pending文件
                if os.path.exists(PENDING_TAGS_FILE):
                    with open(PENDING_TAGS_FILE, 'r', encoding='utf-8') as f:
                        pending_data = json.load(f)
                else:
                    pending_data = {'head': {}, 'tail': {}}
                
                # 准备新标签数据（支持多种字段格式）
                tag_type = data.get('tagType') or data.get('type', 'head')
                sub_category = data.get('subCategory') or data.get('subcategory', '基础')
                zh_tag = data.get('zhTag') or data.get('chinese', '')
                en_tag = data.get('enTag') or data.get('english', '')
                
                # 确保分类结构存在
                if tag_type not in pending_data:
                    pending_data[tag_type] = {}
                if sub_category not in pending_data[tag_type]:
                    pending_data[tag_type][sub_category] = {}
                
                # 添加新标签（使用辞書形式，キーは中国語タグ名）
                new_tag = {
                    'en': en_tag or zh_tag,
                    'image': data.get('image') or '',
                    'usage_count': 0,
                    'url': data.get('pageUrl') or data.get('pageUrl', ''),
                    'title': data.get('pageTitle') or data.get('pageTitle', ''),
                    'timestamp': data.get('_ts') or data.get('_ts', int(time.time()))
                }
                
                # 检查是否已存在相同标签
                if zh_tag not in pending_data[tag_type][sub_category]:
                    pending_data[tag_type][sub_category][zh_tag] = new_tag
                    print(f"[API Push] 添加新标签到pending: {zh_tag} -> {en_tag}")
                else:
                    print(f"[API Push] pending标签已存在，跳过: {zh_tag}")
                
                # 保存到pending文件
                with open(PENDING_TAGS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(pending_data, f, ensure_ascii=False, indent=2)
                
                return {
                    'status': 'success', 
                    'message': f'Tag saved to pending {tag_type}.{sub_category}',
                    'tagType': tag_type,
                    'subCategory': sub_category
                }
                
        except Exception as e:
            error_msg = f"Tag push failed: {str(e)}"
            print(f"[API Push] 标签处理错误: {error_msg}")
            return {'status': 'error', 'message': str(e)}
    
    def _handle_image_push(self, data):
        """处理图片数据的推送"""
        try:
            print(f"[API Push] 处理图片数据")
            
            # 获取图片数据URL
            image_data_url = data.get('imageDataUrl', '')
            if not image_data_url:
                return {'status': 'error', 'message': 'No image data URL provided'}
            
            # 获取标签名称，如果没有则使用默认值（包含时间戳）
            import time
            label_name = data.get('label', data.get('tag', data.get('zhTag', f'浏览器截图_{int(time.time())}')))
            
            # 解析data URL
            import re
            match = re.match(r"^data:(image/\w+);base64,(.+)$", image_data_url)
            if not match:
                return {'status': 'error', 'message': 'Invalid image data URL format'}
            
            ext = match.group(1).split("/")[-1]
            raw = base64.b64decode(match.group(2))
            
            # 使用与本地标签完全相同的命名规则：中文标签名+时间戳
            filename = f"{label_name}_{int(time.time())}.{ext}"
            
            # 直接保存到images目录，跳过webcaps中转
            images_dir = 'images'
            if not os.path.exists(images_dir):
                os.makedirs(images_dir)
            
            # 保存图片文件到images目录
            file_path = os.path.join(images_dir, filename)
            with open(file_path, 'wb') as f:
                f.write(raw)
            
            print(f"[API Push] 图片直接保存到images目录: {file_path}")
            
            # 直接创建标签，跳过web_inbox.jsonl
            bridge_data = {
                'imageFile': file_path,
                'label': label_name,
                'text': data.get('text', data.get('enTag', '')),
                'timestamp': int(time.time())
            }
            
            # 直接调用标签创建逻辑
            try:
                self._create_tag_directly(bridge_data)
                print(f"[API Push] 标签已直接创建: {label_name}")
            except Exception as e:
                print(f"[API Push] 直接创建标签失败，将使用web_inbox: {e}")
                # 回退到web_inbox.jsonl
                inbox_path = 'web_inbox.jsonl'
                try:
                    with open(inbox_path, 'a', encoding='utf-8') as f:
                        f.write(json.dumps(bridge_data, ensure_ascii=False) + "\n")
                    print(f"[API Push] 数据已写入web_inbox.jsonl作为回退")
                except Exception as e2:
                    print(f"[API Push] 写入web_inbox.jsonl失败: {str(e2)}")
            
            return {
                'status': 'success', 
                'message': f'Image and tag created successfully: {file_path}',
                'filePath': file_path
            }
            
        except Exception as e:
            error_msg = f"Image push failed: {str(e)}"
            print(f"[API Push] 图片处理错误: {error_msg}")
            return {'status': 'error', 'message': str(e)}

    def _create_tag_directly(self, data):
        """直接创建标签，跳过中间步骤"""
        try:
            tags_file = 'tags.json'
            label_name = data['label']
            image_path = data['imageFile']
            
            # 读取现有标签数据
            tags_data = {}
            if os.path.exists(tags_file):
                with open(tags_file, 'r', encoding='utf-8') as f:
                    tags_data = json.load(f)
            
            # 确保基本结构存在
            if "head" not in tags_data:
                tags_data["head"] = {}
            if "tail" not in tags_data:
                tags_data["tail"] = {}
            
            # 确定标签类型和分类（默认添加到head的基础分类中）
            tag_type = "head"
            category = "基础"
            
            if tag_type not in tags_data:
                tags_data[tag_type] = {}
            if category not in tags_data[tag_type]:
                tags_data[tag_type][category] = {}
            
            # 创建新标签
            # 处理图片路径：保存相对路径
            relative_image_path = image_path
            if image_path and os.path.isabs(image_path):
                try:
                    relative_image_path = os.path.relpath(image_path, os.getcwd()).replace('\\', '/')
                except ValueError:
                    # 如果无法转换为相对路径，保持绝对路径
                    relative_image_path = image_path
            elif image_path:
                relative_image_path = image_path.replace('\\', '/')
                
            new_tag = {
                "en": data.get('text', label_name),  # 使用英文标签或中文标签名
                "image": relative_image_path,
                "usage_count": 0,
                "url": data.get('url', ''),
                "title": data.get('title', ''),
                "timestamp": data.get('timestamp', int(time.time()))
            }
            
            # 添加标签（如果不存在）
            if label_name not in tags_data[tag_type][category]:
                tags_data[tag_type][category][label_name] = new_tag
                print(f"[直接创建标签] 成功: {label_name} -> {image_path}")
            else:
                print(f"[直接创建标签] 标签已存在: {label_name}")
            
            # 保存标签数据
            with open(tags_file, 'w', encoding='utf-8') as f:
                json.dump(tags_data, f, ensure_ascii=False, indent=2)
                
            # 尝试触发主程序UI刷新
            try:
                import sys
                sys.path.append('.')
                
                # 使用线程安全的方式触发UI刷新
                main_module = sys.modules.get('__main__')
                if main_module and hasattr(main_module, 'refresh_tags_ui'):
                    # 检查是否有全局root对象
                    if hasattr(main_module, 'global_root'):
                        # 使用after方法在主线程中执行UI刷新
                        main_module.global_root.after(0, lambda: main_module.refresh_tags_ui(tags_file))
                        print(f"[直接创建标签] 已安排主程序UI刷新")
                    else:
                        # 直接调用（可能不安全，但作为备用方案）
                        main_module.refresh_tags_ui(tags_file)
                        print(f"[直接创建标签] 已直接触发主程序UI刷新")
                else:
                    print(f"[直接创建标签] 主程序未运行UI刷新方法")
            except Exception as e:
                print(f"[直接创建标签] 触发UI刷新失败: {e}")
                import traceback
                traceback.print_exc()
                
        except Exception as e:
            print(f"[直接创建标签] 失败: {e}")
            raise e
    
    def handle_translate(self, data):
        """处理/translate端点的请求，用于文本翻译"""
        try:
            text = data.get('text', '')
            to_lang = data.get('to', 'zh')
            
            if not text.strip():
                return {
                    'ok': False,
                    'error': 'Empty text provided'
                }
            
            # 使用统一的翻译服务
            from services.api import translate_text
            
            translated = translate_text(text)
            
            return {
                'ok': True,
                'zh': translated,
                'translated': translated,
                'text': text,
                'result': translated
            }
                
        except Exception as e:
            return {
                'ok': False,
                'error': f'Translation failed: {str(e)}'
            }

def start_http_server(port=8766):
    """启动HTTP服务器"""
    with socketserver.ThreadingTCPServer(("", port), TagSyncHandler) as httpd:
        print(f"Tag sync server started at port {port}")
        httpd.serve_forever()

def start_server_in_background(port=8766):
    """在后台线程中启动服务器"""
    server_thread = threading.Thread(target=start_http_server, args=(port,), daemon=True)
    server_thread.start()
    return server_thread

if __name__ == "__main__":
    # 当直接运行此脚本时启动服务器
    start_http_server()