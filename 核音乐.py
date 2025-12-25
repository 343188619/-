import webview
import os
import sys
import shutil
import time
import threading
from urllib.request import urlretrieve
from urllib.error import URLError
import logging
import re
import asyncio
import json
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# ================= 配置与常量 =================
APP_NAME = "Core Music"
INSTALL_DIR_NAME = "CoreMusicPlayer"
SHORTCUT_NAME = "Core Music.lnk"
VERSION = "1.0.3"
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".CoreMusic", "config.json")

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.expanduser("~"), "CoreMusic.log"), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ================= 配置管理 =================
def load_config():
    """加载配置文件"""
    config_dir = os.path.dirname(CONFIG_FILE)
    if not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
    
    # 默认配置
    return {
        "version": VERSION,
        "shortcut_created": False,
        "shortcut_path": None,
        "skip_install": False
    }

def save_config(config):
    """保存配置文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        return False

# ================= HTML 模板 =================

# 安装页面 - 让用户选择创建快捷方式的位置
INSTALLER_HTML = r"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { margin: 0; padding: 0; height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center; background: #000; color: #fff; font-family: -apple-system, BlinkMacSystemFont, sans-serif; overflow: hidden; user-select: none; }
        .container { text-align: center; animation: fadeIn 1s ease; width: 420px; max-width: 90vw; }
        .logo { width: 80px; height: 80px; background: linear-gradient(135deg, #007aff, #00c6ff); border-radius: 20px; margin: 0 auto 20px; box-shadow: 0 0 30px rgba(0, 122, 255, 0.4); display: flex; align-items: center; justify-content: center; }
        .logo svg { width: 40px; height: 40px; color: white; }
        h1 { font-size: 24px; font-weight: 600; margin-bottom: 10px; letter-spacing: -0.5px; }
        p { color: #888; font-size: 14px; margin-bottom: 25px; min-height: 20px; text-align: center; }

        .install-options { width: 100%; margin: 30px 0; }
        .option-card { background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 20px; margin: 15px 0; cursor: pointer; transition: all 0.3s ease; display: flex; align-items: center; gap: 15px; }
        .option-card:hover { background: rgba(0, 122, 255, 0.1); border-color: #007aff; transform: translateY(-2px); }
        .option-card.selected { background: rgba(0, 122, 255, 0.15); border-color: #007aff; box-shadow: 0 0 20px rgba(0, 122, 255, 0.2); }
        .option-icon { width: 40px; height: 40px; background: rgba(0, 122, 255, 0.2); border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
        .option-icon svg { width: 24px; height: 24px; color: #007aff; }
        .option-content { flex: 1; text-align: left; }
        .option-title { font-weight: 600; font-size: 16px; margin-bottom: 5px; }
        .option-desc { color: #aaa; font-size: 12px; line-height: 1.4; }

        .install-btn { background: #007aff; color: white; border: none; padding: 14px 40px; border-radius: 12px; font-size: 16px; font-weight: 600; cursor: pointer; transition: 0.3s; margin-top: 20px; width: 100%; }
        .install-btn:hover { background: #0056cc; transform: scale(1.02); }
        .install-btn:disabled { background: #333; color: #666; cursor: not-allowed; transform: none; }

        .skip-link { color: #888; font-size: 13px; margin-top: 15px; cursor: pointer; text-decoration: underline; }
        .skip-link:hover { color: #aaa; }

        .status { margin-top: 20px; font-size: 13px; color: #888; min-height: 20px; }

        @keyframes fadeIn { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
        @keyframes pulse { 0%, 100% { opacity: 0.6; } 50% { opacity: 1; } }
        .installing { animation: pulse 1.5s infinite; }

        .version { position: fixed; bottom: 10px; right: 10px; font-size: 10px; color: #333; opacity: 0.5; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">
            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/></svg>
        </div>
        <h1>CORE · 核心音乐</h1>
        <p>选择快捷方式创建位置 (可跳过)</p>

        <div class="install-options">
            <div class="option-card" id="option-desktop" onclick="selectOption('desktop')">
                <div class="option-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="4" width="20" height="15" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/></svg>
                </div>
                <div class="option-content">
                    <div class="option-title">桌面快捷方式</div>
                    <div class="option-desc">在桌面上创建快捷方式，方便快速启动</div>
                </div>
            </div>

            <div class="option-card" id="option-startmenu" onclick="selectOption('startmenu')">
                <div class="option-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 6l16 0"/><path d="M4 12l16 0"/><path d="M4 18l16 0"/></svg>
                </div>
                <div class="option-content">
                    <div class="option-title">开始菜单</div>
                    <div class="option-desc">添加到开始菜单，可通过搜索快速找到</div>
                </div>
            </div>

            <div class="option-card" id="option-none" onclick="selectOption('none')">
                <div class="option-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                </div>
                <div class="option-content">
                    <div class="option-title">不创建快捷方式</div>
                    <div class="option-desc">直接运行，稍后可在设置中创建</div>
                </div>
            </div>
        </div>

        <button class="install-btn" id="install-btn" onclick="startInstallation()">继续</button>
        
        <div class="skip-link" onclick="skipInstallation()">跳过，直接进入播放器</div>
        
        <div class="status" id="status">等待选择...</div>
    </div>

    <div class="version">v{VERSION}</div>

    <script>
        let selectedOption = null;
        let isInstalling = false;

        function selectOption(option) {
            if (isInstalling) return;
            
            selectedOption = option;
            
            // 移除所有选中状态
            document.querySelectorAll('.option-card').forEach(card => {
                card.classList.remove('selected');
            });
            
            // 添加当前选中状态
            document.getElementById(`option-${option}`).classList.add('selected');
            
            document.getElementById('install-btn').disabled = false;
            document.getElementById('status').innerText = `已选择: ${getOptionText(option)}`;
        }

        function getOptionText(option) {
            const texts = {
                'desktop': '桌面快捷方式',
                'startmenu': '开始菜单',
                'none': '不创建快捷方式'
            };
            return texts[option] || option;
        }

        async function startInstallation() {
            if (isInstalling || !selectedOption) return;
            
            isInstalling = true;
            const btn = document.getElementById('install-btn');
            btn.innerText = '处理中...';
            btn.disabled = true;
            
            document.getElementById('status').innerText = `正在${selectedOption === 'none' ? '跳过' : '创建快捷方式'}...`;
            
            try {
                if (window.pywebview) {
                    const result = await window.pywebview.api.create_shortcut_option(selectedOption);
                    
                    if (result.status === 'success') {
                        document.getElementById('status').innerText = result.message || '完成!';
                        
                        // 跳转到主界面
                        setTimeout(() => {
                            window.pywebview.api.on_install_complete();
                        }, 1000);
                    } else {
                        document.getElementById('status').innerText = '失败: ' + (result.error || '未知错误');
                        btn.innerText = '重试';
                        btn.disabled = false;
                        isInstalling = false;
                    }
                } else {
                    document.getElementById('status').innerText = '请在Python环境中运行';
                    btn.innerText = '继续';
                    btn.disabled = false;
                    isInstalling = false;
                }
            } catch (error) {
                console.error("Installation error:", error);
                document.getElementById('status').innerText = '发生错误: ' + error.message;
                btn.innerText = '重试';
                btn.disabled = false;
                isInstalling = false;
            }
        }

        function skipInstallation() {
            if (isInstalling) return;
            
            isInstalling = true;
            document.getElementById('status').innerText = '跳过安装，进入播放器...';
            
            if (window.pywebview) {
                // 保存跳过设置
                window.pywebview.api.skip_installation().then(() => {
                    setTimeout(() => {
                        window.pywebview.api.on_install_complete();
                    }, 500);
                });
            } else {
                document.getElementById('status').innerText = '请在Python环境中运行';
                isInstalling = false;
            }
        }

        // 默认选择桌面快捷方式
        setTimeout(() => {
            selectOption('desktop');
        }, 300);
    </script>
</body>
</html>
"""

# 主程序界面保持不变...
MAIN_HTML_TEMPLATE = r""" 
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <!-- 原有主界面HTML代码保持不变 -->
</head>
<body>
    <!-- 原有主界面HTML代码保持不变 -->
</body>
</html>
"""

# ================= Python 后端逻辑 =================

class Api:
    def __init__(self, window):
        self.window = window
        self.config = load_config()
        logger.info("API initialized")

    def close_app(self):
        """完全退出程序"""
        logger.info("Closing application")
        if self.window:
            self.window.destroy()
        return {'status': 'closed'}

    def minimize_window(self):
        """最小化窗口"""
        logger.info("Minimizing window")
        if self.window:
            self.window.minimize()
        return {'status': 'minimized'}

    def maximize_window(self):
        """最大化窗口"""
        logger.info("Maximizing window")
        if self.window:
            self.window.maximize()
        return {'status': 'maximized'}

    def restore_window(self):
        """还原窗口"""
        logger.info("Restoring window")
        if self.window:
            self.window.restore()
        return {'status': 'restored'}

    def start_drag(self):
        """开始拖动窗口 (Windows)"""
        logger.debug("Start drag")
        try:
            import ctypes
            ctypes.windll.user32.ReleaseCapture()
            ctypes.windll.user32.SendMessageW(self.window._window.hwnd, 0x0112, 0xF012, 0)
            return {'status': 'dragging'}
        except Exception as e:
            logger.warning(f"Drag failed: {e}")
            return {'status': 'error', 'error': str(e)}

    def on_install_complete(self):
        """安装完成回调"""
        logger.info("Installation complete, loading main UI")
        time.sleep(0.5)
        self.window.load_html(MAIN_HTML_TEMPLATE.replace("{VERSION}", VERSION))
        return {'status': 'loaded', 'version': VERSION}

    def create_shortcut_option(self, option):
        """根据用户选择创建快捷方式"""
        try:
            if option == 'none':
                # 用户选择不创建快捷方式
                self.config['skip_install'] = True
                self.config['shortcut_created'] = False
                save_config(self.config)
                return {'status': 'success', 'message': '已跳过快捷方式创建'}
            
            elif option == 'desktop':
                # 创建桌面快捷方式
                result = self.create_desktop_shortcut()
                if result['status'] == 'success':
                    self.config['shortcut_created'] = True
                    self.config['shortcut_path'] = result.get('shortcut_path')
                    self.config['skip_install'] = False
                    save_config(self.config)
                    return {'status': 'success', 'message': '桌面快捷方式创建成功'}
                else:
                    return result
                    
            elif option == 'startmenu':
                # 创建开始菜单快捷方式
                result = self.create_start_menu_shortcut()
                if result['status'] == 'success':
                    self.config['shortcut_created'] = True
                    self.config['shortcut_path'] = result.get('shortcut_path')
                    self.config['skip_install'] = False
                    save_config(self.config)
                    return {'status': 'success', 'message': '开始菜单快捷方式创建成功'}
                else:
                    return result
            
            return {'status': 'error', 'error': '无效的选项'}
            
        except Exception as e:
            logger.error(f"Failed to create shortcut: {e}")
            return {'status': 'error', 'error': str(e)}

    def skip_installation(self):
        """跳过安装"""
        self.config['skip_install'] = True
        save_config(self.config)
        return {'status': 'success', 'message': '已跳过安装'}

    def create_desktop_shortcut(self):
        """创建桌面快捷方式"""
        try:
            # 获取当前可执行文件路径
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = sys.argv[0]
                if not os.path.isabs(exe_path):
                    exe_path = os.path.join(os.getcwd(), exe_path)
            
            exe_path = os.path.abspath(exe_path)
            
            # 获取桌面路径
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            shortcut_path = os.path.join(desktop, SHORTCUT_NAME)
            
            logger.info(f"Creating desktop shortcut: {shortcut_path}")
            
            # 如果快捷方式已存在，先删除
            if os.path.exists(shortcut_path):
                try:
                    os.remove(shortcut_path)
                    logger.info(f"Removed existing shortcut: {shortcut_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove existing shortcut: {e}")
            
            # 创建VBS脚本来创建快捷方式
            import tempfile
            vbs_content = f"""
            Set oWS = WScript.CreateObject("WScript.Shell")
            sLinkFile = "{shortcut_path}"
            Set oLink = oWS.CreateShortcut(sLinkFile)
            oLink.TargetPath = "{exe_path}"
            oLink.WorkingDirectory = "{os.path.dirname(exe_path)}"
            oLink.Description = "CORE Music Player"
            oLink.Save
            """
            
            vbs_path = os.path.join(tempfile.gettempdir(), "create_desktop_shortcut.vbs")
            
            try:
                with open(vbs_path, "w", encoding="utf-8-sig") as f:
                    f.write(vbs_content)
                
                import subprocess
                cscript_path = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32", "cscript.exe")
                result = subprocess.run([cscript_path, "//nologo", vbs_path], 
                                      capture_output=True, text=True, shell=False)
                
                if os.path.exists(vbs_path):
                    os.remove(vbs_path)
                
                if os.path.exists(shortcut_path):
                    logger.info(f"Desktop shortcut created successfully: {shortcut_path}")
                    return {'status': 'success', 'shortcut_path': shortcut_path}
                else:
                    logger.error("Desktop shortcut file not found after creation")
                    return {'status': 'error', 'error': '快捷方式创建失败'}
                    
            except Exception as e:
                logger.error(f"Failed to create desktop shortcut via VBS: {e}")
                return {'status': 'error', 'error': str(e)}
                
        except Exception as e:
            logger.error(f"Desktop shortcut creation failed: {e}")
            return {'status': 'error', 'error': str(e)}

    def create_start_menu_shortcut(self):
        """创建开始菜单快捷方式"""
        try:
            # 获取当前可执行文件路径
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = sys.argv[0]
                if not os.path.isabs(exe_path):
                    exe_path = os.path.join(os.getcwd(), exe_path)
            
            exe_path = os.path.abspath(exe_path)
            
            # 获取开始菜单路径（当前用户）
            start_menu = os.path.join(os.environ.get("APPDATA"), "Microsoft", "Windows", "Start Menu", "Programs")
            os.makedirs(start_menu, exist_ok=True)
            
            # 创建程序文件夹
            program_folder = os.path.join(start_menu, APP_NAME)
            os.makedirs(program_folder, exist_ok=True)
            
            shortcut_path = os.path.join(program_folder, SHORTCUT_NAME)
            
            logger.info(f"Creating start menu shortcut: {shortcut_path}")
            
            # 如果快捷方式已存在，先删除
            if os.path.exists(shortcut_path):
                try:
                    os.remove(shortcut_path)
                    logger.info(f"Removed existing shortcut: {shortcut_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove existing shortcut: {e}")
            
            # 创建VBS脚本来创建快捷方式
            import tempfile
            vbs_content = f"""
            Set oWS = WScript.CreateObject("WScript.Shell")
            sLinkFile = "{shortcut_path}"
            Set oLink = oWS.CreateShortcut(sLinkFile)
            oLink.TargetPath = "{exe_path}"
            oLink.WorkingDirectory = "{os.path.dirname(exe_path)}"
            oLink.Description = "CORE Music Player"
            oLink.Save
            """
            
            vbs_path = os.path.join(tempfile.gettempdir(), "create_startmenu_shortcut.vbs")
            
            try:
                with open(vbs_path, "w", encoding="utf-8-sig") as f:
                    f.write(vbs_content)
                
                import subprocess
                cscript_path = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32", "cscript.exe")
                result = subprocess.run([cscript_path, "//nologo", vbs_path], 
                                      capture_output=True, text=True, shell=False)
                
                if os.path.exists(vbs_path):
                    os.remove(vbs_path)
                
                if os.path.exists(shortcut_path):
                    logger.info(f"Start menu shortcut created successfully: {shortcut_path}")
                    return {'status': 'success', 'shortcut_path': shortcut_path}
                else:
                    logger.error("Start menu shortcut file not found after creation")
                    return {'status': 'error', 'error': '快捷方式创建失败'}
                    
            except Exception as e:
                logger.error(f"Failed to create start menu shortcut via VBS: {e}")
                return {'status': 'error', 'error': str(e)}
                
        except Exception as e:
            logger.error(f"Start menu shortcut creation failed: {e}")
            return {'status': 'error', 'error': str(e)}

    def download_file(self, url, filename):
        """下载文件到桌面"""
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            file_path = os.path.join(desktop, filename)

            if os.path.exists(file_path):
                base, ext = os.path.splitext(filename)
                timestamp = int(time.time())
                file_path = os.path.join(desktop, f"{base}_{timestamp}{ext}")
                filename = f"{base}_{timestamp}{ext}"

            logger.info(f"Downloading {url} to {file_path}")

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    urlretrieve(url, file_path)
                    logger.info(f"Download success: {filename}")
                    return {'status': 'success', 'path': file_path, 'filename': filename}
                except Exception as e:
                    logger.warning(f"Download attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(1)
                    else:
                        raise e

        except Exception as e:
            logger.error(f"Download failed: {e}")
            return {'status': 'error', 'error': str(e)}

def check_installation():
    """检查是否需要安装 - 检查配置文件和快捷方式"""
    config = load_config()
    
    # 如果用户之前选择跳过安装，直接进入主界面
    if config.get('skip_install', False):
        logger.info("User previously skipped installation")
        return False
    
    # 如果快捷方式已创建且存在，直接进入主界面
    if config.get('shortcut_created', False):
        shortcut_path = config.get('shortcut_path')
        if shortcut_path and os.path.exists(shortcut_path):
            logger.info(f"Shortcut exists at: {shortcut_path}")
            return False
    
    # 检查是否有桌面快捷方式
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    shortcut_path = os.path.join(desktop, SHORTCUT_NAME)
    
    if os.path.exists(shortcut_path):
        logger.info(f"Desktop shortcut found at: {shortcut_path}")
        # 更新配置
        config['shortcut_created'] = True
        config['shortcut_path'] = shortcut_path
        save_config(config)
        return False
    
    # 需要安装
    logger.info("Installation needed")
    return True

def main():
    logger.info("=" * 50)
    logger.info(f"CORE Music v{VERSION} starting")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Platform: {sys.platform}")
    logger.info(f"Current directory: {os.getcwd()}")
    logger.info(f"Executable: {sys.executable}")

    # 检查是否需要安装
    needs_install = check_installation()
    logger.info(f"Installation needed: {needs_install}")

    # 根据是否需要安装选择HTML
    if needs_install:
        logger.info("Showing installation screen")
        initial_html = INSTALLER_HTML.replace("{VERSION}", VERSION)
        window_title = f"{APP_NAME} v{VERSION} - 初始设置"
    else:
        logger.info("Showing main player screen")
        initial_html = MAIN_HTML_TEMPLATE.replace("{VERSION}", VERSION)
        window_title = f"{APP_NAME} v{VERSION}"

    # 创建窗口
    window = webview.create_window(
        window_title,
        html=initial_html,
        frameless=True,
        on_top=True,
        width=1000,
        height=750,
        min_size=(400, 600),
        transparent=False,
        js_api=Api
    )

    # 获取API实例并暴露方法
    api = Api(window)
    window.expose(
        api.close_app,
        api.download_file,
        api.minimize_window,
        api.maximize_window,
        api.restore_window,
        api.start_drag,
        api.on_install_complete,
        api.create_shortcut_option,
        api.skip_installation
    )

    logger.info("Starting webview...")
    webview.start(debug=False)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        print(f"程序崩溃: {e}")
        input("按回车键退出...")