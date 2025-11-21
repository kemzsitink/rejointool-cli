import os
import sys
import json
import time
import shutil
import sqlite3
import psutil
import requests
import subprocess
import threading
import re
from threading import Lock, Event
from colorama import init, Fore, Style
from prettytable import PrettyTable
from loguru import logger
from datetime import datetime, timezone

# --- CẤU HÌNH LOGGER ---
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>", level="INFO")

# --- KHỞI TẠO COLORAMA ---
init(autoreset=True)

# --- CONSTANTS (HẰNG SỐ) ---
FILES = {
    'SERVER_LINKS': 'server-link.txt',
    'ACCOUNTS': 'account.txt',
    'CACHE': 'username_cache.json',
    'CONFIG_WH': 'config-wh.json',
    'COOKIE_TXT': 'cookie.txt',
    'AUTH_URL': 'https://raw.githubusercontent.com/kemzsitink/rejointool-cli/refs/heads/main/Authencator',
    'LUA_URL': 'https://raw.githubusercontent.com/kemzsitink/rejointool-cli/refs/heads/main/GEMINI.lua',
    'COOKIES_DB_URL': 'https://raw.githubusercontent.com/kemzsitink/rejointool-cli/refs/heads/main/Cookies',
    'APP_STORAGE_URL': 'https://raw.githubusercontent.com/kemzsitink/rejointool-cli/refs/heads/main/appStorage.json'
}

EXECUTORS = {
    'Fluxus': '/storage/emulated/0/Fluxus/',
    'Codex': '/storage/emulated/0/Codex/',
    'Arceus X': '/storage/emulated/0/Arceus X/',
    'Delta': '/storage/emulated/0/Delta/',
    'Cryptic': '/storage/emulated/0/Cryptic/',
    'VegaX': '/storage/emulated/0/VegaX/',
    'Trigon': '/storage/emulated/0/Trigon/'
}

# ==========================================
# CLASS: ROBLOX API HANDLER
# ==========================================
class RobloxAPI:
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }

    @staticmethod
    def get_info_by_cookie(cookie):
        url = 'https://users.roblox.com/v1/users/authenticated'
        cookie_value = cookie.split(".ROBLOSECURITY=")[1].split(";")[0] if ".ROBLOSECURITY=" in cookie else cookie
        headers = RobloxAPI.HEADERS.copy()
        headers['Cookie'] = f'.ROBLOSECURITY={cookie_value}'
        try:
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return str(data.get('name')), str(data.get('id'))
        except: pass
        return None, None

    @staticmethod
    def get_id_by_username(username):
        url = 'https://users.roblox.com/v1/usernames/users'
        payload = {"usernames": [username], "excludeBannedUsers": True}
        try:
            response = requests.post(url, json=payload, headers=RobloxAPI.HEADERS, timeout=5)
            if response.status_code == 200 and response.json().get('data'):
                return str(response.json()['data'][0]['id'])
        except: pass
        return None

    @staticmethod
    def get_username_by_id(user_id):
        url = f'https://users.roblox.com/v1/users/{user_id}'
        try:
            response = requests.get(url, headers=RobloxAPI.HEADERS, timeout=5)
            if response.status_code == 200:
                return str(response.json().get('name'))
        except: pass
        return "Unknown"

# ==========================================
# CLASS: UTILITIES (FIXED LOGO VCP MANAGER)
# ==========================================
class Utils:
    @staticmethod
    def clear_console(): 
        os.system('cls' if os.name == 'nt' else 'clear')
    
    @staticmethod
    def set_title(title):
        if os.name == 'nt': os.system(f'title {title}')
        else: print(f'\033]0;{title}\007', end='', flush=True)

    @staticmethod
    def print_header():
        try: columns = shutil.get_terminal_size().columns
        except: columns = 80
        
        # Logo VCP Manager
        logo = r"""
 __      __  _____  _____   __  __                                   
 \ \    / / / ____||  __ \ |  \/  |                                  
  \ \  / / | |     | |__) || \  / | __ _  _ __   __ _   __ _  ___  _ __ 
   \ \/ /  | |     |  ___/ | |\/| |/ _` || '_ \ / _` | / _` |/ _ \| '__|
    \  /   | |____ | |     | |  | || (_| || | | || (_| || (_| || __/| |   
     \/     \_____||_|     |_|  |_|\__,_||_| |_|\__,_| \__, |\___||_|   
                                                        __/ |          
                                                       |___/           
        """
        
        print(Fore.LIGHTBLUE_EX + ("=" * columns) + Style.RESET_ALL)
        for line in logo.split('\n'):
            if line.strip():
                print(Fore.LIGHTCYAN_EX + line.center(columns) + Style.RESET_ALL)
        
        print(Fore.LIGHTYELLOW_EX + "Dev by kem & Gemini".center(columns) + Style.RESET_ALL)
        print(Fore.LIGHTBLUE_EX + ("=" * columns) + Style.RESET_ALL)

    @staticmethod
    def check_root():
        try:
            res = subprocess.run(['su', '-c', 'id'], capture_output=True, text=True)
            return res.returncode == 0 and 'uid=0' in res.stdout
        except: return False

    @staticmethod
    def run_root_cmd(command):
        try:
            result = subprocess.run(f'su -c "{command}"', shell=True, capture_output=True, text=True)
            return result.stdout.strip()
        except Exception as e: logger.error(f"Root CMD Error: {e}"); return None

    @staticmethod
    def get_package_uid(package_name):
        try:
            output = subprocess.check_output(f'pm list packages -U | grep {package_name}', shell=True, text=True)
            if 'uid:' in output: return output.split('uid:')[1].strip()
        except: pass
        return None

    @staticmethod
    def fix_permissions(path, uid):
        if uid: Utils.run_root_cmd(f'chown -R {uid}:{uid} {path} && chmod -R 777 {path}')

    @staticmethod
    def check_authentication():
        try:
            if requests.get(FILES['AUTH_URL'], timeout=10).text.strip().lower() == 'true':
                logger.success("Authorized Access.")
                return True
            logger.error("Not Authorized."); sys.exit(0)
        except: logger.error("Auth Connection Failed."); sys.exit(1)

# ==========================================
# CLASS: ACCOUNT DETECTOR
# ==========================================
class AccountDetector:
    @staticmethod
    def get_user_info_from_app_storage(package_name):
        try:
            remote = f'/data/data/{package_name}/files/appData/LocalStorage/appStorage.json'
            local = f'/sdcard/Download/temp_st_{package_name}.json'
            Utils.run_root_cmd(f'cp {remote} {local} && chmod 666 {local}')
            if not os.path.exists(local): return None, None
            
            username, user_id = None, None
            try:
                with open(local, 'r', encoding='utf-8', errors='ignore') as f:
                    data = json.load(f)
                    username = data.get('Username') or data.get('AccountName')
                    user_id = str(data.get('UserId')) if data.get('UserId') else None
            except: pass
            os.remove(local)
            
            if username and not user_id: user_id = RobloxAPI.get_id_by_username(username)
            if username and user_id: return str(username), str(user_id)
        except: pass
        return None, None

    @staticmethod
    def get_user_info_from_cookie_db(package_name):
        try:
            remote = f'/data/data/{package_name}/app_webview/Default/Cookies'
            local = f'/sdcard/Download/temp_ck_{package_name}.db'
            Utils.run_root_cmd(f'cp {remote} {local} && chmod 666 {local}')
            if not os.path.exists(local): return None, None
            
            cookie_val = None
            try:
                conn = sqlite3.connect(local); cur = conn.cursor()
                cur.execute("SELECT value FROM cookies WHERE host_key LIKE '%roblox.com%' AND name = '.ROBLOSECURITY'")
                res = cur.fetchone()
                if res: cookie_val = res[0]
                conn.close()
            except: pass
            os.remove(local)
            if cookie_val: return RobloxAPI.get_info_by_cookie(cookie_val)
        except: pass
        return None, None

# ==========================================
# CLASS: WEBHOOK MANAGER (CLEAN & NO STORAGE)
# ==========================================
class WebhookManager:
    def __init__(self):
        self.config = self.load_config()
        self.stop_event = Event()
        self.thread = None

    def load_config(self):
        if os.path.exists(FILES['CONFIG_WH']):
            with open(FILES['CONFIG_WH'], 'r') as f: return json.load(f)
        return {}

    def save_config(self, url, name, interval):
        cfg = {'webhook_url': url, 'device_name': name, 'interval': interval}
        with open(FILES['CONFIG_WH'], 'w') as f: json.dump(cfg, f, indent=4)
        self.config = cfg

    def get_battery_level(self):
        try:
            out = Utils.run_root_cmd("dumpsys battery")
            if out:
                for line in out.splitlines():
                    if "level" in line:
                        return f"{line.split(':')[1].strip()}%"
        except: pass
        
        paths = ["/sys/class/power_supply/battery/capacity"]
        for p in paths:
            if os.path.exists(p):
                try:
                    with open(p, "r") as f: return f"{f.read().strip()}%"
                except: pass
        return "N/A"

    def capture_screenshot(self):
        path = '/sdcard/Download/screenshot.png'
        if os.path.exists(path): 
            try: os.remove(path)
            except: pass

        cmds = [f'screencap -p {path}', f'screencap -p > {path}']
        for cmd in cmds:
            if Utils.check_root(): Utils.run_root_cmd(cmd)
            else: subprocess.run(cmd, shell=True)
            
            if os.path.exists(path) and os.path.getsize(path) > 0:
                return path
        return None

    def send_loop(self):
        ICON_URL = "https://cdn.discordapp.com/attachments/1368608156477034601/1440813962726998159/snapedit_1762772913226.png?ex=691f8611&is=691e3491&hm=42909be797ec991ab68218bf267f6ca166ea97d019577b8986cd49cf4f3b5cb7&"

        while not self.stop_event.is_set():
            try:
                url = self.config.get('webhook_url'); 
                if not url: break
                
                path = self.capture_screenshot()
                
                cpu = psutil.cpu_percent(interval=1)
                uptime = round((time.time() - psutil.boot_time()) / 3600, 1)
                bat = self.get_battery_level()

                # --- ĐÃ XÓA STORAGE, RAM, ROBLOX COUNT ---
                
                color = 2354029 
                if cpu > 90: color = 16711680 

                embed = {
                    'title': f"Device Status: {self.config.get('device_name')}", 
                    'description': f"**Last Updated:** <t:{int(time.time())}:R>",
                    'color': color,
                    'fields': [
                        {'name': '⚡ Battery', 'value': f"`{bat}`", 'inline': True},
                        {'name': '⏳ Uptime', 'value': f"`{uptime}h`", 'inline': True},
                        {'name': '🧠 CPU', 'value': f"`{cpu}%`", 'inline': True},
                    ],
                    'footer': {
                        'text': 'VCPCloud',
                        'icon_url': ICON_URL
                    },
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
                files = None
                if path:
                    files = {'file': ('ss.png', open(path, 'rb'))}
                    embed['image'] = {'url': 'attachment://ss.png'}
                
                payload = {
                    'username': 'VCPCloud Monitor',
                    'avatar_url': ICON_URL,
                    'embeds': [embed]
                }
                
                try:
                    requests.post(url, data={'payload_json': json.dumps(payload)}, files=files)
                    logger.info("Webhook sent.")
                except Exception as e: logger.error(f"Post Err: {e}")
                finally: 
                    if files: files['file'][1].close()

            except Exception as e: logger.error(f"WH Err: {e}")
            
            if self.stop_event.wait(self.config.get('interval', 10) * 60): break

    def start(self):
        if self.thread and self.thread.is_alive(): return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.send_loop, daemon=True)
        self.thread.start()

    def stop(self): self.stop_event.set()

    def ui(self):
        Utils.print_header()
        url = input("Webhook URL: ").strip()
        name = input("Device Name: ").strip()
        try: interval = int(input("Interval (min): ").strip())
        except: interval = 10
        self.save_config(url, name, interval)
        self.stop(); self.start()
        input(Fore.GREEN + "Saved! Enter..." + Style.RESET_ALL)

# ==========================================
# CLASS: COOKIE MANAGER
# ==========================================
class CookieManager:
    @staticmethod
    def get_packages():
        try:
            out = subprocess.check_output('pm list packages', shell=True, text=True)
            return [l.split(':')[1].strip() for l in out.splitlines() if 'com.roblox.' in l]
        except: return []

    @staticmethod
    def download(url, dest):
        try:
            r = requests.get(url, stream=True, timeout=10)
            if r.status_code == 200:
                with open(dest, 'wb') as f: shutil.copyfileobj(r.raw, f)
                return True
        except: pass
        return False

    @staticmethod
    def inject():
        Utils.print_header()
        if not Utils.check_root(): print(Fore.RED + "ROOT REQUIRED!"); input("Enter..."); return
        
        CookieManager.download(FILES['COOKIES_DB_URL'], 'Cookies.db')
        CookieManager.download(FILES['APP_STORAGE_URL'], 'appStorage.json')
        
        if not os.path.exists(FILES['COOKIE_TXT']): open(FILES['COOKIE_TXT'], 'w').close()
        with open(FILES['COOKIE_TXT']) as f: cookies = [l.strip() for l in f if l.strip()]
        pkgs = CookieManager.get_packages()
        if not pkgs: print(Fore.RED + "No Roblox found."); input("Enter..."); return

        for i, pkg in enumerate(pkgs):
            if i >= len(cookies): break
            cookie = cookies[i].split(':')[-1] if cookies[i].count(':') >= 2 else cookies[i]
            info = RobloxAPI.get_info_by_cookie(cookie)
            if not info[0]: print(Fore.RED + f"Invalid Cookie -> {pkg}"); continue

            print(Fore.CYAN + f"Injecting {info[0]} -> {pkg}...")
            data_p = f'/data/data/{pkg}'
            db_d, st_d = f'{data_p}/app_webview/Default', f'{data_p}/files/appData/LocalStorage'
            Utils.run_root_cmd(f'mkdir -p {db_d} {st_d}')
            
            t_db, t_st = f'/sdcard/Download/t_ck_{pkg}.db', f'/sdcard/Download/t_st_{pkg}.json'
            shutil.copy('Cookies.db', t_db); shutil.copy('appStorage.json', t_st)

            try:
                conn = sqlite3.connect(t_db); cur = conn.cursor(); now = int(time.time()*1000000)
                cur.execute("DELETE FROM cookies WHERE host_key LIKE '%roblox.com%' AND name = '.ROBLOSECURITY'")
                cur.execute("INSERT INTO cookies (creation_utc, host_key, name, value, path, expires_utc, is_secure, is_httponly, last_access_utc, has_expires, is_persistent, priority, samesite, source_scheme, source_port, is_same_party) VALUES (?, '.roblox.com', '.ROBLOSECURITY', ?, '/', ?, 0, 0, ?, 1, 1, 1, -1, 1, 443, 0)", (now, cookie, 33136956590883624, now))
                conn.commit(); conn.close()
            except: pass

            Utils.run_root_cmd(f'cp {t_db} {db_d}/Cookies && cp {t_st} {st_d}/appStorage.json && rm {t_db} {t_st}')
            Utils.fix_permissions(f'{data_p}/app_webview', Utils.get_package_uid(pkg))
            Utils.fix_permissions(f'{data_p}/files', Utils.get_package_uid(pkg))
            print(Fore.GREEN + f"Success -> {pkg}")
        input("Done. Enter...")

    @staticmethod
    def clean_cache():
        if not Utils.check_root(): return
        for p in CookieManager.get_packages():
            Utils.run_root_cmd(f'rm -rf /data/data/{p}/cache/*'); print(f"Cleared: {p}")
        input("Done. Enter...")

# ==========================================
# CLASS: REJOIN MANAGER (CORE)
# ==========================================
class RejoinManager:
    def __init__(self):
        self.lock = Lock()
        self.statuses = {}
        self.stop_event = Event()
        self.name_cache = {}
        self.debug_mode = True
        self.launch_times = {} 
        self.MAX_LOAD_TIME = 180 
        
        if os.path.exists(FILES['CACHE']):
            try:
                with open(FILES['CACHE']) as f:
                    self.name_cache = json.load(f)
            except:
                pass

    def get_name(self, uid):
        if uid in self.name_cache: return self.name_cache[uid]
        name = RobloxAPI.get_username_by_id(uid)
        if name != 'Unknown': self.name_cache[uid] = name
        return name

    def setup_lua(self):
        script = f'-- Auto Gen\nloadstring(game:HttpGet("{FILES["LUA_URL"]}"))()\n'
        for n, p in EXECUTORS.items():
            if os.path.exists(p):
                ae = os.path.join(p, 'Autoexec')
                os.makedirs(ae, exist_ok=True)
                with open(os.path.join(ae, 'check.lua'), 'w') as f: f.write(script)

    def ui_loop(self):
        while not self.stop_event.is_set():
            Utils.clear_console(); Utils.print_header()
            t = PrettyTable(['Package', 'User', 'Status']); t.align = 'l'
            with self.lock:
                for p, d in self.statuses.items(): t.add_row([p, d['user'], d['status']])
            print(t)
            print(Fore.YELLOW + "\nLogs (Debug):" + Style.RESET_ALL)
            with self.lock:
                if 'last_error' in self.statuses: print(Fore.RED + f"Err: {self.statuses['last_error']}" + Style.RESET_ALL)
            print(Fore.YELLOW + "\nPress Enter to Stop..." + Style.RESET_ALL)
            time.sleep(2)

    def _execute_launch_cmd(self, cmd, use_root=False):
        full_cmd = f'su -c "{cmd}"' if use_root else cmd
        try:
            result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0 and self.debug_mode:
                return False
            return True
        except: return False

    def launch(self, pkg, link, user):
        try:
            with self.lock: 
                self.statuses[pkg]['status'] = Fore.CYAN + "Launching..." + Style.RESET_ALL
                self.launch_times[pkg] = time.time() 
            
            final_cmd_link = ""
            if "privateServerLinkCode" in link: final_cmd_link = link
            elif link.isdigit(): final_cmd_link = f"roblox://placeID={link}"
            else:
                place_id = ""
                if 'placeId=' in link: place_id = link.split('placeId=')[1].split('&')[0]
                elif 'games/' in link: 
                    try: place_id = link.split('games/')[1].split('/')[0]
                    except: pass
                final_cmd_link = f"roblox://placeID={place_id}" if place_id else link

            # 1. Clean
            Utils.run_root_cmd(f'am force-stop {pkg}')
            for _, p in EXECUTORS.items():
                f = os.path.join(p, 'Workspace', f'executor_check_{user}.txt')
                if os.path.exists(f): os.remove(f)
            time.sleep(1)

            # 2. Wake Up
            with self.lock: self.statuses[pkg]['status'] = Fore.YELLOW + "Opening..." + Style.RESET_ALL
            Utils.run_root_cmd(f'monkey -p {pkg} -c android.intent.category.LAUNCHER 1')

            # 3. Wait Loading
            for i in range(12, 0, -1):
                with self.lock: self.statuses[pkg]['status'] = Fore.YELLOW + f"Loading... {i}s" + Style.RESET_ALL
                time.sleep(1)

            # 4. Join
            with self.lock: self.statuses[pkg]['status'] = Fore.MAGENTA + "Joining..." + Style.RESET_ALL
            
            cmd_join = f'am start -n {pkg}/com.roblox.client.ActivityProtocolLaunch -d "{final_cmd_link}" --ez launchInApp true'
            cmd_fallback = f'am start -a android.intent.action.VIEW -d "{final_cmd_link}" -p {pkg} --ez launchInApp true'

            Utils.run_root_cmd(cmd_join)
            time.sleep(2)
            Utils.run_root_cmd(cmd_fallback)

            with self.lock: self.statuses[pkg]['status'] = Fore.GREEN + "Signal Sent" + Style.RESET_ALL

        except Exception as e:
             with self.lock: self.statuses[pkg]['status'] = Fore.RED + f"Err: {str(e)[:15]}" + Style.RESET_ALL

    def monitor(self, pkg, uid, link):
        user = self.get_name(uid)
        fail_count = 0
        
        while not self.stop_event.is_set():
            time.sleep(10)
            if self.stop_event.is_set(): break

            try: running = pkg in subprocess.check_output(['ps', '-A'], text=True)
            except: running = any(pkg in p.info['name'] for p in psutil.process_iter(['name']))

            if not running:
                with self.lock: self.statuses[pkg]['status'] = Fore.RED + "Crashed! Rejoining..." + Style.RESET_ALL
                self.launch(pkg, link, user)
                time.sleep(20); continue

            active = False
            fname = f'executor_check_{user}.txt'
            for _, path in EXECUTORS.items():
                t_path = os.path.join(path, 'Workspace', fname)
                if os.path.exists(t_path) and (time.time() - os.path.getmtime(t_path) < 60):
                    active = True; break
            
            if active:
                fail_count = 0
                with self.lock: self.statuses[pkg]['status'] = Fore.GREEN + "Running" + Style.RESET_ALL
            else:
                launch_time = self.launch_times.get(pkg, 0)
                elapsed = time.time() - launch_time
                
                if elapsed < self.MAX_LOAD_TIME:
                    remaining = int(self.MAX_LOAD_TIME - elapsed)
                    with self.lock: self.statuses[pkg]['status'] = Fore.YELLOW + f"Game Loading... ({remaining}s)" + Style.RESET_ALL
                    fail_count = 0
                else:
                    fail_count += 1
                    if fail_count >= 3:
                        with self.lock: self.statuses[pkg]['status'] = Fore.RED + "Frozen/Timeout! Rejoining..." + Style.RESET_ALL
                        self.launch(pkg, link, user)
                        fail_count = 0
                        time.sleep(20)

    def run(self):
        self.stop_event.clear()
        pkgs = CookieManager.get_packages()
        if not pkgs: return

        # --- ACCOUNT SETUP ---
        acc_map = {} 
        if os.path.exists(FILES['ACCOUNTS']):
            with open(FILES['ACCOUNTS']) as f:
                acc_map = {l.split(',')[0]: l.split(',')[1].strip() for l in f if ',' in l}

        if Utils.check_root():
            print(Fore.YELLOW + "Scanning accounts..." + Style.RESET_ALL)
            for p in pkgs:
                if p not in acc_map:
                    print(f"Scan {p}...", end='\r')
                    u, i = AccountDetector.get_user_info_from_app_storage(p)
                    if not i: u, i = AccountDetector.get_user_info_from_cookie_db(p)
                    if i: 
                        print(Fore.GREEN + f"Found: {p} -> {u}" + Style.RESET_ALL)
                        acc_map[p] = i; self.name_cache[i] = u
        
        for p in pkgs:
            if p not in acc_map:
                nm = input(f"Manual User for {p} (Enter skip): ").strip()
                if nm:
                    id_ = RobloxAPI.get_id_by_username(nm)
                    if id_: acc_map[p] = id_

        with open(FILES['ACCOUNTS'], 'w') as f: 
            for p, i in acc_map.items(): f.write(f"{p},{i}\n")
        with open(FILES['CACHE'], 'w') as f: json.dump(self.name_cache, f)

        # --- GAME SETUP MENU ---
        links = {}
        
        Utils.clear_console()
        Utils.print_header()
        print(Fore.CYAN + "--- GAME SETUP OPTIONS ---" + Style.RESET_ALL)
        print("1. Global Place ID (Public Server)")
        print("2. Global Private Server Link (VIP)")
        print("3. Load Saved Individual Links")
        print("4. Setup New Individual Links")
        
        choice = input(Fore.GREEN + "Select Option (1-4): " + Style.RESET_ALL).strip()
        
        if choice == '1':
            pid = input("Enter Global Place ID: ").strip()
            if pid:
                for p in acc_map: links[p] = pid
                with open(FILES['SERVER_LINKS'], 'w') as f:
                    for p, l in links.items(): f.write(f"{p},{l}\n")
        elif choice == '2':
            vlink = input("Enter VIP Link: ").strip()
            if vlink:
                for p in acc_map: links[p] = vlink
                with open(FILES['SERVER_LINKS'], 'w') as f:
                    for p, l in links.items(): f.write(f"{p},{l}\n")
        elif choice == '3':
            if os.path.exists(FILES['SERVER_LINKS']):
                with open(FILES['SERVER_LINKS']) as f:
                    links = {l.split(',')[0]: l.split(',')[1].strip() for l in f if ',' in l}
            for p in acc_map:
                if p not in links:
                    l = input(f"Enter link for {p}: ").strip()
                    if l: links[p] = l
            with open(FILES['SERVER_LINKS'], 'w') as f:
                for p, l in links.items(): f.write(f"{p},{l}\n")
        elif choice == '4':
            for p in acc_map:
                user = self.get_name(acc_map[p])
                l = input(f"Link for {p} ({user}): ").strip()
                if l: links[p] = l
            with open(FILES['SERVER_LINKS'], 'w') as f:
                for p, l in links.items(): f.write(f"{p},{l}\n")
        else:
            if os.path.exists(FILES['SERVER_LINKS']):
                with open(FILES['SERVER_LINKS']) as f:
                    links = {l.split(',')[0]: l.split(',')[1].strip() for l in f if ',' in l}

        # --- EXECUTION ---
        self.setup_lua()
        self.statuses = {}
        threads = []
        
        print(Fore.YELLOW + "Starting..." + Style.RESET_ALL)
        threading.Thread(target=self.ui_loop, daemon=True).start()

        for p, uid in acc_map.items():
            if p not in links or not links[p]: continue
            user = self.get_name(uid)
            self.statuses[p] = {'user': user, 'status': 'Starting'}
            
            self.launch(p, links[p], user)
            t = threading.Thread(target=self.monitor, args=(p, uid, links[p]), daemon=True)
            t.start(); threads.append(t)
            time.sleep(5)

        input() # Block
        self.stop_event.set()
        print(Fore.YELLOW + "Stopping...")
        for p in acc_map: 
            if Utils.check_root(): Utils.run_root_cmd(f'am force-stop {p}')
            else: subprocess.run(['am', 'force-stop', p], stdout=subprocess.DEVNULL)

# ==========================================
# MAIN
# ==========================================
def main():
    Utils.check_authentication()
    Utils.set_title("VCP Manager Pro")
    wh = WebhookManager()
    if wh.config.get('webhook_url'): wh.start()

    try:
        while True:
            Utils.clear_console(); Utils.print_header()
            menu = ["Auto Rejoin", "Webhook Setup", "Inject Cookies", "Clear Cache", "Exit"]
            t = PrettyTable(['#', 'Option']); t.align = 'l'
            for i, o in enumerate(menu, 1): t.add_row([i, o])
            print(Fore.CYAN + str(t))
            c = input(Fore.GREEN + "> " + Style.RESET_ALL).strip()
            
            if c == '1': RejoinManager().run()
            elif c == '2': wh.ui()
            elif c == '3': CookieManager.inject()
            elif c == '4': CookieManager.clean_cache()
            elif c == '5': wh.stop(); sys.exit()
    except KeyboardInterrupt: wh.stop(); sys.exit()

if __name__ == "__main__":
    main()