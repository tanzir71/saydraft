# Saydraft profile migration

The first normal launch copies the previous application's profile into
`%LOCALAPPDATA%\Saydraft\`, provided the new profile is absent or empty. An active
old instance must be closed first. Existing independent Saydraft profiles are
left alone.

The copy includes configuration, history (including WAL/SHM companions), dictionary,
snippets, app profiles, logs and models. Originals remain untouched. A migration
intent file permits an interrupted copy to resume; completed destination files
are never overwritten. The completion marker is written only after all copies
succeed. Temporary interrupted copies remain on disk for recovery. Symlinks are
excluded, including paths through symlinked directories.

Editable dictionary, snippets and app profiles now resolve inside the new user
profile. Explicit external paths continue to work. Absolute paths inside the
old profile resolve to their new copy when that copy exists.

Autostart migrates only an exact launch command recognized as one written by the
old app. An unrelated value with the old name is preserved. The new Windows
single-instance object is namespaced to `Tanzir.Saydraft`; a new lock filename and
the existing local second-launch notice prevent duplicate instances.

For one release the former module launcher delegates to `python -m saydraft` and
logs a deprecation warning. The local workspace folder and old installed executable
are preserved. Use the new launcher for the renamed source application.
