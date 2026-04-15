# OpenOCR-GUI

![界面](GUI.png)


https://github.com/Topdu/OpenOCR/tree/main  的分支，OpenOCR 文档识别转换工具的图形化界面程序，支持批量处理 PDF 文件和图片，将其转换为 Markdown、JSON 以及可视化识别结果。

原本OpenOCR是我用过的所有OCR中效果最好的（用过热门的10几个ocr项目了）所以做了这个GUI，介绍见https://github.com/Topdu/OpenOCR/blob/main/README_ch.md

模型下载：https://www.modelscope.cn/models/topdktu/unirec-0.1b/files

## 功能特点

- **多格式支持**：处理 PDF 文件和图片（PNG、JPG、JPEG）
- **批量处理**：可添加多个文件或整个文件夹进行批量转换
- **GPU 加速**：支持 GPU 加速模式（实时监控显卡状态）
- **多种输出格式**：
  - Markdown (.md) - 完整文档文本，保留格式
  - JSON (.json) - 结构化数据输出
  - 图片 (.png) - 可视化识别结果
- **文件合并**：可将多页文档合并为单一输出文件
- **实时预览**：
  - 源文件预览，支持翻页导航
  - Markdown 渲染结果实时预览
- **硬件监控**：实时显示 GPU 显存和使用情况
- **处理日志**：详细记录转换过程，含时间戳

## 环境要求

- Python 3.7+
- OpenOCR 项目（https://github.com/opendatalab/OpenOCR）

## 安装说明

### 1. 环境准备

建议使用conda新建环境：

```bash
conda create -n openocr python=3.10 -y
```

### 2. 安装 OpenOCR 依赖

下载并安装OpenOCR 项目：

```bash
git clone https://github.com/yifenk03/OpenOCR-GUI.git
cd OpenOCR
pip install -r requirements.txt
```

### 3. 运行程序

```bash
python OpenOCR-GUI.py
```

## 依赖说明

| 包名 | 版本要求 | 说明 |
|------|----------|------|
| PyQt5 | >=5.15.0 | 图形界面框架 |
| PyQtWebEngine | >=5.15.0 | Markdown 预览渲染引擎 |
| PyMuPDF | >=1.18.0 | PDF 文件处理 |
| markdown | >=3.3.0 | Markdown 转 HTML 转换 |
| GPUtil | >=1.4.0 | GPU 监控（可选） |

## 使用指南

### 基本操作流程

1. **添加文件**：点击「添加文件」或「添加文件夹」选择要处理的文档
2. **配置设置**：
   - 设置 OpenOCR 脚本路径（默认：`tools/infer_doc.py`）
   - 设置 OpenOCR 工作目录
   - 选择运行设备（GPU/CPU）
   - 选择输出格式选项
3. **设置输出目录**（可选）：默认为源文件所在目录
4. **开始转换**：点击「转换全部」转换所有文件，或选中特定文件后点击「转换所选文件」
5. **预览结果**：在右侧面板查看 Markdown 渲染效果

### 设置项说明

- **脚本路径**：OpenOCR 推理脚本的路径
- **工作目录**：OpenOCR 项目根目录
- **设备模式**：GPU（推荐）或 CPU
- **保存选项**：
  - 识别图片：保存可视化识别结果
  - JSON：保存结构化 JSON 数据
  - Markdown：保存 Markdown 文本
- **整合成一个文件**：将多页文档合并为单一文件

### 预览功能

- **源文件预览**：左侧面板显示原始文档页面
- **结果预览**：右侧面板显示渲染后的 Markdown（含图片）
- **翻页导航**：使用「上一页」「下一页」按钮浏览多页文档


## 常见问题

### GPU 未检测到

- 请确保已正确安装 NVIDIA 显卡驱动
- 安装 GPUtil：`pip install GPUtil`
- 如 GPU 监控失败，程序仍可正常运行，只是不会显示 GPU 状态

### PDF 预览异常

- 请确认 PyMuPDF 已正确安装：`pip install PyMuPDF`
- 较大的 PDF 文件可能需要稍等片刻加载

### 转换失败

- 确认 OpenOCR 脚本路径设置正确
- 确保 OpenOCR 工作目录包含所需依赖文件
- 查看处理日志获取详细错误信息

## 相关项目

- [OpenOCR](https://github.com/Topdu/OpenOCR) - 开源文档识别工具

## 致谢

- 图形界面框架：[PyQt5](https://www.riverbankcomputing.com/software/pyqt/)
- PDF 处理：[PyMuPDF](https://pymupdf.readthedocs.io/)
- Markdown 渲染：[Python-Markdown](https://python-markdown.github.io/)
