"""
Qwen Model Comparison Runner

Simplified runner for testing Qwen 3B model on all new benchmarks
with better error handling.
"""

import asyncio
import json
import logging
import requests
from datetime import datetime
from typing import Dict, Any

from arc_benchmark import ARCBenchmark
from truthfulqa_benchmark import TruthfulQABenchmark
from gsm8k_benchmark import GSM8KBenchmark

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QwenBenchmarkRunner:
    """Simple benchmark runner for Qwen models"""
    
    def __init__(
        self,
        model_name: str = "qwen2.5:3b",
        num_samples: int = 25
    ):
        self.model_name = model_name
        self.num_samples = num_samples
        self.ollama_url = "http://localhost:11434/api/generate"
    
    async def create_inference_fn(self):
        """Create inference function with retries"""
        async def inference(prompt: str) -> str:
            max_retries = 3
            
            for attempt in range(max_retries):
                try:
                    response = requests.post(
                        self.ollama_url,
                        json={
                            'model': self.model_name,
                            'prompt': prompt,
                            'stream': False,
                            'options': {
                                'temperature': 0.1,
                                'num_predict': 100,
                                'top_p': 0.9,
                            }
                        },
                        timeout=60
                    )
                    
                    if response.status_code == 200:
                        return response.json().get('response', 'A')
                    else:
                        logger.warning(
                            f"Attempt {attempt+1}: Ollama returned "
                            f"{response.status_code}"
                        )
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2)
                
                except Exception as e:
                    logger.warning(f"Attempt {attempt+1} failed: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2)
            
            # Fallback
            return "A"
        
        return inference
    
    async def run_all_benchmarks(self) -> Dict[str, Any]:
        """Run all benchmarks"""
        logger.info(f"Starting benchmarks for {self.model_name}")
        logger.info(f"Samples per benchmark: {self.num_samples}")
        
        inference_fn = await self.create_inference_fn()
        
        results = {
            'model': self.model_name,
            'timestamp': datetime.now().isoformat(),
            'num_samples': self.num_samples,
            'benchmarks': {}
        }
        
        # ARC-Easy
        logger.info("\n=== Running ARC-Easy ===")
        try:
            arc_easy = ARCBenchmark(
                num_samples=self.num_samples,
                variant='easy'
            )
            result = await arc_easy.run_benchmark(
                inference_fn,
                self.model_name
            )
            results['benchmarks']['arc_easy'] = {
                'accuracy': result.accuracy,
                'num_correct': result.num_correct,
                'num_questions': result.num_questions,
                'avg_latency_ms': result.avg_latency_ms,
                'category_accuracy': result.details['category_accuracy']
            }
            logger.info(f"ARC-Easy: {result.accuracy:.1f}% accuracy")
        except Exception as e:
            logger.error(f"ARC-Easy failed: {e}")
        
        # ARC-Challenge
        logger.info("\n=== Running ARC-Challenge ===")
        try:
            arc_chal = ARCBenchmark(
                num_samples=self.num_samples,
                variant='challenge'
            )
            result = await arc_chal.run_benchmark(
                inference_fn,
                self.model_name
            )
            results['benchmarks']['arc_challenge'] = {
                'accuracy': result.accuracy,
                'num_correct': result.num_correct,
                'num_questions': result.num_questions,
                'avg_latency_ms': result.avg_latency_ms,
                'category_accuracy': result.details['category_accuracy']
            }
            logger.info(f"ARC-Challenge: {result.accuracy:.1f}% accuracy")
        except Exception as e:
            logger.error(f"ARC-Challenge failed: {e}")
        
        # TruthfulQA
        logger.info("\n=== Running TruthfulQA ===")
        try:
            tfqa = TruthfulQABenchmark(num_samples=self.num_samples)
            result = await tfqa.run_benchmark(
                inference_fn,
                self.model_name
            )
            results['benchmarks']['truthfulqa'] = {
                'accuracy': result.accuracy,
                'num_correct': result.num_correct,
                'num_questions': result.num_questions,
                'avg_latency_ms': result.avg_latency_ms,
                'misconception_rate': result.details['misconception_rate']
            }
            logger.info(
                f"TruthfulQA: {result.accuracy:.1f}% accuracy "
                f"(Misconceptions: "
                f"{result.details['fell_for_misconceptions']})"
            )
        except Exception as e:
            logger.error(f"TruthfulQA failed: {e}")
        
        # GSM8K
        logger.info("\n=== Running GSM8K ===")
        try:
            gsm8k = GSM8KBenchmark(num_samples=self.num_samples)
            result = await gsm8k.run_benchmark(
                inference_fn,
                self.model_name
            )
            results['benchmarks']['gsm8k'] = {
                'accuracy': result.accuracy,
                'num_correct': result.num_correct,
                'num_questions': result.num_questions,
                'avg_latency_ms': result.avg_latency_ms,
                'category_accuracy': result.details['category_accuracy']
            }
            logger.info(f"GSM8K: {result.accuracy:.1f}% accuracy")
        except Exception as e:
            logger.error(f"GSM8K failed: {e}")
        
        return results
    
    def save_results(self, results: Dict[str, Any]):
        """Save results to file"""
        import os
        os.makedirs('benchmark_results', exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = (
            f"benchmark_results/qwen_new_benchmarks_{timestamp}.json"
        )
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"\n✓ Results saved to {filename}")
        return filename
    
    def print_summary(self, results: Dict[str, Any]):
        """Print results summary"""
        print("\n" + "="*60)
        print(f"BENCHMARK RESULTS: {results['model']}")
        print("="*60)
        
        for name, data in results['benchmarks'].items():
            acc = data['accuracy']
            correct = data['num_correct']
            total = data['num_questions']
            latency = data['avg_latency_ms']
            
            print(
                f"{name.upper():15} | "
                f"{acc:5.1f}% ({correct:2}/{total:2}) | "
                f"{latency:6.1f}ms"
            )
        
        # Calculate average
        accs = [d['accuracy'] for d in results['benchmarks'].values()]
        avg_acc = sum(accs) / len(accs) if accs else 0
        
        print("-"*60)
        print(f"{'AVERAGE':15} | {avg_acc:5.1f}%")
        print("="*60)


async def main():
    """Run benchmarks"""
    # Use smaller sample size for faster testing
    runner = QwenBenchmarkRunner(
        model_name="qwen2.5:3b",
        num_samples=25
    )
    
    results = await runner.run_all_benchmarks()
    
    runner.save_results(results)
    runner.print_summary(results)


if __name__ == "__main__":
    asyncio.run(main())
