"""Read the current process's Windows microphone capability without requesting it."""

import os


STATES = {0: 'denied_by_system', 1: 'not_declared', 2: 'denied_by_user',
          3: 'prompt_required', 4: 'allowed'}


def check_microphone_privacy(*, query=None):
    """This is a permission diagnostic, not a device or recording test."""
    if query is None and os.name != 'nt':
        return 'unknown'
    try:
        value = (query or _windows_status)()
        return STATES.get(value, 'unknown') if type(value) is int else 'unknown'
    except (OSError, ValueError, TypeError):
        return 'unknown'


def _windows_status(*, api=None):
    # Windows SDK IAppCapabilityStatics / IAppCapability, UniversalApiContract 8.
    # CheckAccess is synchronous and never calls RequestAccessAsync.
    # https://learn.microsoft.com/uwp/api/windows.security.authorization.appcapabilityaccess.appcapability.checkaccess
    import ctypes
    import uuid

    api = api or ctypes.WinDLL('combase', winmode=0x800)  # System32 only.
    pointer = ctypes.c_void_p
    api.RoInitialize.argtypes, api.RoInitialize.restype = [ctypes.c_uint32], ctypes.c_long
    api.RoUninitialize.argtypes, api.RoUninitialize.restype = [], None
    api.WindowsCreateString.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.POINTER(pointer)]
    api.WindowsCreateString.restype = ctypes.c_long
    api.WindowsDeleteString.argtypes, api.WindowsDeleteString.restype = [pointer], ctypes.c_long
    api.RoGetActivationFactory.argtypes = [pointer, pointer, ctypes.POINTER(pointer)]
    api.RoGetActivationFactory.restype = ctypes.c_long

    def checked(result):
        if result < 0:
            raise OSError('Windows microphone privacy query unavailable')

    def method(instance, index, *types, result=ctypes.c_long):
        table = ctypes.cast(instance, ctypes.POINTER(ctypes.POINTER(pointer))).contents
        return ctypes.WINFUNCTYPE(result, pointer, *types)(table[index])

    initialized = api.RoInitialize(1)
    if initialized != -2147417850:  # RPC_E_CHANGED_MODE: use the existing apartment.
        checked(initialized)
    handles, factory, capability = [], pointer(), pointer()
    try:
        for text in ('Windows.Security.Authorization.AppCapabilityAccess.AppCapability', 'microphone'):
            handle = pointer()
            checked(api.WindowsCreateString(text, len(text), ctypes.byref(handle)))
            handles.append(handle)
        iid = (ctypes.c_ubyte * 16).from_buffer_copy(
            uuid.UUID('7C353E2A-46EE-44E5-AF3D-6AD3FC49BD22').bytes_le)
        checked(api.RoGetActivationFactory(handles[0], iid, ctypes.byref(factory)))
        # Six IInspectable entries, then two request methods, then Create.
        checked(method(factory, 8, pointer, ctypes.POINTER(pointer))(
            factory, handles[1], ctypes.byref(capability)))
        # CapabilityName, User and RequestAccessAsync precede CheckAccess.
        status = ctypes.c_int32()
        checked(method(capability, 9, ctypes.POINTER(ctypes.c_int32))(
            capability, ctypes.byref(status)))
        return status.value
    finally:
        for instance in (capability, factory):
            if instance.value:
                method(instance, 2, result=ctypes.c_ulong)(instance)
        for handle in reversed(handles):
            api.WindowsDeleteString(handle)
        if initialized >= 0:  # Both S_OK and S_FALSE own an initialization count.
            api.RoUninitialize()
