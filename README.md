# VCP Manager

[![GitHub stars](https://img.shields.io/github/stars/kemzsitink/rejointool-cli?style=social)](https://github.com/kemzsitink/rejointool-cli)
[![GitHub license](https://img.shields.io/github/license/kemzsitink/rejointool-cli)](https://github.com/kemzsitink/rejointool-cli)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)



Please ⭐ this repo so I get motivated working on this project! Otherwise I'll stop patching 😊

> **Disclaimer**: Only for research/education only. **The author assumes no responsibility for any misuse, consequences, or account actions resulting from your use of this library.**

> Don't sell this open-source project. Shame on you if you do.

## Project Overview

This project is a Python-based command-line tool named "VCP Manager," designed to manage multiple Roblox clients on an Android device. The script is written primarily in Vietnamese and leverages various Python libraries to provide its functionality.

The main features of the VCP Manager include:

*   **Auto Rejoin:** This feature allows users to automatically rejoin a Roblox game server if the client crashes or becomes unresponsive. It monitors the status of script executors (like Fluxus, Codex, Arceus X) and can handle multiple Roblox application packages simultaneously.
*   **Webhook Monitoring:** The tool can send device status information, including CPU usage, memory usage, and uptime, along with a screenshot, to a specified Discord webhook URL at regular intervals. This is useful for remote monitoring of the device.
*   **Cookie Management:**
    *   **Get Cookies:** It can extract `.ROBLOSECURITY` authentication cookies from the installed Roblox clients on the device.
    *   **Inject Cookies:** It allows users to inject cookies into the Roblox clients, enabling them to switch between different user accounts without manual login.
*   **Cache Management:** The tool provides an option to delete the cache files for all detected Roblox applications, which can help in troubleshooting or freeing up space.

The script uses external libraries such as `requests` for HTTP requests, `psutil` for system monitoring, `colorama` and `prettytable` for a formatted command-line interface, and `loguru` for logging.

## Building and Running

This project is a single-file Python script and does not have a complex build process.

**Prerequisites:**

*   Python 3.x
*   The required Python packages can be installed using pip:
    ```bash
    pip install requests psutil loguru prettytable colorama aiohttp
    ```

**Running the application:**

To run the VCP Manager, execute the following command in your terminal:

```bash
python a.py
```

Upon running, the script will display a menu with the available options in Vietnamese.

## Development Conventions

*   **Language:** The code, comments, and user-facing strings are predominantly in Vietnamese.
*   **Configuration Files:** The tool uses several files to store its configuration and data:
    *   `server-link.txt`: Stores the server links for the auto-rejoin feature.
    *   `account.txt`: Maps Roblox packages to user IDs.
    *   `config-wh.json`: Contains the configuration for the webhook feature (URL, device name, interval).
    *   `cookie.txt`: Used as a source for cookies to be injected into the clients.
    *   `username_cache.json`: Caches usernames to reduce API calls.
*   **User Interface:** The script uses `colorama` for colored output and `prettytable` to display information in a structured table format, creating a user-friendly command-line interface.
*   **Concurrency:** The script makes use of Python's `threading` module to run the webhook and auto-rejoin monitoring tasks in the background, allowing the user to interact with the main menu while these tasks are running. It also uses `asyncio` and `aiohttp` for performing asynchronous API calls to fetch user information from the Roblox API.
*   **Error Handling:** The code includes `try...except` blocks to gracefully handle potential runtime errors, such as network failures, file I/O issues, or invalid user input.
*   **Platform Specificity:** The script is designed to run on an Android environment, as indicated by the use of Android-specific paths (e.g., `/storage/emulated/0/`, `/data/data/`) and shell commands (`pm`, `am`, `pkill`).
</details>

</details>

## Contributing

Contact: `@_hongaan` on discord

## License

[MIT](LICENSE)

## Thanks to

https://github.com/thieusitinks/Rokid-Manager
