"""
Path resolution helper that centralizes where the app stores its data.

All user data lives in a single, well-organized folder under the user's
Documents directory (in pt-BR), regardless of running from source or from
the frozen EXE:

    Documentos/Análises de Crédito/
    ├── configs/           -> config JSONs (UI settings, params) and logs
    ├── relatorios/        -> generated PDF reports
    └── analysis_history.json

Only the bundled assets (logo/icon) come from the EXE / source tree.
"""
import os
import sys

MAIN_FOLDER_NAME = 'Análises de Crédito'
CONFIG_SUBFOLDER = 'configs'
REPORTS_SUBFOLDER = 'relatorios'
HISTORY_FILENAME = 'analysis_history.json'


def _is_frozen():
    return getattr(sys, 'frozen', False)


def _documents_dir():
    """Return the user's Documents folder (Windows / macOS / Linux)."""
    if sys.platform == 'win32':
        # Prefer the real Documents via shell folders, fall back to a guess
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders',
            )
            value, _ = winreg.QueryValueEx(key, 'Personal')
            value = os.path.expandvars(value)
            winreg.CloseKey(key)
            if value:
                return value
        except Exception:
            pass
        # Fallback: default Windows user profile
        return os.path.join(os.path.expanduser('~'), 'Documents')

    # macOS / Linux
    home = os.path.expanduser('~')
    for name in ('Documents', 'Documentos'):
        candidate = os.path.join(home, name)
        if os.path.isdir(candidate):
            return candidate
    return home


def app_dir():
    """The app's main storage folder (under Documents). Created on demand."""
    folder = os.path.join(_documents_dir(), MAIN_FOLDER_NAME)
    os.makedirs(folder, exist_ok=True)
    return folder


def configs_dir():
    """Config/logs subfolder. Created on demand."""
    folder = os.path.join(app_dir(), CONFIG_SUBFOLDER)
    os.makedirs(folder, exist_ok=True)
    return folder


def reports_dir():
    """PDF reports subfolder. Created on demand."""
    folder = os.path.join(app_dir(), REPORTS_SUBFOLDER)
    os.makedirs(folder, exist_ok=True)
    return folder


def history_path():
    """Full path of the cumulative history JSON (kept at app root)."""
    return os.path.join(app_dir(), HISTORY_FILENAME)


def config_file(name):
    """Path of a config/log file inside the configs subfolder."""
    return os.path.join(configs_dir(), name)


def assets_dir():
    """Path to bundled assets (logo/icon)."""
    if _is_frozen():
        base = getattr(sys, '_MEIPASS', app_dir())
        return os.path.join(base, 'assets')
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets')
