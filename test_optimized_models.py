#!/usr/bin/env python3
"""
Test optimized models for performance and accuracy
"""

import time
import asyncio
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ModelTester:
    """Test model performance and quality"""
    
    def __init__(self, models_dir: str = "models"):
        self.models_dir = Path(models_dir)
    
    async def test_llama_cpp_model(self, model_path: Path):
        """Test GGUF model with llama-cpp-python"""
        logger.info(f"\n🧪 Testing {model_path.name}")
        
        try:
            from llama_cpp import Llama
            
            # Load model
            logger.info("   Loading model...")
            start_time = time.time()
            
            llm = Llama(
                model_path=str(model_path),
                n_ctx=2048,
                n_threads=4,
                n_gpu_layers=0,  # CPU only for testing
                verbose=False
            )
            
            load_time = time.time() - start_time
            logger.info(f"   ✅ Loaded in {load_time:.2f}s")
            
            # Test cases
            test_cases = [
                "What is artificial intelligence?",
                "Write a haiku about technology",
                "Explain quantum computing simply"
            ]
            
            total_tokens = 0
            total_time = 0
            
            for i, prompt in enumerate(test_cases, 1):
                logger.info(f"\n   Test {i}: {prompt[:50]}...")
                
                start_time = time.time()
                response = llm(
                    prompt,
                    max_tokens=100,
                    temperature=0.7,
                    stop=["\n\n"]
                )
                inference_time = time.time() - start_time
                
                total_time += inference_time
                tokens = len(response['choices'][0]['text'].split())
                total_tokens += tokens
                
                logger.info(f"   Response ({tokens} tokens, {inference_time:.2f}s):")
                logger.info(f"   {response['choices'][0]['text'][:200]}...")
            
            # Summary
            avg_time = total_time / len(test_cases)
            tokens_per_sec = total_tokens / total_time
            
            logger.info(f"\n   📊 Performance Summary:")
            logger.info(f"      Load time: {load_time:.2f}s")
            logger.info(f"      Avg inference: {avg_time:.2f}s")
            logger.info(f"      Speed: {tokens_per_sec:.1f} tokens/sec")
            
            return {
                'model': model_path.name,
                'load_time': load_time,
                'avg_inference': avg_time,
                'tokens_per_sec': tokens_per_sec
            }
            
        except ImportError:
            logger.error("❌ llama-cpp-python not installed!")
            logger.info("Run: pip install llama-cpp-python")
            return None
        except Exception as e:
            logger.error(f"❌ Error testing model: {e}")
            return None
    
    async def compare_models(self):
        """Compare all models in the directory"""
        logger.info("=" * 60)
        logger.info("🔬 Model Comparison Test")
        logger.info("=" * 60)
        
        # Find all GGUF models
        gguf_models = list(self.models_dir.glob("*.gguf"))
        
        if not gguf_models:
            logger.warning("⚠️  No GGUF models found in models/")
            logger.info("Run: python optimize_models.py download")
            return
        
        logger.info(f"\nFound {len(gguf_models)} models:")
        for model in gguf_models:
            size_mb = model.stat().st_size / (1024**2)
            logger.info(f"   - {model.name} ({size_mb:.1f} MB)")
        
        # Test each model
        results = []
        for model_path in gguf_models:
            result = await self.test_llama_cpp_model(model_path)
            if result:
                results.append(result)
        
        # Final comparison
        if results:
            logger.info("\n" + "=" * 60)
            logger.info("📊 COMPARISON RESULTS")
            logger.info("=" * 60)
            
            # Sort by speed
            results.sort(key=lambda x: x['tokens_per_sec'], reverse=True)
            
            for i, result in enumerate(results, 1):
                logger.info(f"\n{i}. {result['model']}")
                logger.info(f"   Load time: {result['load_time']:.2f}s")
                logger.info(f"   Avg inference: {result['avg_inference']:.2f}s")
                logger.info(f"   Speed: {result['tokens_per_sec']:.1f} tokens/sec")
            
            # Recommendation
            fastest = results[0]
            logger.info(f"\n🏆 Fastest model: {fastest['model']}")
            logger.info(f"   Recommended for production use!")
    
    async def memory_test(self, model_path: Path):
        """Test memory usage"""
        logger.info(f"\n💾 Memory Test: {model_path.name}")
        
        try:
            import psutil
            process = psutil.Process()
            
            # Before loading
            mem_before = process.memory_info().rss / (1024**2)
            logger.info(f"   Memory before: {mem_before:.1f} MB")
            
            # Load model
            from llama_cpp import Llama
            llm = Llama(model_path=str(model_path), n_ctx=2048, verbose=False)
            
            # After loading
            mem_after = process.memory_info().rss / (1024**2)
            mem_used = mem_after - mem_before
            
            logger.info(f"   Memory after: {mem_after:.1f} MB")
            logger.info(f"   Model memory: {mem_used:.1f} MB")
            
            # Run inference
            llm("Test", max_tokens=10)
            mem_inference = process.memory_info().rss / (1024**2)
            
            logger.info(f"   During inference: {mem_inference:.1f} MB")
            
            return {
                'model_memory': mem_used,
                'total_memory': mem_inference
            }
            
        except ImportError:
            logger.error("❌ psutil not installed!")
            logger.info("Run: pip install psutil")
            return None


async def main():
    """Main entry point"""
    tester = ModelTester()
    
    # Run comparison test
    await tester.compare_models()
    
    # Optional: Memory test
    gguf_models = list(Path("models").glob("*.gguf"))
    if gguf_models:
        await tester.memory_test(gguf_models[0])


if __name__ == "__main__":
    asyncio.run(main())
