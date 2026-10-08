# PC setup

No-admin Windows setup: dark theme, auto-hide taskbar, English language/keyboard,
wallpaper, Chrome, PowerToys (Y/Z swap), TranslucentTB. Restarts at the end.

## Run on a fresh PC

Open cmd and paste:

```
curl -L -o setup_pc.py https://raw.githubusercontent.com/adataffi-ai/setup/main/setup_pc.py
```

## Files

- `setup_pc.py` - the setup script (standard library only)
- `s.bat` - downloads portable Python and runs the script

ARM PC? Change `amd64` to `arm64` in `s.bat`.
