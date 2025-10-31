#!/usr/bin/env python3
"""
Run comprehensive benchmarks specifically with Qwen2.5-3B
"""

import asyncio
import sys
import os
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarks.ai_benchmark_suite import BenchmarkRunner
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_ollama_connection():
    """Test if Ollama is running"""
    try:
        response = requests.get('http://localhost:11434/api/tags', timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            logger.info(f"Ollama is running with {len(models)} models")
            for model in models:
                logger.info(f"  - {model['name']}")
            return True
        return False
    except Exception as e:
        logger.error(f"Ollama connection failed: {e}")
        return False


async def create_qwen_inference_fn(model_name: str = "qwen2.5:3b"):
    """Create inference function for Qwen via Ollama"""
    
    async def inference(prompt: str) -> str:
        try:
            logger.debug(f"Sending prompt to {model_name}: {prompt[:100]}...")
            
            response = requests.post(
                'http://localhost:11434/api/generate',
                json={
                    'model': model_name,
                    'prompt': prompt,
                    'stream': False,
                    'options': {
                        'temperature': 0.1,
                        'num_predict': 50,
                        'top_p': 0.9,
                    }
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()['response']
                logger.debug(f"Response: {result[:100]}")
                return result
            else:
                logger.error(
                    f"Ollama error: {response.status_code} - {response.text}"
                )
                return "A"
                
        except requests.Timeout:
            logger.error("Request timeout")
            return "A"
        except Exception as e:
            logger.error(f"Inference error: {e}")
            return "A"
    
    return inference


async def run_qwen_benchmarks():
    """Run all benchmarks on Qwen2.5-3B"""
    
    logger.info("=" * 80)
    logger.info("QWEN2.5-3B COMPREHENSIVE BENCHMARK")
    logger.info("=" * 80)
    
    # Check Ollama connection
    if not await test_ollama_connection():
        logger.error(
            "Ollama is not running or not accessible. "
            "Please start Ollama first."
        )
        return
    
    # Check if Qwen2.5:3b is available
    try:
        response = requests.get('http://localhost:11434/api/tags')
        models = response.json().get('models', [])
        model_names = [m['name'] for m in models]
        
        qwen_models = [
            name for name in model_names 
            if 'qwen' in name.lower()
        ]
        
        if not qwen_models:
            logger.error(
                "No Qwen models found in Ollama. "
                "Please pull the model first:"
            )
            logger.error("  ollama pull qwen2.5:3b")
            return
        
        logger.info(f"Found Qwen models: {qwen_models}")
        target_model = qwen_models[0]  # Use first Qwen model found
        
    except Exception as e:
        logger.error(f"Error checking Ollama models: {e}")
        return
    
    # Create benchmark runner
    runner = BenchmarkRunner(output_dir="benchmark_results")
    
    # Create inference function
    logger.info(f"\nCreating inference function for {target_model}...")
    inference_fn = await create_qwen_inference_fn(target_model)
    
    # Test inference
    logger.info("\nTesting inference...")
    test_response = await inference_fn("What is 2+2? Answer with just a letter A, B, C, or D.\nA) 3\nB) 4\nC) 5\nD) 6\nAnswer:")
    logger.info(f"Test response: {test_response}")
    
    # Run full benchmark suite
    logger.info(f"\nRunning full benchmark suite on {target_model}...")
    logger.info("This may take several minutes...\n")
    
    try:
        results = await runner.run_all_benchmarks(inference_fn, target_model)
        
        # Print detailed results
        logger.info("\n" + "=" * 80)
        logger.info("BENCHMARK RESULTS")
        logger.info("=" * 80)
        
        for bench_name, result in results.items():
            logger.info(f"\n{bench_name.upper()}:")
            logger.info(f"  Accuracy: {result.accuracy:.2f}%")
            logger.info(
                f"  Correct: {result.num_correct}/{result.num_questions}"
            )
            logger.info(f"  Avg Latency: {result.avg_latency_ms:.2f}ms")
            logger.info(f"  Total Time: {result.total_time_sec:.2f}s")
            
            if 'category_accuracy' in result.details:
                logger.info("  Category Breakdown:")
                for cat, acc in result.details['category_accuracy'].items():
                    logger.info(f"    {cat}: {acc:.1f}%")
        
        logger.info("\n" + "=" * 80)
        logger.info(f"Results saved to benchmark_results/")
        logger.info("=" * 80)
        
        # Generate comparison with baseline
        logger.info("\nCOMPARISON WITH BASELINE (Random Guessing):")
        logger.info("-" * 80)
        logger.info(
            f"MMLU: {results['mmlu'].accuracy:.2f}% "
            f"(baseline: ~25% for 4-choice questions)"
        )
        logger.info(
            f"HellaSwag: {results['hellaswag'].accuracy:.2f}% "
            f"(baseline: ~25% for 4-choice questions)"
        )
        
        # Calculate improvement
        mmlu_improvement = results['mmlu'].accuracy - 25.0
        hs_improvement = results['hellaswag'].accuracy - 25.0
        
        logger.info(f"\nImprovement over random:")
        logger.info(
            f"  MMLU: {mmlu_improvement:+.2f} percentage points"
        )
        logger.info(
            f"  HellaSwag: {hs_improvement:+.2f} percentage points"
        )
        
    except Exception as e:
        logger.error(f"Error running benchmarks: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main entry point"""
    await run_qwen_benchmarks()


if __name__ == "__main__":
    asyncio.run(main())
