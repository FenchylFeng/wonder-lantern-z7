"""Standalone Windows front end for the independent Z7 V4 build."""

import binascii
import hashlib
import json
from pathlib import Path
from queue import Empty, Queue
import struct
from tempfile import TemporaryDirectory
from threading import Thread
import tkinter as tk
from tkinter import filedialog, font, messagebox, ttk
import webbrowser

from z30_extensions.container import Z7_CONTAINER_SHA256, Z7_CONTAINER_SIZE
from z30_extensions.features.display_type_a_z7 import build


TITLE = "Nikon Z7 C3.80 自定义固件 V4"
NIKON_URL = "https://downloadcenter.nikonimglib.com/zh-cn/download/fw/558.html"
PROJECT_URL = "https://github.com/FenchylFeng/wonder-lantern-z7"
WARNING = (
    "实验性固件可能存在数据丢失、死机、失去官方质保等风险。"
    "如果您选择接受并使用了该固件，则出现的任何问题，开发者不负任何责任。"
)
OUTPUT_NAME = "EG161080.BIN"
ASSETS = Path(__file__).resolve().parent


def generate_firmware(source, folder):
    destination = folder / OUTPUT_NAME
    if destination.exists():
        raise FileExistsError(f"此位置已有 {OUTPUT_NAME}，请选择其他保存位置。")

    with source.open("rb") as file:
        container = file.read(Z7_CONTAINER_SIZE + 1)
    if len(container) != Z7_CONTAINER_SIZE or hashlib.sha256(container).hexdigest() != Z7_CONTAINER_SHA256:
        raise ValueError("原厂固件校验失败，请选择尼康官网的 Z7 C3.80 原版 Z_7_0380.bin。")

    reference = json.loads((ASSETS / "v4-validation.json").read_text(encoding="utf-8"))["build"]
    renderer = (ASSETS / "v4-renderer.bin").read_bytes()
    (renderer_address,) = struct.unpack_from("<I", renderer)

    def renderer_for_address(address):
        if address != renderer_address:
            raise ValueError("V4 渲染器的链接地址与固件不匹配。")
        return renderer[4:]

    eg, _ = build(container, renderer_for_address=renderer_for_address)
    with TemporaryDirectory(prefix=".z7-v4-", dir=folder) as temporary:
        candidate = Path(temporary) / "display.emulator.eg.bin"
        candidate.write_bytes(eg)
        saved = candidate.read_bytes()
        digest = hashlib.sha256(saved).hexdigest()
        if digest != reference["eg_sha256"] or binascii.crc_hqx(saved, 0):
            raise ValueError("生成的 EG 未通过 SHA-256 或 CRC 校验。")
        # On Windows rename fails if another program created the destination.
        candidate.rename(destination)
    return destination, digest


class FirmwareApp:
    def __init__(self, root):
        self.root = root
        root.title(TITLE)
        root.configure(background="#f5f6f8")
        root.resizable(True, False)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.busy = False
        self.source = tk.StringVar(root)
        self.folder = tk.StringVar(root)
        self.status = tk.StringVar(root)
        self.result = Queue()
        self.fields = []

        family = "Microsoft YaHei UI"
        base_font = font.nametofont("TkDefaultFont")
        base_font.configure(family=family, size=10)
        heading = (family, 19, "bold")
        label = (family, 10, "bold")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#f5f6f8")
        style.configure("TLabel", background="#f5f6f8", foreground="#192231")
        style.configure("TEntry", padding=(9, 7), fieldbackground="#ffffff", bordercolor="#aeb9c8")
        style.configure("TButton", padding=(13, 7), background="#ffffff", foreground="#192231")
        style.map("TButton", background=[("active", "#e7edf5")])
        style.configure("Primary.TButton", background="#274e7a", foreground="#ffffff", font=label)
        style.map("Primary.TButton", background=[("disabled", "#626e7c"), ("active", "#1d3d63")])
        style.configure("Link.TButton", padding=0, relief="flat", borderwidth=0,
                        background="#f5f6f8", foreground="#24548b",
                        font=(family, 10, "underline"))
        style.map("Link.TButton", foreground=[("active", "#173a61")])

        panel = ttk.Frame(root, padding=(30, 23, 30, 20))
        panel.grid(sticky="nsew")
        root.columnconfigure(0, weight=1)
        panel.columnconfigure(0, weight=1)
        ttk.Label(panel, text=TITLE, font=heading).grid(row=0, column=0, sticky="w", pady=(0, 23))
        source_label = ttk.Frame(panel)
        source_label.grid(row=1, column=0, sticky="w")
        ttk.Label(source_label, text="原厂固件", font=label).pack(side="left", padx=(0, 9))
        ttk.Button(source_label, text="下载链接", style="Link.TButton",
                   command=lambda: webbrowser.open(NIKON_URL)).pack(side="left")
        self.add_path(panel, 2, self.source, "选择文件", self.pick_source)
        ttk.Label(panel, text="结果保存位置", font=label).grid(row=3, column=0, sticky="w")
        self.add_path(panel, 4, self.folder, "选择位置", self.pick_folder)
        action = ttk.Frame(panel)
        action.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(2, 15))
        self.generate = ttk.Button(action, text="生成V4固件", style="Primary.TButton",
                                   command=self.confirm)
        self.generate.pack(side="left")
        ttk.Label(action, textvariable=self.status).pack(side="left", padx=12)

        ttk.Separator(panel).grid(row=6, column=0, columnspan=2, sticky="ew")
        ttk.Label(panel, text="实验性项目；仅适用于 Z7 C3.80。刷入修改固件可能损坏相机，本项目不负任何责任。",
                  foreground="#4a5667", justify="left", wraplength=590).grid(
            row=7, column=0, columnspan=2, sticky="w", pady=(12, 6))
        ttk.Button(panel, text="项目地址", style="Link.TButton",
                   command=lambda: webbrowser.open(PROJECT_URL)).grid(row=8, column=0, sticky="w")
        root.update_idletasks()
        root.minsize(max(root.winfo_reqwidth(), 666), root.winfo_reqheight())
        self.fields[0].focus_set()

    def add_path(self, panel, row, value, caption, command):
        entry = ttk.Entry(panel, textvariable=value)
        entry.grid(row=row, column=0, sticky="ew", pady=(6, 18))
        button = ttk.Button(panel, text=caption, command=command)
        button.grid(row=row, column=1, padx=(10, 0), pady=(6, 18))
        self.fields.extend([entry, button])

    def pick_source(self):
        source = filedialog.askopenfilename(parent=self.root, title="选择原厂固件",
                                            filetypes=[("固件文件", "*.bin"), ("所有文件", "*.*")])
        if source:
            self.source.set(source)

    def pick_folder(self):
        folder = filedialog.askdirectory(parent=self.root, title="选择结果保存位置", mustexist=True)
        if folder:
            self.folder.set(folder)

    def close(self):
        if not self.busy:
            self.root.destroy()

    def modal(self, title):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        panel = ttk.Frame(dialog, padding=(25, 23))
        panel.pack(fill="both", expand=True)
        return dialog, panel

    def show_modal(self, dialog, focus):
        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dialog.winfo_reqwidth()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - dialog.winfo_reqheight()) // 2
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
        dialog.grab_set()
        focus.focus_set()

    def confirm(self):
        dialog, panel = self.modal("生成固件确认")
        ttk.Label(panel, text=WARNING, font=("Microsoft YaHei UI", 11, "bold"),
                  wraplength=475, justify="left").pack(anchor="w", pady=(0, 21))
        buttons = ttk.Frame(panel)
        buttons.pack(fill="x")
        decline = ttk.Button(buttons, text="不同意并退出", command=self.close)
        decline.pack(side="left")

        def accept():
            dialog.destroy()
            self.start_build()

        ttk.Button(buttons, text="同意并生成固件", style="Primary.TButton",
                   command=accept).pack(side="right")
        self.show_modal(dialog, decline)

    def show_success(self, path, digest):
        dialog, panel = self.modal("生成成功")
        for label, value in (("保存路径", str(path)), ("SHA-256", digest)):
            ttk.Label(panel, text=label).pack(anchor="w")
            field = ttk.Entry(panel, width=68, font=("Consolas", 10))
            field.insert(0, value)
            field.state(["readonly"])
            field.pack(fill="x", pady=(5, 13))
        close = ttk.Button(panel, text="确定", style="Primary.TButton", command=dialog.destroy)
        close.pack(anchor="e")
        dialog.bind("<Return>", lambda _event: dialog.destroy())
        self.show_modal(dialog, close)

    def start_build(self):
        source_text = self.source.get().strip().strip('"')
        folder_text = self.folder.get().strip().strip('"')
        if not source_text or not Path(source_text).is_file():
            messagebox.showerror("请选择原厂固件", "请输入原厂固件文件地址，或使用“选择文件”。", parent=self.root)
            return
        if not folder_text or not Path(folder_text).is_dir():
            messagebox.showerror("请选择保存位置", "请输入已有文件夹地址，或使用“选择位置”。", parent=self.root)
            return
        self.set_busy(True)
        self.status.set("正在生成并校验固件…")
        Thread(target=self.build_in_background, args=(Path(source_text), Path(folder_text))).start()
        self.root.after(100, self.check_result)

    def set_busy(self, busy):
        self.busy = busy
        state = ["disabled"] if busy else ["!disabled"]
        for widget in [*self.fields, self.generate]:
            widget.state(state)

    def build_in_background(self, source, folder):
        try:
            self.result.put(generate_firmware(source, folder))
        except Exception as error:
            self.result.put(error)

    def check_result(self):
        try:
            result = self.result.get_nowait()
        except Empty:
            self.root.after(100, self.check_result)
            return
        self.set_busy(False)
        if isinstance(result, Exception):
            self.status.set("生成失败")
            messagebox.showerror("生成失败", str(result), parent=self.root)
        else:
            destination, digest = result
            self.status.set("已生成并通过校验")
            self.show_success(destination, digest)


if __name__ == "__main__":
    app = tk.Tk()
    FirmwareApp(app)
    app.mainloop()
