"""Bounded local hints, never browser automation, URL fetching or security evidence."""

import ntpath
import re

GROUPS = frozenset({"messages", "work_chat", "email", "docs", "code", "ai_chat", "general"})
_EXES = {
    "messages": ("whatsapp.exe", "telegram.exe", "signal.exe"),
    "work_chat": ("slack.exe", "teams.exe", "ms-teams.exe", "discord.exe"),
    "email": ("outlook.exe", "thunderbird.exe"),
    "docs": ("winword.exe", "onenote.exe", "notion.exe", "obsidian.exe", "notepad.exe"),
    "code": ("code.exe", "cursor.exe", "windsurf.exe", "devenv.exe", "notepad++.exe",
             "pycharm64.exe", "idea64.exe", "windowsterminal.exe", "powershell.exe", "pwsh.exe", "cmd.exe"),
    "ai_chat": ("chatgpt.exe", "claude.exe"),
}
_DEFAULTS = {exe: group for group, exes in _EXES.items() for exe in exes}
_BROWSERS = {"chrome.exe": "Google Chrome", "msedge.exe": "Microsoft Edge", "firefox.exe": "Mozilla Firefox"}
_SITES = {
    "gmail": ("mail.google.com", "email"), "outlook": ("outlook.live.com", "email"),
    "google docs": ("docs.google.com", "docs"), "notion": ("notion.so", "docs"),
    "slack": ("slack.com", "work_chat"), "microsoft teams": ("teams.microsoft.com", "work_chat"),
    "discord": ("discord.com", "work_chat"), "whatsapp": ("web.whatsapp.com", "messages"),
    "telegram web": ("web.telegram.org", "messages"), "chatgpt": ("chatgpt.com", "ai_chat"),
    "claude": ("claude.ai", "ai_chat"),
}
_SITE_GROUPS = {site: group for site, group in _SITES.values()}
_SEPARATOR = re.compile(r" (?:-|–|—|\|) ")
_HOST = re.compile(r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\Z")


def browser_site(exe, title):
    """Infer a hint only from a recognized browser's final service title segment."""
    brand = _BROWSERS.get(exe.casefold())
    if not brand or not isinstance(title, str) or len(title) > 4096:
        return ""
    parts = _SEPARATOR.split(title.strip())
    if len(parts) < 2 or parts[-1].casefold() != brand.casefold():
        return ""
    suffix = parts[-2].strip().casefold()
    if suffix in _SITES:
        return _SITES[suffix][0]
    # An explicit final hostname may support a user override. Never infer a
    # host from words or links inside arbitrary article/document titles.
    return suffix if _HOST.fullmatch(suffix) else ""


def matches_app(entry, exe="", site="", *, title=None, allow_title=False):
    if not isinstance(entry, dict):
        return False
    expected_exe, expected_site = entry.get("exe"), entry.get("site")
    if expected_exe is None and expected_site is None:
        match = entry.get("match")
        return bool(allow_title and isinstance(match, str) and 0 < len(match) <= 512
            and isinstance(title, str) and len(title) <= 4096 and match.casefold() in title.casefold())
    exe = ntpath.basename(exe).casefold()
    if expected_exe is not None and (not isinstance(expected_exe, str)
            or not expected_exe or len(expected_exe) > 260 or ntpath.basename(expected_exe) != expected_exe
            or expected_exe.casefold() != exe):
        return False
    if expected_site is not None and (not isinstance(expected_site, str) or not site
            or not _HOST.fullmatch(expected_site.casefold()) or expected_site.casefold() != site):
        return False
    return True


def app_group(exe, site="", profiles=()):
    exe = ntpath.basename(exe).casefold()
    for entry in profiles[:128]:
        if (isinstance(entry, dict) and isinstance(entry.get("app_group"), str)
                and entry["app_group"] in GROUPS and matches_app(entry, exe, site)):
            return entry["app_group"]
    return _SITE_GROUPS.get(site, "general") if exe in _BROWSERS else _DEFAULTS.get(exe, "general")
