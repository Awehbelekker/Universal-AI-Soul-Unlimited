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

## 🚀 Quick Start

### Install Dependencies

```bash
pip install llama-cpp-python requests
```

### Run Benchmarks

```bash
# Run on all available models
python benchmarks/run_baseline_benchmarks.py

# Run on specific model (coming soon)
python benchmarks/run_baseline_benchmarks.py --model <model_name>
```

## 📁 Project Structure

```
benchmarks/
├── ai_benchmark_suite.py         # Core benchmark implementations
├── run_baseline_benchmarks.py    # Orchestrator for running all benchmarks
└── benchmark_results/            # JSON results for each run
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
