"""Register Hugging Face safetensors weights in Ollama, keeping the base model's serving config.

Ollama imports Qwen2.5-VL safetensors directly, so no llama.cpp/GGUF step is needed (filename kept for history).
Only the weights change: TEMPLATE, SYSTEM and PARAMETER lines are copied from the base Ollama model,
so score differences come from the weights alone.

Usage: python export_ollama_gguf.py <hf_dir> <tag> [--base scb10x/typhoon-ocr-3b:latest] [--quantize q8_0]
"""
import argparse
import json
import subprocess
import tempfile
import urllib.request
from pathlib import Path

BASE_TAG = 'scb10x/typhoon-ocr-3b:latest'


def build_modelfile(base_modelfile: str, source: str) -> str:
    """Replace the base FROM line with `source`; drop comments and LICENSE; keep everything else verbatim."""
    out, skipping = [f'FROM "{Path(source).as_posix()}"'], False
    for line in base_modelfile.splitlines():
        if skipping:  # inside a multi-line LICENSE """...""" block
            skipping = not line.rstrip().endswith('"""')
            continue
        if line.startswith('#') or line.startswith('FROM '):
            continue
        if line.startswith('LICENSE'):
            body = line[len('LICENSE'):].strip()
            skipping = body.startswith('"""') and not (len(body) > 3 and body.endswith('"""'))
            continue
        out.append(line)
    return '\n'.join(out).rstrip() + '\n'


def ollama_digest(tag: str) -> str:
    with urllib.request.urlopen('http://localhost:11434/api/tags', timeout=30) as r:
        models = json.load(r)['models']
    return next(m['digest'] for m in models if m['name'] == tag)


def export_to_ollama(hf_dir: Path, tag: str, quant: str | None = None, base: str = BASE_TAG) -> str:
    """Create Ollama model `tag` from `hf_dir`; return its digest. quant=None keeps F16 like the base."""
    base_modelfile = subprocess.run(['ollama', 'show', '--modelfile', base], check=True, capture_output=True,
                                    text=True, encoding='utf-8').stdout
    with tempfile.TemporaryDirectory() as tmp:
        modelfile = Path(tmp) / 'Modelfile'
        modelfile.write_text(build_modelfile(base_modelfile, str(Path(hf_dir).resolve())), encoding='utf-8')
        cmd = ['ollama', 'create', tag, '-f', str(modelfile)] + (['--quantize', quant] if quant else [])
        subprocess.run(cmd, check=True)
    full = tag if ':' in tag else tag + ':latest'
    return ollama_digest(full)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('hf_dir', type=Path)
    p.add_argument('tag')
    p.add_argument('--base', default=BASE_TAG)
    p.add_argument('--quantize', default=None)
    a = p.parse_args()
    print('digest', export_to_ollama(a.hf_dir, a.tag, a.quantize, a.base))
