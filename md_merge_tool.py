"""
MD文件合并工具
- 打开文件夹，自动扫描里面的md文件
- 按自然顺序（0, 1, 2, ...）合并
- 输出：文件夹名_all.md
- 支持移除选中文件
"""
import sys
import os
from natsort import natsorted
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QMessageBox, QListWidget, QFileDialog)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt


class MDMergeTool(QWidget):
    def __init__(self):
        super().__init__()
        self.current_folder = ""
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("MD文件合并工具")
        self.setMinimumWidth(500)
        self.resize(550, 800)

        layout = QVBoxLayout()

        # 文件夹选择
        folder_layout = QHBoxLayout()
        self.lbl_folder = QLabel("未选择文件夹")
        self.lbl_folder.setStyleSheet("color: #666; padding: 5px;")
        self.btn_select_folder = QPushButton("选择文件夹")
        self.btn_select_folder.setStyleSheet("background-color: #2196F3; color: white; height: 35px;")
        self.btn_select_folder.clicked.connect(self.select_folder)
        folder_layout.addWidget(QLabel("文件夹:"))
        folder_layout.addWidget(self.lbl_folder, 1)
        folder_layout.addWidget(self.btn_select_folder)
        layout.addLayout(folder_layout)

        # 文件列表
        list_label_layout = QHBoxLayout()
        list_label = QLabel("待合并文件列表 (点击选中后可移除):")
        list_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        list_label_layout.addWidget(list_label)
        list_label_layout.addStretch()
        layout.addLayout(list_label_layout)

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.MultiSelection)
        self.file_list.setStyleSheet("font-family: Consolas; background-color: #f5f5f5;")
        layout.addWidget(self.file_list, 1)

        # 按钮区域 - 第一行
        action_btn_layout = QHBoxLayout()
        self.btn_remove = QPushButton("移除选中")
        self.btn_remove.setEnabled(False)
        self.btn_remove.setStyleSheet("background-color: #f44336; color: white; height: 35px;")
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_clear = QPushButton("清空列表")
        self.btn_clear.setStyleSheet("background-color: #666; color: white; height: 35px;")
        self.btn_clear.clicked.connect(self.clear_list)
        action_btn_layout.addWidget(self.btn_remove)
        action_btn_layout.addWidget(self.btn_clear)
        layout.addLayout(action_btn_layout)

        # 合并按钮 - 单独一行
        self.btn_merge = QPushButton("合并文件")
        self.btn_merge.setEnabled(False)
        self.btn_merge.setStyleSheet("background-color: #4CAF50; color: white; height: 45px; font-weight: bold; font-size: 20px;")
        self.btn_merge.clicked.connect(self.merge_files)
        layout.addWidget(self.btn_merge)

        # 输出信息
        self.lbl_output = QLabel("")
        self.lbl_output.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(self.lbl_output)

        self.setLayout(layout)

        # 连接列表选择变化事件
        self.file_list.itemSelectionChanged.connect(self.on_selection_changed)

    def on_selection_changed(self):
        has_selection = len(self.file_list.selectedItems()) > 0
        self.btn_remove.setEnabled(has_selection and self.file_list.count() > 0)

    def clear_list(self):
        self.file_list.clear()
        self.found_md_files = []
        self.btn_merge.setEnabled(False)
        self.btn_remove.setEnabled(False)
        self.lbl_output.setText("列表已清空")

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择包含MD文件的文件夹")
        if folder:
            self.current_folder = folder
            self.lbl_folder.setText(folder)
            self.scan_and_load(folder)

    def scan_and_load(self, folder):
        self.file_list.clear()
        folder_name = os.path.basename(folder.rstrip(os.sep))

        # 查找所有md文件，排除已经合并的文件
        md_files = [f for f in os.listdir(folder)
                    if f.endswith('.md') and not f.endswith('_all.md')]

        if not md_files:
            self.lbl_output.setText("该文件夹中没有找到MD文件")
            self.btn_merge.setEnabled(False)
            self.btn_remove.setEnabled(False)
            return

        # 自然排序
        md_files = natsorted(md_files)
        self.found_md_files = md_files

        # 添加到列表
        self.file_list.addItems(md_files)
        self.btn_merge.setEnabled(True)
        self.btn_remove.setEnabled(False)
        self.lbl_output.setText(f"合并后输出: {folder_name}_all.md (共 {len(md_files)} 个文件)")

    def remove_selected(self):
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            return

        # 获取选中项的文本
        selected_texts = [item.text() for item in selected_items]

        # 从列表和文件列表中移除
        for item in selected_items:
            row = self.file_list.row(item)
            self.file_list.takeItem(row)

        # 更新文件列表
        self.found_md_files = [f for f in self.found_md_files if f not in selected_texts]

        folder_name = os.path.basename(self.current_folder.rstrip(os.sep))
        count = len(self.found_md_files)
        self.lbl_output.setText(f"合并后输出: {folder_name}_all.md (共 {count} 个文件)")

        # 如果列表为空，禁用合并按钮
        if count == 0:
            self.btn_merge.setEnabled(False)
            self.btn_remove.setEnabled(False)
            self.lbl_output.setText("没有文件可合并")

    def merge_files(self):
        if not self.current_folder or not hasattr(self, 'found_md_files') or not self.found_md_files:
            return

        folder = self.current_folder
        folder_name = os.path.basename(folder.rstrip(os.sep))
        output_file = os.path.join(folder, f"{folder_name}_all.md")

        try:
            with open(output_file, 'w', encoding='utf-8') as outfile:
                for filename in self.found_md_files:
                    filepath = os.path.join(folder, filename)
                    with open(filepath, 'r', encoding='utf-8') as infile:
                        outfile.write(infile.read() + '\n\n')

            QMessageBox.information(
                self,
                "合并成功",
                f"已成功合并 {len(self.found_md_files)} 个文件\n\n"
                f"输出文件: {output_file}"
            )
        except Exception as e:
            QMessageBox.critical(self, "合并失败", f"合并文件时发生错误:\n{str(e)}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))
    window = MDMergeTool()
    window.show()
    sys.exit(app.exec_())
