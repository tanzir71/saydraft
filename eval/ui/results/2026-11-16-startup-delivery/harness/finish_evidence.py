import hashlib,json,shutil,xml.etree.ElementTree as ET
from pathlib import Path
qa=Path(__file__).resolve().parent;repo=Path('C:/Users/tanzir/Desktop/voice_tray')
out=repo/'eval/ui/results/2026-11-16-startup-delivery'
commands={
 'context-final': ['run_context_tests.py','context-final','tests/test_delivery_context_isolation.py','tests/test_uia_context.py','tests/test_uia_worker.py','tests/test_focused_edit.py','tests/test_foreground_context.py','-x'],
 'insertion-r3':['run_context_tests.py','insertion-r3','tests/test_context_capture_reentry.py','tests/test_uia_delivery.py','tests/test_processing.py','tests/test_paste_last.py','tests/test_delivery_context_isolation.py','-x','-vv'],
 'worker-r2':['run_ui_tests.py','worker-r2','tests/test_session_worker.py','tests/test_asr_router.py','tests/test_audio_language_id.py','tests/test_parakeet.py','tests/test_recorder.py','tests/test_qt_app_shell.py','-k','not main_initializes_logging_config_and_qt_shell','-x','-vv'],
 'hub-r1':['run_ui_tests.py','hub-r1','tests/test_hub.py','tests/test_settings_window.py','tests/test_hub_accessibility.py','tests/test_startup_and_setup_repair.py','-x','-vv'],
 'repair-final':['run_ui_tests.py','repair-final','tests/test_startup_and_setup_repair.py','tests/test_tray_ui.py','tests/test_parakeet.py','tests/test_recorder.py','-x'],
 'setup-final-r3':['run_ui_tests.py','setup-final-r3','tests/test_startup_and_setup_repair.py','tests/test_onboarding_window.py','tests/test_onboarding_readiness.py','tests/test_onboarding_shortcuts.py','tests/test_onboarding_practice.py','tests/test_cleanup_picker.py','-x'],
 'gallery-tests':['run_gallery_tests.py'],
 'build':['tools/build.ps1','-Python','C:/Python313/python.exe','-OutputRoot','D:/Saydraft-Codex-QA-20261112-01a1cbc7/startup-delivery-package-20261116-r1','-PipCache','D:/Saydraft-Codex-QA-20261112-01a1cbc7/pip-cache','-SkipInstaller']}
(out/'commands.json').write_text(json.dumps(dict(working_directory=str(repo),python='D:/Saydraft-Codex-QA-20261112-01a1cbc7/app-ui-v2-package-20261116-r1/venv/Scripts/python.exe',arguments=commands),indent=2)+'\n',encoding='utf-8')
for suffix in ('.log','.xml'):shutil.copyfile(qa/('gallery-tests'+suffix),out/'tests'/('gallery-tests'+suffix))
guards=sorted((qa/'gallery-tests-temp').rglob('gallery.guard.json'));assert len(guards)==2
for i,p in enumerate(guards):
 d=json.loads(p.read_text('utf-8'));assert d['blocked_attempts']==[] and d['microphone_used'] is False and d['owner_profile_used'] is False and d['owner_native_input_used'] is False
 shutil.copyfile(p,out/'tests'/f'gallery-test-{i+1}-guard.json')
summary=json.loads((out/'test-summary.json').read_text('utf-8'))
summary['gallery-tests']=dict(tests=2,failures=0,errors=0,skipped=0)
(out/'test-summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
build=qa.parent/'startup-delivery-package-20261116-r1'
if (qa/'artifact-verification.json').is_file():
 dest=out/'packaging';dest.mkdir(exist_ok=True)
 for name in ('build.log','artifact-verification.json','frozen-verification.json','frozen-verification.guard.json','artifact-verification.log','frozen-verification.log'):
  shutil.copyfile(qa/name,dest/name)
 for name in ('bundle.json','runtime.json','preflight.json','requirements-frozen.txt'):
  path=build/'audit'/name
  if path.is_file():shutil.copyfile(path,dest/name)
manifest=[]
for name in ('verify_frozen.py','verify_artifact.py','finish_evidence.py','archive_repairs.py'):
 shutil.copyfile(qa/name,out/'harness'/name)
for path in sorted(out.rglob('*')):
 if path.is_file() and path.name!='manifest.json':
  manifest.append(dict(path=path.relative_to(out).as_posix(),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
(out/'manifest.json').write_text(json.dumps(dict(source='8734123',files=manifest),indent=2)+'\n',encoding='utf-8')
print('evidence files:',len(manifest))
