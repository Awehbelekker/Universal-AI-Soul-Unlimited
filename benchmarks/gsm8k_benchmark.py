"""
GSM8K (Grade School Math 8K) Benchmark Implementation

Tests mathematical reasoning on grade-school level word problems
requiring multi-step reasoning.
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Any, Callable, Awaitable

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class GSM8KResult:
    """Results from GSM8K benchmark"""
    benchmark_name: str
    model_name: str
    accuracy: float
    num_questions: int
    num_correct: int
    avg_latency_ms: float
    total_time_sec: float
    timestamp: str
    details: Dict[str, Any]


class GSM8KBenchmark:
    """
    GSM8K (Grade School Math) Benchmark
    
    Tests mathematical reasoning through word problems that require
    multi-step solutions. Focuses on arithmetic and basic algebra.
    """
    
    def __init__(self, num_samples: int = 50):
        """Initialize GSM8K benchmark"""
        self.num_samples = num_samples
    
    def generate_sample_questions(self) -> List[Dict]:
        """Generate sample GSM8K questions"""
        
        questions = [
            {
                "id": "gsm8k_001",
                "question": (
                    "Janet has 24 apples. She gives 8 apples to her "
                    "friend and then buys 12 more. How many apples "
                    "does Janet have now?"
                ),
                "answer": "28",
                "solution": "24 - 8 + 12 = 28",
                "category": "basic_arithmetic"
            },
            {
                "id": "gsm8k_002",
                "question": (
                    "A bakery makes 15 loaves of bread per hour. "
                    "If they work for 8 hours, how many loaves do "
                    "they make in total?"
                ),
                "answer": "120",
                "solution": "15 × 8 = 120",
                "category": "multiplication"
            },
            {
                "id": "gsm8k_003",
                "question": (
                    "Sarah has $50. She spends $12 on lunch and $8 "
                    "on a book. How much money does she have left?"
                ),
                "answer": "30",
                "solution": "50 - 12 - 8 = 30",
                "category": "basic_arithmetic"
            },
            {
                "id": "gsm8k_004",
                "question": (
                    "A car travels 60 miles per hour. How far will "
                    "it travel in 3.5 hours?"
                ),
                "answer": "210",
                "solution": "60 × 3.5 = 210",
                "category": "rate_problems"
            },
            {
                "id": "gsm8k_005",
                "question": (
                    "Tom has twice as many marbles as Jerry. Jerry "
                    "has 15 marbles. How many marbles does Tom have?"
                ),
                "answer": "30",
                "solution": "15 × 2 = 30",
                "category": "ratios"
            },
            {
                "id": "gsm8k_006",
                "question": (
                    "A pizza is cut into 8 slices. If 3 people each "
                    "eat 2 slices, how many slices are left?"
                ),
                "answer": "2",
                "solution": "8 - (3 × 2) = 8 - 6 = 2",
                "category": "basic_arithmetic"
            },
            {
                "id": "gsm8k_007",
                "question": (
                    "Emma saves $5 per week. How much will she save "
                    "in 12 weeks?"
                ),
                "answer": "60",
                "solution": "5 × 12 = 60",
                "category": "multiplication"
            },
            {
                "id": "gsm8k_008",
                "question": (
                    "A school has 450 students. If 3/5 of them are "
                    "girls, how many girls are in the school?"
                ),
                "answer": "270",
                "solution": "450 × (3/5) = 450 × 0.6 = 270",
                "category": "fractions"
            },
            {
                "id": "gsm8k_009",
                "question": (
                    "Jack runs 3 miles each day. How many miles does "
                    "he run in a week?"
                ),
                "answer": "21",
                "solution": "3 × 7 = 21",
                "category": "multiplication"
            },
            {
                "id": "gsm8k_010",
                "question": (
                    "A box contains 144 crayons arranged in 12 equal "
                    "rows. How many crayons are in each row?"
                ),
                "answer": "12",
                "solution": "144 ÷ 12 = 12",
                "category": "division"
            },
            {
                "id": "gsm8k_011",
                "question": (
                    "Lisa bought 4 books at $7 each and 2 pens at "
                    "$3 each. How much did she spend in total?"
                ),
                "answer": "34",
                "solution": "(4 × 7) + (2 × 3) = 28 + 6 = 34",
                "category": "multi_step"
            },
            {
                "id": "gsm8k_012",
                "question": (
                    "A farmer has 36 chickens and 18 ducks. What is "
                    "the ratio of chickens to ducks?"
                ),
                "answer": "2",
                "solution": "36 ÷ 18 = 2 (or 2:1 ratio)",
                "category": "ratios"
            },
            {
                "id": "gsm8k_013",
                "question": (
                    "Mike is 12 years old. His brother is 3 years "
                    "younger. How old will his brother be in 5 years?"
                ),
                "answer": "14",
                "solution": "(12 - 3) + 5 = 9 + 5 = 14",
                "category": "multi_step"
            },
            {
                "id": "gsm8k_014",
                "question": (
                    "A rectangle has a length of 15 cm and width of "
                    "8 cm. What is its area?"
                ),
                "answer": "120",
                "solution": "15 × 8 = 120 square cm",
                "category": "geometry"
            },
            {
                "id": "gsm8k_015",
                "question": (
                    "Anna has 5 more pencils than Bob. Bob has 8 "
                    "pencils. How many pencils do they have together?"
                ),
                "answer": "21",
                "solution": "Bob: 8, Anna: 8+5=13, Total: 8+13=21",
                "category": "multi_step"
            },
            {
                "id": "gsm8k_016",
                "question": (
                    "A train travels at 80 km/h for 2 hours, then "
                    "60 km/h for 3 hours. What is the total distance?"
                ),
                "answer": "340",
                "solution": "(80 × 2) + (60 × 3) = 160 + 180 = 340",
                "category": "rate_problems"
            },
            {
                "id": "gsm8k_017",
                "question": (
                    "If 5 pencils cost $2.50, how much do "
                    "12 pencils cost?"
                ),
                "answer": "6",
                "solution": (
                    "Cost per pencil: 2.50 ÷ 5 = 0.50, "
                    "12 pencils: 0.50 × 12 = 6"
                ),
                "category": "unit_rates"
            },
            {
                "id": "gsm8k_018",
                "question": (
                    "A jar contains 200 candies. If you eat 15% of "
                    "them, how many candies are left?"
                ),
                "answer": "170",
                "solution": "200 - (200 × 0.15) = 200 - 30 = 170",
                "category": "percentages"
            },
            {
                "id": "gsm8k_019",
                "question": (
                    "Sam mows 3 lawns on Monday, 5 on Tuesday, and "
                    "4 on Wednesday. He earns $8 per lawn. How much "
                    "did he earn?"
                ),
                "answer": "96",
                "solution": "(3 + 5 + 4) × 8 = 12 × 8 = 96",
                "category": "multi_step"
            },
            {
                "id": "gsm8k_020",
                "question": (
                    "A basketball team scored 24 points in the first "
                    "half and 31 in the second. What was their total?"
                ),
                "answer": "55",
                "solution": "24 + 31 = 55",
                "category": "basic_arithmetic"
            }
        ]
        
        # Extend pool by repeating if needed
        while len(questions) < self.num_samples:
            questions.extend(questions[:20])
        
        return questions[:self.num_samples]
    
    def extract_number(self, text: str) -> str:
        """Extract numeric answer from model response"""
        # Look for numbers in the text
        numbers = re.findall(r'\d+\.?\d*', text)
        if numbers:
            # Return the last number found (often the final answer)
            return numbers[-1].rstrip('.')
        return ""
    
    async def run_benchmark(
        self,
        model_inference_fn: Callable[[str], Awaitable[str]],
        model_name: str
    ) -> GSM8KResult:
        """Run GSM8K benchmark on a model"""
        logger.info(f"Starting GSM8K benchmark for {model_name}")
        
        questions = self.generate_sample_questions()
        correct = 0
        latencies = []
        category_stats = {}
        
        start_time = time.time()
        
        for i, q in enumerate(questions):
            prompt = f"""Solve this math problem step by step:

{q['question']}

Provide your final numeric answer at the end:"""
            
            t0 = time.time()
            try:
                response = await model_inference_fn(prompt)
                latency = (time.time() - t0) * 1000
                latencies.append(latency)
                
                # Extract numeric answer
                model_answer = self.extract_number(response)
                
                # Check if correct (allowing for minor formatting)
                if model_answer == q['answer']:
                    correct += 1
                
                # Track category performance
                category = q.get('category', 'unknown')
                if category not in category_stats:
                    category_stats[category] = {'correct': 0, 'total': 0}
                category_stats[category]['total'] += 1
                if model_answer == q['answer']:
                    category_stats[category]['correct'] += 1
                
                if (i + 1) % 10 == 0:
                    logger.info(
                        f"Progress: {i+1}/{len(questions)} - "
                        f"Current accuracy: {correct/(i+1)*100:.1f}%"
                    )
            
            except Exception as e:
                logger.error(f"Error on question {i+1}: {e}")
                latencies.append(0)
        
        total_time = time.time() - start_time
        
        # Calculate category accuracies
        category_accuracy = {
            cat: (stats['correct'] / stats['total'] * 100)
            for cat, stats in category_stats.items()
        }
        
        result = GSM8KResult(
            benchmark_name="GSM8K",
            model_name=model_name,
            accuracy=correct / len(questions) * 100,
            num_questions=len(questions),
            num_correct=correct,
            avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
            total_time_sec=total_time,
            timestamp=datetime.now().isoformat(),
            details={
                "category_accuracy": category_accuracy,
                "category_stats": category_stats,
                "latencies_ms": latencies,
                "num_categories": len(category_stats)
            }
        )
        
        logger.info(
            f"GSM8K Complete: {result.accuracy:.2f}% accuracy "
            f"({result.num_correct}/{result.num_questions})"
        )
        
        return result
    
    def save_results(
        self,
        result: GSM8KResult,
        output_dir: str = "benchmark_results"
    ):
        """Save benchmark results to JSON file"""
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{output_dir}/gsm8k_{result.model_name}_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(asdict(result), f, indent=2)
        
        logger.info(f"Results saved to {filename}")
        return filename


async def main():
    """Example usage"""
    async def dummy_inference(prompt: str) -> str:
        await asyncio.sleep(0.1)
        return "The answer is 42"
    
    benchmark = GSM8KBenchmark(num_samples=20)
    result = await benchmark.run_benchmark(dummy_inference, "DummyModel")
    benchmark.save_results(result)
    
    print(f"\nGSM8K Accuracy: {result.accuracy:.2f}%")
    print(f"Category breakdown:")
    for cat, acc in result.details['category_accuracy'].items():
        print(f"  {cat}: {acc:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
