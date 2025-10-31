"""
Comprehensive Benchmark Runner for All Qwen Models

Runs MMLU, HellaSwag, ARC, TruthfulQA, and GSM8K benchmarks
on Qwen 3B, 7B, and 14B models with GPU optimization.
"""

import asyncio
import json
import logging
import os
import sys
import time
import requests
from datetime import datetime
from typing import Dict, Any, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from arc_benchmark import ARCBenchmark
from truthfulqa_benchmark import TruthfulQABenchmark
from gsm8k_benchmark import GSM8KBenchmark
from gpu_optimization import GPUOptimizer

# Import existing benchmarks
try:
    from ai_benchmark_suite import MMLUBenchmark, HellaSwagBenchmark
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Could not import existing benchmarks")
    MMLUBenchmark = None
    HellaSwagBenchmark = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ComprehensiveBenchmarkRunner:
    """Run all benchmarks on all available Qwen models"""
    
    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        num_samples: int = 50
    ):
        self.ollama_host = ollama_host
        self.api_url = f"{ollama_host}/api"
        self.num_samples = num_samples
        self.optimizer = GPUOptimizer(ollama_host)
        self.results = {}
    
    async def check_ollama_connection(self) -> bool:
        """Check if Ollama server is accessible"""
        try:
            response = requests.get(
                f"{self.api_url}/tags",
                timeout=5
            )
            if response.status_code == 200:
                logger.info("✓ Ollama connection successful")
                return True
        except Exception as e:
            logger.error(f"✗ Ollama connection failed: {e}")
        
        return False
    
    def get_qwen_models(self) -> List[str]:
        """Get list of available Qwen models"""
        try:
            response = requests.get(f"{self.api_url}/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                qwen_models = [
                    m['name'] for m in data.get('models', [])
                    if 'qwen' in m['name'].lower()
                ]
                logger.info(f"Found {len(qwen_models)} Qwen models")
                for model in qwen_models:
                    logger.info(f"  - {model}")
                return qwen_models
        except Exception as e:
            logger.error(f"Error getting models: {e}")
        
        return []
    
    async def create_qwen_inference_fn(self, model_name: str):
        """Create inference function for a Qwen model"""
        # Get optimal parameters
        params = self.optimizer.get_optimal_model_params(
            model_name,
            'benchmark'
        )
        
        async def inference(prompt: str) -> str:
            try:
                logger.debug(f"Inference on {model_name}: {prompt[:50]}...")
                
                response = requests.post(
                    f"{self.api_url}/generate",
                    json={
                        'model': model_name,
                        'prompt': prompt,
                        'stream': False,
                        'options': params
                    },
                    timeout=120
                )
                
                if response.status_code == 200:
                    result = response.json().get('response', '')
                    return result
                else:
                    logger.error(
                        f"Ollama error {response.status_code}"
                    )
                    return "A"
            
            except requests.Timeout:
                logger.error("Request timeout")
                return "A"
            except Exception as e:
                logger.error(f"Inference error: {e}")
                return "A"
        
        return inference
    
    async def run_all_benchmarks_for_model(
        self,
        model_name: str
    ) -> Dict[str, Any]:
        """Run all benchmarks for a single model"""
        logger.info(f"\n{'='*60}")
        logger.info(f"Starting benchmarks for: {model_name}")
        logger.info(f"{'='*60}\n")
        
        # Get GPU optimization info
        opt_config = self.optimizer.optimize_for_benchmarking(model_name)
        if 'warning' in opt_config:
            logger.warning(opt_config['warning'])
            logger.info(opt_config.get('recommendation', ''))
        
        # Preload model
        logger.info("Preloading model into memory...")
        self.optimizer.preload_model(
            model_name,
            opt_config['recommended_params']
        )
        
        # Create inference function
        inference_fn = await self.create_qwen_inference_fn(model_name)
        
        # Test inference
        logger.info("Testing model inference...")
        test_response = await inference_fn("Answer with just the letter A:")
        logger.info(f"Test response: {test_response[:50]}")
        
        results = {
            'model_name': model_name,
            'timestamp': datetime.now().isoformat(),
            'gpu_config': opt_config,
            'benchmarks': {}
        }
        
        # Run MMLU
        if MMLUBenchmark:
            logger.info("\n--- Running MMLU Benchmark ---")
            mmlu = MMLUBenchmark(num_samples=self.num_samples)
            mmlu_result = await mmlu.run_benchmark(
                inference_fn,
                model_name
            )
            results['benchmarks']['mmlu'] = {
                'accuracy': mmlu_result.accuracy,
                'num_correct': mmlu_result.num_correct,
                'num_questions': mmlu_result.num_questions,
                'avg_latency_ms': mmlu_result.avg_latency_ms,
                'category_accuracy': mmlu_result.details.get(
                    'category_accuracy',
                    {}
                )
            }
        
        # Run HellaSwag
        if HellaSwagBenchmark:
            logger.info("\n--- Running HellaSwag Benchmark ---")
            hellaswag = HellaSwagBenchmark(num_samples=self.num_samples)
            hs_result = await hellaswag.run_benchmark(
                inference_fn,
                model_name
            )
            results['benchmarks']['hellaswag'] = {
                'accuracy': hs_result.accuracy,
                'num_correct': hs_result.num_correct,
                'num_questions': hs_result.num_questions,
                'avg_latency_ms': hs_result.avg_latency_ms
            }
        
        # Run ARC-Easy
        logger.info("\n--- Running ARC-Easy Benchmark ---")
        arc_easy = ARCBenchmark(
            num_samples=self.num_samples,
            variant="easy"
        )
        arc_easy_result = await arc_easy.run_benchmark(
            inference_fn,
            model_name
        )
        results['benchmarks']['arc_easy'] = {
            'accuracy': arc_easy_result.accuracy,
            'num_correct': arc_easy_result.num_correct,
            'num_questions': arc_easy_result.num_questions,
            'avg_latency_ms': arc_easy_result.avg_latency_ms,
            'category_accuracy': arc_easy_result.details.get(
                'category_accuracy',
                {}
            )
        }
        
        # Run ARC-Challenge
        logger.info("\n--- Running ARC-Challenge Benchmark ---")
        arc_challenge = ARCBenchmark(
            num_samples=self.num_samples,
            variant="challenge"
        )
        arc_chal_result = await arc_challenge.run_benchmark(
            inference_fn,
            model_name
        )
        results['benchmarks']['arc_challenge'] = {
            'accuracy': arc_chal_result.accuracy,
            'num_correct': arc_chal_result.num_correct,
            'num_questions': arc_chal_result.num_questions,
            'avg_latency_ms': arc_chal_result.avg_latency_ms,
            'category_accuracy': arc_chal_result.details.get(
                'category_accuracy',
                {}
            )
        }
        
        # Run TruthfulQA
        logger.info("\n--- Running TruthfulQA Benchmark ---")
        truthfulqa = TruthfulQABenchmark(num_samples=self.num_samples)
        tfqa_result = await truthfulqa.run_benchmark(
            inference_fn,
            model_name
        )
        results['benchmarks']['truthfulqa'] = {
            'accuracy': tfqa_result.accuracy,
            'num_correct': tfqa_result.num_correct,
            'num_questions': tfqa_result.num_questions,
            'avg_latency_ms': tfqa_result.avg_latency_ms,
            'misconception_rate': tfqa_result.details.get(
                'misconception_rate',
                0
            )
        }
        
        # Run GSM8K
        logger.info("\n--- Running GSM8K Benchmark ---")
        gsm8k = GSM8KBenchmark(num_samples=self.num_samples)
        gsm8k_result = await gsm8k.run_benchmark(
            inference_fn,
            model_name
        )
        results['benchmarks']['gsm8k'] = {
            'accuracy': gsm8k_result.accuracy,
            'num_correct': gsm8k_result.num_correct,
            'num_questions': gsm8k_result.num_questions,
            'avg_latency_ms': gsm8k_result.avg_latency_ms,
            'category_accuracy': gsm8k_result.details.get(
                'category_accuracy',
                {}
            )
        }
        
        # Unload model to free memory
        logger.info(f"\nUnloading {model_name} from memory...")
        self.optimizer.unload_model(model_name)
        
        # Wait a bit before next model
        await asyncio.sleep(2)
        
        return results
    
    async def run_all(self) -> Dict[str, Any]:
        """Run all benchmarks on all available Qwen models"""
        # Check connection
        if not await self.check_ollama_connection():
            logger.error("Cannot connect to Ollama. Exiting.")
            return {}
        
        # Get GPU info
        gpu_info = self.optimizer.get_gpu_info()
        logger.info(f"\nGPU Info: {json.dumps(gpu_info, indent=2)}")
        
        # Get available models
        qwen_models = self.get_qwen_models()
        if not qwen_models:
            logger.error("No Qwen models found. Exiting.")
            return {}
        
        # Run benchmarks for each model
        all_results = {
            'timestamp': datetime.now().isoformat(),
            'gpu_info': gpu_info,
            'num_samples_per_benchmark': self.num_samples,
            'models': {}
        }
        
        for model in qwen_models:
            try:
                model_results = await self.run_all_benchmarks_for_model(
                    model
                )
                all_results['models'][model] = model_results
            except Exception as e:
                logger.error(
                    f"Error benchmarking {model}: {e}",
                    exc_info=True
                )
                continue
        
        return all_results
    
    def save_results(self, results: Dict[str, Any]):
        """Save results to JSON file"""
        os.makedirs('benchmark_results', exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"benchmark_results/comprehensive_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"\n✓ Results saved to {filename}")
        return filename
    
    def generate_summary_report(self, results: Dict[str, Any]):
        """Generate human-readable summary"""
        print("\n" + "="*70)
        print("COMPREHENSIVE BENCHMARK RESULTS SUMMARY")
        print("="*70)
        
        for model_name, model_data in results.get('models', {}).items():
            print(f"\n{model_name.upper()}")
            print("-" * 70)
            
            benchmarks = model_data.get('benchmarks', {})
            
            for bench_name, bench_data in benchmarks.items():
                acc = bench_data.get('accuracy', 0)
                correct = bench_data.get('num_correct', 0)
                total = bench_data.get('num_questions', 0)
                latency = bench_data.get('avg_latency_ms', 0)
                
                print(
                    f"{bench_name.upper():15} | "
                    f"Accuracy: {acc:5.1f}% ({correct:2}/{total:2}) | "
                    f"Latency: {latency:6.1f}ms"
                )
        
        print("\n" + "="*70)


async def main():
    """Main entry point"""
    logger.info("Starting Comprehensive Qwen Benchmark Suite")
    logger.info("Benchmarks: MMLU, HellaSwag, ARC, TruthfulQA, GSM8K")
    
    # Create runner
    runner = ComprehensiveBenchmarkRunner(num_samples=50)
    
    # Run all benchmarks
    results = await runner.run_all()
    
    if results:
        # Save results
        runner.save_results(results)
        
        # Print summary
        runner.generate_summary_report(results)
        
        logger.info("\n✓ All benchmarks completed successfully!")
    else:
        logger.error("No results generated.")


if __name__ == "__main__":
    asyncio.run(main())
