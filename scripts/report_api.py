#!/usr/bin/env python3
"""
股票报告生成接口
支持POST生成+SSE进度推送
"""

import os
import json
import subprocess
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

REPORT_DIR = "/home/admin/AUTO-STOCK/reports/individual"
SCRIPT_PATH = "/home/admin/AUTO-STOCK/scripts/stock_analysis.py"
PROGRESS_FILE = "/tmp/stock_analysis_progress_{code}.json"
LOCK_FILE = "/tmp/generating_{code}.lock"
CACHE_FILE = "/home/admin/AUTO-STOCK/reports/individual/generated_at.json"

def get_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def generate_report(code):
    """生成个股报告"""
    cache = get_cache()
    today = datetime.now().strftime('%Y-%m-%d')
    if cache.get(code) == today:
        report_file = os.path.join(REPORT_DIR, f"stock_analysis_{code}.html")
        if os.path.exists(report_file):
            return True  # 今天已生成，跳过
    try:
        result = subprocess.run(
            ["python3", SCRIPT_PATH, code],
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Error: {e}")
        return False

def read_progress(code):
    """读取进度"""
    pf = PROGRESS_FILE.replace("{code}", code)
    if os.path.exists(pf):
        try:
            with open(pf, 'r') as f:
                return json.load(f)
        except:
            pass
    return None

class ReportHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b''
        
        try:
            data = json.loads(body) if body else {}
            code = data.get('code', '')
        except:
            code = ''
        
        if not code or len(code) != 6:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Invalid code'}).encode())
            return
        
        # 检查缓存（是否今天已生成）
        cache = get_cache()
        today = datetime.now().strftime('%Y-%m-%d')
        if cache.get(code) == today:
            report_file = os.path.join(REPORT_DIR, f"stock_analysis_{code}.html")
            if os.path.exists(report_file):
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'status': 'exists',
                    'url': f'/reports/individual/stock_analysis_{code}.html'
                }).encode())
                return

        # 锁存在说明另一个请求正在生成，直接返回 generating
        lock_path = LOCK_FILE.replace("{code}", code)
        if os.path.exists(lock_path):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'generating'}).encode())
            return

        # 启动后台生成任务
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'status': 'generating'}).encode())

        # 创建锁文件，防止并发重复生成
        lock_path = LOCK_FILE.replace("{code}", code)
        open(lock_path, 'w').close()

        def safe_generate():
            try:
                generate_report(code)
            finally:
                if os.path.exists(lock_path):
                    os.remove(lock_path)

        thread = threading.Thread(target=safe_generate)
        thread.start()
    
    def do_GET(self):
        if self.path.startswith('/api/generate_report'):
            code = self.path.split('/api/generate_report?code=')[-1].strip('/')
            if not code or len(code) != 6:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Invalid code'}).encode())
                return
            
            report_file = os.path.join(REPORT_DIR, f"stock_analysis_{code}.html")
            lock_path = LOCK_FILE.replace("{code}", code)

            # 锁存在，说明另一个请求正在生成中，等它完成
            if os.path.exists(lock_path):
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'generating'}).encode())
                return

            if os.path.exists(report_file):
                # 文件存在但检查缓存日期
                cache = get_cache()
                today = datetime.now().strftime('%Y-%m-%d')
                if cache.get(code) == today:
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'status': 'exists', 'url': f'/reports/individual/stock_analysis_{code}.html'}).encode())
                else:
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'status': 'regenerating'}).encode())
                    lock_path = LOCK_FILE.replace("{code}", code)
                    open(lock_path, 'w').close()
                    def safe_regen():
                        try:
                            generate_report(code)
                        finally:
                            if os.path.exists(lock_path):
                                os.remove(lock_path)
                    thread = threading.Thread(target=safe_regen)
                    thread.start()
            else:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'generating'}).encode())
                lock_path = LOCK_FILE.replace("{code}", code)
                open(lock_path, 'w').close()
                def safe_gen():
                    try:
                        generate_report(code)
                    finally:
                        if os.path.exists(lock_path):
                            os.remove(lock_path)
                thread = threading.Thread(target=safe_gen)
                thread.start()
            return
        
        if self.path.startswith('/api/sse/'):
            code = self.path.split('/api/sse/')[-1].strip('/')
            if not code or len(code) != 6:
                self.send_response(400)
                self.end_headers()
                return
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            self.wfile.write(b'data: {"event": "progress", "progress": 0, "message": "Starting..."}\n\n')

            try:
                report_file = os.path.join(REPORT_DIR, f"stock_analysis_{code}.html")

                # 如果不存在，启动生成
                if not os.path.exists(report_file):
                    thread = threading.Thread(target=generate_report, args=(code,))
                    thread.start()

                # 读取真实进度 (最多120秒)
                for i in range(1, 121):
                    time.sleep(1)

                    if os.path.exists(report_file):
                        progress_data = read_progress(code)
                        progress = 100
                        msg_str = "完成"
                        if progress_data:
                            progress = progress_data.get("progress", 100)
                            msg_str = progress_data.get("message", "完成")
                        msg = json.dumps({"event": "complete", "progress": progress, "message": msg_str})
                        self.wfile.write(f"data: {msg}\n\n".encode())

                        url = f"/reports/individual/stock_analysis_{code}.html"
                        self.wfile.write(f'data: {{"event": "complete", "url": "{url}"}}\n\n'.encode())
                        break
                    else:
                        progress_data = read_progress(code)
                        if progress_data:
                            progress = progress_data.get("progress", 5)
                            msg_str = progress_data.get("message", "Generating...")
                            msg = json.dumps({"event": "progress", "progress": progress, "message": msg_str})
                        else:
                            progress = 5
                            msg = json.dumps({"event": "progress", "progress": progress, "message": "Generating..."})
                        self.wfile.write(f"data: {msg}\n\n".encode())
            except Exception as e:
                pass
            return
        
        self.send_response(404)
        self.end_headers()
    
    def log_message(self, format, *args):
        pass

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8766), ReportHandler)
    print("API started on port 8766")
    server.serve_forever()
