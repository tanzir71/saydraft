"""Held fallback with owned native field metadata and scripted clipboard/audio/model ports."""

from tools.probe_command_recording import exercise
from tools.probe_selection import main as selection_main


def fallback(fixture, report):
    exercise(fixture, report, modes=('fallback_copy', 'fallback_sensitive', 'fallback_cancel'))
    report['command_scope'] = ('compiled synthetic chord -> actual worker -> native own-EDIT field metadata '
        'on one MTA, deliberately suppressed selection pattern -> scripted clipboard capture -> sealed lease '
        '-> scripted ASR/model -> actual SQLite and queued Copy recovery; no native clipboard or key input')


def main(argv=None):
    return selection_main(argv, exercise=fallback)


if __name__ == '__main__':
    raise SystemExit(main())
