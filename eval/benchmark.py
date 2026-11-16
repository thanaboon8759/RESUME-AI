import json
import logging
import time
import sys
from typing import List

from schemas.models import CandidateProfile, ModelBenchmarkResult, BenchmarkReport
from extraction.llm_local import extract_candidate_profile, check_ollama_connectivity
from eval.test_data import TEST_SAMPLES

logger = logging.getLogger(__name__)

try:
    from rich.console import Console
    from rich.table import Table
except ImportError:
    Console = None
    Table = None

MODELS_TO_TEST = [
    'qwen2.5:7b',
    'deepseek-r1:8b',
    'scb10x/typhoon2:8b',
    'gemma2:9b',
    'llama3.1:8b',
]

def calculate_metrics(extracted_skills: List[str], ground_truth_skills: List[str]):
    extracted = set(s.lower().strip() for s in extracted_skills)
    gt = set(s.lower().strip() for s in ground_truth_skills)
    
    true_positives = extracted.intersection(gt)
    
    precision = len(true_positives) / len(extracted) if extracted else 0.0
    recall = len(true_positives) / len(gt) if gt else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return precision, recall, f1

def run_benchmark(mock: bool = False):
    if not mock and not check_ollama_connectivity():
        print("[FAIL] Ollama server is not reachable at http://localhost:11434.")
        print("[INFO] Start Ollama with 'ollama serve', or run with '--mock' to test the benchmark suite offline.")
        sys.exit(1)

    import urllib.request
    models_to_run = list(MODELS_TO_TEST)
    if not mock:
        try:
            resp = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
            installed = [m["name"].split(":")[0] + ":" + m["name"].split(":")[1] for m in json.loads(resp.read().decode()).get("models", [])]
            # Filter to installed models that are text-capable
            models_to_run = [m for m in MODELS_TO_TEST if any(m in inst for inst in installed) and "ocr" not in m]
            if not models_to_run:
                models_to_run = [m for m in installed if "ocr" not in m]
        except Exception as e:
            logger.warning(f"Could not fetch installed models: {e}")

    print(f"[INFO] Running benchmark on models: {models_to_run} (mock={mock})")
    results = []

    for model in models_to_run:
        print(f"Benchmarking model: {model}...")
        valid_count = 0
        total_latency = 0.0
        total_precision = 0.0
        total_recall = 0.0
        total_f1 = 0.0
        
        for sample in TEST_SAMPLES:
            markdown = sample['markdown']
            gt_skills = sample['ground_truth']['skills']
            
            start_time = time.time()
            is_valid = False
            skills = []
            
            if mock:
                # Simulate model characteristics on RTX 4080 (16GB VRAM)
                time.sleep(0.04)
                if "qwen" in model:
                    skills = list(gt_skills)
                elif "deepseek" in model:
                    skills = list(gt_skills)
                elif "typhoon" in model:
                    # High recall on Thai, slightly lower on obscure cloud tools
                    skills = [s for s in gt_skills if not s.startswith("Datadog")]
                elif "gemma" in model:
                    skills = [s for s in gt_skills if not s.startswith("Helm")]
                else:
                    skills = gt_skills[:max(1, len(gt_skills) - 1)]
                is_valid = True
            else:
                try:
                    profile = extract_candidate_profile(markdown, model=model)
                    is_valid = isinstance(profile, CandidateProfile)
                    if is_valid:
                        skills = profile.skills
                except Exception as e:
                    print(f"  Failed on sample {sample['id']}: {e}")
            
            latency = time.time() - start_time
            total_latency += latency
            
            if is_valid:
                valid_count += 1
                p, r, f1 = calculate_metrics(skills, gt_skills)
                total_precision += p
                total_recall += r
                total_f1 += f1
                
        num_samples = len(TEST_SAMPLES)
        validity_rate = valid_count / num_samples if num_samples > 0 else 0.0
        avg_latency = total_latency / num_samples if num_samples > 0 else 0.0
        
        avg_precision = total_precision / valid_count if valid_count > 0 else 0.0
        avg_recall = total_recall / valid_count if valid_count > 0 else 0.0
        avg_f1 = total_f1 / valid_count if valid_count > 0 else 0.0
        
        result = ModelBenchmarkResult(
            model_name=model,
            total_samples=num_samples,
            schema_validity_rate=validity_rate,
            avg_latency_seconds=avg_latency,
            precision=avg_precision,
            recall=avg_recall,
            f1_score=avg_f1
        )
        results.append(result)

    best_model = max(results, key=lambda x: x.f1_score).model_name if results else None
    
    report = BenchmarkReport(
        results=results,
        best_model=best_model
    )

    with open('benchmark_results.json', 'w', encoding='utf-8') as f:
        f.write(report.model_dump_json(indent=2))

    if Console and Table:
        console = Console()
        table = Table(title="Benchmark Results")
        table.add_column("model_name", justify="left", style="cyan", no_wrap=True)
        table.add_column("validity_rate", justify="right", style="magenta")
        table.add_column("avg_latency", justify="right", style="green")
        table.add_column("precision", justify="right")
        table.add_column("recall", justify="right")
        table.add_column("f1", justify="right", style="yellow")

        for r in results:
            table.add_row(
                r.model_name,
                f"{r.schema_validity_rate:.2f}",
                f"{r.avg_latency_seconds:.2f}",
                f"{r.precision:.2f}",
                f"{r.recall:.2f}",
                f"{r.f1_score:.2f}"
            )
        console.print(table)
        console.print(f"\nBest Model (F1): [bold green]{best_model}[/bold green]")
    else:
        print("\n--- Benchmark Results ---")
        for r in results:
            print(f"{r.model_name}: Validity: {r.schema_validity_rate:.2f}, Latency: {r.avg_latency_seconds:.2f}s, P: {r.precision:.2f}, R: {r.recall:.2f}, F1: {r.f1_score:.2f}")

if __name__ == '__main__':
    is_mock = "--mock" in sys.argv or "--dry-run" in sys.argv
    run_benchmark(mock=is_mock)
