import copy
from dataclasses import replace
from types import SimpleNamespace
import threading

import numpy as np
import pytest

from saydraft.audio.devices import InputSelection, list_inputs, resolve_input, selected_input_stream
from saydraft.audio.meter import InputMeter
from saydraft.config import default_config, sanitize_config
from saydraft.core.microphone import MicrophoneTest
from tests.test_session_worker import Executor, Timer, make_worker


def device_backend(devices=None):
    return SimpleNamespace(query_devices=lambda: devices or [
        {"name":"Speakers","max_input_channels":0,"hostapi":0},
        {"name":"USB mic","max_input_channels":1,"hostapi":0},
        {"name":"USB mic","max_input_channels":2,"hostapi":1}],
        query_hostapis=lambda: [{"name":"MME"},{"name":"Windows WASAPI"}])


def test_device_selection_filters_outputs_and_resolves_name_and_api_after_indexes_move():
    backend = device_backend()
    devices = list_inputs(backend=backend)
    assert [d.index for d in devices] == [1,2]
    selected = InputSelection("USB mic","Windows WASAPI")
    assert resolve_input(selected,backend=backend)==2
    backend.query_devices=lambda: [
        {"name":"USB mic","max_input_channels":2,"hostapi":1},
        {"name":"USB mic","max_input_channels":1,"hostapi":0}]
    assert resolve_input(selected,backend=backend)==0


def test_default_does_not_query_devices_and_missing_or_ambiguous_input_never_falls_back():
    assert resolve_input(InputSelection(),backend=SimpleNamespace()) is None
    with pytest.raises(RuntimeError):
        resolve_input(InputSelection("Missing","MME"),backend=device_backend())
    rows=[{"name":"USB mic","max_input_channels":1,"hostapi":0}]*2
    with pytest.raises(RuntimeError):
        resolve_input(InputSelection("USB mic","MME"),backend=device_backend(rows))


def test_named_wasapi_stream_uses_shared_conversion_and_other_apis_keep_their_settings(monkeypatch):
    import sounddevice
    backend, calls = device_backend(), []
    monkeypatch.setattr(sounddevice,"query_devices",backend.query_devices)
    monkeypatch.setattr(sounddevice,"query_hostapis",backend.query_hostapis)
    monkeypatch.setattr(sounddevice,"InputStream",lambda **kwargs:calls.append(kwargs) or "owned-stream")
    monkeypatch.setattr(sounddevice,"WasapiSettings",lambda **kwargs:kwargs)
    assert selected_input_stream(InputSelection("USB mic","Windows WASAPI"),samplerate=16000)=="owned-stream"
    selected_input_stream(InputSelection("USB mic","MME"),samplerate=16000)
    assert calls[0]=={"samplerate":16000,"device":2,"extra_settings":{"auto_convert":True}}
    assert calls[1]=={"samplerate":16000,"device":1}


@pytest.mark.parametrize("name,api", [("USB mic","Windows WASAPI"),("مايك বাংলা","MME"),("","")])
def test_input_preferences_round_trip_without_changing_other_configuration(name,api):
    config=default_config()
    original=copy.deepcopy(config)
    config["recording"].update(input_device=name,input_hostapi=api)
    saved=sanitize_config(config)
    assert InputSelection.from_config(saved)==InputSelection(name,api)
    saved["recording"].update(input_device="",input_hostapi="")
    assert saved==original


@pytest.mark.parametrize("name,api", [("Mic",""),("","MME"),("x"*513,"MME"),("bad\nname","MME")],
    ids=["missing-api","missing-name","oversized","control-character"])
def test_invalid_input_preference_pair_uses_the_default(name,api):
    config=default_config()
    config["recording"].update(input_device=name,input_hostapi=api)
    assert InputSelection.from_config(sanitize_config(config))==InputSelection()


class Stream:
    def __init__(self, **kwargs):
        self.kwargs, self.started, self.stopped, self.closed = kwargs,False,False,False
    def start(self): self.started=True
    def stop(self): self.stopped=True
    def close(self): self.closed=True


def test_level_only_meter_throttles_finite_rms_and_retains_no_audio_after_callback():
    clock=SimpleNamespace(now=0.)
    streams,levels,finished=[],[],[]
    meter=InputMeter(InputSelection("USB mic","MME"),clock=lambda:clock.now,
        on_level=levels.append,on_finished=lambda:finished.append(True),
        stream_factory=lambda **kwargs: streams.append(Stream(**kwargs)) or streams[-1])
    meter.start()
    stream=streams[0]
    samples=np.full((160,1),.125,dtype=np.float32)
    callback=stream.kwargs["callback"]
    callback(samples,160,None,None)
    clock.now=.01
    callback(samples,160,None,None)
    assert levels==[.125]
    clock.now=.1
    callback(np.full((160,1),np.nan,dtype=np.float32),160,None,None)
    assert levels==[.125,0.]
    assert not any(isinstance(value,np.ndarray) for value in vars(meter).values())
    assert not hasattr(meter,"_chunks")
    meter.stop()
    callback(samples,160,None,None)
    stream.kwargs["finished_callback"]()
    assert levels==[.125,0.] and not finished
    assert stream.started and stream.stopped and stream.closed


def test_failed_meter_start_always_closes_the_owned_stream():
    stream=Stream()
    stream.start=lambda: (_ for _ in ()).throw(RuntimeError("private driver details"))
    meter=InputMeter(stream_factory=lambda **kwargs:stream)
    with pytest.raises(RuntimeError):
        meter.start()
    assert stream.closed


class Meter:
    def __init__(self, selection, **kwargs):
        self.selection,self.kwargs,self.started,self.stopped=selection,kwargs,False,False
    def start(self): self.started=True
    def stop(self): self.stopped=True


def controller():
    executor,events,meters,timers=Executor(queued=True),[],[],[]
    def factory(selection,**kwargs):
        meters.append(Meter(selection,**kwargs))
        return meters[-1]
    def timer(seconds,callback):
        timers.append(Timer(seconds,callback))
        return timers[-1]
    test=MicrophoneTest(schedule=executor.submit,emit=lambda *args:events.append(args),factory=factory,timer_factory=timer)
    return test,executor,events,meters,timers


def test_meter_control_bounds_duration_and_ignores_old_generations_and_late_levels():
    test,executor,events,meters,timers=controller()
    first=test.start(InputSelection())
    executor.drain()
    assert test.active and meters[0].started and timers[0].seconds==10
    meters[0].kwargs["on_level"](.1)
    assert ("microphone_test_level",first,.1) in events
    timers[0].callback()
    executor.drain()
    assert not test.active and meters[0].stopped and timers[0].cancelled
    second=test.start(InputSelection("USB mic","MME"))
    executor.drain()
    before=len(events)
    meters[0].kwargs["on_level"](.9)
    timers[0].callback()
    assert len(events)==before and test.active and second>first
    assert not test.stop(first)
    test.close()
    executor.drain()
    assert meters[1].stopped and not test.active


def test_cancel_before_queued_meter_start_opens_nothing():
    test,executor,_,meters,_=controller()
    generation=test.start(InputSelection())
    assert test.stop(generation)
    executor.drain()
    assert not meters and not test.active


def test_shutdown_during_a_blocked_device_open_retires_it_without_blocking_the_caller():
    from concurrent.futures import ThreadPoolExecutor
    entered,release,ended=threading.Event(),threading.Event(),threading.Event()
    meter=Meter(InputSelection())
    def start():
        entered.set()
        assert release.wait(3)
        meter.started=True
    meter.start=start
    executor=ThreadPoolExecutor(max_workers=1)
    test=MicrophoneTest(schedule=executor.submit,emit=lambda *args:None,
        factory=lambda *args,**kwargs:meter,finished=ended.set)
    try:
        test.start(InputSelection())
        assert entered.wait(2)
        test.close()
        assert not ended.is_set()
        release.set()
        assert ended.wait(2) and meter.stopped and not test.active
    finally:
        release.set()
        executor.shutdown()


def test_stopped_input_and_rejected_stop_queue_retire_the_stream_without_driver_details():
    test,executor,events,meters,_=controller()
    test.start(InputSelection())
    executor.drain()
    ended=threading.Event()
    test.finished=ended.set
    test.schedule=lambda *args: (_ for _ in ()).throw(RuntimeError("queue closed"))
    meters[0].kwargs["on_finished"]()
    assert ended.wait(2) and meters[0].stopped and not test.active
    assert events[-1][-1]=="failed"


def test_real_session_worker_reserves_capture_for_the_meter_and_applies_settings_after_close():
    worker,_,executor,events,signals,_=make_worker(queued=True)
    meters=[]
    worker.microphone_test.factory=lambda selection,**kwargs:meters.append(Meter(selection,**kwargs)) or meters[-1]
    generation=worker.start_microphone_test(InputSelection("USB mic","MME"))
    assert generation and not worker.start_recording() and not worker.benchmark_hardware()
    executor.drain()
    assert worker.busy and not worker.services.recorder.started and not events
    services=worker.services
    worker.services_factory=lambda config,**kwargs:replace(services,config=config)
    config=copy.deepcopy(services.config)
    config["recording"].update(input_device="USB mic",input_hostapi="MME")
    worker.configure(config)
    executor.drain()
    assert meters[0].stopped and not worker.busy and worker.services.config==config
    assert not events and ("microphone_test_status",generation,"stopped") in signals
    worker.shutdown()


@pytest.mark.parametrize("named", [False,True])
def test_real_container_routes_dictation_to_the_selected_input_without_opening_a_real_device(tmp_path,monkeypatch,named):
    import sounddevice
    from saydraft.core.container import create_services
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    backend,calls=device_backend(),[]
    monkeypatch.setattr(sounddevice,"query_devices",backend.query_devices)
    monkeypatch.setattr(sounddevice,"query_hostapis",backend.query_hostapis)
    monkeypatch.setattr(sounddevice,"WasapiSettings",lambda **kwargs:kwargs)
    monkeypatch.setattr(sounddevice,"InputStream",lambda **kwargs:calls.append(Stream(**kwargs)) or calls[-1])
    config=default_config()
    if named:
        config["recording"].update(input_device="USB mic",input_hostapi="Windows WASAPI")
    services=create_services(config)
    services.recorder.start()
    assert calls[0].kwargs["device"]==(2 if named else None)
    assert calls[0].kwargs["samplerate"]==16000 and calls[0].kwargs["channels"]==1
    assert services.recorder.stop().size==0 and calls[0].closed


@pytest.mark.parametrize("stage",["queue","construct","start","stop"])
def test_failed_meter_lifecycle_retires_reservation_and_reports_only_generic_state(stage):
    test,executor,events,meters,_=controller()
    def fail(*args,**kwargs):
        raise RuntimeError("private device details")
    if stage=="queue":
        test.schedule=fail
    elif stage=="construct":
        test.factory=fail
    elif stage=="start":
        def factory(selection,**kwargs):
            meter=Meter(selection,**kwargs)
            meter.start=fail
            meters.append(meter)
            return meter
        test.factory=factory
    generation=test.start(InputSelection())
    executor.drain()
    if stage=="stop":
        meters[0].stop=fail
        assert test.stop(generation)
        executor.drain()
    assert not test.active and events[-1][-1]=="failed"
    assert "private" not in repr(events)
    if stage=="start":
        assert meters[0].stopped
