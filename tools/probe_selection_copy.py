"""Native copy transaction on a new private station; never the owner clipboard.

An invisible, owned EDIT receives WM_COPY, not injected keyboard input. This
qualifies the native clipboard/owner/restore boundary only, not physical Ctrl+C.
There is deliberately no backed-up-owner-clipboard mode.
"""

import argparse
import ctypes as ct
from ctypes import wintypes as wt
import json
from pathlib import Path
import struct
import subprocess

from tools.probe_native_clipboard import fingerprint as fingerprint_handle, isolated_clipboard


def replay(report):
    # Isolation must succeed before constructing any native clipboard objects.
    from saydraft.insert._clipboard_win32 import NativeClipboardApi
    from saydraft.insert.clipboard_win import Snapshot, WindowsClipboard

    api = NativeClipboardApi()
    user = api.user
    user.SendMessageTimeoutW.argtypes = [wt.HWND, wt.UINT, ct.c_size_t, ct.c_ssize_t,
                                       wt.UINT, wt.UINT, ct.POINTER(ct.c_size_t)]
    user.SendMessageTimeoutW.restype = ct.c_size_t
    user.SetWindowTextW.argtypes, user.SetWindowTextW.restype = [wt.HWND, wt.LPCWSTR], wt.BOOL
    user.IsWindowVisible.argtypes, user.IsWindowVisible.restype = [wt.HWND], wt.BOOL
    api.kernel.GetCurrentProcessId.restype = wt.DWORD
    pid = api.kernel.GetCurrentProcessId()
    edit = user.CreateWindowExW(0, 'EDIT', '', 0x80000000 | 4, 0, 0, 300, 200,
                               None, None, None, None)  # Invisible multiline WS_POPUP.
    if not edit:
        raise OSError('Owned EDIT unavailable')
    clipboard = WindowsClipboard(api_factory=lambda: api)

    def message(kind, wparam=0, lparam=0):
        if user.IsWindowVisible(edit) or api.window_pid(edit) != pid:
            raise OSError('Owned invisible EDIT identity changed')
        result = ct.c_size_t()
        if not user.SendMessageTimeoutW(edit, kind, wparam, lparam, 2, 250, ct.byref(result)):
            raise OSError('Owned EDIT message failed')

    def fingerprint():
        with api.window() as hwnd, api.opened(hwnd):
            snapshot = Snapshot.take(api)
            try:
                if snapshot.skipped:
                    raise OSError('Incomplete public fixture snapshot')
                return [(copy.format, fingerprint_handle(api, copy).hex()) for copy in snapshot.copies]
            finally:
                snapshot.close()

    try:
        report['stage'] = 'publish_private_surface_public_fixtures'
        rtf = user.RegisterClipboardFormatW('Rich Text Format')
        # Include a public DIB, RTF, Unicode and all three privacy flags.
        fixtures = [(rtf, br'{\rtf1 public \b rich\b0 text}' + bytes(1)),
            (8, struct.pack('<IiiHHIIiiII', 40, 1, 1, 1, 32, 0, 4, 0, 0, 0, 0) + bytes((0, 0, 255, 0))),
            (13, 'Original public clipboard\0'.encode('utf-16-le'))]
        with api.window() as hwnd, api.opened(hwnd):
            api.empty()
            for format in api.privacy:
                api.put(api.memory(format, bytes(4)))
            for format, data in fixtures:
                api.put(api.memory(format, data))
        expected = fingerprint()
        report['original_public_formats'] = len(expected)
        report['cases'] = []
        for label, text in [('plain', 'Selected public text'),
                            ('unicode', '\u09ac\u09be\u0982\u09b2\u09be \u0627\u0644\u0639\u0631\u0628\u064a\u0629 \U0001f600'),
                            ('limit', 'x' * 8192)]:
            report['stage'] = label
            if not user.SetWindowTextW(edit, text):
                raise OSError('Owned EDIT text unavailable')
            message(0xB1, 0, -1)  # EM_SETSEL, full authored text only.
            result = clipboard.capture_selection(process_id=pid, guard=lambda: '',
                                                  send_copy=lambda: message(0x301))  # WM_COPY.
            exact = fingerprint() == expected
            report['cases'].append({'case': label, 'reason': result.reason,
                'selection_units': len(text.encode('utf-16-le')) // 2, 'text_exact': result.text == text,
                'restore_status': result.restore_status, 'all_formats_exact': exact,
                'pending': clipboard.pending is not None})
            assert result.reason == 'ok' and result.text == text and result.restore_status == 'restored'
            assert exact and clipboard.pending is None
        report['stage'] = 'pre_input_refusal'
        result = clipboard.capture_selection(process_id=pid, guard=lambda: 'password_field',
            send_copy=lambda: (_ for _ in ()).throw(AssertionError('Refused copy attempted')))
        assert result.reason == 'password_field' and not result.text and fingerprint() == expected
        report['pre_input_refusal'] = True
    finally:
        report['clipboard_recovery_retired'] = clipboard.close() and clipboard.pending is None
        report['owned_edit_closed'] = bool(user.DestroyWindow(edit))
        # Only the new private station is open here. Leave it empty before retirement.
        with api.window() as hwnd, api.opened(hwnd):
            api.empty()
        if not report['clipboard_recovery_retired'] or not report['owned_edit_closed']:
            raise OSError('Owned copy resources did not retire')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    report = {'probe_complete': False, 'owner_clipboard_accessed': False, 'input_injected': False,
        'microphone_used': False, 'scope': 'native clipboard and owned invisible EDIT WM_COPY; no physical Ctrl+C or UIA/worker integration',
        'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'source_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip())}
    try:
        with isolated_clipboard(report):
            from saydraft.privacy.netguard import NetworkGuard
            NetworkGuard.install()
            replay(report)
        report['probe_complete'] = True
    except Exception as error:
        report['error'] = str(error) if 'stage' not in report else type(error).__name__
        trace = error.__traceback__
        while trace.tb_next is not None:
            trace = trace.tb_next
        report['error_location'] = {'file': Path(trace.tb_frame.f_code.co_filename).name, 'line': trace.tb_lineno}
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return 0 if report['probe_complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
