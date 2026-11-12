# Download worker lifetime

A settings/download regression reproduced a deleted signal source when its owner
window was destroyed before the Python worker completed. The worker's parented
QObject disappeared while its progress/result signals were still in use. This
was found while investigating a full-suite Qt access violation; the exact cause
of that native crash is not independently established.

Download tasks now live independently until their worker exits. Owner destruction
and app shutdown request pause, preserving resumable staging. A queued GUI-thread
completion checks physical thread exit before publishing `finished`, releasing
the active-task reference and scheduling deletion. Consumers no longer delete a
task directly. Speech-detection status handlers are QObject slots, so destroying
their window disconnects them automatically. Qt's
[signal/slot thread-affinity guidance](https://doc.qt.io/qtforpython-6/tutorials/basictutorial/signals_and_slots.html#thread-affinity)
describes the receiver context used here.

Tests cover success/failure status updates on the GUI thread, window destruction
while the worker waits, and a delayed physical thread exit that must precede
completion/deletion. The full suite passes 1459 tests with four optional native
skips; rules 432/432, adversarial checks 100/100, and Ruff/diff checks pass.
