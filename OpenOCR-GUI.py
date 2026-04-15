import sys
import os
import re
import subprocess
import time
import shutil
import json
import markdown
import fitz  # PyMuPDF
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog,
                             QListWidget, QRadioButton, QCheckBox, QGroupBox, QTabWidget,
                             QSplitter, QMessageBox, QFrame, QScrollArea, QSizePolicy, QFormLayout)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt5.QtGui import QPixmap, QFont, QTextCursor, QImage
from PyQt5.QtWebEngineWidgets import QWebEngineView       #from PyQt5.WebEngineWidgets import QWebEngineView
 
try:
    import GPUtil
    HAS_GPUtil = True
except ImportError:
    HAS_GPUtil = False
 
class ODLWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)
 
    def __init__(self, command, cwd=None, log_lines=None):
        super().__init__()
        self.command = command
        self.cwd = cwd
        self._is_running = True
        self.log_lines = log_lines if log_lines is not None else []
 
    def run(self):
        self.log_signal.emit(f"[系统] 正在执行命令: {' '.join(self.command)}")
        self.log_signal.emit("-" * 50)
        try:
            process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=False,
                cwd=self.cwd
            )
            while True:
                if not self._is_running:
                    process.terminate()
                    self.log_signal.emit("[系统] 任务已被用户终止。")
                    break
                output = process.stdout.readline()
                if output == b'' and process.poll() is not None:
                    break
                if output:
                    try:
                        output_str = output.decode('utf-8').strip()
                    except UnicodeDecodeError:
                        try:
                            output_str = output.decode('gbk').strip()
                        except UnicodeDecodeError:
                            output_str = output.decode('utf-8', errors='replace').strip()
                    self.log_signal.emit(output_str)
                    self.log_lines.append(output_str)
            rc = process.poll()
            if rc == 0:
                self.finished_signal.emit(True, "转换任务完成。")
            else:
                self.finished_signal.emit(False, f"转换任务失败，退出码: {rc}")
        except Exception as e:
            self.finished_signal.emit(False, f"发生异常: {str(e)}")
 
    def stop(self):
        self._is_running = False
 
class OpenOCRGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenOCR-GUI")
        self.resize(1400, 900)
        self.input_files = []
        self.worker = None
        self.current_preview_file = None
        self.current_source_page = 0
        self.source_total_pages = 0
        self.current_result_page = 0
        self.result_total_pages = 0
        self.log_lines = []
        
        # 统一逐个文件处理队列
        self._pending_files = []
        
        self.init_ui()
        self.gpu_timer = QTimer()
        self.gpu_timer.timeout.connect(self.update_gpu_info)
        self.gpu_timer.start(1000)
 
    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
 
        left_panel = QVBoxLayout()
        top_container = QWidget()
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
 
        file_group = QGroupBox("文件选择")
        file_layout = QVBoxLayout(file_group)
        btn_layout = QHBoxLayout()
        self.btn_add_files = QPushButton("添加文件")
        self.btn_add_folder = QPushButton("添加文件夹")
        self.btn_clear = QPushButton("清空列表")
        self.btn_clear.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; height: 30px;")
        btn_layout.addWidget(self.btn_add_files)
        btn_layout.addWidget(self.btn_add_folder)
        btn_layout.addWidget(self.btn_clear)
        self.lbl_file_count = QLabel("未添加文件")
        self.lbl_file_count.setStyleSheet("color: #666; font-size: 11px;")
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.SingleSelection)
        self.file_list.itemClicked.connect(self.preview_source_file)
        file_layout.addLayout(btn_layout)
        file_layout.addWidget(self.lbl_file_count)
        file_layout.addWidget(self.file_list)
 
        output_layout = QHBoxLayout()
        self.label_output = QLabel("输出目录:")
        self.txt_output_dir = QLineEdit()
        self.txt_output_dir.setPlaceholderText("默认为源文件所在目录")
        self.btn_browse_output = QPushButton("浏览...")
        self.btn_source_folder = QPushButton("同源文件夹")
        self.btn_source_folder.clicked.connect(self.set_output_to_source_folder)
        output_layout.addWidget(self.label_output)
        output_layout.addWidget(self.txt_output_dir)
        output_layout.addWidget(self.btn_browse_output)
        output_layout.addWidget(self.btn_source_folder)
        file_layout.addLayout(output_layout)
 
        top_layout.addWidget(file_group)
 
        settings_tabs = QTabWidget()
        tab_basic = QWidget()
        layout_basic = QFormLayout(tab_basic)
 
        # OpenOCR 脚本路径配置
        script_layout = QHBoxLayout()
        self.txt_script_path = QLineEdit("tools/infer_doc.py")
        self.txt_script_path.setPlaceholderText("例如: tools/infer_doc.py")
        script_layout.addWidget(self.txt_script_path)
        layout_basic.addRow("脚本路径:", script_layout)
 
        # OpenOCR 工作目录配置
        workdir_layout = QHBoxLayout()
        self.txt_work_dir = QLineEdit("")
        self.txt_work_dir.setPlaceholderText("OpenOCR项目根目录，留空则为当前目录")
        self.btn_browse_workdir = QPushButton("浏览...")
        self.btn_browse_workdir.clicked.connect(self.browse_work_dir)
        workdir_layout.addWidget(self.txt_work_dir)
        workdir_layout.addWidget(self.btn_browse_workdir)
        layout_basic.addRow("工作目录:", workdir_layout)
 
        # 设备模式 (单选，默认GPU)
        device_layout = QHBoxLayout()
        self.radio_gpu = QRadioButton("GPU (--gpus 0)")
        self.radio_gpu.setChecked(True)
        self.radio_cpu = QRadioButton("CPU (--gpus -1)")
        device_layout.addWidget(self.radio_gpu)
        device_layout.addWidget(self.radio_cpu)
        layout_basic.addRow("设备模式:", device_layout)
 
        # 保存选项 (多选)
        save_layout = QVBoxLayout()
        self.chk_save_img = QCheckBox("识别图片 (--is_save_vis_img)")
        self.chk_save_json = QCheckBox("JSON (--is_save_json)")
        self.chk_save_md = QCheckBox("Markdown (--is_save_markdown)")
        self.chk_save_md.setChecked(True)
        save_layout.addWidget(self.chk_save_img)
        save_layout.addWidget(self.chk_save_json)
        save_layout.addWidget(self.chk_save_md)
        layout_basic.addRow("保存选项:", save_layout)
 
        # 整合选项
        self.chk_merge_files = QCheckBox("整合成一个文件 (合并为 原文件名.md/json)")
        self.chk_merge_files.setChecked(True)
        self.chk_merge_files.stateChanged.connect(self.on_merge_state_changed)
        layout_basic.addRow("", self.chk_merge_files)
 
        settings_tabs.addTab(tab_basic, "基础设置")
        top_layout.addWidget(settings_tabs)
        left_panel.addWidget(top_container)
 
        log_group = QGroupBox("处理日志")
        log_layout = QVBoxLayout(log_group)
        self.log_window = QTextEdit()
        self.log_window.setReadOnly(True)
        self.log_window.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: Consolas;")
        self.log_window.setFont(QFont("Consolas", 12))
        log_layout.addWidget(self.log_window)
        self.btn_clear_log = QPushButton("清空Log")
        self.btn_clear_log.clicked.connect(self.clear_log)
        log_layout.addWidget(self.btn_clear_log)
        left_panel.addWidget(log_group, 1)
 
        gpu_group = QGroupBox("硬件监控")
        gpu_layout = QVBoxLayout(gpu_group)
        self.lbl_gpu_info = QLabel("正在检测显卡...")
        self.lbl_gpu_info.setStyleSheet("font-family: Consolas; background-color: black; color: #00FF00; padding: 5px;")
        self.lbl_gpu_info.setFont(QFont("Consolas", 10))
        gpu_layout.addWidget(self.lbl_gpu_info)
        left_panel.addWidget(gpu_group)
 
        main_layout.addLayout(left_panel, 3)
 
        right_panel = QVBoxLayout()
        preview_splitter = QSplitter(Qt.Horizontal)
        preview_splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
 
        source_container = QWidget()
        source_layout = QVBoxLayout(source_container)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_label = QLabel("源文件预览")
        source_label.setAlignment(Qt.AlignCenter)
        source_label.setStyleSheet("font-weight: bold;")
        source_label.setFixedHeight(35)
        source_layout.addWidget(source_label)
 
        self.source_scroll = QScrollArea()
        self.source_scroll.setWidgetResizable(True)
        self.source_scroll.setAlignment(Qt.AlignCenter)
        self.source_scroll.setStyleSheet("border: 1px solid #ccc;")
        self.source_preview_container = QWidget()
        self.source_preview_layout = QVBoxLayout(self.source_preview_container)
        self.source_preview_layout.setContentsMargins(0, 0, 0, 0)
        self.source_preview_layout.setAlignment(Qt.AlignCenter)
        self.source_preview_label = QLabel("请选择文件以预览\n支持 PDF 和图片")
        self.source_preview_label.setAlignment(Qt.AlignCenter)
        self.source_preview_label.setStyleSheet("background-color: #333; color: white;")
        self.source_preview_layout.addWidget(self.source_preview_label)
        self.source_scroll.setWidget(self.source_preview_container)
        source_layout.addWidget(self.source_scroll, 1)
 
        source_nav_layout = QHBoxLayout()
        self.btn_source_prev = QPushButton("上一页")
        self.btn_source_prev.setFixedWidth(80)
        self.btn_source_prev.setEnabled(False)
        self.lbl_source_page = QLabel("0/0")
        self.lbl_source_page.setAlignment(Qt.AlignCenter)
        self.lbl_source_page.setFixedHeight(30)
        self.lbl_source_page.setStyleSheet("border: 1px solid #ccc; background-color: #f5f5f5;")
        self.btn_source_next = QPushButton("下一页")
        self.btn_source_next.setFixedWidth(80)
        self.btn_source_next.setEnabled(False)
        source_nav_layout.addWidget(self.btn_source_prev)
        source_nav_layout.addWidget(self.lbl_source_page)
        source_nav_layout.addWidget(self.btn_source_next)
        source_layout.addLayout(source_nav_layout)
        source_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_splitter.addWidget(source_container)
 
        result_container = QWidget()
        result_layout = QVBoxLayout(result_container)
        result_layout.setContentsMargins(0, 0, 0, 0)
        result_label = QLabel("结果预览")
        result_label.setAlignment(Qt.AlignCenter)
        result_label.setStyleSheet("font-weight: bold;")
        result_label.setFixedHeight(35)
        result_layout.addWidget(result_label)
 
        self.result_scroll = QScrollArea()
        self.result_scroll.setWidgetResizable(True)
        self.result_scroll.setStyleSheet("border: 1px solid #ccc;")
        self.result_preview = QWebEngineView()
        self.result_preview.setHtml("<html><body style='background-color:#fff; color:#333;'><h3>识别结果预览</h3><p>转换完成后将在此处显示 Markdown 渲染结果。</p></body></html>")
        self.result_scroll.setWidget(self.result_preview)
        result_layout.addWidget(self.result_scroll, 1)
 
        self.lbl_result_page = QLabel("0/0")
        self.lbl_result_page.setAlignment(Qt.AlignCenter)
        self.lbl_result_page.setFixedHeight(30)
        self.lbl_result_page.setStyleSheet("border: 1px solid #ccc; background-color: #f5f5f5;")
        result_layout.addWidget(self.lbl_result_page)
        result_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_splitter.addWidget(result_container)
 
        right_panel.addWidget(preview_splitter, 1)
        preview_splitter.setStretchFactor(0, 1)
        preview_splitter.setStretchFactor(1, 1)
        QTimer.singleShot(0, lambda: self.set_splitter_equal_width(preview_splitter))
        source_container.setMinimumWidth(300)
        result_container.setMinimumWidth(300)
 
        btn_frame = QFrame()
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(0, 10, 0, 0)
        self.btn_start = QPushButton("转换全部")
        self.btn_start.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; height: 40px;")
        self.btn_convert_selected = QPushButton("转换所选文件")
        self.btn_convert_selected.setEnabled(False)
        self.btn_convert_selected.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold; height: 40px;")
        self.btn_open_folder = QPushButton("打开输出目录")
        self.btn_open_folder.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; height: 40px;")
        self.btn_download = QPushButton("下载/另存为...")
        self.btn_download.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold; height: 40px;")
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_convert_selected)
        btn_layout.addWidget(self.btn_open_folder)
        btn_layout.addWidget(self.btn_download)
        right_panel.addWidget(btn_frame)
 
        main_layout.addLayout(right_panel, 7)
 
        self.btn_add_files.clicked.connect(self.add_files)
        self.btn_add_folder.clicked.connect(self.add_folder)
        self.btn_clear.clicked.connect(self.clear_file_list)
        self.btn_browse_output.clicked.connect(self.browse_output_dir)
        self.btn_start.clicked.connect(self.start_conversion)
        self.btn_convert_selected.clicked.connect(self.convert_selected_file)
        self.btn_open_folder.clicked.connect(self.open_output_folder)
        self.btn_download.clicked.connect(self.download_result)
        self.btn_source_prev.clicked.connect(self.prev_source_page)
        self.btn_source_next.clicked.connect(self.next_source_page)
 
    # ==========================================
    # Logic Implementation
    # ==========================================
    def on_merge_state_changed(self):
        if self.current_preview_file:
            self.load_result_preview(self.current_preview_file)
 
    def clear_file_list(self):
        self.file_list.clear()
        self.input_files.clear()
        self.txt_output_dir.clear()
        self.update_file_count_label()
 
    def set_output_to_source_folder(self):
        self.txt_output_dir.clear()
 
    def browse_work_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "选择OpenOCR工作目录")
        if folder:
            self.txt_work_dir.setText(folder)
 
    def log(self, message):
        cursor = self.log_window.textCursor()
        cursor.movePosition(QTextCursor.End)
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        cursor.insertText(f"[{timestamp}] {message}\n")
        self.log_window.setTextCursor(cursor)
        self.log_window.ensureCursorVisible()
        self.log_lines.append(f"[{timestamp}] {message}")
 
    def clear_log(self):
        self.log_window.clear()
        self.log_lines.clear()
        self.log("日志已清空")
 
    def update_gpu_info(self):
        if not HAS_GPUtil:
            self.lbl_gpu_info.setText("GPUtil未安装")
            return
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]
                usage_percent = (gpu.memoryUsed / gpu.memoryTotal) * 100 if gpu.memoryTotal > 0 else 0
                gpu_info = f"GPU: {gpu.name}\n显存: {gpu.memoryTotal}MB (已用: {gpu.memoryUsed}MB, {usage_percent:.1f}% | 可用: {gpu.memoryFree}MB)"
                self.lbl_gpu_info.setText(gpu_info)
            else:
                self.lbl_gpu_info.setText("未检测到独立显卡 (使用CPU)")
        except Exception as e:
            self.lbl_gpu_info.setText(f"GPU监控错误: {str(e)}")
 
    def update_file_count_label(self):
        font = QFont()
        font.setPointSize(11)
        self.lbl_file_count.setFont(font)
        count = self.file_list.count()
        if count == 0:
            self.lbl_file_count.setText("未添加文件")
        elif count == 1:
            item = self.file_list.item(0)
            if item:
                file_path = item.text()
                if file_path.lower().endswith('.pdf'):
                    try:
                        doc = fitz.open(file_path)
                        page_count = doc.page_count
                        doc.close()
                        self.lbl_file_count.setText(f"已添加 1 个文件，共 {page_count} 页")
                    except:
                        self.lbl_file_count.setText("已添加 1 个文件")
                else:
                    self.lbl_file_count.setText("已添加 1 个图片文件")
        else:
            self.lbl_file_count.setText(f"已添加 {count} 个文件 (批量模式)")
 
    def set_splitter_equal_width(self, splitter):
        total_width = splitter.width()
        if total_width > 0:
            splitter.setSizes([total_width // 2, total_width // 2])
        else:
            splitter.setSizes([500, 500])
 
    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择文件", "", "PDF Files (*.pdf);;Images (*.png *.jpg *.jpeg)")
        if files:
            self.file_list.addItems(files)
            self.input_files.extend(files)
            self.update_file_count_label()
            if len(files) == 1 and self.file_list.count() == 1:
                self.preview_source_file(self.file_list.item(0))
 
    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            count_before = self.file_list.count()
            for root, dirs, files in os.walk(folder):
                for f in files:
                    if f.lower().endswith('.pdf'):
                        full_path = os.path.join(root, f)
                        self.file_list.addItem(full_path)
                        self.input_files.append(full_path)
            if self.file_list.count() > count_before:
                self.update_file_count_label()
                if self.file_list.count() == 1:
                    self.preview_source_file(self.file_list.item(0))
 
    def browse_output_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if folder:
            self.txt_output_dir.setText(folder)
 
    def render_source_page(self, file_path, page_num):
        try:
            scroll_size = self.source_scroll.viewport().size()
            max_width = scroll_size.width() - 20
            max_height = scroll_size.height() - 20
            if file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
                pixmap = QPixmap(file_path)
                scaled_pixmap = pixmap.scaled(max_width, max_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.source_preview_label.setPixmap(scaled_pixmap)
                self.source_preview_label.setFixedSize(scaled_pixmap.size())
                self.source_preview_container.setFixedSize(scaled_pixmap.size())
                self.lbl_source_page.setText("1/1")
                self.source_total_pages = 1
                self.btn_source_prev.setEnabled(False)
                self.btn_source_next.setEnabled(False)
            elif file_path.lower().endswith('.pdf'):
                doc = fitz.open(file_path)
                self.source_total_pages = doc.page_count
                if page_num >= self.source_total_pages:
                    page_num = self.source_total_pages - 1
                if page_num < 0:
                    page_num = 0
                self.current_source_page = page_num
                page = doc.load_page(page_num)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(img)
                scaled_pixmap = pixmap.scaled(max_width, max_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.source_preview_label.setPixmap(scaled_pixmap)
                self.source_preview_label.setFixedSize(scaled_pixmap.size())
                self.source_preview_container.setFixedSize(scaled_pixmap.size())
                self.lbl_source_page.setText(f"{self.current_source_page + 1}/{self.source_total_pages}")
                self.btn_source_prev.setEnabled(self.current_source_page > 0)
                self.btn_source_next.setEnabled(self.current_source_page < self.source_total_pages - 1)
                doc.close()
        except Exception as e:
            self.source_preview_label.setText(f"无法预览文件:\n{str(e)}")
 
    def prev_source_page(self):
        if self.current_source_page > 0:
            self.current_source_page -= 1
            self.render_source_page(self.current_preview_file, self.current_source_page)
            if not self.chk_merge_files.isChecked():
                self.load_result_preview(self.current_preview_file)
 
    def next_source_page(self):
        if self.current_source_page < self.source_total_pages - 1:
            self.current_source_page += 1
            self.render_source_page(self.current_preview_file, self.current_source_page)
            if not self.chk_merge_files.isChecked():
                self.load_result_preview(self.current_preview_file)
 
    def preview_source_file(self, item):
        file_path = item.text()
        self.current_preview_file = file_path
        self.current_source_page = 0
        self.btn_convert_selected.setEnabled(True)
        self.log(f"预览源文件: {file_path}")
        self.render_source_page(file_path, 0)
        self.load_result_preview(file_path)
 
    def find_output_subdir(self, output_dir, base_name):
        """查找最匹配的输出目录，如果存在没有后缀的则优先返回，否则返回后缀最大的"""
        default_path = os.path.join(output_dir, base_name)
        if os.path.exists(default_path) and os.path.isdir(default_path):
            return default_path
            
        max_idx = -1
        for d in os.listdir(output_dir):
            full_d = os.path.join(output_dir, d)
            if os.path.isdir(full_d) and d.startswith(base_name + "-"):
                try:
                    idx = int(d.replace(base_name + "-", ""))
                    if idx > max_idx:
                        max_idx = idx
                except:
                    pass
        
        if max_idx > -1:
            return os.path.join(output_dir, f"{base_name}-{max_idx:02d}")
            
        return default_path
 
    def get_available_output_subdir(self, output_dir, base_name):
        """获取可用的输出子目录，避免覆盖"""
        subdir = os.path.join(output_dir, base_name)
        if not os.path.exists(subdir):
            return subdir
            
        counter = 1
        while True:
            subdir = os.path.join(output_dir, f"{base_name}-{counter:02d}")
            if not os.path.exists(subdir):
                return subdir
            counter += 1
 
    def load_result_preview(self, file_path):
        if not file_path:
            return
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        output_dir = self.txt_output_dir.text() if self.txt_output_dir.text() else os.path.dirname(file_path)
        
        target_subdir = self.find_output_subdir(output_dir, base_name)
        
        if self.chk_merge_files.isChecked():
            target_file = os.path.join(target_subdir, f"{base_name}.md")
            if os.path.exists(target_file):
                self.preview_result(target_file)
                return
        else:
            # 使用当前源文件页码匹配结果预览
            page_idx = self.current_source_page
            target_file = os.path.join(target_subdir, f"{base_name}_{page_idx}.md")
            if os.path.exists(target_file):
                self.preview_result(target_file)
                return
                
        self.result_preview.setHtml("<html><body style='background-color:#fff; color:#333;'><h3>识别结果预览</h3><p>该文件尚未转换或未找到转换结果。</p></body></html>")
 
    def start_conversion(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "提示", "已有任务在运行中...")
            return
        if self.file_list.count() == 0:
            QMessageBox.warning(self, "提示", "请先添加要转换的文件。")
            return
 
        self.log_lines = []
        files_to_process = []
        for i in range(self.file_list.count()):
            files_to_process.append(self.file_list.item(i).text())
 
        self._pending_files = list(files_to_process)
        self.btn_start.setEnabled(False)
        self.btn_convert_selected.setEnabled(False)
        self._process_next_file()
 
    def _process_next_file(self):
        if not self._pending_files:
            self.log("所有文件处理完成！")
            self.btn_start.setEnabled(True)
            self.btn_convert_selected.setEnabled(True)
            if self.current_preview_file:
                self.load_result_preview(self.current_preview_file)
            return
 
        file_path = self._pending_files.pop(0)
        self.log(f"开始处理文件: {os.path.basename(file_path)}")
        self.run_single_file_conversion(file_path)
 
    def run_single_file_conversion(self, file_path):
        script_path = self.txt_script_path.text().strip() or "tools/infer_doc.py"
        work_dir = self.txt_work_dir.text().strip() or None
        
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        source_dir = os.path.dirname(file_path)
        output_dir = self.txt_output_dir.text() if self.txt_output_dir.text() else source_dir
        
        # 获取避免覆盖的子目录
        effective_output_dir = self.get_available_output_subdir(output_dir, base_name)
 
        args = [sys.executable, script_path]
        args.extend(["--input_path", file_path])
        args.extend(["--output_path", effective_output_dir])
        
        if self.radio_gpu.isChecked():
            args.extend(["--gpus", "0"])
        else:
            args.extend(["--gpus", "-1"])
            
        if self.chk_save_img.isChecked():
            args.append("--is_save_vis_img")
        if self.chk_save_json.isChecked():
            args.append("--is_save_json")
        if self.chk_save_md.isChecked():
            args.append("--is_save_markdown")
            
        args.append("--pretty")
 
        self.worker = ODLWorker(args, cwd=work_dir, log_lines=self.log_lines)
        self.worker.log_signal.connect(self.log)
 
        def on_single_finished(success, msg):
            self.log(msg)
            if success:
                if self.chk_merge_files.isChecked() and os.path.exists(effective_output_dir):
                    self.merge_output_files(effective_output_dir, base_name)
                self.log(f"文件 {os.path.basename(file_path)} 处理成功")
            else:
                self.log(f"文件 {os.path.basename(file_path)} 处理失败: {msg}")
            
            self._process_next_file()
 
        self.worker.finished_signal.connect(on_single_finished)
        self.worker.start()
 
    def merge_output_files(self, target_dir, base_name):
        # 合并 MD
        if self.chk_save_md.isChecked():
            md_files = sorted([f for f in os.listdir(target_dir) if f.endswith('.md') and f != f"{base_name}.md"])
            if md_files:
                merged_path = os.path.join(target_dir, f"{base_name}.md")
                try:
                    with open(merged_path, 'w', encoding='utf-8') as outfile:
                        for filename in md_files:
                            with open(os.path.join(target_dir, filename), 'r', encoding='utf-8') as infile:
                                outfile.write(infile.read() + '\n\n')
                    self.log(f"已合并 MD 文件: {merged_path}")
                except Exception as e:
                    self.log(f"合并 MD 失败: {str(e)}")
 
        # 合并 JSON
        if self.chk_save_json.isChecked():
            json_files = sorted([f for f in os.listdir(target_dir) if f.endswith('.json') and f != f"{base_name}.json"])
            if json_files:
                merged_json_path = os.path.join(target_dir, f"{base_name}.json")
                try:
                    merged_data = []
                    for filename in json_files:
                        with open(os.path.join(target_dir, filename), 'r', encoding='utf-8') as infile:
                            data = json.load(infile)
                            if isinstance(data, list):
                                merged_data.extend(data)
                            else:
                                merged_data.append(data)
                    with open(merged_json_path, 'w', encoding='utf-8') as outfile:
                        json.dump(merged_data, outfile, ensure_ascii=False, indent=2)
                    self.log(f"已合并 JSON 文件: {merged_json_path}")
                except Exception as e:
                    self.log(f"合并 JSON 失败: {str(e)}")
 
    def convert_selected_file(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "提示", "已有任务在运行中...")
            return
        if not self.current_preview_file:
            QMessageBox.warning(self, "提示", "请先在文件列表中选择要转换的文件。")
            return
 
        self.log_lines = []
        self._pending_files = [self.current_preview_file]
        self.btn_start.setEnabled(False)
        self.btn_convert_selected.setEnabled(False)
        self._process_next_file()
 
    def preview_result(self, md_path):
        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
            line_count = len(md_content.split('\n'))
            self.result_total_pages = max(1, (line_count + 99) // 100)
            self.current_result_page = 1
            self.lbl_result_page.setText(f"{self.current_result_page}/{self.result_total_pages}")
 
            md_dir = os.path.dirname(os.path.abspath(md_path))
            md_base_name = os.path.splitext(os.path.basename(md_path))[0]
            clean_base_name = re.sub(r'[（(]page_[^）)]+[）)]', '', md_base_name).strip()
 
            def fix_image_path(match):
                img_src = match.group(1)
                if img_src.startswith(('http://', 'https://', 'file://', 'data:')):
                    return f'src="{img_src}"'
                
                # OpenOCR 图片通常保存在同目录的 imgs 文件夹下
                img_full_path = os.path.join(md_dir, img_src)
                if not os.path.exists(img_full_path):
                    img_filename = os.path.basename(img_src)
                    alt_path = os.path.join(md_dir, "imgs", img_filename)
                    if os.path.exists(alt_path):
                        img_full_path = alt_path
                        
                file_url = QUrl.fromLocalFile(os.path.normpath(img_full_path)).toString()
                return f'src="{file_url}"'
 
            html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])
            html_content = re.sub(r'src="([^"]*)"', fix_image_path, html_content)
 
            full_html = f"""
            <html>
            <head>
            <style>
                body {{ font-family: 'Microsoft YaHei', sans-serif; margin: 20px; line-height: 1.6; }}
                pre {{ background-color: #f4f4f4; padding: 10px; border-radius: 5px; overflow-x: auto; }}
                code {{ font-family: Consolas; background-color: #f4f4f4; padding: 2px 4px; border-radius: 3px; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                img {{ max-width: 100%; height: auto; }}
            </style>
            </head>
            <body>
            {html_content}
            </body>
            </html>
            """
            base_url = QUrl.fromLocalFile(md_dir + os.sep)
            self.result_preview.setHtml(full_html, base_url)
            self.log(f"已加载预览: {md_path}")
        except Exception as e:
            self.log(f"预览失败: {str(e)}")
 
    def open_output_folder(self):
        output_dir = self.txt_output_dir.text()
        if self.current_preview_file:
            base_name = os.path.splitext(os.path.basename(self.current_preview_file))[0]
            source_dir = os.path.dirname(self.current_preview_file)
            target_dir = output_dir if output_dir else source_dir
            sub_dir = self.find_output_subdir(target_dir, base_name)
            if os.path.exists(sub_dir):
                os.startfile(sub_dir)
                return
                
        if output_dir and os.path.exists(output_dir):
            os.startfile(output_dir)
            return
            
        QMessageBox.warning(self, "提示", "请先设置输出目录或选择一个文件。")
 
    def download_result(self):
        if not self.current_preview_file:
            return
        base_name = os.path.splitext(os.path.basename(self.current_preview_file))[0]
        source_dir = os.path.dirname(self.current_preview_file)
        output_dir = self.txt_output_dir.text() if self.txt_output_dir.text() else source_dir
        
        target_subdir = self.find_output_subdir(output_dir, base_name)
        src_path = None
        
        if self.chk_merge_files.isChecked():
            possible_paths = [
                os.path.join(target_subdir, f"{base_name}.md"),
            ]
        else:
            possible_paths = [
                os.path.join(target_subdir, f"{base_name}_{self.current_source_page}.md"),
                os.path.join(target_subdir, f"{base_name}.md"), # fallback
            ]
            
        for p in possible_paths:
            if os.path.exists(p):
                src_path = p
                break
                
        if not src_path:
            QMessageBox.warning(self, "错误", "未找到转换结果文件。")
            return
 
        default_save_name = f"{base_name}.md"
        save_path, _ = QFileDialog.getSaveFileName(self, "保存结果", default_save_name, "Markdown Files (*.md)")
        if save_path:
            try:
                shutil.copy(src_path, save_path)
                self.log(f"文件已保存至: {save_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", str(e))
 
if __name__ == '__main__':
    app = QApplication(sys.argv)
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)
    window = OpenOCRGUI()
    window.show()
    sys.exit(app.exec_())