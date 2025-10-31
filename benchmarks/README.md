# AI Model Benchmark Suite

Comprehensive benchmarking system for evaluating AI models using industry-standard benchmarks.

## 📊 Benchmarks Implemented

### 1. MMLU (Massive Multitask Language Understanding)
- **Purpose**: Evaluate knowledge across 57 academic subjects
- **Categories**: STEM, Humanities, Social Sciences, Professional domains
- **Format**: Multiple choice questions (A/B/C/D)
- **Metrics**: Accuracy, per-category scores, latency

### 2. HellaSwag (Commonsense Reasoning)
- **Purpose**: Test common sense and scenario completion ability
- **Format**: Complete realistic scenarios with most likely continuation
- **Metrics**: Accuracy, reasoning quality, latency

### 3. ARC (AI2 Reasoning Challenge) ✨ NEW
- **Purpose**: Test scientific reasoning and world knowledge
- **Variants**: ARC-Easy and ARC-Challenge
- **Categories**: Physics, Chemistry, Biology, Earth Science
- **Format**: Grade 3-12 science exam questions
- **Metrics**: Accuracy per variant, category breakdown

### 4. TruthfulQA ✨ NEW
- **Purpose**: Evaluate truthfulness and detect misconceptions
- **Categories**: Health, Science, Law, Misconceptions
- **Format**: Questions designed to elicit common false beliefs
- **Metrics**: Accuracy, misconception rate

### 5. GSM8K (Grade School Math) ✨ NEW
- **Purpose**: Mathematical reasoning through word problems
- **Categories**: Arithmetic, Ratios, Geometry, Multi-step problems
- **Format**: Grade school level math word problems
- **Metrics**: Accuracy, category performance, numeric extraction quality

## 🚀 Quick Start

### Install Dependencies

```bash
pip install requests asyncio aiohttp
# For local models (optional)
pip install llama-cpp-python
```

### Run All Benchmarks on Qwen Models

```bash
# Comprehensive test on all Qwen models (3B, 7B, 14B)
python benchmarks/run_comprehensive_benchmarks.py

# Quick test on Qwen 3B with new benchmarks
python benchmarks/run_qwen_new_benchmarks.py

# Legacy MMLU + HellaSwag on Qwen
python benchmarks/run_qwen_benchmarks.py
```

### Run Individual Benchmarks

```python
import asyncio
from arc_benchmark import ARCBenchmark
from truthfulqa_benchmark import TruthfulQABenchmark
from gsm8k_benchmark import GSM8KBenchmark

async def your_inference_fn(prompt: str) -> str:
    # Your model inference logic
    return "A"

# Run ARC-Challenge
benchmark = ARCBenchmark(num_samples=50, variant="challenge")
result = await benchmark.run_benchmark(your_inference_fn, "YourModel")
print(f"Accuracy: {result.accuracy}%")
```

### Check GPU Optimization

```bash
# View GPU status and optimization recommendations
python benchmarks/gpu_optimization.py
```

## 📁 Project Structure

```
benchmarks/
├── ai_benchmark_suite.py              # MMLU + HellaSwag implementation
├── arc_benchmark.py                   # ARC (Easy + Challenge) ✨ NEW
├── truthfulqa_benchmark.py            # TruthfulQA ✨ NEW
├── gsm8k_benchmark.py                 # Grade School Math ✨ NEW
├── gpu_optimization.py                # GPU/memory optimization ✨ NEW
├── run_comprehensive_benchmarks.py    # All benchmarks, all models ✨ NEW
├── run_qwen_new_benchmarks.py         # New benchmarks on Qwen 3B ✨ NEW
├── run_qwen_benchmarks.py             # MMLU + HellaSwag on Qwen
├── run_baseline_benchmarks.py         # Original baseline runner
├── test_new_benchmarks.py             # Unit tests for new benchmarks
├── README.md                          # This file
├── QWEN_RESULTS.md                    # Detailed Qwen 3B analysis
├── FINE_TUNING_GUIDE.md              # Fine-tuning strategies ✨ NEW
└── benchmark_results/                 # JSON results directory
```

## 📈 Baseline Results

### Current Baseline (Using Dummy Model)

| Model | MMLU | HellaSwag | Avg Latency |
|-------|------|-----------|-------------|
| hrm_27m.bin | 28.00% | 18.00% | 61.66ms |

**Note**: These are baseline results using a random-answer model for testing. Real model performance will vary significantly.

### Expected Performance Ranges

| Model Size | Expected MMLU | Expected HellaSwag |
|------------|---------------|-------------------|
| Small (< 1B params) | 25-40% | 30-45% |
| Medium (1-7B params) | 40-60% | 45-65% |
| Large (7-13B params) | 55-75% | 60-80% |
| Very Large (13B+ params) | 70-90% | 75-90% |

## 🔧 Supported Model Types

### Local Models
- **GGUF** files (llama.cpp format)
- **Safetensors** (Hugging Face format)
- **Bin files** (PyTorch checkpoints)

### API Models
- **OpenAI** (GPT-3.5, GPT-4)
- **Anthropic** (Claude family)
- **Ollama** (Local server)

## 📝 Result Format

Benchmarks generate JSON files with the following structure:

```json
{
  "benchmark_name": "MMLU",
  "model_name": "model-name",
  "accuracy": 85.5,
  "num_questions": 100,
  "num_correct": 86,
  "avg_latency_ms": 150.5,
  "total_time_sec": 15.05,
  "timestamp": "2025-10-31T14:44:16",
  "details": {
    "category_accuracy": {
      "mathematics": 90.0,
      "physics": 85.0,
      ...
    },
    "latencies_ms": [145.2, 155.8, ...]
  }
}
```

## 🎯 Key Metrics

### Accuracy
- **Primary metric**: Percentage of correct answers
- **MMLU**: 57 subjects, weighted equally
- **HellaSwag**: Overall scenario completion accuracy

### Latency
- **Avg Latency**: Mean response time per question (milliseconds)
- **Total Time**: Complete benchmark duration (seconds)
- **Distribution**: Per-question latency for analysis

### Category Performance
- **MMLU**: Breakdown by subject area
- **Useful for**: Identifying model strengths/weaknesses

## 🔬 Benchmark Details

### MMLU Categories

**STEM**:
- Mathematics (algebra, calculus, statistics)
- Physics (conceptual, mechanics, quantum)
- Chemistry (organic, inorganic)
- Computer Science (security, algorithms)
- Biology (molecular, ecology)

**Humanities**:
- Philosophy
- History (US, European, World)
- Law
- Moral scenarios

**Social Sciences**:
- Psychology
- Economics (macro, micro)
- Geography
- Sociology

**Professional**:
- Medicine
- Accounting
- Marketing
- Management

### HellaSwag Scenarios

Tests ability to complete everyday scenarios:
- Physical actions
- Social interactions
- Causal reasoning
- Common sense physics

## 📊 Customization

### Adjust Sample Size

```python
# In run_baseline_benchmarks.py
runner = BenchmarkRunner(output_dir="benchmark_results")
runner.mmlu.num_samples = 200  # Default: 50
runner.hellaswag.num_samples = 200  # Default: 50
```

### Add Custom Benchmarks

```python
class CustomBenchmark:
    async def run_benchmark(self, model_fn, model_name):
        # Your benchmark logic
        return BenchmarkResult(...)

# Add to BenchmarkRunner
runner.custom = CustomBenchmark()
```

## 🐛 Troubleshooting

### No Models Found
- Check `models/` directory exists
- Verify model file extensions (.gguf, .bin, .safetensors)
- Use dummy model for testing: system automatically falls back

### Low Accuracy
- Verify model is loading correctly
- Check inference function returns proper format
- Adjust temperature (lower = more deterministic)

### High Latency
- Enable GPU acceleration (n_gpu_layers parameter)
- Reduce context window (n_ctx parameter)
- Use smaller models for faster inference

## 📚 References

- **MMLU Paper**: [Measuring Massive Multitask Language Understanding](https://arxiv.org/abs/2009.03300)
- **HellaSwag Paper**: [HellaSwag: Can a Machine Really Finish Your Sentence?](https://arxiv.org/abs/1905.07830)

## 🤝 Contributing

To add new benchmarks:

1. Implement benchmark class with `run_benchmark()` method
2. Return `BenchmarkResult` with standardized metrics
3. Add to `BenchmarkRunner` orchestrator
4. Update this README with benchmark details

## 📄 License

Part of the Universal AI Soul Unlimited project.

---

**Last Updated**: October 31, 2025
**Benchmark Version**: 1.0.0
