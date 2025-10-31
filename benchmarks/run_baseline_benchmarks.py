#!/usr/bin/env python3
"""
Run Baseline Benchmarks on All Available Models
Generates comprehensive baseline scores for MMLU and HellaSwag
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarks.ai_benchmark_suite import BenchmarkRunner
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModelBenchmarkOrchestrator:
    """Orchestrate benchmarks across all available models"""

    def __init__(self):
        self.runner = BenchmarkRunner(output_dir="benchmark_results")
        self.all_results = {}

    async def get_available_models(self) -> list:
        """Detect all available models in the system"""
        models = []

        # Check for local models
        local_model_paths = [
            "models/",
            "models/hrm-checkpoints/",
            "../models/"
        ]

        for path in local_model_paths:
            if os.path.exists(path):
                for item in os.listdir(path):
                    if item.endswith(('.gguf', '.bin', '.safetensors')):
                        models.append({
                            'name': item,
                            'type': 'local',
                            'path': os.path.join(path, item)
                        })

        # Add cloud/API models
        api_models = [
            {'name': 'gpt-3.5-turbo', 'type': 'openai'},
            {'name': 'gpt-4', 'type': 'openai'},
            {'name': 'claude-3-sonnet', 'type': 'anthropic'},
            {'name': 'qwen-2.5-7b', 'type': 'ollama'},
            {'name': 'llama-3.1-8b', 'type': 'ollama'}
        ]

        # Only add API models if we have credentials
        # models.extend(api_models)  # Uncomment when ready

        logger.info(f"Found {len(models)} available models")
        return models

    async def create_model_inference_function(self, model_config: dict):
        """Create inference function for a specific model"""

        if model_config['type'] == 'local':
            return await self._create_local_model_fn(model_config)
        elif model_config['type'] in ['openai', 'anthropic']:
            return await self._create_api_model_fn(model_config)
        elif model_config['type'] == 'ollama':
            return await self._create_ollama_fn(model_config)
        else:
            raise ValueError(f"Unknown model type: {model_config['type']}")

    async def _create_local_model_fn(self, config: dict):
        """Create inference function for local model"""
        try:
            from llama_cpp import Llama

            model_path = config['path']
            logger.info(f"Loading local model: {model_path}")

            # Load model
            llm = Llama(
                model_path=model_path,
                n_ctx=2048,
                n_threads=4,
                n_gpu_layers=0  # CPU only, adjust for GPU
            )

            async def inference(prompt: str) -> str:
                try:
                    response = llm(
                        prompt,
                        max_tokens=100,
                        temperature=0.1,
                        stop=["\n\n"]
                    )
                    return response['choices'][0]['text']
                except Exception as e:
                    logger.error(f"Inference error: {e}")
                    return "A"  # Default answer

            return inference

        except ImportError:
            logger.warning(
                "llama-cpp-python not available, "
                "using dummy model"
            )
            return self._create_dummy_model()

    async def _create_api_model_fn(self, config: dict):
        """Create inference function for API-based model"""
        # Placeholder for OpenAI/Anthropic API
        logger.info(
            f"API models ({config['name']}) not yet implemented, "
            "using dummy"
        )
        return self._create_dummy_model()

    async def _create_ollama_fn(self, config: dict):
        """Create inference function for Ollama model"""
        try:
            import requests

            model_name = config['name']

            async def inference(prompt: str) -> str:
                try:
                    response = requests.post(
                        'http://localhost:11434/api/generate',
                        json={
                            'model': model_name,
                            'prompt': prompt,
                            'stream': False,
                            'options': {
                                'temperature': 0.1,
                                'num_predict': 100
                            }
                        },
                        timeout=30
                    )
                    if response.status_code == 200:
                        return response.json()['response']
                    return "A"
                except Exception as e:
                    logger.error(f"Ollama error: {e}")
                    return "A"

            return inference

        except ImportError:
            logger.warning("requests not available")
            return self._create_dummy_model()

    def _create_dummy_model(self):
        """Create dummy model for testing"""
        import random

        async def inference(prompt: str) -> str:
            await asyncio.sleep(0.05)
            return random.choice(['A', 'B', 'C', 'D'])

        return inference

    async def run_baseline_benchmarks(self):
        """Run benchmarks on all available models"""
        logger.info("Starting baseline benchmark run...")

        models = await self.get_available_models()

        if not models:
            logger.warning(
                "No models found! Using dummy model for demonstration"
            )
            models = [
                {'name': 'dummy-model', 'type': 'dummy'}
            ]

        for model_config in models:
            model_name = model_config['name']
            logger.info(f"\n{'='*80}")
            logger.info(f"Benchmarking: {model_name}")
            logger.info(f"{'='*80}")

            try:
                # Create inference function
                inference_fn = await self.create_model_inference_function(
                    model_config
                )

                # Run benchmarks
                results = await self.runner.run_all_benchmarks(
                    inference_fn, model_name
                )

                self.all_results[model_name] = results

                # Print summary
                logger.info(f"\nResults for {model_name}:")
                for bench_name, result in results.items():
                    logger.info(
                        f"  {bench_name}: {result.accuracy:.2f}% "
                        f"({result.num_correct}/{result.num_questions})"
                    )

            except Exception as e:
                logger.error(f"Error benchmarking {model_name}: {e}")
                import traceback
                traceback.print_exc()

        # Generate final report
        self.generate_summary_report()

    def generate_summary_report(self):
        """Generate comprehensive summary report"""
        print("\n" + "=" * 80)
        print("BASELINE BENCHMARK SUMMARY")
        print("=" * 80)

        # Create comparison table
        print(
            f"\n{'Model':<30} {'MMLU':<15} {'HellaSwag':<15} "
            f"{'Avg Latency':<15}"
        )
        print("-" * 80)

        for model_name, results in self.all_results.items():
            mmlu_acc = results.get('mmlu').accuracy if 'mmlu' in results else 0
            hs_acc = (
                results.get('hellaswag').accuracy
                if 'hellaswag' in results else 0
            )
            avg_latency = (
                sum([r.avg_latency_ms for r in results.values()]) /
                len(results) if results else 0
            )

            print(
                f"{model_name:<30} {mmlu_acc:>6.2f}%      "
                f"{hs_acc:>6.2f}%      {avg_latency:>8.2f}ms"
            )

        print("\n" + "=" * 80)

        # Find best performers
        if self.all_results:
            best_mmlu = max(
                self.all_results.items(),
                key=lambda x: x[1].get('mmlu').accuracy
                if 'mmlu' in x[1] else 0
            )
            best_hs = max(
                self.all_results.items(),
                key=lambda x: x[1].get('hellaswag').accuracy
                if 'hellaswag' in x[1] else 0
            )

            print("\nBest Performers:")
            print(
                f"  MMLU: {best_mmlu[0]} "
                f"({best_mmlu[1]['mmlu'].accuracy:.2f}%)"
            )
            print(
                f"  HellaSwag: {best_hs[0]} "
                f"({best_hs[1]['hellaswag'].accuracy:.2f}%)"
            )

        print("\n" + "=" * 80)
        print(
            f"Results saved to: benchmark_results/"
        )
        print("=" * 80)


async def main():
    """Main entry point"""
    orchestrator = ModelBenchmarkOrchestrator()
    await orchestrator.run_baseline_benchmarks()


if __name__ == "__main__":
    asyncio.run(main())
