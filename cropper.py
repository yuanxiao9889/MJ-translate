# cropper.py
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk

class Cropper(tk.Toplevel):
    def __init__(self, image=None, box_size=(600, 600), keep_aspect=True):
        super().__init__()
        self.title('裁剪图片')
        self.keep_aspect = keep_aspect
        self.box_size = box_size

        # 加载图片
        if isinstance(image, str):
            self.image = Image.open(image)
        else:
            self.image = image

        self.tk_image = ImageTk.PhotoImage(self.image)
        self.canvas = tk.Canvas(self, width=self.tk_image.width(), height=self.tk_image.height(), bg='white')
        self.canvas.pack(fill="both", expand=True)  # 修改为填充并扩展
        self.canvas.create_image(0, 0, anchor='nw', image=self.tk_image)

        # 修改弹窗初始大小为更合适的尺寸
        self.geometry("800x600")  # 将原尺寸（如"400x300"）调整为更大值
        self.resizable(True, True)  # 允许用户调整窗口大小
        center_window(self)  # 添加这行居中代码

        # 初始裁剪框
        w, h = self.tk_image.width(), self.tk_image.height()
        bw, bh = int(box_size[0]*1.5), int(box_size[1]*1.5)  # 增大裁剪框1.5倍
        left = (w - bw) // 2
        top = (h - bh) // 2
        right = left + bw
        bottom = top + bh

        self.rect = self.canvas.create_rectangle(left, top, right, bottom, outline='red', width=2)
        self._drag_data = {"x": 0, "y": 0, "item": None}
        self._rect_coords = [left, top, right, bottom]

        # 鼠标事件绑定
        self.canvas.tag_bind(self.rect, "<ButtonPress-1>", self.on_press)
        self.canvas.tag_bind(self.rect, "<B1-Motion>", self.on_move)
        self.canvas.tag_bind(self.rect, "<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

        # 裁剪按钮
        # 确保主容器使用pack并填充空间
        self.main_frame = tk.Frame(self)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 按钮区域使用适当的布局
        self.button_frame = tk.Frame(self.main_frame)
        self.button_frame.pack(side="bottom", fill="x", pady=10)
        
        # 确保所有按钮可见
        self.crop_button = tk.Button(self.button_frame, text="裁剪", command=self.crop)
        self.crop_button.pack(side="left", padx=5)
        self.cropped_image = None
        self.update_idletasks()  # 确保获取正确的窗口尺寸
        self.center_window()  # 添加居中调用

    def on_press(self, event):
        self._drag_data["item"] = "rect"
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def on_move(self, event):
        dx = event.x - self._drag_data["x"]
        dy = event.y - self._drag_data["y"]
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
        # 移动裁剪框
        self.canvas.move(self.rect, dx, dy)
        coords = self.canvas.coords(self.rect)
        self._rect_coords = coords

    def on_release(self, event):
        self._drag_data["item"] = None

    def on_canvas_press(self, event):
        # 在边缘拉伸（可扩展为四角八向拉伸）
        self._drag_data["item"] = None

    def on_canvas_move(self, event):
        pass

    def on_canvas_release(self, event):
        pass

    def crop_and_close(self):
        x0, y0, x1, y1 = [int(c) for c in self.canvas.coords(self.rect)]
        cropped = self.image.crop((x0, y0, x1, y1))
        # 裁剪为固定大小（如 box_size）
        cropped = cropped.resize(self.box_size)
        self.cropped_image = cropped
        self.destroy()

    def crop(self):
        self.grab_set()
        self.wait_window()
        return self.cropped_image
