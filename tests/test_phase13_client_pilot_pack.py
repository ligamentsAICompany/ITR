import json
from pathlib import Path


def test_demo_data_files_are_synthetic_and_cover_expected_personas():
    demo_root = Path("demo_data")
    persona_files = sorted((demo_root / "personas").glob("*.json"))
    expected_output_files = sorted((demo_root / "expected_outputs").glob("*.json"))

    assert {path.name for path in persona_files} >= {
        "salaried_it1.json",
        "freelancer_itr4.json",
        "foreign_assets_itr2.json",
        "business_itr3.json",
    }
    assert {path.name for path in expected_output_files} >= {
        "salaried_itr1_expected.json",
        "freelancer_itr4_expected.json",
        "foreign_assets_itr2_expected.json",
    }

    for path in [*persona_files, *expected_output_files]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["data_classification"] == "synthetic_demo_only"
        assert payload["live_filing_enabled"] is False
        text = json.dumps(payload)
        assert "mock" in text.lower()
        assert "real taxpayer" not in text.lower()


def test_demo_loader_requires_explicit_demo_flag_and_hides_sensitive_values(capsys):
    from app.tools.load_demo_data import main

    blocked_exit = main([])
    blocked_output = capsys.readouterr().out

    assert blocked_exit == 2
    assert "--demo" in blocked_output

    exit_code = main(["--demo"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "synthetic demo personas" in output.lower()
    assert "salaried_it1" in output
    assert "ABCDE1234F" not in output
    assert "999988887777" not in output
    assert "secret" not in output.lower()
