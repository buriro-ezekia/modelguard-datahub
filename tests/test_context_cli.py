import json
from pathlib import Path

from modelguard.cli import main


def test_context_collect_fixture_command(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.json"
    urn = "urn:li:mlModel:test"
    fixture.write_text(
        json.dumps(
            {
                "source_urn": urn,
                "provider": "fixture",
                "generated_at": "2026-07-24T00:00:00+00:00",
                "entity": {"urn": urn, "name": "test"},
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "modelguard.yml"
    config.write_text(
        f"""
project: {{name: test}}
model: {{urn: '{urn}'}}
datahub:
  provider: fixture
  fixture_path: {fixture.name}
""",
        encoding="utf-8",
    )
    output = tmp_path / "snapshot.json"

    exit_code = main(
        [
            "context",
            "collect",
            "--config",
            str(config),
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["provider"] == "fixture"
    assert payload["source_urn"] == urn


def test_context_check_fixture_command(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.json"
    urn = "urn:li:mlModel:test"
    fixture.write_text(
        json.dumps(
            {
                "source_urn": urn,
                "provider": "fixture",
                "generated_at": "2026-07-24T00:00:00+00:00",
                "entity": {"urn": urn},
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "modelguard.yml"
    config.write_text(
        (
            f"project: {{name: test}}\n"
            f"model: {{urn: '{urn}'}}\n"
            f"datahub: {{fixture_path: '{fixture.name}'}}\n"
        ),
        encoding="utf-8",
    )

    assert main(["context", "check", "--config", str(config)]) == 0
