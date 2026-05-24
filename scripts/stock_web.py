#!/usr/bin/env python3
"""
股票报告 Web 服务 - Flask 集成版
整合报告生成 API，替代独立的 report_api.py
"""

import os
import sys
import json
import subprocess
import threading
import time
from datetime import datetime
from flask import Flask, jsonify, request, Response, send_from_directory
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# 配置
REPORT_DIR = "/home/admin/AUTO-STOCK/reports/individual"
SCRIPT_PATH = "/home/admin/AUTO-STOCK/scripts/stock_analysis.py"
CACHE_FILE = os.path.join(REPORT_DIR, "generated_at.json")
DAILY_REPORT_DIR = "/home/admin/AUTO-STOCK/reports"

# 线程池（限制并发数）
executor = ThreadPoolExecutor(max_workers=4)

# 任务状态追踪
task_status = {}  # {code: {'status': 'pending|generating|completed|failed', 'start_time': ..., 'end_time': ...}}


def generate_report(code):
    """生成个股报告"""
    task_status[code] = {'status': 'generating', 'start_time': datetime.now().isoformat()}
    
    try:
        result = subprocess.run(
            ["python3", SCRIPT_PATH, code],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            task_status[code] = {
                'status': 'completed',
                'start_time': task_status[code]['start_time'],
                'end_time': datetime.now().isoformat()
            }
            return True
        else:
            task_status[code] = {
                'status': 'failed',
                'start_time': task_status[code]['start_time'],
                'end_time': datetime.now().isoformat(),
                'error': result.stderr[:500]
            }
            return False
    except Exception as e:
        task_status[code] = {
            'status': 'failed',
            'start_time': task_status[code]['start_time'],
            'end_time': datetime.now().isoformat(),
            'error': str(e)
        }
        return False


@app.route('/api/generate', methods=['POST'])
def generate():
    """生成报告 API"""
    data = request.get_json() or {}
    code = data.get('code', '')
    
    if not code or len(code) != 6:
        return jsonify({'error': 'Invalid stock code'}), 400
    
    report_path = os.path.join(REPORT_DIR, f"stock_analysis_{code}.html")
    
    # 如果报告已存在，直接返回
    if os.path.exists(report_path):
        return jsonify({
            'status': 'exists',
            'url': f'/reports/individual/stock_analysis_{code}.html',
            'message': '报告已存在'
        })
    
    # 如果已有任务在处理，返回排队状态
    if code in task_status and task_status[code]['status'] == 'generating':
        return jsonify({
            'status': 'pending',
            'message': '报告正在生成中，请稍候'
        })
    
    # 启动后台任务
    executor.submit(generate_report, code)
    
    return jsonify({
        'status': 'generating',
        'message': '报告生成中，请稍后刷新页面或等待自动跳转'
    })


@app.route('/api/status/<code>', methods=['GET'])
def status(code):
    """查询报告生成状态"""
    report_path = os.path.join(REPORT_DIR, f"stock_analysis_{code}.html")
    
    if os.path.exists(report_path):
        return jsonify({
            'status': 'ready',
            'url': f'/reports/individual/stock_analysis_{code}.html'
        })
    
    if code in task_status:
        return jsonify({
            'status': task_status[code]['status'],
            'message': task_status[code].get('message', '生成中')
        })
    
    return jsonify({'status': 'not_started'})


@app.route('/api/sse/<code>')
def sse(code):
    """Server-Sent Events - 实时推送状态更新"""
    def event_stream():
        # 发送初始状态
        yield f"data: {json.dumps({'event': 'status', 'status': 'checking'})}\n\n"
        
        # 轮询检查，最多 60 秒
        for i in range(60):
            report_path = os.path.join(REPORT_DIR, f"stock_analysis_{code}.html")
            
            if os.path.exists(report_path):
                yield f"data: {json.dumps({'event': 'complete', 'url': f'/reports/individual/stock_analysis_{code}.html'})}\n\n"
                break
            
            # 检查任务状态
            if code in task_status:
                status = task_status[code]['status']
                if status == 'failed':
                    error = task_status[code].get('error', '未知错误')
                    yield f"data: {json.dumps({'event': 'error', 'message': error})}\n\n"
                    break
            
            # 每秒发送一次心跳
            yield f"data: {json.dumps({'event': 'progress', 'progress': min(i+1, 100)})}\n\n"
            time.sleep(1)
        else:
            yield f"data: {json.dumps({'event': 'timeout', 'message': '生成超时，请手动刷新'})}\n\n"
    
    return Response(event_stream(), mimetype='text/event-stream')


@app.route('/api/daily', methods=['GET'])
def daily_report():
    """获取最新日报"""
    # 查找最新的日报文件
    files = [f for f in os.listdir(DAILY_REPORT_DIR) if f.startswith('daily_report_') and f.endswith('.html')]
    if not files:
        return jsonify({'error': 'No daily report found'}), 404
    
    # 按日期排序，取最新的
    files.sort(reverse=True)
    latest = files[0]
    
    return jsonify({
        'file': latest,
        'url': f'/reports/{latest}'
    })


@app.route('/reports/<path:filename>')
def serve_report(filename):
    """Serve 报告文件"""
    return send_from_directory(DAILY_REPORT_DIR, filename)


@app.route('/reports/individual/<path:filename>')
def serve_individual_report(filename):
    """Serve 个股报告文件"""
    return send_from_directory(REPORT_DIR, filename)


@app.route('/')
def index():
    """首页"""
    return jsonify({
        'service': '股票报告生成服务',
        'version': '2.0 (Flask 集成版)',
        'endpoints': {
            'POST /api/generate': '生成个股报告',
            'GET /api/status/<code>': '查询报告状态',
            'GET /api/sse/<code>': 'SSE 实时推送',
            'GET /api/daily': '获取最新日报',
            'GET /reports/<filename>': '获取日报文件',
            'GET /reports/individual/<filename>': '获取个股报告文件'
        }
    })


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    print(f"🚀 股票报告 Web 服务启动在 http://0.0.0.0:{port}")
    print(f"📊 报告目录: {REPORT_DIR}")
    print(f"📝 脚本路径: {SCRIPT_PATH}")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)