"""Shared download feedback for GUI tasks and disposable network verification."""

from urllib.error import URLError


def download_failure_message(error):
    if isinstance(error, (URLError, ConnectionError, TimeoutError)):
        return ("Could not reach the model host. Check your connection. If you enabled “Block Saydraft from the internet”, "
                "remove Saydraft’s block rule in Settings → Privacy, then choose Download to resume.")
    return str(error)
