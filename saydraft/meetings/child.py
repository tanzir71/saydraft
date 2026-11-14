"""Isolated capture helper; no profile, hotkeys, model loading or disk audio.

The application must show the persistent recording capsule before launch.
Only an explicitly confirmed request, an owner-created stop event and a binary
stdout pipe admit native device opening. Driver hangs end with process exit.
"""

import ctypes as c
from ctypes import wintypes as w
import os
import threading
import time

from .audio import AudioGapError, DesktopReader, MicrophoneReader, SAMPLE_RATE
from .protocol import END, ERROR, READY, START, MAX_AUDIO_SAMPLES, PacketWriter, audio_frame, json_frame
from .request import CaptureRequest
from .stop import StopEvent, valid_event_name

REQUEST_ENV = 'SAYDRAFT_MEETING_CAPTURE'


def open_capture_output():
    """Windowed frozen Python can have stdout=None; use its explicit pipe handle."""
    if os.name != 'nt':
        raise OSError('Meeting capture transport requires Windows')
    import msvcrt
    api = c.WinDLL('kernel32', use_last_error=True, winmode=0x800)
    api.GetStdHandle.restype, api.GetStdHandle.argtypes = w.HANDLE, [w.DWORD]
    api.GetFileType.restype, api.GetFileType.argtypes = w.DWORD, [w.HANDLE]
    api.SetHandleInformation.restype, api.SetHandleInformation.argtypes = w.BOOL, [w.HANDLE, w.DWORD, w.DWORD]
    api.GetCurrentProcess.restype, api.GetCurrentProcess.argtypes = w.HANDLE, []
    api.DuplicateHandle.restype, api.DuplicateHandle.argtypes = w.BOOL, [w.HANDLE, w.HANDLE, w.HANDLE,
        c.POINTER(w.HANDLE), w.DWORD, w.BOOL, w.DWORD]
    api.CloseHandle.restype, api.CloseHandle.argtypes = w.BOOL, [w.HANDLE]
    handle = api.GetStdHandle(w.DWORD(-11).value)
    if handle in (None, c.c_void_p(-1).value) or api.GetFileType(handle) != 3:
        raise OSError('Meeting capture requires the owned binary output pipe')
    if not api.SetHandleInformation(handle, 1, 0):
        raise c.WinError(c.get_last_error())
    duplicate, process = w.HANDLE(), api.GetCurrentProcess()
    if not api.DuplicateHandle(process, handle, process, c.byref(duplicate), 0, False, 2):
        raise c.WinError(c.get_last_error())
    try:
        descriptor = msvcrt.open_osfhandle(int(duplicate.value), os.O_WRONLY | os.O_BINARY)
    except BaseException:
        api.CloseHandle(duplicate)
        raise
    try:
        os.set_inheritable(descriptor, False)
        return os.fdopen(descriptor, 'wb', buffering=0)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise


class _TransportFailure(Exception):
    pass


def run_capture(request, signal, output, *, microphone_factory=None, desktop_factory=None,
                clock=time.monotonic, stop_grace=1.0):
    """Capture on two affine threads, returning before a bounded forced child exit.

    Pure fixture factories are used by controlled tests. A returned failure code
    is never evidence that native threads stopped: the owner observes the Job
    Object's complete tree exit. The CLI wrapper hard-exits after this function.
    """
    if type(request) is not CaptureRequest or not request.consent:
        raise PermissionError('Meeting capture requires a confirmed request')
    if type(stop_grace) not in (int, float) or not 0 < stop_grace <= 2:
        raise ValueError('Invalid meeting stop grace')
    microphone_factory = microphone_factory or (lambda: MicrophoneReader(request.microphone, consent=True))
    desktop_factory = desktop_factory or (lambda: DesktopReader(consent=True, endpoint_id=request.desktop_endpoint))
    writer = PacketWriter(output)
    lock, stop = threading.RLock(), threading.Event()
    epoch = clock()
    frames = {'microphone': 0, 'desktop': 0}
    opened = set()
    errors = set()
    state = {'admit': True, 'ready': False, 'transport_failed': False, 'limit': False}
    maximum = request.max_seconds * SAMPLE_RATE + MAX_AUDIO_SAMPLES

    def emit(packet):
        try:
            writer.write(packet)
        except BaseException as error:
            state.update(transport_failed=True, admit=False)
            stop.set()
            raise _TransportFailure() from error

    def fail(track, reason):
        stop.set()
        with lock:
            if track in errors:
                return
            errors.add(track)
            if state['admit']:
                emit(json_frame(ERROR, {'reason': reason}))

    def push(track, samples):
        for offset in range(0, len(samples), MAX_AUDIO_SAMPLES):
            with lock:
                if not state['admit']:
                    return
                remaining = maximum - frames[track]
                if remaining <= 0:
                    state['limit'] = True
                    stop.set()
                    return
                part = samples[offset:offset + min(MAX_AUDIO_SAMPLES, remaining)]
                emit(audio_frame(track, frames[track], part))
                frames[track] += len(part)
                if frames[track] == maximum:
                    state['limit'] = True
                    stop.set()

    def capture(track, factory):
        reader, entered = None, False
        try:
            if stop.is_set():
                return
            reader = factory()
            with reader:
                entered = True
                with lock:
                    offset = max(0.0, clock() - epoch)
                    if offset > request.max_seconds:
                        state['limit'] = True
                        stop.set()
                    if not stop.is_set():
                        emit(json_frame(START, {'track': track, 'offset_seconds': offset}))
                        opened.add(track)
                        if len(opened) == 2:
                            emit(json_frame(READY, {}))
                            state['ready'] = True
                while not stop.is_set():
                    push(track, reader.read())
        except _TransportFailure:
            pass
        except BaseException as error:
            reason = ('device_unavailable' if not entered else 'audio_gap' if isinstance(error, AudioGapError)
                      else 'invalid_audio' if isinstance(error, ValueError) else 'capture_failed')
            try:
                fail(track, reason)
            except _TransportFailure:
                pass
        finally:
            if entered and track == 'desktop' and track in opened:
                try:
                    push(track, reader.finish_audio())
                except _TransportFailure:
                    pass
                except BaseException:
                    try:
                        fail(track, 'capture_failed')
                    except _TransportFailure:
                        pass

    threads = []
    stop_at = None
    try:
        if not signal.is_set():
            for track, factory in (('microphone', microphone_factory), ('desktop', desktop_factory)):
                thread = threading.Thread(target=capture, args=(track, factory), name='Saydraft-meeting-' + track, daemon=True)
                thread.start()
                threads.append(thread)
            while any(thread.is_alive() for thread in threads):
                now = clock()
                if signal.is_set() or now - epoch >= request.max_seconds:
                    if now - epoch >= request.max_seconds:
                        state['limit'] = True
                    stop.set()
                if stop.is_set():
                    stop_at = now if stop_at is None else stop_at
                    if now - stop_at >= stop_grace:
                        try:
                            fail('coordinator', 'capture_failed')
                        except _TransportFailure:
                            pass
                        break
                time.sleep(.01)
    except BaseException:
        stop.set()
        try:
            fail('coordinator', 'capture_failed')
        except _TransportFailure:
            pass
    finally:
        stop.set()

    # Normal completion reaches this point only after both readers close. A
    # hanging reader gets no further packet admission and dies with this child.
    with lock:
        hung = any(thread.is_alive() for thread in threads)
        if hung:
            errors.add('coordinator')
        state['admit'] = False
        complete = state['ready'] and not errors and not state['transport_failed'] and not hung and all(frames.values())
        reason = ('transport_failed' if state['transport_failed'] else 'capture_failed' if errors or hung
                  else 'limit' if state['limit'] else 'stopped' if complete else 'cancelled')
        if not state['transport_failed']:
            try:
                emit(json_frame(END, {'complete': bool(complete), 'reason': reason, 'frames': dict(frames)}))
            except _TransportFailure:
                pass
        return 0 if complete else 3 if state['transport_failed'] else 2


def helper_main(args, *, environment=None, output_factory=open_capture_output, signal_factory=StopEvent.open,
                exit_process=os._exit):
    """Private entrypoint; malformed invocation returns before opening audio."""
    if len(args) != 1 or not valid_event_name(args[0]):
        return 2
    environment = os.environ if environment is None else environment
    text = environment.pop(REQUEST_ENV, '')
    try:
        request = CaptureRequest.from_json(text)
        with signal_factory(args[0]) as signal, output_factory() as output:
            code = run_capture(request, signal, output)
    except BaseException:
        code = 2
    # Native readers are daemon threads because drivers can block indefinitely.
    # Avoid Python/global-COM shutdown while such a thread is still inside a
    # driver. Kernel process exit closes all native audio handles. The owner
    # separately confirms this exit and never trusts END alone.
    exit_process(code)
    return code  # Injectable exit seam for unit tests.
