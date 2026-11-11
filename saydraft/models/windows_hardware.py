"""Read Windows capabilities using system APIs; no subprocesses or downloads."""

from __future__ import annotations

import ctypes as c
import os
import struct
import uuid


def _library(name):
    if os.name != "nt":
        raise OSError("Windows capability probe is unavailable")
    return c.WinDLL(name, winmode=0x800, use_last_error=True)  # System32 only.


def cpu_features():
    kernel = _library("kernel32.dll")
    feature = kernel.IsProcessorFeaturePresent
    feature.argtypes, feature.restype = [c.c_uint32], c.c_int32
    physical = None
    info = kernel.GetLogicalProcessorInformationEx
    info.argtypes, info.restype = [c.c_int32, c.c_void_p, c.POINTER(c.c_uint32)], c.c_int32
    size = c.c_uint32()
    info(0, None, c.byref(size))  # RelationProcessorCore, variable-sized records.
    if 0 < size.value < 1024 * 1024:
        buffer = c.create_string_buffer(size.value)
        if info(0, buffer, c.byref(size)):
            offset, count = 0, 0
            while offset + 8 <= size.value:
                relation, length = struct.unpack_from("<II", buffer, offset)
                if length < 8 or offset + length > size.value:
                    raise OSError("Invalid processor topology response")
                count += relation == 0
                offset += length
            physical = count or None
    return {"physical_cores": physical, "avx2": bool(feature(40)), "avx512f": bool(feature(41))}


def physical_memory():
    class Memory(c.Structure):
        _fields_ = [("length", c.c_uint32), ("load", c.c_uint32)] + [
            (name, c.c_uint64) for name in ("total", "available", "page_total", "page_available",
                                          "virtual_total", "virtual_available", "extended")]

    kernel = _library("kernel32.dll")
    query = kernel.GlobalMemoryStatusEx
    query.argtypes, query.restype = [c.POINTER(Memory)], c.c_int32
    memory = Memory(length=c.sizeof(Memory))
    if not query(c.byref(memory)):
        raise c.WinError(c.get_last_error())
    return int(memory.total)


def _method(pointer, slot, result, *arguments):
    table = c.cast(pointer, c.POINTER(c.POINTER(c.c_void_p))).contents
    return c.WINFUNCTYPE(result, c.c_void_p, *arguments)(table[slot])


def dxgi_adapters():
    class Description(c.Structure):
        _fields_ = [("name", c.c_wchar * 128)] + [(name, c.c_uint32) for name in (
            "vendor", "device", "subsystem", "revision")] + [
            (name, c.c_size_t) for name in ("vram", "system_ram", "shared_ram")] + [
            ("luid_low", c.c_uint32), ("luid_high", c.c_int32), ("flags", c.c_uint32)]

    dxgi = _library("dxgi.dll")
    create = dxgi.CreateDXGIFactory1
    create.argtypes, create.restype = [c.c_void_p, c.POINTER(c.c_void_p)], c.c_int32
    iid = (c.c_ubyte * 16).from_buffer_copy(uuid.UUID("770aae78-f26f-4dba-a829-253c83d1b387").bytes_le)
    factory = c.c_void_p()
    if create(c.byref(iid), c.byref(factory)) < 0:
        raise OSError("Cannot create DXGI factory")
    adapters = []
    try:
        enumerate_adapter = _method(factory, 12, c.c_int32, c.c_uint32, c.POINTER(c.c_void_p))
        for index in range(64):
            adapter = c.c_void_p()
            result = enumerate_adapter(factory, index, c.byref(adapter))
            if result & 0xFFFFFFFF == 0x887A0002:  # DXGI_ERROR_NOT_FOUND
                return adapters
            if result < 0:
                raise OSError("Cannot enumerate DXGI adapters")
            try:
                description = Description()
                if _method(adapter, 10, c.c_int32, c.POINTER(Description))(
                        adapter, c.byref(description)) < 0:
                    raise OSError("Cannot read DXGI adapter")
                if not description.flags & 2:  # Exclude software adapters.
                    adapters.append({"name": description.name, "vendor_id": description.vendor,
                                     "device_id": description.device, "vram_bytes": description.vram,
                                     "shared_ram_bytes": description.shared_ram})
            finally:
                _method(adapter, 2, c.c_uint32)(adapter)
        raise OSError("Unexpected DXGI adapter count")
    finally:
        _method(factory, 2, c.c_uint32)(factory)


def vulkan_devices():
    class Application(c.Structure):
        _fields_ = [("type", c.c_uint32), ("next", c.c_void_p), ("name", c.c_char_p),
                    ("version", c.c_uint32), ("engine", c.c_char_p),
                    ("engine_version", c.c_uint32), ("api_version", c.c_uint32)]

    class Instance(c.Structure):
        _fields_ = [("type", c.c_uint32), ("next", c.c_void_p), ("flags", c.c_uint32),
                    ("application", c.POINTER(Application)), ("layers", c.c_uint32),
                    ("layer_names", c.c_void_p), ("extensions", c.c_uint32), ("extension_names", c.c_void_p)]

    library = _library("vulkan-1.dll")
    create = library.vkCreateInstance
    create.argtypes, create.restype = [c.POINTER(Instance), c.c_void_p, c.POINTER(c.c_void_p)], c.c_int32
    destroy = library.vkDestroyInstance
    destroy.argtypes, destroy.restype = [c.c_void_p, c.c_void_p], None
    enumerate_devices = library.vkEnumeratePhysicalDevices
    enumerate_devices.argtypes = [c.c_void_p, c.POINTER(c.c_uint32), c.POINTER(c.c_void_p)]
    enumerate_devices.restype = c.c_int32
    properties = library.vkGetPhysicalDeviceProperties
    properties.argtypes, properties.restype = [c.c_void_p, c.c_void_p], None
    application = Application(name=b"Saydraft hardware check", api_version=1 << 22)
    config = Instance(type=1, application=c.pointer(application))
    instance = c.c_void_p()
    if create(c.byref(config), None, c.byref(instance)) != 0:
        raise OSError("Vulkan initialization unavailable")
    try:
        count = c.c_uint32()
        if enumerate_devices(instance, c.byref(count), None) != 0 or count.value > 64:
            raise OSError("Cannot enumerate Vulkan devices")
        devices = (c.c_void_p * count.value)()
        if enumerate_devices(instance, c.byref(count), devices) != 0:
            raise OSError("Vulkan devices changed during enumeration")
        result = []
        for device in devices[:count.value]:
            # Vulkan 1.0 properties have a fixed ABI. Reserve more than the full
            # structure (824 bytes on Windows x64) and read only its typed prefix.
            buffer = c.create_string_buffer(2048)
            properties(device, buffer)
            _api, _driver, vendor, device_id, kind, name = struct.unpack_from("<IIIII256s", buffer)
            if kind != 4:  # VK_PHYSICAL_DEVICE_TYPE_CPU is software, not acceleration.
                result.append({"name": name.split(b"\0", 1)[0].decode("utf-8", errors="replace"),
                               "vendor_id": vendor, "device_id": device_id, "device_type": kind})
        return result
    finally:
        destroy(instance, None)


def cuda_devices():
    library = _library("nvcuda.dll")
    initialize = library.cuInit
    initialize.argtypes, initialize.restype = [c.c_uint32], c.c_int32
    count_devices = library.cuDeviceGetCount
    count_devices.argtypes, count_devices.restype = [c.POINTER(c.c_int32)], c.c_int32
    get_device = library.cuDeviceGet
    get_device.argtypes, get_device.restype = [c.POINTER(c.c_int32), c.c_int32], c.c_int32
    get_name = library.cuDeviceGetName
    get_name.argtypes, get_name.restype = [c.c_void_p, c.c_int32, c.c_int32], c.c_int32
    count = c.c_int32()
    if initialize(0) != 0 or count_devices(c.byref(count)) != 0 or not 0 <= count.value <= 64:
        raise OSError("CUDA initialization unavailable")
    result = []
    for index in range(count.value):
        device, name = c.c_int32(), c.create_string_buffer(256)
        if get_device(c.byref(device), index) != 0 or get_name(name, len(name), device) != 0:
            raise OSError("Cannot read CUDA device")
        result.append({"name": name.value.decode("utf-8", errors="replace")})
    return result
