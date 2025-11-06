#!/bin/bash
termux-setup-storage && yes | pkg update && yes | pkg upgrade && yes | pkg i python && yes | pkg install python-pip && pkg install python tsu libexpat openssl -y && pip install requests psutil loguru prettytable colorama aiohttp
curl -Ls "https://raw.githubusercontent.com/kemzsitink/rejointool-cli/refs/heads/main/rejointool-cli.py" -o /sdcard/Download/Rejoin.py