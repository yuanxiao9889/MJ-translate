# image_tools.py
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageGrab
import os
import time

def center_window(window, width=None, height=None):
    """
    自动将窗口居中显示在屏幕中间
    """
    window.update_idletasks()
    if width is None or height is None:
        width = window.winfo_width()
        height = window.winfo_height()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")

class Cropper(tk.Toplevel):
    """
    图片裁剪弹窗，正方形裁剪
    """
    def __init__(self, image=None, box_size=(200, 200), keep_aspect=True):
        super().__init__()
        self.title('裁剪图片')
        self.keep_aspect = keep_aspect
        self.box_size = box_size

        if isinstance(image, str):
            self.image = Image.open(image)
        else:
            self.image = image

        # 自动等比缩放到窗口最大500像素
        max_display_size = 500
        w, h = self.image.size
        scale = min(max_display_size / w, max_display_size / h, 1.0)
        if scale < 1.0:
            self.image = self.image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        self.tk_image = ImageTk.PhotoImage(self.image)  # 必须用self.tk_image
        self.canvas = tk.Canvas(self, width=self.tk_image.width(), height=self.tk_image.height(), bg='white')
        self.canvas.pack(side="top", fill="both", expand=True)  # 画布永远在最上面

        # 必须等canvas创建完后再显示图片，并用self.tk_image保存引用
        self.canvas.create_image(0, 0, anchor='nw', image=self.tk_image)

        # 按钮永远在最下方
        self.crop_button = tk.Button(self, text="裁剪", command=self.crop_and_close)
        self.crop_button.pack(side="bottom", fill="x", pady=10)


        # 设置窗口尺寸：画布高度+按钮空间
        min_height = self.tk_image.height() + 60  # 60为按钮和上下间距
        min_width = self.tk_image.width()
        self.minsize(min_width, min_height)
        self.geometry(f"{min(800, min_width)}x{min(600, min_height)}")
        self.resizable(True, True)
        center_window(self)

        # 初始正方形裁剪框，居中
        w, h = self.tk_image.width(), self.tk_image.height()
        side = min(w, h, 300)
        left = (w - side) // 2
        top = (h - side) // 2
        right = left + side
        bottom = top + side

        self.rect = self.canvas.create_rectangle(left, top, right, bottom, outline='red', width=2)
        self._drag_data = {"x": 0, "y": 0, "item": None}
        self._rect_coords = [left, top, right, bottom]

        # 鼠标事件
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

    def on_press(self, event):
        self._drag_data["item"] = "rect"
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def on_move(self, event):
        dx = event.x - self._drag_data["x"]
        dy = event.y - self._drag_data["y"]
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
        coords = self.canvas.coords(self.rect)
        # 保持正方形
        side = coords[2] - coords[0]
        # 按实际拖动量一起平移
        new_coords = [coords[0] + dx, coords[1] + dy, coords[2] + dx, coords[3] + dy]
        # 限制不超界
        w, h = self.tk_image.width(), self.tk_image.height()
        if new_coords[0] < 0:
            new_coords[2] -= new_coords[0]
            new_coords[0] = 0
        if new_coords[1] < 0:
            new_coords[3] -= new_coords[1]
            new_coords[1] = 0
        if new_coords[2] > w:
            new_coords[0] -= (new_coords[2] - w)
            new_coords[2] = w
        if new_coords[3] > h:
            new_coords[1] -= (new_coords[3] - h)
            new_coords[3] = h
        self.canvas.coords(self.rect, *new_coords)
        self._rect_coords = new_coords

    def on_release(self, event):
        self._drag_data["item"] = None

    def crop_and_close(self):
        x0, y0, x1, y1 = [int(c) for c in self.canvas.coords(self.rect)]
        cropped = self.image.crop((x0, y0, x1, y1))
        cropped = cropped.resize(self.box_size)
        self.cropped_image = cropped
        self.destroy()

def select_and_crop_image(label_name="标签图片", box_size=(200,200)):
    """
    选择本地图片后弹窗正方形裁剪
    """
    file_path = filedialog.askopenfilename(
        title="选择图片",
        filetypes=[("图片文件", "*.png;*.jpg;*.jpeg;*.bmp")]
    )
    if not file_path:
        return None
    im = Image.open(file_path)
    cropper = Cropper(im, box_size=box_size, keep_aspect=True)
    cropper.grab_set()
    cropper.wait_window()
    cropped_img = cropper.cropped_image
    if cropped_img is None:
        return None
    fname = f"{label_name}_{int(time.time())}.png"
    os.makedirs("images", exist_ok=True)
    save_path = os.path.join("images", fname)
    cropped_img.save(save_path)
    return save_path


    
    # 绑定事件
    print("[DEBUG] 绑定鼠标和键盘事件")
    canvas.bind('<ButtonPress-1>', on_press)
    canvas.bind('<ButtonPress-3>', on_press)  # 右键
    canvas.bind('<B1-Motion>', on_drag)
    canvas.bind('<ButtonRelease-1>', on_release)
    canvas.bind('<ButtonRelease-3>', on_release)  # 右键释放
    print("[DEBUG] 事件绑定完成")
    print(f"[DEBUG] canvas对象: {canvas}")
    print(f"[DEBUG] crop_win对象: {crop_win}")
    
    # 绑定键盘事件
    crop_win.bind('<Escape>', cancel)
    crop_win.bind('<Return>', cancel)  # 回车也可以取消
    canvas.bind('<Escape>', cancel)
    canvas.bind('<Return>', cancel)
    
    # 确保可以接收键盘事件
    crop_win.focus_set()
    canvas.focus_set()
    print("[DEBUG] 开始等待用户操作...")
    
    try:
        crop_win.wait_window()
        print("[DEBUG] 窗口已关闭")
    except Exception as ex:
        print(f"[DEBUG] 截图窗口错误: {ex}")
        capture_result[0] = None
        cleanup_and_exit()
    
    print(f"[DEBUG] 返回结果: {capture_result[0]}")
    return capture_result[0]
