"""Saydraft process entrypoint."""

from __future__ import annotations


def main() -> int:
    """Run Saydraft."""
    from .privacy.netguard import NetworkGuard

    NetworkGuard.install()
    import sys

    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Tanzir.Saydraft")
    from .config import load_config
    from .logging_config import configure_logging
    from .single_instance import SingleInstanceLock, default_lock_path
    from .compat.migrate import legacy_instance_running, migrate_profile

    if legacy_instance_running():
        if sys.platform == "win32":
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, "Close VoiceTray to avoid double hotkeys", "Saydraft", 0x40)
        return 1
    migrate_profile()

    configure_logging()
    load_config()
    from .compat.migrate import migrate_autostart
    from .autostart import WindowsAutoStartManager

    migrate_autostart(WindowsAutoStartManager())

    lock = SingleInstanceLock(default_lock_path())
    if not lock.acquire():
        lock.notify_existing_instance("Saydraft is already running")
        return 1

    try:
        from .app import SaydraftApp

        return int(SaydraftApp().run())
    finally:
        lock.release()
