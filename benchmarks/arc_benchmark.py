"""
ARC (AI2 Reasoning Challenge) Benchmark Implementation

Tests scientific reasoning and world knowledge through multiple-choice
questions requiring complex inference.
Includes both ARC-Easy and ARC-Challenge variants.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Any, Callable, Awaitable

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ARCResult:
    """Results from ARC benchmark"""
    benchmark_name: str
    model_name: str
    variant: str  # "easy" or "challenge"
    accuracy: float
    num_questions: int
    num_correct: int
    avg_latency_ms: float
    total_time_sec: float
    timestamp: str
    details: Dict[str, Any]


class ARCBenchmark:
    """
    ARC (AI2 Reasoning Challenge) Benchmark
    
    Tests scientific reasoning with questions from 3rd-12th grade science
    exams. Requires inference beyond simple fact retrieval.
    """
    
    def __init__(self, num_samples: int = 50, variant: str = "easy"):
        """
        Initialize ARC benchmark
        
        Args:
            num_samples: Number of questions to test
            variant: "easy" or "challenge" difficulty
        """
        self.num_samples = num_samples
        self.variant = variant.lower()
        if self.variant not in ["easy", "challenge"]:
            raise ValueError("variant must be 'easy' or 'challenge'")
    
    def generate_sample_questions(self) -> List[Dict]:
        """Generate sample ARC questions"""
        
        # ARC-Easy questions
        easy_questions = [
            {
                "id": "arc_e_001",
                "question": "Which property of water allows it to dissolve many substances?",
                "choices": {
                    "A": "Water has a neutral pH",
                    "B": "Water is a polar molecule",
                    "C": "Water has a high boiling point",
                    "D": "Water exists in three states"
                },
                "correct": "B",
                "category": "chemistry"
            },
            {
                "id": "arc_e_002",
                "question": "What happens to the molecules in a substance when it changes from a liquid to a gas?",
                "choices": {
                    "A": "They move faster and spread apart",
                    "B": "They move slower and come together",
                    "C": "They stop moving completely",
                    "D": "They change into different molecules"
                },
                "correct": "A",
                "category": "physics"
            },
            {
                "id": "arc_e_003",
                "question": "Which of these is an example of a physical change?",
                "choices": {
                    "A": "Paper burning to ash",
                    "B": "Iron rusting in water",
                    "C": "Ice melting into water",
                    "D": "Food being digested"
                },
                "correct": "C",
                "category": "chemistry"
            },
            {
                "id": "arc_e_004",
                "question": "What is the primary source of energy for producers in most ecosystems?",
                "choices": {
                    "A": "Water",
                    "B": "Soil nutrients",
                    "C": "Sunlight",
                    "D": "Carbon dioxide"
                },
                "correct": "C",
                "category": "biology"
            },
            {
                "id": "arc_e_005",
                "question": "Which part of a plant cell is responsible for photosynthesis?",
                "choices": {
                    "A": "Nucleus",
                    "B": "Mitochondria",
                    "C": "Chloroplast",
                    "D": "Cell membrane"
                },
                "correct": "C",
                "category": "biology"
            },
            {
                "id": "arc_e_006",
                "question": "What causes the seasons on Earth?",
                "choices": {
                    "A": "Earth's distance from the Sun",
                    "B": "Earth's tilted axis",
                    "C": "The Moon's gravitational pull",
                    "D": "Solar flares"
                },
                "correct": "B",
                "category": "earth_science"
            },
            {
                "id": "arc_e_007",
                "question": "Which force pulls objects toward the center of Earth?",
                "choices": {
                    "A": "Friction",
                    "B": "Magnetism",
                    "C": "Gravity",
                    "D": "Electricity"
                },
                "correct": "C",
                "category": "physics"
            },
            {
                "id": "arc_e_008",
                "question": "What is the main function of red blood cells?",
                "choices": {
                    "A": "Fight infections",
                    "B": "Carry oxygen",
                    "C": "Digest food",
                    "D": "Produce hormones"
                },
                "correct": "B",
                "category": "biology"
            },
            {
                "id": "arc_e_009",
                "question": "Which type of rock is formed by cooling lava?",
                "choices": {
                    "A": "Sedimentary",
                    "B": "Metamorphic",
                    "C": "Igneous",
                    "D": "Mineral"
                },
                "correct": "C",
                "category": "earth_science"
            },
            {
                "id": "arc_e_010",
                "question": "What is the smallest unit of life?",
                "choices": {
                    "A": "Atom",
                    "B": "Molecule",
                    "C": "Cell",
                    "D": "Tissue"
                },
                "correct": "C",
                "category": "biology"
            }
        ]
        
        # ARC-Challenge questions (more difficult)
        challenge_questions = [
            {
                "id": "arc_c_001",
                "question": "A student measures the acceleration of a cart moving down a ramp. The same cart is then moved down a steeper ramp. What will happen to the cart's acceleration?",
                "choices": {
                    "A": "It will increase due to greater gravitational component",
                    "B": "It will decrease due to increased friction",
                    "C": "It will remain constant regardless of ramp angle",
                    "D": "It will become zero at the steeper angle"
                },
                "correct": "A",
                "category": "physics"
            },
            {
                "id": "arc_c_002",
                "question": "In a food web, energy is transferred from producers to consumers. Why is only about 10% of energy passed to the next trophic level?",
                "choices": {
                    "A": "Most energy is stored in bones",
                    "B": "Most energy is lost as heat through metabolism",
                    "C": "Producers absorb most of the energy back",
                    "D": "Energy is destroyed during digestion"
                },
                "correct": "B",
                "category": "biology"
            },
            {
                "id": "arc_c_003",
                "question": "Why does water have a higher boiling point than other molecules of similar size?",
                "choices": {
                    "A": "Water molecules are heavier than similar-sized molecules",
                    "B": "Hydrogen bonding requires extra energy to break",
                    "C": "Water contains oxygen which is very stable",
                    "D": "Water molecules move faster than other molecules"
                },
                "correct": "B",
                "category": "chemistry"
            },
            {
                "id": "arc_c_004",
                "question": "A population of beetles includes both green and brown individuals. After a forest fire, the ratio changes significantly toward brown beetles. What evolutionary process best explains this?",
                "choices": {
                    "A": "Genetic drift through random chance",
                    "B": "Natural selection favoring camouflage",
                    "C": "Mutation creating new brown beetles",
                    "D": "Migration of brown beetles to the area"
                },
                "correct": "B",
                "category": "biology"
            },
            {
                "id": "arc_c_005",
                "question": "In a chemical reaction, the products have less mass than the reactants. What is the most likely explanation?",
                "choices": {
                    "A": "Mass was converted to energy (nuclear reaction)",
                    "B": "A gas was produced and escaped the system",
                    "C": "The measurement was incorrect",
                    "D": "Mass is not conserved in chemical reactions"
                },
                "correct": "B",
                "category": "chemistry"
            },
            {
                "id": "arc_c_006",
                "question": "Why do scientists use multiple trials in experiments?",
                "choices": {
                    "A": "To make the experiment take longer",
                    "B": "To reduce the impact of random errors",
                    "C": "To use more materials",
                    "D": "To make the data more complicated"
                },
                "correct": "B",
                "category": "scientific_method"
            },
            {
                "id": "arc_c_007",
                "question": "Continental drift is supported by evidence that similar fossils are found on different continents. What does this suggest?",
                "choices": {
                    "A": "The continents were once connected",
                    "B": "Animals could swim between continents",
                    "C": "The fossils formed at different times",
                    "D": "Evolution occurred independently"
                },
                "correct": "A",
                "category": "earth_science"
            },
            {
                "id": "arc_c_008",
                "question": "A circuit has three light bulbs in series. If one bulb burns out, what happens to the other bulbs?",
                "choices": {
                    "A": "They shine brighter",
                    "B": "They remain unchanged",
                    "C": "They also go out",
                    "D": "They shine dimmer"
                },
                "correct": "C",
                "category": "physics"
            },
            {
                "id": "arc_c_009",
                "question": "What is the primary reason that vaccines provide immunity against diseases?",
                "choices": {
                    "A": "They kill all bacteria in the body",
                    "B": "They stimulate the immune system to produce memory cells",
                    "C": "They provide antibodies that last forever",
                    "D": "They change the DNA to resist disease"
                },
                "correct": "B",
                "category": "biology"
            },
            {
                "id": "arc_c_010",
                "question": "Why is carbon dioxide considered a greenhouse gas?",
                "choices": {
                    "A": "It is produced by greenhouses",
                    "B": "It absorbs and re-emits infrared radiation",
                    "C": "It is green in color",
                    "D": "It is used by plants for photosynthesis"
                },
                "correct": "B",
                "category": "earth_science"
            }
        ]
        
        # Select questions based on variant
        question_pool = (challenge_questions if self.variant == "challenge" 
                        else easy_questions)
        
        # Extend pool by repeating if needed
        while len(question_pool) < self.num_samples:
            question_pool.extend(
                challenge_questions if self.variant == "challenge"
                else easy_questions
            )
        
        return question_pool[:self.num_samples]
    
    async def run_benchmark(
        self,
        model_inference_fn: Callable[[str], Awaitable[str]],
        model_name: str
    ) -> ARCResult:
        """
        Run ARC benchmark on a model
        
        Args:
            model_inference_fn: Async function that takes prompt, returns answer
            model_name: Name of the model being tested
            
        Returns:
            ARCResult with detailed metrics
        """
        logger.info(f"Starting ARC-{self.variant.upper()} benchmark for {model_name}")
        
        questions = self.generate_sample_questions()
        correct = 0
        latencies = []
        category_stats = {}
        
        start_time = time.time()
        
        for i, q in enumerate(questions):
            # Create prompt
            prompt = f"""Question: {q['question']}

Choices:
{q['choices']['A']}
{q['choices']['B']}
{q['choices']['C']}
{q['choices']['D']}

Answer with only the letter (A, B, C, or D):"""
            
            # Time the inference
            t0 = time.time()
            try:
                response = await model_inference_fn(prompt)
                latency = (time.time() - t0) * 1000
                latencies.append(latency)
                
                # Extract answer (first letter A-D)
                answer = None
                for char in response.upper():
                    if char in ['A', 'B', 'C', 'D']:
                        answer = char
                        break
                
                if answer == q['correct']:
                    correct += 1
                
                # Track category performance
                category = q.get('category', 'unknown')
                if category not in category_stats:
                    category_stats[category] = {'correct': 0, 'total': 0}
                category_stats[category]['total'] += 1
                if answer == q['correct']:
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
        
        result = ARCResult(
            benchmark_name=f"ARC-{self.variant.upper()}",
            model_name=model_name,
            variant=self.variant,
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
            f"ARC-{self.variant.upper()} Complete: "
            f"{result.accuracy:.2f}% accuracy "
            f"({result.num_correct}/{result.num_questions})"
        )
        
        return result
    
    def save_results(self, result: ARCResult, output_dir: str = "benchmark_results"):
        """Save benchmark results to JSON file"""
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{output_dir}/arc_{self.variant}_{result.model_name}_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(asdict(result), f, indent=2)
        
        logger.info(f"Results saved to {filename}")
        return filename


async def main():
    """Example usage"""
    # Create a dummy inference function for testing
    async def dummy_inference(prompt: str) -> str:
        await asyncio.sleep(0.1)  # Simulate latency
        return "B"  # Always answer B
    
    # Run ARC-Easy
    easy_benchmark = ARCBenchmark(num_samples=10, variant="easy")
    easy_result = await easy_benchmark.run_benchmark(
        dummy_inference, 
        "DummyModel"
    )
    easy_benchmark.save_results(easy_result)
    
    # Run ARC-Challenge
    challenge_benchmark = ARCBenchmark(num_samples=10, variant="challenge")
    challenge_result = await challenge_benchmark.run_benchmark(
        dummy_inference,
        "DummyModel"
    )
    challenge_benchmark.save_results(challenge_result)
    
    print(f"\nARC-Easy: {easy_result.accuracy:.2f}% accuracy")
    print(f"ARC-Challenge: {challenge_result.accuracy:.2f}% accuracy")


if __name__ == "__main__":
    asyncio.run(main())
