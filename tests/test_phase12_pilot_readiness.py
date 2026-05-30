import json
import os
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.rate_limit import rate_limiter
from app.main import app
from app.models.provider_integration import ProviderMode
from app.repositories.provider_spec_repository import PROVIDER_CONTRACT_RESULT_CACHE, PROVIDER_SPEC_CACHE


client = TestClient(app)


def setup_function():
    rate_limiter.clear()
    get_settings.cache_clear()
    PROVIDER_SPEC_CACHE.clear()
    PROVIDER_CONTRACT_RESULT_CACHE.clear()


def teardown_function():
    rate_limiter.clear()
    get_settings.cache_clear()


def auth():
    return {
        "X-Demo-User-Id": "11111111-1111-4111-8111-111111111111",
        "X-Demo-User-Role": "admin",
        "X-Demo-Organization-Id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    }


def write_spec(tmp_path: Path, **updates) -> Path:
    data = {
        "provider_name": "eri",
        "provider_mode": "sandbox",
        "spec_version": "sandbox-v1",
        "base_url": "https://sandbox.invalid",
        "token_url": "https://sandbox.invalid/token",
        "callback_url": "https://api.example.com/v1/filing/provider-callbacks/eri_sandbox",
        "supported_operations": ["submit_return", "status_check", "everification", "acknowledgement", "callback"],
        "auth_type": "bearer_token",
        "signature_type": "hmac_signature",
        "payload_format": "json",
        "status_mapping_version": "v1",
    }
    data.update(updates)
    path = tmp_path / "sandbox_provider_spec.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def configure_env_sandbox(monkeypatch):
    monkeypatch.setenv("SECRET_BACKEND", "env")
    monkeypatch.setenv("ERI_SANDBOX_CLIENT_ID_SECRET_NAME", "SBX_ID")
    monkeypatch.setenv("ERI_SANDBOX_CLIENT_SECRET_SECRET_NAME", "SBX_SECRET")
    monkeypatch.setenv("SBX_ID", "sandbox-client-id")
    monkeypatch.setenv("SBX_SECRET", "sandbox-secret-value")
    monkeypatch.setenv("ALLOW_SANDBOX_PROVIDER_CALLS", "true")
    monkeypatch.setenv("FILING_PROVIDER", "eri_sandbox")
    monkeypatch.setenv("FILING_PROVIDER_MODE", "sandbox")
    get_settings.cache_clear()


def test_verify_secrets_env_backend_success_and_no_value_leak(monkeypatch, capsys):
    from app.tools.verify_secrets import main

    configure_env_sandbox(monkeypatch)

    exit_code = main([])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "ERI_SANDBOX_CLIENT_ID_SECRET_NAME" in output
    assert "accessible" in output.lower()
    assert "sandbox-client-id" not in output
    assert "sandbox-secret-value" not in output


def test_verify_secrets_missing_reports_not_verified(monkeypatch, capsys):
    from app.tools.verify_secrets import main

    monkeypatch.setenv("SECRET_BACKEND", "env")
    monkeypatch.delenv("ERI_SANDBOX_CLIENT_ID_SECRET_NAME", raising=False)
    monkeypatch.delenv("ERI_SANDBOX_CLIENT_SECRET_SECRET_NAME", raising=False)
    get_settings.cache_clear()

    exit_code = main([])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "NOT_VERIFIED" in output
    assert "value" not in output.lower()


def test_register_provider_spec_validates_hash_and_activates(tmp_path, capsys):
    from app.tools.register_provider_spec import main

    path = write_spec(tmp_path)

    exit_code = main(["--file", str(path)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "registered" in output.lower()
    assert "sha256" in output.lower()
    active = next(spec for spec in PROVIDER_SPEC_CACHE.values() if spec.provider_name == "eri")
    assert active.provider_mode == ProviderMode.SANDBOX
    assert active.is_active is True


def test_register_provider_spec_rejects_secret_like_fields(tmp_path, capsys):
    from app.tools.register_provider_spec import main

    path = write_spec(tmp_path, client_secret="do-not-store")

    exit_code = main(["--file", str(path)])
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "secret" in output.lower()
    assert "do-not-store" not in output
    assert not PROVIDER_SPEC_CACHE


def test_register_provider_spec_rejects_missing_required_fields(tmp_path, capsys):
    from app.tools.register_provider_spec import main

    path = write_spec(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("base_url")
    path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code = main(["--file", str(path)])
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "base_url" in output


def test_contract_runner_no_credentials_not_verified(monkeypatch, tmp_path, capsys):
    from app.tools.register_provider_spec import main as register_spec
    from app.tools.run_provider_contract_tests import main

    monkeypatch.setenv("ALLOW_SANDBOX_PROVIDER_CALLS", "true")
    monkeypatch.delenv("ERI_SANDBOX_CLIENT_ID_SECRET_NAME", raising=False)
    monkeypatch.delenv("ERI_SANDBOX_CLIENT_SECRET_SECRET_NAME", raising=False)
    get_settings.cache_clear()
    register_spec(["--file", str(write_spec(tmp_path))])
    capsys.readouterr()

    exit_code = main(["--provider", "eri", "--mode", "sandbox"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "NOT_VERIFIED" in output
    assert "missing approved sandbox credentials" in output.lower()


def test_contract_runner_mock_success(capsys):
    from app.tools.run_provider_contract_tests import main

    exit_code = main(["--provider", "mock", "--mode", "mock"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "passed" in output.lower()
    assert "raw" not in output.lower()


def test_sandbox_smoke_no_credentials_not_verified(monkeypatch, tmp_path, capsys):
    from app.tools.register_provider_spec import main as register_spec
    from app.tools.run_sandbox_smoke import main

    monkeypatch.setenv("ALLOW_SANDBOX_PROVIDER_CALLS", "true")
    monkeypatch.delenv("ERI_SANDBOX_CLIENT_ID_SECRET_NAME", raising=False)
    monkeypatch.delenv("ERI_SANDBOX_CLIENT_SECRET_SECRET_NAME", raising=False)
    get_settings.cache_clear()
    register_spec(["--file", str(write_spec(tmp_path))])
    capsys.readouterr()

    exit_code = main([])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "NOT_VERIFIED" in output
    assert "sandbox" in output.lower()


def test_sandbox_smoke_mocked_success(monkeypatch, tmp_path, capsys):
    from app.tools.register_provider_spec import main as register_spec
    from app.tools.run_sandbox_smoke import main

    configure_env_sandbox(monkeypatch)
    monkeypatch.setenv("ERI_BASE_URL", "https://sandbox.invalid")
    monkeypatch.setenv("ERI_TOKEN_URL", "https://sandbox.invalid/token")
    monkeypatch.setenv("SANDBOX_PROVIDER_TRANSPORT", "mock")
    register_spec(["--file", str(write_spec(tmp_path))])
    capsys.readouterr()

    exit_code = main([])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "passed" in output.lower()
    assert "sandbox-secret-value" not in output
    assert "ABCDE1234F" not in output


def test_pilot_readiness_false_demo_only_and_true_paths(monkeypatch, tmp_path):
    from app.services.pilot_readiness_service import PilotReadinessService
    from app.tools.register_provider_spec import main as register_spec

    report = PilotReadinessService().generate()
    assert report.pilot_ready is False
    assert "sandbox_secrets_verified" in report.not_verified_items

    monkeypatch.setenv("PILOT_READINESS_POLICY", "demo_only")
    get_settings.cache_clear()
    demo_report = PilotReadinessService().generate()
    assert demo_report.pilot_ready is False
    assert demo_report.demo_only is True

    monkeypatch.delenv("PILOT_READINESS_POLICY", raising=False)
    configure_env_sandbox(monkeypatch)
    monkeypatch.setenv("ERI_BASE_URL", "https://sandbox.invalid")
    monkeypatch.setenv("ERI_TOKEN_URL", "https://sandbox.invalid/token")
    register_spec(["--file", str(write_spec(tmp_path))])
    PROVIDER_CONTRACT_RESULT_CACHE["eri:sandbox"] = {"status": "passed", "tested_at": "2026-05-30T00:00:00+00:00"}
    PROVIDER_CONTRACT_RESULT_CACHE["eri:sandbox_smoke"] = {"status": "passed", "tested_at": "2026-05-30T00:00:00+00:00"}

    ready = PilotReadinessService().generate()
    assert ready.pilot_ready is True
    assert "sandbox_contract_tests_passed" in ready.verified_items
    assert "no_live_filing_enabled" in ready.verified_items


def test_diagnostics_include_phase12_fields_and_hide_secrets(monkeypatch, tmp_path):
    from app.tools.register_provider_spec import main as register_spec

    configure_env_sandbox(monkeypatch)
    register_spec(["--file", str(write_spec(tmp_path))])
    PROVIDER_CONTRACT_RESULT_CACHE["eri:sandbox"] = {"status": "passed", "tested_at": "2026-05-30T00:00:00+00:00"}
    PROVIDER_CONTRACT_RESULT_CACHE["eri:sandbox_smoke"] = {"status": "not_verified", "tested_at": "2026-05-30T00:00:00+00:00"}

    response = client.get("/v1/filing/provider-diagnostics", headers=auth())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sandbox_secrets_verified"] is True
    assert body["sandbox_spec_active"] is True
    assert body["sandbox_contract_status"] == "passed"
    assert body["sandbox_smoke_status"] == "not_verified"
    assert body["pilot_ready"] is False
    assert body["pilot_blockers"]
    assert "sandbox-secret-value" not in response.text
    assert "sandbox.invalid" not in response.text


def test_generate_pilot_readiness_report_output_is_safe(monkeypatch, tmp_path, capsys):
    from app.tools.generate_pilot_readiness_report import main
    from app.tools.register_provider_spec import main as register_spec

    configure_env_sandbox(monkeypatch)
    register_spec(["--file", str(write_spec(tmp_path))])
    capsys.readouterr()

    exit_code = main([])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "pilot_ready" in output
    assert "sandbox-secret-value" not in output
    assert "raw" not in output.lower()


def test_cli_registered_spec_and_runner_results_persist_across_processes(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    spec_path = write_spec(tmp_path)
    env = os.environ.copy()
    env.update(
        {
            "PERSISTENCE_BACKEND": "sqlite",
            "PERSISTENCE_STORAGE_DIR": str(tmp_path / "persist"),
            "SECRET_BACKEND": "env",
            "ERI_SANDBOX_CLIENT_ID_SECRET_NAME": "SBX_ID",
            "ERI_SANDBOX_CLIENT_SECRET_SECRET_NAME": "SBX_SECRET",
            "SBX_ID": "sandbox-client-id",
            "SBX_SECRET": "sandbox-secret-value",
            "ALLOW_SANDBOX_PROVIDER_CALLS": "true",
            "FILING_PROVIDER": "eri_sandbox",
            "FILING_PROVIDER_MODE": "sandbox",
            "ERI_BASE_URL": "https://sandbox.invalid",
            "ERI_TOKEN_URL": "https://sandbox.invalid/token",
            "SANDBOX_PROVIDER_TRANSPORT": "mock",
        }
    )

    registered = subprocess.run(
        [sys.executable, "-m", "app.tools.register_provider_spec", "--file", str(spec_path)],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert registered.returncode == 0, registered.stderr

    contract = subprocess.run(
        [sys.executable, "-m", "app.tools.run_provider_contract_tests", "--provider", "eri", "--mode", "sandbox"],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert contract.returncode == 0, contract.stderr
    assert '"status": "passed"' in contract.stdout
    assert "Active sandbox provider spec is missing" not in contract.stdout
    assert "sandbox-secret-value" not in contract.stdout

    smoke = subprocess.run(
        [sys.executable, "-m", "app.tools.run_sandbox_smoke"],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert smoke.returncode == 0, smoke.stderr
    assert '"status": "passed"' in smoke.stdout
    assert "Active sandbox provider spec is missing" not in smoke.stdout
    assert "sandbox-secret-value" not in smoke.stdout

    report = subprocess.run(
        [sys.executable, "-m", "app.tools.generate_pilot_readiness_report"],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert report.returncode == 0, report.stderr
    body = json.loads(report.stdout)
    assert body["pilot_ready"] is True
    assert "sandbox_contract_tests_passed" in body["verified_items"]
    assert "sandbox_smoke_passed" in body["verified_items"]
    assert "sandbox-secret-value" not in report.stdout
