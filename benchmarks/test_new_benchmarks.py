"""Quick test of new benchmarks"""
import asyncio
from arc_benchmark import ARCBenchmark
from truthfulqa_benchmark import TruthfulQABenchmark
from gsm8k_benchmark import GSM8KBenchmark


async def dummy_inference(prompt: str) -> str:
    """Dummy model that always returns B"""
    await asyncio.sleep(0.01)
    return "B"


async def main():
    print("Testing new benchmarks...\n")
    
    # Test ARC-Easy
    print("1. Testing ARC-Easy...")
    arc_easy = ARCBenchmark(num_samples=5, variant="easy")
    result = await arc_easy.run_benchmark(dummy_inference, "TestModel")
    print(f"   Result: {result.accuracy}% ({result.num_correct}/{result.num_questions})\n")
    
    # Test ARC-Challenge
    print("2. Testing ARC-Challenge...")
    arc_chal = ARCBenchmark(num_samples=5, variant="challenge")
    result = await arc_chal.run_benchmark(dummy_inference, "TestModel")
    print(f"   Result: {result.accuracy}% ({result.num_correct}/{result.num_questions})\n")
    
    # Test TruthfulQA
    print("3. Testing TruthfulQA...")
    tfqa = TruthfulQABenchmark(num_samples=5)
    result = await tfqa.run_benchmark(dummy_inference, "TestModel")
    print(f"   Result: {result.accuracy}% ({result.num_correct}/{result.num_questions})")
    print(f"   Misconceptions: {result.details['fell_for_misconceptions']}\n")
    
    # Test GSM8K
    print("4. Testing GSM8K...")
    gsm8k = GSM8KBenchmark(num_samples=5)
    result = await gsm8k.run_benchmark(dummy_inference, "TestModel")
    print(f"   Result: {result.accuracy}% ({result.num_correct}/{result.num_questions})\n")
    
    print("✓ All benchmark tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
