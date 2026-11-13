"""Explicit CI/developer public-metadata smoke; never starts the desktop app."""

import argparse
import json
import socket

from saydraft.privacy.netguard import NetworkBlockedError, NetworkGuard
from saydraft.updates import check_updates


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enabled', action='store_true', help='explicitly permit the public GitHub metadata request')
    args = parser.parse_args(argv)
    NetworkGuard.install()
    try:
        result = check_updates(enabled=args.enabled)
        try:
            socket.getaddrinfo('api.github.com', 443)
        except NetworkBlockedError:
            retired = True
        else:
            retired = False
        complete = retired and result.state in (('available', 'current', 'no_release') if args.enabled else ('disabled',))
        print(json.dumps({'complete': complete, 'opt_in': args.enabled, 'state': result.state,
                          'api_scope_retired': retired, 'installer_downloaded': False,
                          'browser_opened': False, 'desktop_app_started': False}))
        return 0 if complete else 1
    finally:
        NetworkGuard.uninstall()


if __name__ == '__main__':
    raise SystemExit(main())
