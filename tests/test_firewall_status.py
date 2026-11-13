import base64
import json
from types import SimpleNamespace

import pytest

from saydraft.privacy.firewall import FirewallStatus,inspect_firewall


@pytest.mark.parametrize("count,state",[(0,"absent"),(1,"found"),(4,"found")])
def test_rule_inspection_is_read_only_hidden_and_keeps_program_data_out_of_script(count,state):
    calls=[]
    program="C:/Public'; Write-Host test/Saydraft.exe"
    def run(command,**kwargs):
        calls.append((command,kwargs))
        return SimpleNamespace(returncode=0,stdout=json.dumps({"matching_rules":count}))
    assert inspect_firewall(program=program,runner=run,platform="win32")==FirewallStatus(state,count)
    command,options=calls[0]
    script=base64.b64decode(command[-1]).decode("utf-16-le")
    assert "Get-NetFirewallApplicationFilter -PolicyStore ActiveStore" in script and "Get-NetFirewallRule" in script
    assert all(word not in script for word in ("New-Net","Set-Net","Remove-Net","Start-Process","Write-Host test"))
    assert json.loads(options["input"])["program"].endswith("Saydraft.exe")
    assert command[command.index("-WindowStyle")+1]=="Hidden" and options["timeout"]==8
    assert "shell" not in options


@pytest.mark.parametrize("response",["invalid",'{"matching_rules":true}','{"matching_rules":-1}',
    '{"matching_rules":100001}','{}'],ids=["invalid-json","bool","negative","oversized","missing"])
def test_unusable_inspection_output_stays_unknown_without_exposing_details(response):
    result=inspect_firewall(runner=lambda *args,**kwargs:SimpleNamespace(returncode=0,stdout=response),platform="win32")
    assert result==FirewallStatus()


def test_unsupported_unc_and_failed_inspections_never_claim_protection():
    def forbidden(*args,**kwargs):
        raise AssertionError("Unsupported or UNC inspection spawned a command")
    assert inspect_firewall(platform="linux",runner=forbidden)==FirewallStatus("unsupported")
    assert inspect_firewall(platform="win32",program=r"\\public-server\share\app.exe",runner=forbidden)==FirewallStatus()
    assert inspect_firewall(platform="win32",runner=lambda *args,**kwargs:
        SimpleNamespace(returncode=1,stdout="private rule details"))==FirewallStatus()
    def timeout(*args,**kwargs):
        raise TimeoutError("private program path")
    assert inspect_firewall(platform="win32",runner=timeout)==FirewallStatus()
