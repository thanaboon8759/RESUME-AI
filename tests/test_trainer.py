from pathlib import Path

import pytest

BASE = Path("models/typhoon-ocr-3b-hf")
pytestmark = pytest.mark.skipif(not (BASE / "config.json").exists(), reason="base weights not downloaded")


@pytest.fixture(scope="module")
def processor():
    from transformers import AutoProcessor
    return AutoProcessor.from_pretrained(BASE, min_pixels=256 * 28 * 28, max_pixels=512 * 28 * 28)


def test_collator_masks_prompt_tokens(processor):
    from train_typhoon_qlora import PROMPT, make_collator
    sample = {"image": "resume-lab/training/v1/train_th_1.png",
              "text": Path("resume-lab/training/v1/train_th_1.txt").read_text(encoding="utf-8")}
    batch = make_collator(processor, PROMPT)([sample])
    labels = batch["labels"][0]
    learned = labels[labels != -100].tolist()
    answer = processor.tokenizer(sample["text"], add_special_tokens=False)["input_ids"]
    assert learned[:len(answer)] == answer           # the answer is learned, starting at its first token
    assert len(learned) == len(answer) + 1           # plus the <|im_end|> that ends the turn
    image_pad = processor.tokenizer.convert_tokens_to_ids("<|image_pad|>")
    assert image_pad not in learned                  # prompt and image tokens are never learned


def test_prompt_matches_serving():
    from train_typhoon_qlora import PROMPT
    assert PROMPT in Path("resume-lab/server.py").read_text(encoding="utf-8")
