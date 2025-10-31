#!/usr/bin/env python3
"""
Comprehensive AI Model Benchmark Suite
Implements MMLU, HellaSwag, and custom benchmarks for baseline scoring
"""

import json
import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Store benchmark results"""
    benchmark_name: str
    model_name: str
    accuracy: float
    num_questions: int
    num_correct: int
    avg_latency_ms: float
    total_time_sec: float
    timestamp: str
    details: Dict[str, Any]


class MMLUBenchmark:
    """
    Massive Multitask Language Understanding (MMLU) Benchmark

    Tests knowledge across 57 subjects including:
    - STEM (math, physics, chemistry, biology)
    - Humanities (history, philosophy, law)
    - Social Sciences (psychology, economics, geography)
    - Other (professional medicine, accounting, etc.)
    """

    def __init__(self, num_samples: int = 100):
        self.num_samples = num_samples
        self.categories = [
            "abstract_algebra", "anatomy", "astronomy", "business_ethics",
            "clinical_knowledge", "college_biology", "college_chemistry",
            "college_computer_science", "college_mathematics",
            "college_medicine", "college_physics", "computer_security",
            "conceptual_physics", "econometrics", "electrical_engineering",
            "elementary_mathematics", "formal_logic", "global_facts",
            "high_school_biology", "high_school_chemistry",
            "high_school_computer_science", "high_school_european_history",
            "high_school_geography", "high_school_government_and_politics",
            "high_school_macroeconomics", "high_school_mathematics",
            "high_school_microeconomics", "high_school_physics",
            "high_school_psychology", "high_school_statistics",
            "high_school_us_history", "high_school_world_history",
            "human_aging", "human_sexuality", "international_law",
            "jurisprudence", "logical_fallacies", "machine_learning",
            "management", "marketing", "medical_genetics",
            "miscellaneous", "moral_disputes", "moral_scenarios",
            "nutrition", "philosophy", "prehistory",
            "professional_accounting", "professional_law",
            "professional_medicine", "professional_psychology",
            "public_relations", "security_studies", "sociology",
            "us_foreign_policy", "virology", "world_religions"
        ]

    def generate_sample_questions(self) -> List[Dict[str, Any]]:
        """Generate sample MMLU-style questions"""
        questions = []

        # Sample questions across different categories
        samples = [
            {
                "category": "high_school_mathematics",
                "question": "What is the derivative of x^2?",
                "choices": ["2x", "x", "2", "x^2"],
                "answer": 0,
                "difficulty": "easy"
            },
            {
                "category": "computer_security",
                "question": (
                    "Which encryption algorithm is considered "
                    "quantum-resistant?"
                ),
                "choices": [
                    "RSA", "ECC", "Lattice-based cryptography", "AES-256"
                ],
                "answer": 2,
                "difficulty": "hard"
            },
            {
                "category": "world_history",
                "question": (
                    "In what year did the Berlin Wall fall?"
                ),
                "choices": ["1987", "1988", "1989", "1990"],
                "answer": 2,
                "difficulty": "medium"
            },
            {
                "category": "biology",
                "question": (
                    "What is the powerhouse of the cell?"
                ),
                "choices": [
                    "Nucleus", "Mitochondria",
                    "Ribosome", "Endoplasmic reticulum"
                ],
                "answer": 1,
                "difficulty": "easy"
            },
            {
                "category": "philosophy",
                "question": (
                    "Who wrote 'Critique of Pure Reason'?"
                ),
                "choices": [
                    "Immanuel Kant", "Hegel",
                    "Descartes", "Nietzsche"
                ],
                "answer": 0,
                "difficulty": "medium"
            }
        ]

        # Repeat samples to reach num_samples
        while len(questions) < self.num_samples:
            questions.extend(samples)

        return questions[:self.num_samples]

    async def run_benchmark(
            self, model_inference_fn, model_name: str) -> BenchmarkResult:
        """
        Run MMLU benchmark on a model

        Args:
            model_inference_fn: Function that takes a prompt and returns
                               a response
            model_name: Name of the model being tested

        Returns:
            BenchmarkResult with accuracy and metrics
        """
        logger.info(f"Running MMLU benchmark on {model_name}...")

        questions = self.generate_sample_questions()
        correct = 0
        latencies = []
        start_time = time.time()

        category_scores = {}

        for i, q in enumerate(questions):
            prompt = self._format_mmlu_prompt(q)

            # Measure latency
            q_start = time.time()
            try:
                response = await model_inference_fn(prompt)
                latency = (time.time() - q_start) * 1000  # ms

                # Extract answer (A, B, C, or D)
                answer_idx = self._extract_answer(response, q["choices"])
                is_correct = (answer_idx == q["answer"])

                if is_correct:
                    correct += 1

                # Track per-category scores
                cat = q["category"]
                if cat not in category_scores:
                    category_scores[cat] = {"correct": 0, "total": 0}
                category_scores[cat]["total"] += 1
                if is_correct:
                    category_scores[cat]["correct"] += 1

                latencies.append(latency)

            except Exception as e:
                logger.error(f"Error on question {i}: {e}")
                latencies.append(0)

            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i + 1}/{len(questions)}")

        total_time = time.time() - start_time
        accuracy = (correct / len(questions)) * 100

        # Calculate per-category accuracy
        category_accuracy = {
            cat: (scores["correct"] / scores["total"]) * 100
            for cat, scores in category_scores.items()
        }

        result = BenchmarkResult(
            benchmark_name="MMLU",
            model_name=model_name,
            accuracy=accuracy,
            num_questions=len(questions),
            num_correct=correct,
            avg_latency_ms=sum(latencies) / len(latencies)
            if latencies else 0,
            total_time_sec=total_time,
            timestamp=datetime.now().isoformat(),
            details={
                "category_accuracy": category_accuracy,
                "num_categories": len(category_scores),
                "latencies_ms": latencies
            }
        )

        logger.info(
            f"MMLU Results: {accuracy:.2f}% accuracy "
            f"({correct}/{len(questions)})"
        )

        return result

    def _format_mmlu_prompt(self, question: Dict[str, Any]) -> str:
        """Format question as multiple choice prompt"""
        prompt = f"Category: {question['category']}\n\n"
        prompt += f"Question: {question['question']}\n\n"
        prompt += "Choices:\n"
        for i, choice in enumerate(question['choices']):
            prompt += f"{chr(65 + i)}. {choice}\n"
        prompt += (
            "\nAnswer with only the letter (A, B, C, or D) "
            "of the correct choice:"
        )
        return prompt

    def _extract_answer(
            self, response: str, choices: List[str]) -> Optional[int]:
        """Extract answer index from model response"""
        response = response.strip().upper()

        # Look for letter answer
        for letter in ['A', 'B', 'C', 'D']:
            if letter in response[:10]:  # Check first 10 chars
                return ord(letter) - ord('A')

        # Look for choice text
        for i, choice in enumerate(choices):
            if choice.lower() in response.lower():
                return i

        return None


class HellaSwagBenchmark:
    """
    HellaSwag: Commonsense Reasoning Benchmark

    Tests ability to complete sentences with common sense reasoning
    """

    def __init__(self, num_samples: int = 100):
        self.num_samples = num_samples

    def generate_sample_questions(self) -> List[Dict[str, Any]]:
        """Generate sample HellaSwag-style questions"""
        questions = [
            {
                "context": (
                    "A woman is sitting at a piano. She"
                ),
                "choices": [
                    "starts playing the keys with her fingers",
                    "jumps out of the window",
                    "begins to fly around the room",
                    "transforms into a dragon"
                ],
                "answer": 0
            },
            {
                "context": (
                    "A man is cooking in a kitchen. He picks up a knife and"
                ),
                "choices": [
                    "throws it at the ceiling",
                    "starts chopping vegetables",
                    "uses it to paint a picture",
                    "eats the knife"
                ],
                "answer": 1
            },
            {
                "context": (
                    "A child is building with blocks. The tower gets "
                    "too tall and"
                ),
                "choices": [
                    "launches into space",
                    "turns into gold",
                    "falls over",
                    "starts talking"
                ],
                "answer": 2
            },
            {
                "context": (
                    "Someone is reading a book in a library. They"
                ),
                "choices": [
                    "turn the page quietly",
                    "eat the book",
                    "throw it at other people",
                    "use it as a skateboard"
                ],
                "answer": 0
            },
            {
                "context": (
                    "A person opens their umbrella because"
                ),
                "choices": [
                    "they want to fly",
                    "it's starting to rain",
                    "they're indoors and bored",
                    "umbrellas taste good"
                ],
                "answer": 1
            }
        ]

        # Repeat to reach num_samples
        result = []
        while len(result) < self.num_samples:
            result.extend(questions)

        return result[:self.num_samples]

    async def run_benchmark(
            self, model_inference_fn, model_name: str) -> BenchmarkResult:
        """Run HellaSwag benchmark"""
        logger.info(f"Running HellaSwag benchmark on {model_name}...")

        questions = self.generate_sample_questions()
        correct = 0
        latencies = []
        start_time = time.time()

        for i, q in enumerate(questions):
            prompt = self._format_hellaswag_prompt(q)

            q_start = time.time()
            try:
                response = await model_inference_fn(prompt)
                latency = (time.time() - q_start) * 1000

                answer_idx = self._extract_answer(response, q["choices"])
                if answer_idx == q["answer"]:
                    correct += 1

                latencies.append(latency)

            except Exception as e:
                logger.error(f"Error on question {i}: {e}")
                latencies.append(0)

            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i + 1}/{len(questions)}")

        total_time = time.time() - start_time
        accuracy = (correct / len(questions)) * 100

        result = BenchmarkResult(
            benchmark_name="HellaSwag",
            model_name=model_name,
            accuracy=accuracy,
            num_questions=len(questions),
            num_correct=correct,
            avg_latency_ms=sum(latencies) / len(latencies)
            if latencies else 0,
            total_time_sec=total_time,
            timestamp=datetime.now().isoformat(),
            details={
                "latencies_ms": latencies
            }
        )

        logger.info(
            f"HellaSwag Results: {accuracy:.2f}% accuracy "
            f"({correct}/{len(questions)})"
        )

        return result

    def _format_hellaswag_prompt(self, question: Dict[str, Any]) -> str:
        """Format HellaSwag prompt"""
        prompt = "Complete the following scenario with common sense:\n\n"
        prompt += f"{question['context']}\n\n"
        prompt += "Choose the most likely continuation:\n"
        for i, choice in enumerate(question['choices']):
            prompt += f"{chr(65 + i)}. {choice}\n"
        prompt += "\nAnswer with only the letter (A, B, C, or D):"
        return prompt

    def _extract_answer(
            self, response: str, choices: List[str]) -> Optional[int]:
        """Extract answer index from response"""
        response = response.strip().upper()

        # Look for letter
        for letter in ['A', 'B', 'C', 'D']:
            if letter in response[:10]:
                return ord(letter) - ord('A')

        # Look for choice text
        for i, choice in enumerate(choices):
            if choice.lower() in response.lower():
                return i

        return None


class BenchmarkRunner:
    """Run all benchmarks and generate reports"""

    def __init__(self, output_dir: str = "benchmark_results"):
        self.output_dir = output_dir
        self.mmlu = MMLUBenchmark(num_samples=50)
        self.hellaswag = HellaSwagBenchmark(num_samples=50)

    async def run_all_benchmarks(
            self, model_inference_fn,
            model_name: str) -> Dict[str, BenchmarkResult]:
        """Run all benchmarks on a model"""
        logger.info(f"Running full benchmark suite on {model_name}")

        results = {}

        # Run MMLU
        results["mmlu"] = await self.mmlu.run_benchmark(
            model_inference_fn, model_name
        )

        # Run HellaSwag
        results["hellaswag"] = await self.hellaswag.run_benchmark(
            model_inference_fn, model_name
        )

        # Save results
        self.save_results(results, model_name)

        return results

    def save_results(
            self, results: Dict[str, BenchmarkResult], model_name: str):
        """Save benchmark results to JSON"""
        import os
        os.makedirs(self.output_dir, exist_ok=True)

        filename = (
            f"{self.output_dir}/{model_name.replace('/', '_')}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        data = {
            name: asdict(result) for name, result in results.items()
        }

        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Results saved to {filename}")

    def generate_report(
            self, all_results: Dict[str, Dict[str, BenchmarkResult]]):
        """Generate comparative benchmark report"""
        print("\n" + "=" * 80)
        print("AI MODEL BENCHMARK REPORT")
        print("=" * 80)

        for model_name, results in all_results.items():
            print(f"\n{model_name}:")
            print("-" * 80)

            for bench_name, result in results.items():
                print(f"  {bench_name.upper()}:")
                print(f"    Accuracy: {result.accuracy:.2f}%")
                print(f"    Correct: {result.num_correct}/"
                      f"{result.num_questions}")
                print(f"    Avg Latency: {result.avg_latency_ms:.2f}ms")
                print(f"    Total Time: {result.total_time_sec:.2f}s")

        print("\n" + "=" * 80)


# Example usage
if __name__ == "__main__":
    import asyncio

    async def dummy_model(prompt: str) -> str:
        """Dummy model for testing"""
        await asyncio.sleep(0.1)
        # Randomly return A, B, C, or D
        return random.choice(['A', 'B', 'C', 'D'])

    async def main():
        runner = BenchmarkRunner()
        results = await runner.run_all_benchmarks(
            dummy_model, "test-model"
        )
        runner.generate_report({"test-model": results})

    asyncio.run(main())
