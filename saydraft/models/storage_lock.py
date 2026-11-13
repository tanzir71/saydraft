"""Serialize managed model writes, including nested package installation."""

import threading

storage_lock = threading.RLock()
