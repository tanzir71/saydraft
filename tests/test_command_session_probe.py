"""The probe observes duplicate handles, never retired process wrappers."""

from types import SimpleNamespace

import pytest

from tools.probe_command_session import prior_exits_observed


@pytest.mark.parametrize('codes,expected', [([], True), ([0], True), ([0, 0, 0], True),
                                          ([0, 258], False), ([0, 0xffffffff], False)])
def test_process_launch_requires_observed_exit_on_every_retained_handle(codes, expected):
    calls = []
    def wait(handle, timeout):
        calls.append((handle, timeout))
        return codes[handle]
    meter = SimpleNamespace(handles=list(range(len(codes))), kernel=SimpleNamespace(WaitForSingleObject=wait))
    assert prior_exits_observed(meter) is expected
    assert all(timeout == 0 for _, timeout in calls)
