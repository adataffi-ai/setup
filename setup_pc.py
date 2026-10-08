"""
Self-contained, no-admin Windows setup script.

Needs ONLY Python (standard library, nothing to pip install). No winget, no
Microsoft Store. Everything else is downloaded directly by this script.

Does: dark theme, auto-hide taskbar, makes sure animations are ON, English (US)
keyboard, wallpaper, installs TranslucentTB + PowerToys + Chrome (per-user,
skipped if already installed), swaps Y<->Z with PowerToys, launches Chrome
once to finish its setup then closes it, and starts TranslucentTB.

Run:  python setup_pc.py
"""
import ctypes
import json
import os
import platform
import subprocess
import time
import urllib.request
import winreg

# ---------- CONFIG ----------
# DIRECT image link (right-click image on Pinterest -> "Copy image address",
# looks like https://i.pinimg.com/originals/xx/xx/....jpg).
# Leave empty and the script will ask you when it runs.
WALLPAPER_URL = ""

CHROME_URL = "https://dl.google.com/chrome/install/latest/chrome_installer.exe"
# ----------------------------

LOCALAPPDATA = os.environ["LOCALAPPDATA"]
PROGRAMFILES = os.environ.get("ProgramFiles", r"C:\Program Files")
PROGRAMFILES86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
TEMP = os.environ["TEMP"]
PICTURES = os.path.join(os.environ["USERPROFILE"], "Pictures")
ARCH = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x64"


def log(msg):
    print(f"[+] {msg}", flush=True)


def run(cmd, **kw):
    return subprocess.run(cmd, shell=True, **kw)


def powershell(command, capture=False):
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=capture, text=True,
    )


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        f.write(r.read())
    return dest


def github_asset(repo, match):
    """Return (name, url) of the first asset in the latest release where match(name_lower) is True."""
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases/latest",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        release = json.load(r)
    for a in release["assets"]:
        if match(a["name"].lower()):
            return a["name"], a["browser_download_url"]
    return None, None


def first_existing(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    return None


# ---------- "Is it already installed?" checks ----------
def chrome_exe():
    return first_existing([
        os.path.join(LOCALAPPDATA, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(PROGRAMFILES, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(PROGRAMFILES86, "Google", "Chrome", "Application", "chrome.exe"),
    ])


def powertoys_exe():
    return first_existing([
        os.path.join(LOCALAPPDATA, "PowerToys", "PowerToys.exe"),
        os.path.join(PROGRAMFILES, "PowerToys", "PowerToys.exe"),
    ])


def translucenttb_installed():
    r = powershell("(Get-AppxPackage *TranslucentTB*).PackageFullName", capture=True)
    return bool(r.stdout.strip())


# ---------- Dark theme ----------
def dark_theme():
    log("Enabling dark theme")
    key = winreg.CreateKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
    )
    winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, 0)
    winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, 0)
    winreg.CloseKey(key)


# ---------- Taskbar auto-hide ----------
def autohide_taskbar():
    log("Setting taskbar to auto-hide")
    path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StuckRects3"
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0,
                         winreg.KEY_READ | winreg.KEY_WRITE)
    data, _ = winreg.QueryValueEx(key, "Settings")
    data = bytearray(data)
    data[8] = 3  # 3 = auto-hide, 2 = always visible
    winreg.SetValueEx(key, "Settings", 0, winreg.REG_BINARY, bytes(data))
    winreg.CloseKey(key)


# ---------- Animations back ON ----------
def restore_animations():
    log("Turning Windows animations on")
    # Registry side (so the settings stick)
    k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop\WindowMetrics")
    winreg.SetValueEx(k, "MinAnimate", 0, winreg.REG_SZ, "1")
    winreg.CloseKey(k)
    k = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                         r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced")
    winreg.SetValueEx(k, "TaskbarAnimations", 0, winreg.REG_DWORD, 1)
    winreg.CloseKey(k)
    # 3 = "custom", so Windows doesn't re-apply a "best performance" preset
    k = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                         r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects")
    winreg.SetValueEx(k, "VisualFXSetting", 0, winreg.REG_DWORD, 3)
    winreg.CloseKey(k)

    # Live side (applies immediately)
    class ANIMATIONINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("iMinAnimate", ctypes.c_int)]

    user32 = ctypes.windll.user32
    flags = 3  # SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
    info = ANIMATIONINFO(ctypes.sizeof(ANIMATIONINFO), 1)
    user32.SystemParametersInfoW(0x0049, ctypes.sizeof(info), ctypes.byref(info), flags)  # window min/max animation
    for code in (
        0x103F,  # UI effects (master switch)
        0x1043,  # client-area animations ("Animation effects" in Settings)
        0x1003,  # menu animation
        0x1005,  # combo box animation
        0x1007,  # list box smooth scrolling
        0x1009,  # gradient captions
        0x1013,  # menu fade
        0x1015,  # selection fade
        0x1017,  # tooltip animation
        0x1019,  # tooltip fade
        0x101B,  # cursor shadow
    ):
        user32.SystemParametersInfoW(code, 0, ctypes.c_void_p(1), flags)


# ---------- Keyboard language ----------
def english_keyboard():
    log("Setting keyboard/language to English (US)")
    powershell("Set-WinUserLanguageList -LanguageList en-US -Force")
    powershell("Set-WinDefaultInputMethodOverride -InputTip '0409:00000409'")


def english_display_language():
    # Per-user only (no admin). Needs the English language pack to already be
    # installed on the PC - installing a NEW language pack would need admin.
    log("Setting Windows display language to English (US) for this user")
    r = powershell("Set-WinUILanguageOverride -Language en-US", capture=True)
    if r.returncode != 0:
        log("Couldn't set display language - English pack probably isn't installed "
            "(that part needs admin). Error: " + (r.stderr or "").strip()[:200])
    else:
        log("Display language set - takes effect after you sign out and back in")


# ---------- Wallpaper ----------
def set_wallpaper():
    url = WALLPAPER_URL.strip()
    if not url:
        url = input("Paste a direct wallpaper image link (or press Enter to skip): ").strip()
    if not url:
        log("No wallpaper link, skipping wallpaper")
        return
    log("Downloading and setting wallpaper")
    os.makedirs(PICTURES, exist_ok=True)
    ext = os.path.splitext(url.split("?")[0])[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".bmp"):
        ext = ".jpg"
    dest = os.path.join(PICTURES, "wallpaper" + ext)
    download(url, dest)
    # SPI_SETDESKWALLPAPER = 20, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE = 3
    ctypes.windll.user32.SystemParametersInfoW(20, 0, dest, 3)


# ---------- TranslucentTB (no Store, no winget) ----------
def install_translucenttb():
    if translucenttb_installed():
        log("TranslucentTB already installed, skipping")
        return
    log("Installing TranslucentTB")
    # 1) Easiest: the app installer file pulls in its own dependencies automatically
    r = powershell(
        "Add-AppxPackage -AppInstallerFile "
        "'https://github.com/TranslucentTB/TranslucentTB/releases/latest/download/TranslucentTB.appinstaller'"
    )
    if r.returncode == 0:
        return

    # 2) Fallback: download the package + the VC++ runtime package and install together
    log("App installer route failed, trying direct package + dependencies")
    try:
        name, url = github_asset(
            "TranslucentTB/TranslucentTB",
            lambda n: n.endswith((".msix", ".msixbundle")) and ARCH in n,
        )
        if not url:
            name, url = github_asset(
                "TranslucentTB/TranslucentTB",
                lambda n: n.endswith((".msix", ".msixbundle")),
            )
        if not url:
            log("Couldn't find a TranslucentTB package on GitHub")
            return
        pkg = download(url, os.path.join(TEMP, name))
        deps = []
        try:
            deps.append(download(
                f"https://aka.ms/Microsoft.VCLibs.{ARCH}.14.00.Desktop.appx",
                os.path.join(TEMP, f"VCLibs.{ARCH}.appx")))
        except Exception as e:
            log(f"Couldn't download VC++ dependency: {e}")
        dep_arg = ""
        if deps:
            dep_arg = " -DependencyPath " + ",".join(f"'{d}'" for d in deps)
        r = powershell(f"Add-AppxPackage -Path '{pkg}'{dep_arg}")
        if r.returncode != 0:
            log("TranslucentTB install failed (sideloading may be blocked on this PC)")
    except Exception as e:
        log(f"TranslucentTB install failed: {e}")


def launch_translucenttb():
    if not translucenttb_installed():
        log("TranslucentTB isn't installed, nothing to launch")
        return
    log("Launching TranslucentTB")
    powershell(
        "$p = Get-AppxPackage *TranslucentTB* | Select-Object -First 1; "
        "$id = ($p | Get-AppxPackageManifest).Package.Applications.Application.Id; "
        "Start-Process \"shell:AppsFolder\\$($p.PackageFamilyName)!$id\""
    )


# ---------- PowerToys (per-user installer from GitHub) ----------
def install_powertoys():
    if powertoys_exe():
        log("PowerToys already installed, skipping")
        return
    log("Installing PowerToys (per-user)")
    try:
        name, url = github_asset(
            "microsoft/PowerToys",
            lambda n: n.startswith("powertoysusersetup") and ARCH in n and n.endswith(".exe"),
        )
        if not url:
            log("Couldn't find the PowerToys per-user installer on GitHub")
            return
        installer = download(url, os.path.join(TEMP, name))
        subprocess.run([installer, "--silent"])
    except Exception as e:
        log(f"PowerToys install failed: {e}")


def kill_powertoys():
    for exe in ("PowerToys.exe", "PowerToys.KeyboardManagerEngine.exe",
                "PowerToys.KeyboardManagerEditor.exe"):
        run(f"taskkill /F /IM {exe} >nul 2>&1")
    time.sleep(2)


# ---------- PowerToys: swap Y <-> Z ----------
def swap_y_z():
    exe = powertoys_exe()
    if not exe:
        log("PowerToys isn't installed, can't set up the Y<->Z swap")
        return
    log("Configuring PowerToys Keyboard Manager (Y <-> Z)")

    # 1) Let PowerToys start once so it creates its own settings files, then stop it
    kill_powertoys()
    subprocess.Popen([exe])
    time.sleep(12)
    kill_powertoys()

    pt_dir = os.path.join(LOCALAPPDATA, "Microsoft", "PowerToys")
    kbm_dir = os.path.join(pt_dir, "Keyboard Manager")
    os.makedirs(kbm_dir, exist_ok=True)

    # 2) Make sure the Keyboard Manager module is switched ON
    general_path = os.path.join(pt_dir, "settings.json")
    general = {}
    if os.path.exists(general_path):
        try:
            with open(general_path, encoding="utf-8-sig") as f:
                general = json.load(f)
        except Exception:
            general = {}
    general.setdefault("enabled", {})["Keyboard Manager"] = True
    with open(general_path, "w", encoding="utf-8") as f:
        json.dump(general, f)

    # 3) Add the remaps (keeps any remaps you already had)
    # Virtual-key codes: Y = 0x59 = 89, Z = 0x5A = 90
    config_path = os.path.join(kbm_dir, "default.json")
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, encoding="utf-8-sig") as f:
                config = json.load(f)
        except Exception:
            config = {}
    config.setdefault("remapKeys", {}).setdefault("inProcess", [])
    config.setdefault("remapKeysToText", {}).setdefault("inProcess", [])
    config.setdefault("remapShortcuts", {}).setdefault("global", [])
    config["remapShortcuts"].setdefault("appSpecific", [])
    config.setdefault("remapShortcutsToText", {}).setdefault("global", [])
    config["remapShortcutsToText"].setdefault("appSpecific", [])
    existing = {e.get("originalKeys") for e in config["remapKeys"]["inProcess"]}
    for src, dst in (("89", "90"), ("90", "89")):
        if src not in existing:
            config["remapKeys"]["inProcess"].append(
                {"originalKeys": src, "newRemapKeys": dst})
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f)
    with open(os.path.join(kbm_dir, "settings.json"), "w", encoding="utf-8") as f:
        json.dump({"properties": {"activeConfiguration": {"value": "default"}}}, f)

    # 4) Start PowerToys again with the new config and check the remap engine is running
    subprocess.Popen([exe])
    time.sleep(8)
    out = run('tasklist /FI "IMAGENAME eq PowerToys.KeyboardManagerEngine.exe"',
              capture_output=True, text=True).stdout
    if "KeyboardManagerEngine" in out:
        log("Keyboard Manager engine is running - Y and Z should be swapped")
    else:
        log("Keyboard Manager engine is NOT running - open PowerToys > Keyboard Manager "
            "and check it's enabled")


# ---------- Chrome ----------
def install_chrome_and_run():
    if chrome_exe():
        log("Chrome already installed, skipping")
        return
    log("Downloading Chrome installer")
    installer = download(CHROME_URL, os.path.join(TEMP, "chrome_installer.exe"))
    log("Installing Chrome (per-user, this can take a minute)")
    run(f'"{installer}" /silent /install')

    chrome = None
    for _ in range(60):  # wait up to ~2 min for the install to finish
        chrome = chrome_exe()
        if chrome:
            break
        time.sleep(2)
    if not chrome:
        log("Chrome didn't show up - install may have failed")
        return

    log("Launching Chrome once to finish setup")
    subprocess.Popen([chrome, "--no-first-run", "about:blank"])
    time.sleep(15)
    run("taskkill /F /IM chrome.exe >nul 2>&1")
    log("Chrome closed")


# ---------- Restart Explorer so taskbar/theme changes apply ----------
def restart_explorer():
    log("Restarting Explorer")
    run("taskkill /F /IM explorer.exe >nul 2>&1")
    time.sleep(1)
    subprocess.Popen("explorer.exe")
    time.sleep(3)


def step(fn):
    """Run a step; if it crashes, report and keep going."""
    try:
        fn()
    except Exception as e:
        log(f"{fn.__name__} failed: {e}")


def main():
    for fn in (dark_theme, autohide_taskbar, english_keyboard,
               english_display_language, set_wallpaper,
               install_translucenttb, install_powertoys, install_chrome_and_run,
               swap_y_z, restart_explorer, restore_animations, launch_translucenttb):
        step(fn)
    log("Done! Restarting in 15 seconds so the language applies (run 'shutdown /a' to cancel)")
    run("shutdown /r /t 15")


if __name__ == "__main__":
    main()
