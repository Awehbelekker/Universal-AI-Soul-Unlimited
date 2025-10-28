#!/usr/bin/env python3
"""
Qwen2.5-3B Performance Benchmark
Comprehensive testing of model performance and optimization
"""

import asyncio
import time
import json
import statistics
from typing import List, Dict, Tuple
from datetime import datetime
import sys

try:
    import ollama
except ImportError:
    print("❌ Error: ollama package not found. Install with: pip install ollama")
    sys.exit(1)


class QwenBenchmark:
    """Benchmark suite for Qwen2.5-3B performance testing"""
    
    TEST_CATEGORIES = {
        "simple": [
            "Hello! How are you?",
            "What is 2+2?",
            "Define AI in one sentence.",
        ],
        "reasoning": [
            "If all roses are flowers and some flowers fade quickly, what can we conclude?",
            "A farmer has 17 sheep, all but 9 die. How many are left?",
            "Explain the trolley problem briefly.",
        ],
        "coding": [
            "Write a Python function to check if a number is prime.",
            "Create a JavaScript function to reverse a string.",
            "Write SQL to find duplicate records in a users table.",
        ],
        "creative": [
            "Write a haiku about artificial intelligence.",
            "Describe a sunset in 2 sentences.",
            "Create a tagline for a coffee shop.",
        ],
        "complex": [
            "Explain quantum entanglement and its implications for computing.",
            "Compare microservices vs monolithic architecture with pros/cons.",
            "Design a caching strategy for a high-traffic web application.",
        ]
    }
    
    def __init__(self, model: str = "qwen2.5:3b", runs_per_test: int = 3):
        self.model = model
        self.runs_per_test = runs_per_test
        self.results = {
            "model": model,
            "timestamp": datetime.now().isoformat(),
            "runs_per_test": runs_per_test,
            "categories": {}
        }
    
    def _tokens_estimate(self, text: str) -> int:
        """Rough token count estimation (1 token ≈ 4 chars)"""
        return len(text) // 4
    
    async def benchmark_prompt(self, prompt: str) -> Dict:
        """Benchmark a single prompt"""
        times = []
        tokens = []
        responses = []
        
        for run in range(self.runs_per_test):
            try:
                start = time.time()
                
                response = ollama.chat(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                elapsed = time.time() - start
                response_text = response['message']['content']
                token_count = self._tokens_estimate(response_text)
                
                times.append(elapsed)
                tokens.append(token_count)
                responses.append(response_text)
                
                # Small delay between runs
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"  ❌ Error on run {run + 1}: {e}")
                continue
        
        if not times:
            return None
        
        return {
            "prompt": prompt,
            "runs": self.runs_per_test,
            "avg_time": round(statistics.mean(times), 3),
            "min_time": round(min(times), 3),
            "max_time": round(max(times), 3),
            "avg_tokens": round(statistics.mean(tokens)),
            "avg_tokens_per_second": round(statistics.mean(tokens) / statistics.mean(times), 2),
            "sample_response": responses[0][:100] + "..." if responses[0] else ""
        }
    
    async def benchmark_category(self, category: str, prompts: List[str]):
        """Benchmark a category of prompts"""
        print(f"\n{'='*70}")
        print(f"📊 Testing: {category.upper()}")
        print(f"{'='*70}")
        
        category_results = []
        
        for i, prompt in enumerate(prompts, 1):
            print(f"\n  [{i}/{len(prompts)}] Testing: {prompt[:60]}...")
            
            result = await self.benchmark_prompt(prompt)
            
            if result:
                category_results.append(result)
                print(f"    ⏱️  Avg Time: {result['avg_time']}s")
                print(f"    🚀 Speed: {result['avg_tokens_per_second']} tokens/sec")
            else:
                print(f"    ❌ Test failed")
        
        # Calculate category statistics
        if category_results:
            avg_category_time = statistics.mean([r['avg_time'] for r in category_results])
            avg_category_speed = statistics.mean([r['avg_tokens_per_second'] for r in category_results])
            
            self.results["categories"][category] = {
                "tests": category_results,
                "summary": {
                    "avg_time": round(avg_category_time, 3),
                    "avg_speed": round(avg_category_speed, 2),
                    "total_tests": len(category_results)
                }
            }
    
    async def run_full_benchmark(self):
        """Run complete benchmark suite"""
        print("\n" + "="*70)
        print("🚀 QWEN2.5-3B PERFORMANCE BENCHMARK")
        print("="*70)
        print(f"Model: {self.model}")
        print(f"Runs per test: {self.runs_per_test}")
        print(f"Total tests: {sum(len(p) for p in self.TEST_CATEGORIES.values())}")
        print("="*70)
        
        start_time = time.time()
        
        for category, prompts in self.TEST_CATEGORIES.items():
            await self.benchmark_category(category, prompts)
        
        total_time = time.time() - start_time
        
        # Overall summary
        print(f"\n{'='*70}")
        print("📈 OVERALL SUMMARY")
        print(f"{'='*70}")
        
        all_times = []
        all_speeds = []
        
        for category, data in self.results["categories"].items():
            summary = data["summary"]
            print(f"\n  {category.upper():12} → Time: {summary['avg_time']}s | Speed: {summary['avg_speed']} t/s")
            all_times.append(summary['avg_time'])
            all_speeds.append(summary['avg_speed'])
        
        if all_times:
            print(f"\n  {'OVERALL':12} → Time: {round(statistics.mean(all_times), 3)}s | Speed: {round(statistics.mean(all_speeds), 2)} t/s")
        
        print(f"\n  Total benchmark time: {round(total_time, 1)}s")
        
        self.results["overall"] = {
            "total_time": round(total_time, 1),
            "avg_response_time": round(statistics.mean(all_times), 3) if all_times else 0,
            "avg_tokens_per_second": round(statistics.mean(all_speeds), 2) if all_speeds else 0
        }
        
        return self.results
    
    def save_results(self, filename: str = "qwen_benchmark_results.json"):
        """Save results to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Results saved to: {filename}")
    
    def print_recommendations(self):
        """Print optimization recommendations based on results"""
        print(f"\n{'='*70}")
        print("💡 OPTIMIZATION RECOMMENDATIONS")
        print(f"{'='*70}")
        
        if "overall" in self.results:
            avg_time = self.results["overall"]["avg_response_time"]
            avg_speed = self.results["overall"]["avg_tokens_per_second"]
            
            if avg_time > 3:
                print("\n⚠️  High latency detected:")
                print("   • Consider using Q4 quantization for faster inference")
                print("   • Enable GPU acceleration if available")
                print("   • Reduce context window size (num_ctx)")
                print("   • Increase CPU thread count (num_thread)")
            
            if avg_speed < 20:
                print("\n⚠️  Low throughput detected:")
                print("   • Enable GPU layers (num_gpu > 0)")
                print("   • Use larger batch size (num_batch = 512)")
                print("   • Enable memory mapping (use_mmap = true)")
                print("   • Consider hardware upgrade")
            
            if avg_time < 2 and avg_speed > 40:
                print("\n✅ Excellent performance! Consider:")
                print("   • Use Q8 quantization for better quality")
                print("   • Increase context window for longer conversations")
                print("   • Enable parallel requests (num_parallel = 2-4)")
            
            if 2 <= avg_time <= 3 and 25 <= avg_speed <= 40:
                print("\n✅ Good performance! Fine-tuning options:")
                print("   • Balance between Q4 and Q8 quantization")
                print("   • Implement response caching for common queries")
                print("   • Enable streaming for better UX")


async def main():
    """Main benchmark execution"""
    print("Qwen2.5-3B Performance Benchmark")
    print("=" * 70)
    
    # Check if model is available
    try:
        models = ollama.list()
        print(f"\n✅ Connected to Ollama")
    except Exception as e:
        print(f"\n❌ Error connecting to Ollama: {e}")
        print("\nMake sure Ollama is running: ollama serve")
        return
    
    # Select model
    model = input("\nEnter model name (default: qwen2.5:3b): ").strip() or "qwen2.5:3b"
    runs = input("Runs per test (default: 3): ").strip()
    runs = int(runs) if runs.isdigit() else 3
    
    # Run benchmark
    benchmark = QwenBenchmark(model=model, runs_per_test=runs)
    
    try:
        results = await benchmark.run_full_benchmark()
        benchmark.save_results()
        benchmark.print_recommendations()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Benchmark interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Benchmark error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
