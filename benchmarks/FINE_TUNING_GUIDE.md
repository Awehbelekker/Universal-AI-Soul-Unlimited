# Fine-Tuning Guide for Qwen Models

## Overview

This guide provides strategies for improving Qwen model performance on factual knowledge domains where benchmarks showed weaknesses (history, biology, computer security).

## Current Performance Analysis

Based on benchmark results, Qwen2.5-3B shows:

**Strengths:**
- ✅ Mathematical reasoning: 100% on high school mathematics
- ✅ Abstract thinking: 100% on philosophy
- ✅ Multi-step reasoning: Strong GSM8K performance

**Weaknesses:**
- ❌ Factual knowledge: 0% on history, biology, security
- ❌ Domain-specific terminology
- ❌ Memorization of facts

## Fine-Tuning Strategies

### 1. Domain-Specific Fine-Tuning

#### Data Collection
```python
# Example: Creating a biology training dataset
biology_qa_pairs = [
    {
        "instruction": "What is photosynthesis?",
        "input": "",
        "output": "Photosynthesis is the process by which plants..."
    },
    {
        "instruction": "Explain the function of mitochondria",
        "input": "",
        "output": "Mitochondria are the powerhouses of cells..."
    }
]
```

#### Dataset Requirements
- **Size**: 1,000-10,000 examples per domain
- **Format**: Instruction-following format (Alpaca, ShareGPT)
- **Quality**: Verified factual accuracy
- **Coverage**: Comprehensive domain coverage

#### Recommended Datasets

**Biology:**
- SciQ (13,679 science questions)
- Biology QA datasets from Hugging Face
- Medical QA datasets (filtered for biology)

**History:**
- HistoryQA datasets
- Timeline-based QA pairs
- Historical events encyclopedia

**Computer Security:**
- CTF writeups converted to QA
- Security certifications practice questions
- CVE descriptions and explanations

### 2. Retrieval-Augmented Generation (RAG)

Instead of fine-tuning, use RAG for factual queries:

```python
from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.llms import Ollama

# Setup vector store
embeddings = HuggingFaceEmbeddings()
vectorstore = Chroma.from_documents(
    documents=biology_docs,
    embedding=embeddings
)

# RAG pipeline
def rag_query(question: str) -> str:
    # Retrieve relevant context
    docs = vectorstore.similarity_search(question, k=3)
    context = "\n".join([doc.page_content for doc in docs])
    
    # Generate answer with context
    prompt = f"""Context: {context}
    
Question: {question}

Answer based on the context above:"""
    
    llm = Ollama(model="qwen2.5:3b")
    return llm(prompt)
```

**Advantages:**
- No retraining required
- Always up-to-date information
- Traceable sources
- Lower computational cost

**Implementation Steps:**
1. Build domain-specific knowledge bases
2. Create embeddings for retrieval
3. Integrate with existing benchmarks
4. Measure accuracy improvement

### 3. Parameter-Efficient Fine-Tuning (PEFT)

Use LoRA (Low-Rank Adaptation) for efficient fine-tuning:

```python
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM

# Load base model
model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-3B")

# Configure LoRA
lora_config = LoraConfig(
    r=16,  # Rank
    lora_alpha=32,
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM"
)

# Apply LoRA
model = get_peft_model(model, lora_config)

# Only ~1% of parameters are trainable
trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
print(f"Trainable parameters: {trainable_params:,}")
```

**Benefits:**
- Memory efficient (fits on consumer GPUs)
- Fast training
- Easy to switch between adaptors
- Preserves base model capabilities

### 4. Multi-Task Learning

Train on multiple domains simultaneously:

```python
# Training dataset mixing
training_mix = {
    "biology": 0.3,      # 30% biology questions
    "history": 0.3,      # 30% history questions
    "security": 0.2,     # 20% security questions
    "math": 0.1,         # 10% math (maintain strength)
    "reasoning": 0.1     # 10% reasoning (maintain strength)
}
```

**Best Practices:**
- Maintain some math/reasoning examples to prevent catastrophic forgetting
- Use curriculum learning (easy → hard examples)
- Monitor all benchmarks during training

### 5. Continuous Learning Pipeline

```yaml
# CI/CD integration for continuous improvement
continuous_learning:
  triggers:
    - New training data available
    - Benchmark accuracy drops
    - Weekly scheduled run
  
  process:
    1. Collect new domain-specific data
    2. Fine-tune LoRA adaptor
    3. Run full benchmark suite
    4. Compare with baseline
    5. Deploy if improvement > 5%
    6. Archive previous version
```

## Training Configuration

### Recommended Hyperparameters

```python
training_args = {
    "learning_rate": 2e-4,
    "num_train_epochs": 3,
    "per_device_train_batch_size": 4,
    "gradient_accumulation_steps": 8,
    "warmup_steps": 100,
    "logging_steps": 10,
    "save_steps": 500,
    "eval_steps": 500,
    "fp16": True,  # Mixed precision
    "optim": "adamw_torch",
    "max_grad_norm": 1.0,
}
```

### GPU Requirements

| Model Size | Fine-Tuning Method | Min VRAM | Recommended VRAM |
|------------|-------------------|----------|------------------|
| 3B | Full Fine-Tuning | 12GB | 24GB |
| 3B | LoRA | 6GB | 12GB |
| 7B | Full Fine-Tuning | 24GB | 40GB |
| 7B | LoRA | 12GB | 24GB |
| 14B | Full Fine-Tuning | 40GB | 80GB |
| 14B | LoRA | 20GB | 40GB |

## Evaluation Protocol

### Before Fine-Tuning
1. Run full benchmark suite (baseline)
2. Identify specific weakness categories
3. Collect representative failure cases

### During Fine-Tuning
1. Monitor training loss
2. Run validation benchmarks every 500 steps
3. Check for catastrophic forgetting on math/reasoning

### After Fine-Tuning
1. Re-run full benchmark suite
2. Compare category-by-category
3. Test on held-out examples
4. Verify no regression on strengths

## Quick Start Example

```bash
# 1. Prepare dataset
python prepare_domain_dataset.py --domain biology --size 5000

# 2. Fine-tune with LoRA
python fine_tune_lora.py \
  --model Qwen/Qwen2.5-3B \
  --dataset biology_qa.json \
  --epochs 3 \
  --output biology_lora

# 3. Benchmark fine-tuned model
python benchmarks/run_comprehensive_benchmarks.py \
  --model biology_lora \
  --num_samples 50

# 4. Compare results
python compare_benchmarks.py \
  --baseline baseline_results.json \
  --finetuned biology_results.json
```

## Alternative Approach: Model Ensembling

Use specialized models for different domains:

```python
class EnsembleModel:
    def __init__(self):
        self.base_model = "qwen2.5:3b"
        self.biology_lora = "biology_adaptor"
        self.history_lora = "history_adaptor"
        self.security_lora = "security_adaptor"
    
    def classify_domain(self, question: str) -> str:
        """Classify question domain"""
        # Use keywords or small classifier
        if any(word in question.lower() for word in 
               ['cell', 'DNA', 'organism', 'photosynthesis']):
            return 'biology'
        # ... similar for other domains
        return 'general'
    
    async def answer(self, question: str) -> str:
        domain = self.classify_domain(question)
        
        if domain == 'biology':
            model = f"{self.base_model}+{self.biology_lora}"
        elif domain == 'history':
            model = f"{self.base_model}+{self.history_lora}"
        # ... etc
        
        return await inference(model, question)
```

## Expected Improvements

Based on similar fine-tuning experiments:

| Domain | Baseline | After LoRA FT | After RAG | Combined |
|--------|----------|---------------|-----------|----------|
| Biology | 0% | 40-60% | 70-80% | 80-90% |
| History | 0% | 35-55% | 65-75% | 75-85% |
| Security | 0% | 45-65% | 75-85% | 85-95% |
| Math | 100% | 95-100% | 100% | 100% |
| Overall | 40% | 60-70% | 75-85% | 85-90% |

## Resources

### Datasets
- **Hugging Face**: https://huggingface.co/datasets
- **OpenAssistant**: Instruction-following dataset
- **Databricks Dolly**: 15k instruction pairs
- **FLAN Collection**: Multi-task datasets

### Tools
- **Unsloth**: 2x faster fine-tuning
- **axolotl**: Easy YAML-based fine-tuning
- **LLaMA-Factory**: GUI for fine-tuning
- **AutoTrain**: Automated fine-tuning

### Papers
- LoRA: https://arxiv.org/abs/2106.09685
- QLoRA: https://arxiv.org/abs/2305.14314
- RAG: https://arxiv.org/abs/2005.11401

## Monitoring & Maintenance

```python
# Automated monitoring script
def monitor_model_performance():
    # Run benchmarks weekly
    schedule.every().sunday.at("00:00").do(run_benchmarks)
    
    # Check for accuracy drops
    if current_accuracy < baseline * 0.95:
        alert_team("Model accuracy dropped!")
        trigger_retraining()
    
    # Update knowledge base monthly
    schedule.every().month.do(update_knowledge_base)
```

## Conclusion

**Recommended Approach:**
1. **Short-term**: Implement RAG for factual domains (fastest)
2. **Medium-term**: Fine-tune with LoRA on domain datasets
3. **Long-term**: Build continuous learning pipeline

**Priority Order:**
1. RAG implementation (immediate 70-80% improvement)
2. Biology fine-tuning (highest impact)
3. History fine-tuning
4. Security fine-tuning
5. Ensemble system for production

For questions or issues, refer to the benchmark results and adjust strategies accordingly.
