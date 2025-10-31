#!/usr/bin/env python3
"""
Run comprehensive benchmarks on all models including Qwen2.5-3B
"""

import asyncio
import sys
import os
from pathlib import Path
import json
import requests
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarks.ai_benchmark_suite import BenchmarkRunner
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ComprehensiveBenchmarkRunner:
    """Run benchmarks on all available models including Qwen2.5-3B"""

    def __init__(self):
        self.runner = BenchmarkRunner(output_dir="benchmark_results")
        self.all_results = {}

    async def create_ollama_inference(self, model_name: str):
        """Create inference function for Ollama models"""
        
        async def inference(prompt: str) -> str:
            try:
                logger.info(f"Querying {model_name}...")
                response = requests.post(
                    'http://localhost:11434/api/generate',
                    json={
                        'model': model_name,
                        'prompt': prompt,
                        'stream': False,
                        'options': {
                            'temperature': 0.1,
                            'num_predict': 50,
                            'top_k': 10,
                            'top_p': 0.9
                        }
                    },
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()['response'].strip()
                    logger.debug(f"Response: {result[:100]}")
                    return result
                else:
                    logger.error(f"HTTP {response.status_code}: {response.text}")
                    return "A"
                    
            except requests.exceptions.Timeout:
                logger.error(f"Timeout querying {model_name}")
                return "A"
            except Exception as e:
                logger.error(f"Error with {model_name}: {e}")
                return "A"
        
        return inference

    async def benchmark_model(self, model_name: str, display_name: str = None):
        """Run benchmarks on a specific model"""
        if display_name is None:
            display_name = model_name
            
        logger.info("\n" + "="*80)
        logger.info(f"BENCHMARKING: {display_name}")
        logger.info("="*80)
        
        try:
            # Create inference function
            inference_fn = await self.create_ollama_inference(model_name)
            
            # Test connection
            logger.info(f"Testing connection to {model_name}...")
            test_response = await inference_fn("Test")
            logger.info(f"Connection successful! Sample response: {test_response[:50]}")
            
            # Run benchmarks
            logger.info(f"\nStarting MMLU and HellaSwag benchmarks...")
            results = await self.runner.run_all_benchmarks(
                inference_fn, display_name
            )
            
            self.all_results[display_name] = results
            
            # Print immediate results
            print("\n" + "-"*80)
            print(f"RESULTS FOR {display_name}:")
            print("-"*80)
            for bench_name, result in results.items():
                print(f"{bench_name.upper()}:")
                print(f"  Accuracy: {result.accuracy:.2f}%")
                print(f"  Correct: {result.num_correct}/{result.num_questions}")
                print(f"  Avg Latency: {result.avg_latency_ms:.2f}ms")
                print(f"  Total Time: {result.total_time_sec:.2f}s")
            print("-"*80)
            
            return results
            
        except Exception as e:
            logger.error(f"Error benchmarking {display_name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def run_all_benchmarks(self):
        """Run benchmarks on all available models"""
        logger.info("Starting comprehensive benchmark suite...")
        logger.info(f"Benchmark output directory: benchmark_results/\n")
        
        # Define models to benchmark
        models_to_test = [
            ("qwen2.5:3b", "Qwen2.5-3B"),
            ("qwen2.5-fast:latest", "Qwen2.5-Fast"),
            ("qwen2.5-optimized:latest", "Qwen2.5-Optimized"),
        ]
        
        # Run benchmarks on each model
        for model_name, display_name in models_to_test:
            try:
                await self.benchmark_model(model_name, display_name)
                # Small delay between models
                await asyncio.sleep(2)
            except KeyboardInterrupt:
                logger.warning("Benchmark interrupted by user")
                break
            except Exception as e:
                logger.error(f"Failed to benchmark {display_name}: {e}")
                continue
        
        # Generate final report
        self.generate_comprehensive_report()

    def generate_comprehensive_report(self):
        """Generate detailed comparison report"""
        print("\n\n")
        print("="*80)
        print(" "*20 + "COMPREHENSIVE BENCHMARK REPORT")
        print("="*80)
        
        if not self.all_results:
            print("\nNo results to report!")
            return
        
        # Summary table
        print(f"\n{'Model':<30} {'MMLU':<15} {'HellaSwag':<15} {'Avg Latency':<15}")
        print("-"*80)
        
        model_stats = []
        for model_name, results in self.all_results.items():
            mmlu_acc = results.get('mmlu').accuracy if 'mmlu' in results else 0
            hs_acc = results.get('hellaswag').accuracy if 'hellaswag' in results else 0
            
            # Calculate average latency across both benchmarks
            latencies = []
            if 'mmlu' in results:
                latencies.append(results['mmlu'].avg_latency_ms)
            if 'hellaswag' in results:
                latencies.append(results['hellaswag'].avg_latency_ms)
            avg_latency = sum(latencies) / len(latencies) if latencies else 0
            
            model_stats.append({
                'name': model_name,
                'mmlu': mmlu_acc,
                'hellaswag': hs_acc,
                'latency': avg_latency
            })
            
            print(f"{model_name:<30} {mmlu_acc:>6.2f}%      {hs_acc:>6.2f}%      {avg_latency:>8.2f}ms")
        
        # Best performers
        print("\n" + "="*80)
        print("BEST PERFORMERS")
        print("="*80)
        
        if model_stats:
            best_mmlu = max(model_stats, key=lambda x: x['mmlu'])
            best_hs = max(model_stats, key=lambda x: x['hellaswag'])
            fastest = min(model_stats, key=lambda x: x['latency'])
            
            print(f"\nHighest MMLU Score:")
            print(f"  {best_mmlu['name']}: {best_mmlu['mmlu']:.2f}%")
            
            print(f"\nHighest HellaSwag Score:")
            print(f"  {best_hs['name']}: {best_hs['hellaswag']:.2f}%")
            
            print(f"\nFastest Response Time:")
            print(f"  {fastest['name']}: {fastest['latency']:.2f}ms")
        
        # Detailed category breakdown for MMLU
        print("\n" + "="*80)
        print("MMLU CATEGORY BREAKDOWN")
        print("="*80)
        
        for model_name, results in self.all_results.items():
            if 'mmlu' in results and 'category_accuracy' in results['mmlu'].details:
                print(f"\n{model_name}:")
                cat_acc = results['mmlu'].details['category_accuracy']
                for category, accuracy in sorted(cat_acc.items(), key=lambda x: x[1], reverse=True):
                    print(f"  {category:<30} {accuracy:>6.2f}%")
        
        print("\n" + "="*80)
        print("ANALYSIS COMPLETE")
        print("="*80)
        print(f"\nResults saved to: benchmark_results/")
        print(f"Total models benchmarked: {len(self.all_results)}")
        print("="*80 + "\n")


async def main():
    """Main entry point"""
    runner = ComprehensiveBenchmarkRunner()
    await runner.run_all_benchmarks()


if __name__ == "__main__":
    print("\n" + "="*80)
    print(" "*15 + "COMPREHENSIVE AI MODEL BENCHMARK SUITE")
    print("="*80)
    print("\nBenchmarks: MMLU + HellaSwag")
    print("Models: Qwen2.5-3B, Qwen2.5-Fast, Qwen2.5-Optimized")
    print("\nStarting in 3 seconds...\n")
    
    import time
    time.sleep(3)
    
    asyncio.run(main())
