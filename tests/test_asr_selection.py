import subprocess
import sys


def test_model_metadata_does_not_import_inference_or_download_modules():
    result = subprocess.run([sys.executable, "-c", """
import sys
from saydraft.asr.selection import configured_model_id
assert configured_model_id({'stt': {'engine': 'parakeet'}}) == 'parakeet-tdt-0-6b-v3-int8'
assert 'saydraft.asr.sherpa_parakeet' not in sys.modules
assert 'saydraft.models.downloader' not in sys.modules
"""], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
