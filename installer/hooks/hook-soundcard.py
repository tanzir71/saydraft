"""Retain CFFI declarations without importing or enumerating audio endpoints."""

from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files('soundcard', includes=['*.py.h'])
