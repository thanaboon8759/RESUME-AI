from pathlib import Path


def test_trainer_has_no_simulation_path():
    src = Path("train_typhoon_qlora.py").read_text(encoding="utf-8")
    assert "randn" not in src and "dry_run" not in src and "0.042" not in src
    assert not Path("adapters/typhoon_ocr_lora/adapter_model.bin").exists()
