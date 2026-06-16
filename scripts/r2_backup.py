#!/usr/bin/env python3
"""
Cloudflare R2 备份脚本 - 打包版
将 AUTO-STOCK 文件夹打包成一个 .tar.gz 上传到 R2
节省 A 类操作次数(从17000次降到1次)
"""

import os
import sys
import datetime
import hashlib
import requests
import tarfile
import tempfile
from pathlib import Path

# ==================== 配置 ====================
SOURCE_DIR = "/home/admin/AUTO-STOCK"
BUCKET = "stock"

# 排除不需要备份的目录
EXCLUDE_DIRS = {
    'venv',
    'node_modules',
    '__pycache__',
    '.git',
    '.claude',
    '.vscode',
    'dist',
}

# 排除不需要备份的文件模式
EXCLUDE_PATTERNS = [
    '*.pyc',
    '*.pyo',
    '*.log',
    '.DS_Store',
}
ACCOUNT_ID = "4a5ad40871345e9e5390407ad8d8258e"
API_TOKEN = "cfat_1IqcN8DaTYJNoSFMYoSBBe2rhucGzrfiUzkIqsTJbaea742b"

# API URL
API_BASE = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/r2/buckets/{BUCKET}/objects"

# 日志
LOG_FILE = "/home/admin/logs/r2-backup.log"

# ==================== 函数 ====================
def log(msg):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    Path("/home/admin/logs").mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def should_exclude(path):
    """检查路径是否应该被排除"""
    parts = Path(path).parts
    for part in parts:
        if part in EXCLUDE_DIRS:
            return True
    for pattern in EXCLUDE_PATTERNS:
        if Path(path).match(pattern):
            return True
    return False

def create_tarball(source_dir):
    """创建 tar.gz 打包文件"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    tarball_name = f"auto-stock-backup_{timestamp}.tar.gz"
    tarball_path = f"/tmp/{tarball_name}"

    log(f"Creating archive: {tarball_name}")

    file_count = 0
    with tarfile.open(tarball_path, "w:gz") as tar:
        for root, dirs, files in os.walk(source_dir):
            # 排除目录（原地修改dirs可以阻止os.walk进入这些目录）
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for file in files:
                file_path = os.path.join(root, file)
                if should_exclude(file_path):
                    continue
                arcname = os.path.relpath(file_path, source_dir)
                tar.add(file_path, arcname=arcname)
                file_count += 1

    size = os.path.getsize(tarball_path)
    log(f"Archive created: {tarball_name} ({size / 1024 / 1024:.1f} MB, {file_count} files)")

    return tarball_path

def upload_file(local_path, remote_key):
    """上传单个文件到 R2"""
    url = f"{API_BASE}/{remote_key}"

    try:
        with open(local_path, 'rb') as f:
            data = f.read()

        resp = requests.put(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {API_TOKEN}",
                "Content-Type": "application/gzip",
            },
            timeout=300  # 大文件给更长超时
        )

        result = resp.json()
        if result.get("success"):
            return True, None
        else:
            return False, result.get('errors', [{'message': 'unknown'}])[0].get('message')

    except Exception as e:
        return False, str(e)

def delete_old_backup(backup_name):
    """删除旧的备份文件"""
    url = f"{API_BASE}/{backup_name}"

    try:
        resp = requests.delete(
            url,
            headers={"Authorization": f"Bearer {API_TOKEN}"},
            timeout=30
        )

        if resp.status_code in [200, 204, 404]:
            log(f"Deleted old backup: {backup_name}")
            return True
        else:
            log(f"Failed to delete old backup: {resp.status_code}")
            return False
    except Exception as e:
        log(f"Error deleting old backup: {e}")
        return False

def list_backups():
    """列出 R2 中的备份文件"""
    url = f"{API_BASE}?prefix=auto-stock-backup_"

    try:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {API_TOKEN}"},
            timeout=30
        )

        result = resp.json()
        if result.get("success"):
            objects = result.get("result", [])
            return [obj.get("key") for obj in objects if obj.get("key")]
        return []
    except:
        return []

def main():
    log("=" * 60)
    log("R2 Backup Started (archive mode)")
    log(f"Source: {SOURCE_DIR}")

    # 列出旧备份
    old_backups = list_backups()
    if old_backups:
        log(f"Found {len(old_backups)} old backup(s): {old_backups}")

    # 创建打包文件
    tarball_path = create_tarball(SOURCE_DIR)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"auto-stock-backup_{timestamp}.tar.gz"

    # 上传
    log(f"Uploading to R2: {backup_name}...")
    success, err = upload_file(tarball_path, backup_name)

    # 上传后根据结果决定是否清理本地文件
    if success:
        log(f"Upload successful!")

        # 删除旧备份(只保留最新一个)
        for old in old_backups:
            delete_old_backup(old)

        # 删除本地临时文件(上传成功后才删)
        try:
            os.remove(tarball_path)
            log("Cleaned up local archive")
        except:
            pass

        log("=" * 60)
        log("Backup completed successfully!")
    else:
        # 上传失败,保留本地备份,不删除旧备份
        log(f"Upload failed: {err}")
        log(f"Local archive kept at: {tarball_path} (not deleted)")
        log("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()