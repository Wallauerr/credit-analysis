"""
Path resolution helper that handles both source (python) and frozen
(PyInstaller EXE) execution, so files (outputs, history, config, assets)
are always written/read from the correct place.

- Source:   everything is relative to the project root (parent of src/).
- Frozen:   everything is relative to the folder of the EXE.
"""
import os
import sys


def _is_frozen():
    return getattr(sys, 'frozen', False)


def project_dir():
    if _is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def assets_dir():
    if _is_frozen():
        # Assets are bundled inside _MEIPASS (onefile temp dir)
        base = getattr(sys, '_MEIPASS', project_dir())
        return os.path.join(base, 'assets')
    return os.path.join(project_dir(), 'assets')


def outputs_dir():
    d = os.path.join(project_dir(), 'outputs')
    os.makedirs(d, exist_ok=True)
    return d


def project_file(name):
    """Path of a file living in the project/EXE directory."""
    return os.path.join(project_dir(), name)
