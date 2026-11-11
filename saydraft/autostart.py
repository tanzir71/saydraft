"""User-scoped Windows autostart, independent of the Qt UI."""
from __future__ import annotations

import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_RUN_VALUE = "Saydraft"


class WindowsAutoStartManager:
    def __init__(
        self,
        *,
        registry=None,
        platform: str | None = None,
        command: str | None = None,
    ):
        self.platform = sys.platform if platform is None else platform
        self.registry = registry
        self.command = command or self.default_command()

    def default_command(self) -> str:
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"'
        executable = Path(sys.executable)
        pythonw = executable.with_name("pythonw.exe")
        launcher = pythonw if pythonw.exists() else executable
        return f'"{launcher}" -m saydraft'

    def is_enabled(self) -> bool:
        if self.platform != "win32":
            return False
        registry = self._registry()
        try:
            key = registry.OpenKey(registry.HKEY_CURRENT_USER, RUN_KEY, 0, getattr(registry, "KEY_READ", 0))
            try:
                value, _kind = registry.QueryValueEx(key, APP_RUN_VALUE)
                return bool(value)
            finally:
                registry.CloseKey(key)
        except OSError:
            return False
        except KeyError:
            return False

    def set_enabled(self, enabled: bool) -> None:
        if self.platform != "win32":
            return
        registry = self._registry()
        key = registry.CreateKey(registry.HKEY_CURRENT_USER, RUN_KEY)
        try:
            if enabled:
                registry.SetValueEx(key, APP_RUN_VALUE, 0, registry.REG_SZ, self.command)
            else:
                try:
                    registry.DeleteValue(key, APP_RUN_VALUE)
                except OSError:
                    pass
                except KeyError:
                    pass
        finally:
            registry.CloseKey(key)

    def _registry(self):
        if self.registry is not None:
            return self.registry
        import winreg

        return winreg

