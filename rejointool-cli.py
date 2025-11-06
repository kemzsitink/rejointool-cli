import os
import uuid
import requests
import json
import time
import subprocess
import asyncio
import aiohttp
import threading
import psutil
import sqlite3
import shutil
import sys
import random
import string
import re
from datetime import datetime
from colorama import init, Fore, Style
from threading import Lock
import base64
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor
from loguru import logger
from prettytable import PrettyTable

# --- Khởi tạo Colorama ---
init(autoreset=True)

# --- Các biến toàn cục ---
SERVER_LINKS_FILE = 'server-link.txt'
ACCOUNTS_FILE = 'account.txt'
CACHE_FILE = 'username_cache.json'
CONFIG_WH_FILE = 'config-wh.json'  # Tệp cấu hình cho Webhook

# Biến cho tính năng Webhook
webhook_url = None
device_name = None
interval = None
stop_webhook_thread = False
webhook_thread = None

# Biến cho tính năng Auto Rejoin
status_lock = Lock()
package_statuses = {}
username_cache = {}
stop_event = threading.Event()

# Đường dẫn executor cho auto-rejoin
executors = {
    'Fluxus': '/storage/emulated/0/Fluxus/',
    'Codex': '/storage/emulated/0/Codex/',
    'Arceus X': '/storage/emulated/0/Arceus X/',
    'Delta': '/storage/emulated/0/Delta/',
    'Cryptic': '/storage/emulated/0/Cryptic/',
    'VegaX': '/storage/emulated/0/VegaX/',
    'Trigon': '/storage/emulated/0/Trigon/'
}
workspace_paths = []
for executor, base_path in executors.items():
    workspace_paths.append(f'{base_path}Workspace')
    workspace_paths.append(f'{base_path}workspace')

lua_script_template = '-- # Developed By Gemini\nloadstring(game:HttpGet("https://raw.githubusercontent.com/kemzsitink/rejointool-cli/refs/heads/main/GEMINI.lua"))()\n'

# Cấu hình Logger
logger.remove()
logger.add(sink=sys.stdout, format='{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}', level='INFO')

# Khởi tạo ThreadPoolExecutor cho các tác vụ I/O chặn
# Số worker = số luồng giám sát + 1 (cho webhook) + 1 (dự phòng)
MAX_WORKERS = max(threading.active_count(), 10) 
executor_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)

# --- Hàm tiện ích cho Shell/ADB (Chạy trong Executor) ---

def run_shell_command_blocking(command_list, check=False):
    """Chạy lệnh shell đồng bộ trong một luồng riêng."""
    try:
        # Nếu command_list là string (ví dụ: cho os.system), dùng shell=True
        if isinstance(command_list, str):
            result = subprocess.run(command_list, shell=True, capture_output=True, text=True, check=check)
        else:
            # Nếu command_list là list, dùng shell=False
            result = subprocess.run(command_list, capture_output=True, text=True, check=check)
            
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {command_list}. Stderr: {e.stderr}")
        return e
    except Exception as e:
        logger.error(f"Error executing command {command_list}: {e}")
        return None

# --- Các hàm Tiện ích & Giao diện (UI) ---

def set_console_title(title):
    """Đặt tiêu đề cho cửa sổ console (chỉ hoạt động trên Windows)."""
    if os.name == 'nt':
        os.system(f'title {title}')

def clear_console():
    """Xóa màn hình console."""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    """In tiêu đề VCP Manager."""
    header = r"""
\0_0/       
\^_^/       
\>_< /      
\°o°/       
\*_*/       
\(0_0)/     
\（◎_◎）/   
\0_0>       
<0_0/>      
\0_0/>☁️            
"""
    print(Fore.LIGHTYELLOW_EX + header + Style.RESET_ALL)
    print(Fore.LIGHTYELLOW_EX + 'Developed By kem - VCPCLOUD' + Style.RESET_ALL)

def check_authencation():
    """Kiểm tra xem người dùng có được phép sử dụng công cụ hay không."""
    github_raw_link = 'https://raw.githubusercontent.com/kemzsitink/rejointool-cli/refs/heads/main/Authencator'
    try:
        response = requests.get(github_raw_link)
        response.raise_for_status()
        content = response.text.strip().lower()
        if content == 'true':
            print(Fore.GREEN + '[ VCP Manager ] -> Authorized' + Style.RESET_ALL)
            return True
        else:
            print(Fore.RED + '[ VCP Manager ] -> Not Authorized' + Style.RESET_ALL)
            sys.exit(0)
    except requests.RequestException as e:
        print(f'An error occurred: {e}')
        sys.exit(1)

def create_dynamic_menu(options):
    """Tạo và hiển thị một menu động từ danh sách các lựa chọn."""
    clear_console()
    print_header()
    table = PrettyTable()
    table.field_names = ['Option', 'Function']
    table.align = 'l'
    table.border = True
    for i, option in enumerate(options, start=1):
        table.add_row([f'{i}.', option])
    print(Fore.LIGHTCYAN_EX + str(table))

def update_status_table_blocking(package_statuses):
    """Cập nhật và hiển thị bảng trạng thái cho tính năng auto-rejoin (Blocking I/O)."""
    clear_console()
    print_header()
    table = PrettyTable()
    table.field_names = ['Package', 'Username', 'Status']
    table.align = 'l'
    table.border = True
    
    current_statuses = {}
    with status_lock:
        current_statuses.update(package_statuses)
        
    for package, info in current_statuses.items():
        table.add_row([package, info.get('Username', 'Unknown'), info.get('Status', '')])
    print(str(table))

def status_update_thread_func():
    """Luồng chạy nền để cập nhật bảng trạng thái định kỳ."""
    while not stop_event.is_set():
        # Chỉ cập nhật nếu có trạng thái cần hiển thị
        if package_statuses:
            update_status_table_blocking(package_statuses)
        time.sleep(1) # Cập nhật mỗi giây

def get_roblox_packages():
    """Lấy danh sách các gói (package) Roblox đã cài đặt trên thiết bị (Chạy trong Executor)."""
    packages = []
    
    # Sử dụng subprocess để đảm bảo lệnh được chạy trong luồng pool
    output = executor_pool.submit(run_shell_command_blocking, 'pm list packages').result()
    
    if isinstance(output, subprocess.CalledProcessError):
        print(Fore.RED + 'An error occurred while searching for packages on your device!' + Style.RESET_ALL)
        return packages
    
    if output is None:
        return packages

    print(Fore.YELLOW + 'Checking Packages On Your Device .....' + Style.RESET_ALL)
    for line in output.stdout.splitlines():
        if 'com.roblox.' in line:
            package_name = line.split(':')[1]
            print(Fore.GREEN + f'Package Found : {package_name}' + Style.RESET_ALL)
            packages.append(package_name)

    if not packages:
        print(Fore.RED + 'No Roblox-related packages found on your device.' + Style.RESET_ALL)
    
    return packages

def delete_roblox_cache():
    """Xóa bộ nhớ đệm (cache) của tất cả các ứng dụng Roblox (Chạy trong Executor)."""
    base_path = '/data/data'
    deleted_count = 0
    
    try:
        # Giả sử chúng ta có thể liệt kê thư mục /data/data (cần root)
        folders = os.listdir(base_path) 
    except FileNotFoundError:
        print(Fore.RED + 'Cannot access /data/data. Do you have root permission?' + Style.RESET_ALL)
        input(Fore.CYAN + "Press Enter to return to main menu..." + Style.RESET_ALL)
        return
    except Exception as e:
        print(Fore.RED + f'Error listing folders: {e}' + Style.RESET_ALL)
        input(Fore.CYAN + "Press Enter to return to main menu..." + Style.RESET_ALL)
        return

    print(Fore.YELLOW + 'Starting cache deletion (using "rm -rf")...' + Style.RESET_ALL)
    
    delete_tasks = []
    for folder in folders:
        if folder.startswith('com.roblox.'):
            cache_path = os.path.join(base_path, folder, 'cache')
            # Sử dụng lệnh shell rm -rf để đảm bảo xóa nhanh chóng và an toàn (với quyền root)
            delete_tasks.append(executor_pool.submit(run_shell_command_blocking, f'rm -rf {cache_path}'))
            deleted_count += 1
            print(Fore.YELLOW + f'Scheduled deletion for {folder} cache.' + Style.RESET_ALL)

    # Chờ tất cả tác vụ hoàn thành
    for task in delete_tasks:
        task.result() 

    if deleted_count == 0:
        print(Fore.YELLOW + 'No Roblox cache found to delete.' + Style.RESET_ALL)
    else:
        print(Fore.GREEN + f'Cache deletion scheduled/completed for {deleted_count} packages.' + Style.RESET_ALL)
    
    input(Fore.CYAN + "Press Enter to return to main menu..." + Style.RESET_ALL)

# --- Tính năng 1: Webhook ---

def capture_screenshot():
    """Chụp ảnh màn hình và lưu vào /storage/emulated/0/Download/ (Chạy trong Executor)."""
    screenshot_path = '/storage/emulated/0/Download/screenshot.png'
    command = f'/system/bin/screencap -p {screenshot_path}'
    
    # Chạy lệnh blocking trong Executor
    result = executor_pool.submit(run_shell_command_blocking, command).result()
    
    if result is not None and result.returncode == 0 and os.path.exists(screenshot_path):
        print(Fore.GREEN + f'[ VCP Manager ] - Screenshot saved to: {screenshot_path}' + Style.RESET_ALL)
        return screenshot_path
    else:
        error_message = (result.stderr.strip() if result and result.stderr else "Unknown error.")
        logger.error(f'[ VCP Manager ] - Error capturing screenshot. Error: {error_message}')
        return None

def get_system_info():
    """Lấy thông tin hệ thống (CPU, RAM, Uptime)."""
    cpu_usage = psutil.cpu_percent(interval=1)
    memory_info = psutil.virtual_memory()
    uptime = time.time() - psutil.boot_time()
    system_info = {
        'cpu_usage': cpu_usage,
        'memory_total': memory_info.total,
        'memory_available': memory_info.available,
        'memory_used': memory_info.used,
        'uptime': uptime
    }
    return system_info

def load_webhook_config():
    """Tải cấu hình webhook từ tệp config-wh.json."""
    global webhook_url, device_name, interval
    if os.path.exists(CONFIG_WH_FILE):
        try:
            with open(CONFIG_WH_FILE, 'r') as file:
                config = json.load(file)
                webhook_url = config.get('webhook_url')
                device_name = config.get('device_name')
                interval = config.get('interval')
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Error loading webhook config: {e}. Resetting config.")
            webhook_url = None
            device_name = None
            interval = None
    else:
        webhook_url = None
        device_name = None
        interval = None

def save_webhook_config():
    """Lưu cấu hình webhook vào tệp config-wh.json."""
    config = {'webhook_url': webhook_url, 'device_name': device_name, 'interval': interval}
    try:
        with open(CONFIG_WH_FILE, 'w') as file:
            json.dump(config, file, indent=4)
    except IOError as e:
        logger.error(f"Error saving webhook config: {e}")


def send_webhook():
    """Vòng lặp gửi thông tin thiết bị và ảnh chụp màn hình tới webhook."""
    global stop_webhook_thread
    while not stop_webhook_thread:
        if not webhook_url or not device_name or not interval:
            print(Fore.RED + '[ VCP Manager ] - Webhook config is missing. Stopping thread.' + Style.RESET_ALL)
            break
            
        # Tác vụ chặn: Chụp màn hình
        screenshot_path = capture_screenshot() 
        
        if screenshot_path is None or not os.path.exists(screenshot_path):
            print(Fore.RED + '[ VCP Manager ] - Screenshot file does not exist or capture failed. Skipping webhook.' + Style.RESET_ALL)
            time.sleep(interval * 60)
            continue

        system_info = get_system_info()
        embed = {
            'color': 16776961,
            'fields': [
                {'name': ':small_blue_diamond: Device Name', 'value': f'`{device_name}`', 'inline': True},
                {'name': ':gear: CPU Usage', 'value': f'`{system_info["cpu_usage"]:.2f}%`', 'inline': True},
                {'name': ':floppy_disk: Memory Usage', 'value': f'`{system_info["memory_used"] / system_info["memory_total"] * 100:.2f}%`', 'inline': True},
                {'name': ':floppy_disk: Memory Available', 'value': f'`{system_info["memory_available"] / system_info["memory_total"] * 100:.2f}%`', 'inline': True},
                {'name': ':bulb: Total Memory', 'value': f'`{system_info["memory_total"] / 1024 ** 3:.2f} GB`', 'inline': True},
                {'name': ':timer: Uptime', 'value': f'`{system_info["uptime"] / 3600:.2f} hours`', 'inline': True}
            ],
        }
        payload = {'embeds': [embed], 'username': device_name}

        # Tác vụ chặn: Gửi request
        try:
            with open(screenshot_path, 'rb') as file:
                # Sử dụng requests đồng bộ, chấp nhận việc luồng này bị chặn khi gửi
                response = requests.post(webhook_url, 
                                         data={'payload_json': json.dumps(payload)}, 
                                         files={'file': ('screenshot.png', file)},
                                         timeout=30)
            
            if response.status_code in [204, 200]:
                print(Fore.GREEN + '[ VCP Manager ] - Device information has been successfully sent to the webhook.' + Style.RESET_ALL)
            else:
                print(Fore.RED + f'[ VCP Manager ] - Error sending device information to the webhook, status code: {response.status_code}' + Style.RESET_ALL)
        except Exception as e:
            print(Fore.RED + f'[ VCP Manager ] - Exception while sending webhook: {e}' + Style.RESET_ALL)
        
        time.sleep(interval * 60)

def start_webhook_thread():
    """Khởi động luồng (thread) gửi webhook nếu chưa chạy."""
    global webhook_thread, stop_webhook_thread
    if webhook_thread is None or not webhook_thread.is_alive():
        stop_webhook_thread = False
        webhook_thread = threading.Thread(target=send_webhook, daemon=True)
        webhook_thread.start()
        print(Fore.GREEN + '[ VCP Manager ] - Webhook thread started.' + Style.RESET_ALL)

def stop_webhook():
    """Dừng luồng gửi webhook."""
    global stop_webhook_thread
    stop_webhook_thread = True
    if webhook_thread and webhook_thread.is_alive():
        # Không cần join vì nó sẽ dừng ở time.sleep tiếp theo
        pass
    print(Fore.YELLOW + '[ VCP Manager ] - Webhook thread stopped.' + Style.RESET_ALL)

def setup_webhook():
    """Giao diện cho người dùng nhập thông tin cấu hình webhook."""
    global webhook_url, device_name, interval, stop_webhook_thread
    
    stop_webhook() # Dừng luồng cũ nếu đang chạy
    
    print_header()
    print(Fore.CYAN + "--- Webhook Setup ---" + Style.RESET_ALL)
    
    webhook_url = input(Fore.MAGENTA + '[ VCP Manager ] - Please enter your Webhook URL: ' + Style.RESET_ALL).strip()
    device_name = input(Fore.MAGENTA + '[ VCP Manager ] - Please enter your device name: ' + Style.RESET_ALL).strip()
    
    while True:
        try:
            interval_input = input(Fore.MAGENTA + '[ VCP Manager ] - Please enter the interval (in minutes): ' + Style.RESET_ALL)
            interval = int(interval_input)
            if interval <= 0:
                print(Fore.RED + "Interval must be a positive number." + Style.RESET_ALL)
                continue
            break
        except ValueError:
            print(Fore.RED + "Invalid input. Please enter a number." + Style.RESET_ALL)
            
    save_webhook_config()
    start_webhook_thread()
    
    print(Fore.GREEN + "Webhook configured successfully and started!" + Style.RESET_ALL)
    input(Fore.CYAN + "Press Enter to return to main menu..." + Style.RESET_ALL)


# --- Tính năng 2: Lấy & Tiêm Cookies ---

def verify_cookie(cookie_value):
    """Kiểm tra xem cookie .ROBLOSECURITY có hợp lệ hay không."""
    try:
        # Sử dụng requests đồng bộ, chấp nhận việc này chặn luồng gọi nó.
        headers = {
            'Cookie': f'.ROBLOSECURITY={cookie_value}',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'
        }
        response = requests.get('https://users.roblox.com/v1/users/authenticated', headers=headers, timeout=10)
        
        if response.status_code == 200:
            print(Fore.GREEN + '[ VCP Manager ] -> Cookie is valid! User is authenticated.' + Style.RESET_ALL)
            return True
        elif response.status_code == 401:
            print(Fore.RED + '[ VCP Manager ] -> Invalid cookie. The user is not authenticated.' + Style.RESET_ALL)
            return False
        else:
            print(Fore.RED + f'[ VCP Manager ] -> Error verifying cookie: {response.status_code} - {response.text}' + Style.RESET_ALL)
            return False
    except Exception as e:
        print(Fore.RED + f'Exception occurred while verifying cookie: {e}' + Style.RESET_ALL)
        return False

def download_file(url, destination, binary=False):
    """Tải tệp từ URL về máy."""
    # Tác vụ chặn: download
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        mode = 'wb' if binary else 'w'
        with open(destination, mode) as file:
            if binary:
                shutil.copyfileobj(response.raw, file)
            else:
                file.write(response.text)
        print(Fore.GREEN + f'[ VCP Manager ] -> {os.path.basename(destination)} downloaded successfully.' + Style.RESET_ALL)
        return destination
    except requests.RequestException as e:
        print(Fore.RED + f'[ VCP Manager ] -> Failed to download {os.path.basename(destination)}: {e}' + Style.RESET_ALL)
        return None
    except Exception as e:
        print(Fore.RED + f'[ VCP Manager ] -> Error downloading {os.path.basename(destination)}: {e}' + Style.RESET_ALL)
        return None

def replace_cookie_value_in_db(db_path, new_cookie_value):
    """Thay thế giá trị cookie .ROBLOSECURITY trong tệp CSDL SQLite (Tác vụ chặn)."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Kiểm tra xem cookie đã tồn tại chưa
        cursor.execute("SELECT COUNT(*) FROM cookies WHERE host_key = '.roblox.com' AND name = '.ROBLOSECURITY'")
        cookie_exists = cursor.fetchone()[0]
        
        current_time_utc = int(time.time() * 1000000)
        expiry_time_utc = 99999999999999999 # Thời gian hết hạn rất xa
        
        if cookie_exists:
            cursor.execute(
                """
                UPDATE cookies
                SET value = ?, last_access_utc = ?, expires_utc = ?
                WHERE host_key = '.roblox.com' AND name = '.ROBLOSECURITY'
                """, (new_cookie_value, current_time_utc, expiry_time_utc)
            )
        else:
            cursor.execute(
                """
                INSERT INTO cookies (creation_utc, host_key, name, value, path, expires_utc, is_secure, is_httponly, last_access_utc)
                VALUES (?, '.roblox.com', '.ROBLOSECURITY', ?, '/', ?, 0, 0, ?)
                """, (current_time_utc, new_cookie_value, expiry_time_utc, current_time_utc)
            )
            
        conn.commit()
        conn.close()
        print(Fore.GREEN + '[ VCP Manager ] -> Cookie value replaced successfully in the database!' + Style.RESET_ALL)
    except sqlite3.OperationalError as e:
        print(Fore.RED + f'[ VCP Manager ] -> Database error during cookie replacement: {e}' + Style.RESET_ALL)
    except Exception as e:
        print(Fore.RED + f'[ VCP Manager ] -> Error replacing cookie value in database: {e}' + Style.RESET_ALL)

def inject_cookies_and_appstorage():
    """Tiêm cookie và appStorage vào tất cả các gói Roblox (Tác vụ chặn)."""
    print_header()
    print(Fore.CYAN + "--- Inject Cookies and AppStorage ---" + Style.RESET_ALL)
    
    db_url = 'https://raw.githubusercontent.com/kemzsitink/rejointool-cli/refs/heads/main/Cookies'
    appstorage_url = 'https://raw.githubusercontent.com/kemzsitink/rejointool-cli/refs/heads/main/appStorage.json'
    
    # Download file (Blocking I/O)
    downloaded_db_path = download_file(db_url, 'Cookies.db', binary=True)
    downloaded_appstorage_path = download_file(appstorage_url, 'appStorage.json', binary=False)
    
    if not downloaded_db_path or not downloaded_appstorage_path:
        print(Fore.RED + '[ VCP Manager ] -> Failed to download necessary files. Exiting.' + Style.RESET_ALL)
        input(Fore.CYAN + "Press Enter to return to main menu..." + Style.RESET_ALL)
        return

    cookie_txt_path = 'cookie.txt'
    if not os.path.exists(cookie_txt_path):
        print(Fore.RED + '[ VCP Manager ] -> cookie.txt not found in the current directory!' + Style.RESET_ALL)
        with open(cookie_txt_path, 'w') as file:
            file.write('')
        print(Fore.GREEN + '[ VCP Manager ] -> cookie.txt has been created! Please add cookies to it.' + Style.RESET_ALL)
        input(Fore.CYAN + "Press Enter to return to main menu..." + Style.RESET_ALL)
        return

    with open(cookie_txt_path, 'r') as file:
        cookies = [line.strip() for line in file.readlines() if line.strip()]

    if not cookies:
        print(Fore.RED + '[ VCP Manager ] -> No cookies found in cookie.txt. Please add your cookies.' + Style.RESET_ALL)
        input(Fore.CYAN + "Press Enter to return to main menu..." + Style.RESET_ALL)
        return

    packages = get_roblox_packages() # Blocking call, nhưng đã được tối ưu hóa trong phần khác
    if not packages:
        input(Fore.CYAN + "Press Enter to return to main menu..." + Style.RESET_ALL)
        return

    if len(cookies) > len(packages):
        print(Fore.YELLOW + '[ VCP Manager ] -> Warning: More cookies in cookie.txt than packages available. Extra cookies will be ignored.' + Style.RESET_ALL)
    
    for idx, package_name in enumerate(packages):
        if idx >= len(cookies):
            print(Fore.YELLOW + f'No more cookies to inject. Stopping at package {package_name}.' + Style.RESET_ALL)
            break
            
        try:
            raw_cookie = cookies[idx]
            cookie = None
            
            if raw_cookie.count(':') >= 2:
                parts = raw_cookie.split(':')
                cookie = ':'.join(parts[2:]) # Giả sử cookie là phần cuối cùng
            else:
                cookie = raw_cookie
            
            print(Fore.CYAN + f'[ VCP Manager ] -> Verifying cookie for {package_name} before injection...' + Style.RESET_ALL)
            if not verify_cookie(cookie):
                print(Fore.RED + f'[ VCP Manager ] -> Cookie for {package_name} is invalid. Skipping injection...' + Style.RESET_ALL)
                continue
                
            print(Fore.GREEN + f'[ VCP Manager ] -> Injecting cookie for {package_name}...' + Style.RESET_ALL)
            
            # --- Thao tác file trên Android (Cần quyền root) ---
            destination_db_dir = f'/data/data/{package_name}/app_webview/Default/'
            destination_appstorage_dir = f'/data/data/{package_name}/files/appData/LocalStorage/'
            
            os.makedirs(destination_db_dir, exist_ok=True)
            os.makedirs(destination_appstorage_dir, exist_ok=True)
            
            destination_db_path = os.path.join(destination_db_dir, 'Cookies')
            shutil.copyfile(downloaded_db_path, destination_db_path)
            print(Fore.GREEN + f'Copied Cookies.db to {destination_db_path}' + Style.RESET_ALL)
            
            destination_appstorage_path = os.path.join(destination_appstorage_dir, 'appStorage.json')
            shutil.copyfile(downloaded_appstorage_path, destination_appstorage_path)
            print(Fore.GREEN + f'Copied appStorage.json to {destination_appstorage_path}' + Style.RESET_ALL)
            
            replace_cookie_value_in_db(destination_db_path, cookie)
            
        except Exception as e:
            print(Fore.RED + f'Error injecting cookie for {package_name}: {e}' + Style.RESET_ALL)

    print(Fore.GREEN + '[ VCP Manager ] -> Cookie and appStorage injection completed.' + Style.RESET_ALL)
    input(Fore.CYAN + "Press Enter to return to main menu..." + Style.RESET_ALL)

def find_other_roblox_data_paths():
    """Tìm tất cả các thư mục dữ liệu của Roblox (bắt đầu bằng com.roblox.)."""
    base_path = '/data/data'
    paths = []
    try:
        # Cần quyền root để liệt kê thư mục này
        for folder in os.listdir(base_path):
            if folder.lower().startswith('com.roblox.'):
                potential_path = os.path.join(base_path, folder)
                if os.path.isdir(potential_path):
                    paths.append(potential_path)
    except FileNotFoundError:
        print(Fore.RED + 'Cannot access /data/data. Do you have root permission?' + Style.RESET_ALL)
        pass
    return paths

def extract_user_info(json_path):
    """Trích xuất Username và UserId từ tệp appStorage.json."""
    try:
        if not os.path.exists(json_path):
            return None
        with open(json_path, 'r') as file:
            data = json.load(file)
            username = data.get('Username')
            user_id = data.get('UserId')
            if username and user_id:
                return (username, user_id)
            else:
                return None
    except (json.JSONDecodeError, IOError):
        return None

def get_cookies_from_path(cookies_db_path):
    """Lấy cookie .ROBLOSECURITY từ tệp CSDL Cookies."""
    cookies = []
    if not os.path.exists(cookies_db_path):
        return cookies
        
    try:
        conn = sqlite3.connect(cookies_db_path)
        cursor = conn.cursor()
        # Tìm cookie .ROBLOSECURITY
        query = "SELECT value FROM cookies WHERE host_key LIKE '%roblox.com%' AND name = '.ROBLOSECURITY'"
        cursor.execute(query)
        rows = cursor.fetchall()
        
        for row in rows:
            cookies.append(row[0])
            
        cursor.close()
        conn.close()
    except sqlite3.Error as e:
        print(Fore.RED + f"SQLite error: {e}" + Style.RESET_ALL)
    except Exception as e:
        print(Fore.RED + f"Error reading cookies DB: {e}" + Style.RESET_ALL)
        
    return cookies

def display_statistics(roblox_paths):
    """Hiển thị thông tin các tài khoản Roblox tìm thấy."""
    print(Fore.CYAN + 'Roblox Client Paths Detected:' + Style.RESET_ALL)
    statistics = []
    for index, path in enumerate(roblox_paths):
        json_path = os.path.join(path, 'files/appData/LocalStorage/appStorage.json')
        user_info = extract_user_info(json_path)
        username = user_info[0] if user_info else 'Unknown'
        user_id = user_info[1] if user_info else 'Unknown'
        print(f'{index + 1}. Username: {username} | User ID: {user_id} | Path: {path}')
        statistics.append((username, user_id, path))
    return statistics

def auto_get_cookies_from_paths(selected_paths):
    """Tự động lấy cookies từ các đường dẫn đã chọn và lưu vào tệp."""
    found_cookies = []
    for path in selected_paths:
        cookies_db_path = os.path.join(path, 'app_webview', 'Default', 'Cookies')
        cookies = get_cookies_from_path(cookies_db_path)
        if cookies:
            found_cookies.extend(cookies)
        else:
            print(Fore.YELLOW + f'No .ROBLOSECURITY cookie found in {path}' + Style.RESET_ALL)

    if found_cookies:
        storage_folder = 'Cookies Storage'
        os.makedirs(storage_folder, exist_ok=True)
        output_file = os.path.join(storage_folder, 'cookies-data.txt')
        with open(output_file, 'w') as output:
            output.write('\n'.join(found_cookies))
        print(Fore.GREEN + f'[ VCP Manager ] -> {len(found_cookies)} Cookies saved to {output_file}' + Style.RESET_ALL)
    else:
        print(Fore.RED + '[ VCP Manager ] -> No valid cookies found in the selected paths.' + Style.RESET_ALL)

def getcookie_process():
    """Quy trình chính để lấy cookie từ thiết bị."""
    print_header()
    print(Fore.CYAN + "--- Get Cookies From Device ---" + Style.RESET_ALL)
    
    roblox_paths = find_other_roblox_data_paths()
    if not roblox_paths:
        print(Fore.RED + 'No Roblox paths detected.' + Style.RESET_ALL)
        input(Fore.CYAN + "Press Enter to return to main menu..." + Style.RESET_ALL)
        return

    statistics = display_statistics(roblox_paths)

    while True:
        print(Fore.YELLOW + '\n[ VCP Manager ] -> Choose an option:' + Style.RESET_ALL)
        print('q - Quit to Main Menu')
        print('0 - Get cookies from all paths')
        # Hiển thị lại các lựa chọn
        for index in range(len(statistics)):
            print(f'{index + 1} - Get cookies from path: {statistics[index][2]}')

        choice = input('Enter your choice: ').strip()
        
        if choice.lower() == 'q':
            return
            
        if choice.isdigit():
            choice = int(choice)
            if choice == 0:
                auto_get_cookies_from_paths([stat[2] for stat in statistics])
                break
            elif 1 <= choice <= len(statistics):
                selected_path = [statistics[choice - 1][2]]
                auto_get_cookies_from_paths(selected_path)
                break
            else:
                print(Fore.RED + '[ VCP Manager ] -> Invalid choice. Please try again.' + Style.RESET_ALL)
        else:
            print(Fore.RED + '[ VCP Manager ] -> Invalid choice. Please try again.' + Style.RESET_ALL)
            
    input(Fore.CYAN + "Press Enter to return to main menu..." + Style.RESET_ALL)


# --- Tính năng 3: Auto Rejoin ---

def detect_and_write_lua_script():
    """Phát hiện các executor và ghi tệp LUA vào thư mục Autoexec (Tác vụ chặn)."""
    detected_executors = []
    for executor_name, base_path in executors.items():
        if not os.path.exists(base_path) or not os.path.isdir(base_path):
            continue

        autoexec_path = os.path.join(base_path, 'Autoexec')
        lua_written = False
        
        try:
            os.makedirs(autoexec_path, exist_ok=True)
            lua_script_path = os.path.join(autoexec_path, 'executor_check.lua')
            with open(lua_script_path, 'w') as file:
                file.write(lua_script_template)
            lua_written = True
            
        except Exception as e:
            logger.error(f'Failed to create/write to {autoexec_path}: {e}')
        
        if lua_written:
            detected_executors.append(executor_name)
            
    return detected_executors

def reset_executor_file(username):
    """Xóa tệp trạng thái executor_check_USERNAME.txt (Tác vụ chặn)."""
    status_file = f'executor_check_{username}.txt'
    for workspace_path in workspace_paths:
        if os.path.exists(workspace_path):
            file_path = os.path.join(workspace_path, status_file)
            if os.path.exists(file_path):
                try:
                    # Sử dụng lệnh shell rm để xóa
                    executor_pool.submit(run_shell_command_blocking, f'rm {file_path}').result()
                except Exception:
                    pass

def check_executor_status(username, max_inactivity_time=30):
    """Kiểm tra trạng thái executor (Tác vụ chặn)."""
    status_file = f'executor_check_{username}.txt'
    active_workspace_found = False
    
    for workspace_path in workspace_paths:
        if not os.path.exists(workspace_path):
            continue
            
        active_workspace_found = True
        file_path = os.path.join(workspace_path, status_file)
        
        if os.path.exists(file_path):
            try:
                last_modified_time = os.path.getmtime(file_path)
                current_time = time.time()
                
                if (current_time - last_modified_time) < max_inactivity_time:
                    return True # Executor đang hoạt động
            except Exception as e:
                logger.error(f"Error checking file status {file_path}: {e}")
                
    return False

def kill_roblox_process(package_name):
    """Dừng tiến trình Roblox bằng pkill (Chạy trong Executor)."""
    logger.info(f'Killing Roblox process for {package_name}...')
    # Sử dụng pkill -f để đảm bảo dừng đúng package
    executor_pool.submit(run_shell_command_blocking, f'pkill -f {package_name}').result()
    time.sleep(2) 

def format_server_link_if_needed(input_link):
    """Đảm bảo link server ở đúng định dạng URI roblox://"""
    if input_link.isdigit():
        return f'roblox://placeID={input_link}'
    elif 'roblox.com' in input_link:
        return input_link
    else:
        return input_link

def launch_roblox(package_name, server_link, num_packages, package_statuses):
    """Khởi chạy Roblox và tham gia máy chủ (Chạy trong Executor)."""
    
    formatted_link = format_server_link_if_needed(server_link)
    
    with status_lock:
        package_statuses[package_name]['Status'] = Fore.LIGHTCYAN_EX + f'Opening Roblox for {package_name}...' + Style.RESET_ALL
    
    # Lệnh 1: Mở ứng dụng (Splash screen)
    cmd1 = ['am', 'start', '-n', f'{package_name}/com.roblox.client.startup.ActivitySplash', '-d', formatted_link]
    executor_pool.submit(run_shell_command_blocking, cmd1).result()
    
    time.sleep(15 if num_packages >= 6 else 8)
    
    with status_lock:
        package_statuses[package_name]['Status'] = Fore.LIGHTCYAN_EX + f'Joining Roblox for {package_name}...' + Style.RESET_ALL
    
    # Lệnh 2: Gửi lệnh join
    cmd2 = ['am', 'start', '-n', f'{package_name}/com.roblox.client.ActivityProtocolLaunch', '-d', formatted_link]
    executor_pool.submit(run_shell_command_blocking, cmd2).result()
    
    time.sleep(20) # Đợi game tải
    
    with status_lock:
        package_statuses[package_name]['Status'] = Fore.GREEN + 'Joined Roblox' + Style.RESET_ALL

def background_executor_monitor(package_name, username, package_statuses, server_link, num_packages, retry_limit=3):
    """
    Luồng chạy nền để giám sát trạng thái executor.
    Tự động rejoin nếu executor bị lỗi.
    """
    retry_count = 0
    while not stop_event.is_set():
        try:
            time.sleep(30) # Tần suất kiểm tra
            
            if stop_event.is_set():
                break

            # Kiểm tra trạng thái executor (tác vụ chặn I/O)
            if not executor_pool.submit(check_executor_status, username).result():
                retry_count += 1
                logger.warning(f"Executor failed for {username}. Rejoin attempt {retry_count}/{retry_limit}.")
                
                with status_lock:
                    package_statuses[package_name]['Status'] = Fore.RED + f'Executor failed, rejoining (Attempt {retry_count})...' + Style.RESET_ALL

                if retry_count >= retry_limit:
                    with status_lock:
                        package_statuses[package_name]['Status'] = Fore.RED + 'Reached retry limit, stopping rejoin attempts.' + Style.RESET_ALL
                    break 

                # Rejoin: Kill, Reset, Launch (Tất cả đều là tác vụ blocking, chạy trong pool)
                kill_roblox_process(package_name)
                reset_executor_file(username) 
                time.sleep(5)
                # Chạy Launch trong luồng pool
                executor_pool.submit(launch_roblox, package_name, server_link, num_packages, package_statuses).result()
                
                time.sleep(60) # Đợi game và executor tải lại

                # Kiểm tra lại trạng thái sau khi rejoin
                if executor_pool.submit(check_executor_status, username).result():
                    retry_count = 0 
                    with status_lock:
                        package_statuses[package_name]['Status'] = Fore.GREEN + 'Executor reloaded successfully.' + Style.RESET_ALL
                else:
                    logger.error(f"Executor still failed for {username} after rejoin.")
            
        except Exception as e:
            logger.error(f"Error in background monitor for {username}: {e}")
            with status_lock:
                package_statuses[package_name]['Status'] = Fore.RED + f'Monitor Error: {e}' + Style.RESET_ALL


async def get_user_id_from_username(username):
    """Lấy User ID từ Username (bất đồng bộ)."""
    urls = [
        'https://users.roblox.com/v1/usernames/users',
        'https://users.roproxy.com/v1/usernames/users' # Fallback
    ]
    payload = {'usernames': [username], 'excludeBannedUsers': True}
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'
    }

    for url in urls:
        try:
            logger.info(f"Attempting to get User ID from: {url}")
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'data' in data and len(data['data']) > 0:
                            return data['data'][0]['id']
                    else:
                        logger.warning(f"Failed to fetch from {url}, status: {response.status}")
        except Exception as e:
            logger.error(f"Error getting user ID for {username} from {url}: {e}")
            
    return None

def get_username(user_id):
    """Lấy Username từ User ID, sử dụng cache (Tác vụ chặn)."""
    if user_id in username_cache:
        return username_cache[user_id]

    retry_attempts = 2
    urls = [
        f'https://users.roblox.com/v1/users/{user_id}',
        f'https://users.roproxy.com/v1/users/{user_id}' # Fallback
    ]

    for url in urls:
        for attempt in range(retry_attempts):
            try:
                # Sử dụng requests đồng bộ
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                username = data.get('name', 'Unknown')
                if username != 'Unknown':
                    username_cache[user_id] = username
                    return username
            except requests.exceptions.RequestException as e:
                logger.warning(f'Attempt {attempt + 1} failed for {url}: {e}')
                time.sleep(1)
                
    return 'Unknown'

def save_cache():
    """Lưu cache username vào tệp."""
    try:
        temp_file = CACHE_FILE + '.tmp'
        with open(temp_file, 'w') as f:
            json.dump(username_cache, f)
        os.replace(temp_file, CACHE_FILE)
    except IOError as e:
        logger.error(f'Error saving cache: {e}')

def load_cache():
    """Tải cache username từ tệp."""
    global username_cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                username_cache = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Error loading cache: {e}. Starting with empty cache.")
            username_cache = {}

def get_server_link(package_name, server_links):
    """Lấy link server cho một package từ danh sách đã lưu."""
    return next((link for pkg, link in server_links if pkg == package_name), None)

def load_accounts():
    """Tải danh sách tài khoản (package, user_id) từ tệp account.txt."""
    accounts = []
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, 'r') as file:
            for line in file:
                line = line.strip()
                if line:
                    try:
                        package, user_id = line.split(',', 1)
                        accounts.append((package, user_id))
                    except ValueError:
                        print(f"{Fore.RED}Invalid line format: {line}. Expected 'package,user_id'.{Style.RESET_ALL}")
    return accounts

def save_accounts(accounts):
    """Lưu danh sách tài khoản (package, user_id) vào tệp account.txt."""
    with open(ACCOUNTS_FILE, 'w') as file:
        for package, user_id in accounts:
            file.write(f'{package},{user_id}\n')

def load_server_links():
    """Tải danh sách link server (package, link) từ tệp server-link.txt."""
    server_links = []
    if os.path.exists(SERVER_LINKS_FILE):
        with open(SERVER_LINKS_FILE, 'r') as file:
            for line in file:
                line = line.strip()
                if line:
                    try:
                        package, link = line.strip().split(',', 1)
                        server_links.append((package, link))
                    except ValueError:
                         print(f"{Fore.RED}Invalid line format: {line}. Expected 'package,link'.{Style.RESET_ALL}")
    return server_links

def save_server_links(server_links):
    """Lưu danh sách link server (package, link) vào tệp server-link.txt."""
    with open(SERVER_LINKS_FILE, 'w') as file:
        for package, link in server_links:
            file.write(f'{package},{link}\n')


async def setup_rejoin_accounts(packages):
    """Thiết lập UserID cho các package."""
    old_accounts_dict = dict(load_accounts())
    new_accounts_dict = {}
    
    tasks = []
    packages_to_ask = []
    
    for pkg in packages:
        if pkg in old_accounts_dict and old_accounts_dict[pkg] != 'SKIPPED':
            new_accounts_dict[pkg] = old_accounts_dict[pkg]
            print(Fore.GREEN + f"Found existing account for {pkg}." + Style.RESET_ALL)
        else:
            username = input(Fore.CYAN + f"Enter Username for new package {pkg} (leave blank to skip): " + Style.RESET_ALL).strip()
            if username:
                tasks.append(get_user_id_from_username(username))
                packages_to_ask.append((pkg, username))
            else:
                new_accounts_dict[pkg] = 'SKIPPED'

    if tasks:
        print(Fore.YELLOW + "Fetching User IDs from Roblox API..." + Style.RESET_ALL)
        user_ids = await asyncio.gather(*tasks)
        
        for (pkg, username), user_id in zip(packages_to_ask, user_ids):
            if user_id:
                print(Fore.GREEN + f"Found User ID for {username}: {user_id}" + Style.RESET_ALL)
                new_accounts_dict[pkg] = str(user_id)
            else:
                print(Fore.RED + f"Could not find User ID for {username}. Skipping package {pkg}." + Style.RESET_ALL)
                new_accounts_dict[pkg] = 'SKIPPED'
            
    final_accounts = [(pkg, uid) for pkg, uid in new_accounts_dict.items() if uid != 'SKIPPED']
    save_accounts(final_accounts) 
    return final_accounts

def setup_server_links(accounts):
    """Thiết lập link server cho các package."""
    server_links = load_server_links()
    server_links_dict = dict(server_links)
    
    master_link = None
    
    for pkg, uid in accounts:
        if pkg not in server_links_dict:
            if master_link:
                server_links_dict[pkg] = master_link
                print(Fore.GREEN + f"Using master link for {pkg}" + Style.RESET_ALL)
                continue
                
            username = get_username(uid) # Blocking call
            link = input(Fore.CYAN + f"Enter server link (or Game ID) for {pkg} (Username: {username}): " + Style.RESET_ALL).strip()
            if link:
                server_links_dict[pkg] = link
                if not master_link:
                    master_link_choice = input(Fore.CYAN + "Use this link for all other packages? (y/n): " + Style.RESET_ALL).strip().lower()
                    if master_link_choice == 'y':
                        master_link = link
            else:
                print(Fore.RED + f"Skipping {pkg} as no server link was provided." + Style.RESET_ALL)

    final_links = [(pkg, link) for pkg, link in server_links_dict.items()]
    save_server_links(final_links)
    return final_links

def start_auto_rejoin():
    """Quy trình chính để bắt đầu Auto Rejoin."""
    global package_statuses # SỬA LỖI: Đảm bảo global được khai báo đầu tiên
    
    print_header()
    print(Fore.CYAN + "--- Auto Rejoin ---" + Style.RESET_ALL)
    stop_event.clear()

    # Chạy tác vụ chặn trong pool
    packages = executor_pool.submit(get_roblox_packages).result()
    if not packages:
        input(Fore.CYAN + "Press Enter to return to main menu..." + Style.RESET_ALL)
        return

    # 1. Thiết lập tài khoản (UserID) - Bất đồng bộ
    print(Fore.YELLOW + "Setting up accounts..." + Style.RESET_ALL)
    try:
        accounts = asyncio.run(setup_rejoin_accounts(packages))
    except RuntimeError:
        # Nếu đã có event loop chạy (hiếm), chạy thủ công
        accounts = setup_rejoin_accounts(packages)
        
    if not accounts:
        print(Fore.RED + "No accounts configured. Cannot start auto-rejoin." + Style.RESET_ALL)
        input(Fore.CYAN + "Press Enter to return to main menu..." + Style.RESET_ALL)
        return
        
    # 2. Thiết lập link server
    print(Fore.YELLOW + "Setting up server links..." + Style.RESET_ALL)
    server_links = setup_server_links(accounts)
    server_links_dict = dict(server_links)

    # 3. Phát hiện executor (Tác vụ chặn)
    print(Fore.YELLOW + "Detecting executors and writing LUA scripts..." + Style.RESET_ALL)
    detected_executors = executor_pool.submit(detect_and_write_lua_script).result()
    if detected_executors:
        print(Fore.GREEN + f"Detected executors: {', '.join(detected_executors)}" + Style.RESET_ALL)
    else:
        print(Fore.YELLOW + "No compatible executor found. Will join game without executor monitoring." + Style.RESET_ALL)

    # 4. Khởi động các package
    num_packages = len(accounts)
    package_statuses = {}
    threads = []
    
    # Khởi động luồng cập nhật UI
    status_thread = threading.Thread(target=status_update_thread_func, daemon=True)
    status_thread.start()
    threads.append(status_thread)

    for package_name, user_id in accounts:
        server_link = server_links_dict.get(package_name)
        if not server_link:
            logger.warning(f"No server link found for {package_name}. Skipping.")
            continue
            
        username = get_username(user_id)
        
        with status_lock:
            package_statuses[package_name] = {'Username': username, 'Status': Fore.YELLOW + 'Preparing...' + Style.RESET_ALL}
        
        # Thao tác tiền khởi động (Kill, Reset file)
        kill_roblox_process(package_name)
        reset_executor_file(username)
        
        # Khởi chạy Roblox (Chạy trong pool)
        executor_pool.submit(launch_roblox, package_name, server_link, num_packages, package_statuses)
        
        # Nếu phát hiện executor, khởi động luồng giám sát
        if detected_executors:
            monitor_thread = threading.Thread(
                target=background_executor_monitor,
                args=(package_name, username, package_statuses, server_link, num_packages),
                daemon=True
            )
            monitor_thread.start()
            threads.append(monitor_thread)

    print(Fore.GREEN + "All packages launched. Monitoring executor status..." + Style.RESET_ALL)
    print(Fore.CYAN + "Press 'q' and Enter to stop auto-rejoin and return to main menu." + Style.RESET_ALL)
    
    try:
        while True:
            # Chỉ cần kiểm tra input, UI được cập nhật bởi luồng riêng
            user_input = input().strip().lower()
            if user_input == 'q':
                break
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    
    print(Fore.YELLOW + "Stopping auto-rejoin... (Killing processes)" + Style.RESET_ALL)
    stop_event.set()
    
    # Giết tiến trình sau khi dừng
    for package_name, _ in accounts:
        kill_roblox_process(package_name)
    
    # Chờ các luồng monitor kết thúc (sử dụng timeout nhỏ)
    for t in threads:
        t.join(timeout=2)
        
    package_statuses = {} # Xóa trạng thái

# --- Hàm Main (Chính) ---

def main():
    """Hiển thị menu chính và điều hướng người dùng."""
    set_console_title('VCP Manager - VCP Rejoin')
    
    load_cache()
    
    load_webhook_config()
    if webhook_url:
        print(Fore.GREEN + "Webhook config loaded. Starting webhook thread..." + Style.RESET_ALL)
        start_webhook_thread()
    
    while True:
        menu_options = [
            'Auto Rejoin',
            'Webhook Setup',
            'Get Cookies from Device',
            'Inject Cookies and AppStorage',
            'Delete Roblox Cache',
            'Exit'
        ]
        create_dynamic_menu(menu_options)
        
        choice = input(Fore.CYAN + 'Select an option: ' + Style.RESET_ALL).strip()
        
        if choice == '1':
            start_auto_rejoin()
        elif choice == '2':
            setup_webhook()
        elif choice == '3':
            getcookie_process()
        elif choice == '4':
            # Chạy tác vụ chặn nặng trong pool
            executor_pool.submit(inject_cookies_and_appstorage).result() 
        elif choice == '5':
            # Chạy tác vụ chặn nặng trong pool
            executor_pool.submit(delete_roblox_cache).result() 
        elif choice == '6':
            print(Fore.YELLOW + 'Exiting... Thank thank for using VCP Manager!' + Style.RESET_ALL)
            stop_event.set()
            stop_webhook()
            save_cache()
            executor_pool.shutdown(wait=False) # Đóng pool
            sys.exit(0)
        else:
            print(Fore.RED + 'Invalid option. Please try again.' + Style.RESET_ALL)
            time.sleep(1)

if __name__ == '__main__':
    try:
        check_authencation()
        main()
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\nShutdown requested. Saving cache...")
        save_cache()
        stop_event.set()
        stop_webhook()
        executor_pool.shutdown(wait=False)
        print(Fore.GREEN + "Cache saved. Goodbye!")
        sys.exit(0)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        save_cache()
        executor_pool.shutdown(wait=False)
        sys.exit(1)