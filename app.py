#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
截图OCR提取工具 - 单文件Flask应用
将截图上传，自动提取其中的中文和英文文本
"""

import os
import io
from flask import Flask, render_template_string, request, jsonify, send_file
from werkzeug.utils import secure_filename
from PIL import Image
import pytesseract

# 配置
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# 创建Flask应用
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# 确保上传目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# HTML模板（内嵌）
INDEX_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>截图OCR提取工具</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
        }
        .description {
            color: #666;
            margin-bottom: 30px;
        }
        .upload-area {
            border: 2px dashed #ccc;
            border-radius: 8px;
            padding: 40px;
            text-align: center;
            margin-bottom: 20px;
            cursor: pointer;
            transition: border-color 0.3s;
        }
        .upload-area:hover {
            border-color: #4CAF50;
        }
        .upload-area.dragover {
            border-color: #4CAF50;
            background-color: #f9fff9;
        }
        #fileInput {
            display: none;
        }
        .upload-btn {
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            transition: background-color 0.3s;
        }
        .upload-btn:hover {
            background-color: #45a049;
        }
        .upload-btn:disabled {
            background-color: #cccccc;
            cursor: not-allowed;
        }
        .preview {
            max-width: 100%;
            max-height: 300px;
            margin: 20px auto;
            display: block;
            border-radius: 4px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .result-area {
            margin-top: 30px;
            padding: 20px;
            background-color: #f9f9f9;
            border-radius: 4px;
            display: none;
        }
        .result-title {
            font-weight: bold;
            margin-bottom: 10px;
            color: #333;
        }
        .result-text {
            white-space: pre-wrap;
            word-wrap: break-word;
            background-color: white;
            padding: 15px;
            border-radius: 4px;
            border: 1px solid #ddd;
            max-height: 300px;
            overflow-y: auto;
            font-family: monospace;
        }
        .loading {
            display: none;
            text-align: center;
            margin: 20px 0;
        }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #4CAF50;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .error {
            color: #d32f2f;
            background-color: #ffebee;
            padding: 10px;
            border-radius: 4px;
            margin-top: 10px;
            display: none;
        }
        .supported-formats {
            color: #888;
            font-size: 14px;
            margin-top: 10px;
        }
        .copy-btn {
            background-color: #2196F3;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            margin-top: 10px;
            float: right;
        }
        .copy-btn:hover {
            background-color: #0b7dda;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📷 截图OCR提取工具</h1>
        <p class="description">上传截图，自动提取图片中的中文和英文文本。支持 PNG、JPG、JPEG、BMP 格式，最大 10MB。</p>

        <div class="upload-area" id="uploadArea">
            <div style="font-size: 48px; margin-bottom: 10px;">📁</div>
            <h3>点击选择文件或拖拽到此处</h3>
            <p class="supported-formats">支持格式: PNG, JPG, JPEG, BMP (最大 10MB)</p>
            <input type="file" id="fileInput" accept=".png,.jpg,.jpeg,.bmp">
            <br><br>
            <button class="upload-btn" id="uploadBtn" onclick="uploadFile()" disabled>上传并提取文字</button>
        </div>

        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>正在处理图像，提取文字中...</p>
        </div>

        <div class="error" id="error"></div>

        <img id="preview" class="preview">

        <div class="result-area" id="resultArea">
            <div class="result-title">提取的文字结果：</div>
            <button class="copy-btn" onclick="copyToClipboard()">📋 复制</button>
            <div class="result-text" id="resultText"></div>
        </div>
    </div>

    <script>
        const fileInput = document.getElementById('fileInput');
        const uploadArea = document.getElementById('uploadArea');
        const uploadBtn = document.getElementById('uploadBtn');
        const preview = document.getElementById('preview');
        const loading = document.getElementById('loading');
        const resultArea = document.getElementById('resultArea');
        const resultText = document.getElementById('resultText');
        const errorDiv = document.getElementById('error');

        let selectedFile = null;

        // 点击上传区域触发文件选择
        uploadArea.addEventListener('click', () => {
            fileInput.click();
        });

        // 拖拽功能
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            if (e.dataTransfer.files.length) {
                handleFileSelect(e.dataTransfer.files[0]);
            }
        });

        // 文件选择变化
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length) {
                handleFileSelect(e.target.files[0]);
            }
        });

        function handleFileSelect(file) {
            // 验证文件类型
            const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/bmp'];
            if (!validTypes.includes(file.type)) {
                showError('请选择有效的图像文件 (PNG, JPG, JPEG, BMP)');
                return;
            }

            // 验证文件大小 (10MB)
            if (file.size > 10 * 1024 * 1024) {
                showError('文件大小不能超过 10MB');
                return;
            }

            selectedFile = file;
            uploadBtn.disabled = false;

            // 显示预览
            const reader = new FileReader();
            reader.onload = (e) => {
                preview.src = e.target.result;
                preview.style.display = 'block';
                resultArea.style.display = 'none';
                errorDiv.style.display = 'none';
            };
            reader.readAsDataURL(file);
        }

        function uploadFile() {
            if (!selectedFile) return;

            const formData = new FormData();
            formData.append('file', selectedFile);

            // 显示加载状态
            loading.style.display = 'block';
            uploadBtn.disabled = true;
            errorDiv.style.display = 'none';

            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                loading.style.display = 'none';
                uploadBtn.disabled = false;

                if (data.success) {
                    resultText.textContent = data.text;
                    resultArea.style.display = 'block';
                    // 滚动到结果区域
                    resultArea.scrollIntoView({ behavior: 'smooth' });
                } else {
                    showError(data.error || '提取文字失败');
                }
            })
            .catch(error => {
                loading.style.display = 'none';
                uploadBtn.disabled = false;
                showError('网络错误: ' + error.message);
            });
        }

        function showError(message) {
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
        }

        function copyToClipboard() {
            const text = resultText.textContent;
            navigator.clipboard.writeText(text).then(() => {
                alert('已复制到剪贴板！');
            }).catch(err => {
                console.error('复制失败: ', err);
            });
        }
    </script>
</body>
</html>
"""

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_image(image_path):
    """
    从图像中提取中英文文本
    使用Tesseract OCR，语言设置为中文+英文
    """
    try:
        # 打开图像
        img = Image.open(image_path)

        # 如果图像有透明通道，转换为RGB
        if img.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                background.paste(img, mask=img.split()[-1])
            else:
                background.paste(img, mask=img)
            img = background

        # 使用Tesseract提取文本
        # 尝试中英文混合识别，如果失败则只使用英文
        try:
            text = pytesseract.image_to_string(img, lang='chi_sim+eng')
        except:
            # 如果中文语言包未安装，回退到英文
            text = pytesseract.image_to_string(img, lang='eng')

        return text.strip()
    except Exception as e:
        raise Exception(f"OCR处理失败: {str(e)}")

@app.route('/')
def index():
    """首页"""
    return render_template_string(INDEX_HTML)

@app.route('/upload', methods=['POST'])
def upload_file():
    """处理文件上传和OCR提取"""
    # 检查是否有文件
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '没有选择文件'})

    file = request.files['file']

    # 检查文件名
    if file.filename == '':
        return jsonify({'success': False, 'error': '没有选择文件'})

    # 检查文件类型
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': '不支持的文件格式，请上传PNG、JPG、JPEG或BMP格式'})

    try:
        # 保存上传的文件
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # 提取文本
        extracted_text = extract_text_from_image(filepath)

        # 删除临时文件
        try:
            os.remove(filepath)
        except:
            pass

        if not extracted_text:
            return jsonify({'success': False, 'error': '未检测到文字，请确认图片包含可识别的中英文文本'})

        return jsonify({'success': True, 'text': extracted_text})

    except Exception as e:
        # 清理临时文件
        try:
            if 'filepath' in locals():
                os.remove(filepath)
        except:
            pass

        return jsonify({'success': False, 'error': str(e)})

@app.route('/health')
def health_check():
    """健康检查端点"""
    return jsonify({'status': 'ok', 'service': 'screenshot-ocr-tool'})

if __name__ == '__main__':
    # 检查Tesseract是否可用
    try:
        pytesseract.get_tesseract_version()
        print("✓ Tesseract OCR 检测成功")
    except Exception as e:
        print("⚠ 警告: Tesseract OCR 未安装或未在PATH中")
        print("  请安装 Tesseract OCR: https://github.com/tesseract-ocr/tesseract")
        print("  并确保已安装中文语言包 (chi_sim)")

    print("🚀 启动截图OCR提取工具...")
    print("🌐 请在浏览器中访问: http://127.0.0.1:5000")
    print("📌 按 Ctrl+C 停止服务")

    # 启动Flask应用
    app.run(debug=True, host='127.0.0.1', port=5000)