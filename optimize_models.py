#!/usr/bin/env python3
"""
Universal Soul AI - Model Optimization Script
Quantize and optimize models for faster inference
"""

import os
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ModelOptimizer:
    """Optimize AI models for production deployment"""
    
    def __init__(self, models_dir: str = "models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(exist_ok=True)
        
    def download_optimized_models(self):
        """Download pre-quantized GGUF models (fastest option)"""
        logger.info("🚀 Downloading optimized GGUF models...")
        
        models = {
            'qwen2.5-3b': {
                'repo': 'Qwen/Qwen2.5-3B-Instruct-GGUF',
                'file': 'qwen2.5-3b-instruct-q4_k_m.gguf',
                'size': '1.8GB',
                'description': 'Qwen2.5-3B INT4 quantized (4x smaller, 5x faster)'
            },
            'qwen2.5-1.5b': {
                'repo': 'Qwen/Qwen2.5-1.5B-Instruct-GGUF',
                'file': 'qwen2.5-1.5b-instruct-q4_k_m.gguf',
                'size': '900MB',
                'description': 'Smaller Qwen variant for mobile'
            }
        }
        
        try:
            from huggingface_hub import hf_hub_download
            
            for model_name, info in models.items():
                logger.info(f"\n📦 {model_name}:")
                logger.info(f"   {info['description']}")
                logger.info(f"   Size: {info['size']}")
                
                output_path = self.models_dir / info['file']
                
                if output_path.exists():
                    logger.info(f"   ✅ Already downloaded: {output_path}")
                    continue
                
                logger.info(f"   ⬇️  Downloading from {info['repo']}...")
                
                hf_hub_download(
                    repo_id=info['repo'],
                    filename=info['file'],
                    local_dir=str(self.models_dir)
                )
                
                logger.info(f"   ✅ Downloaded: {output_path}")
                
        except ImportError:
            logger.error("❌ huggingface-hub not installed!")
            logger.info("Run: pip install huggingface-hub")
            sys.exit(1)
    
    def quantize_pytorch_model(self, model_path: str, output_path: str):
        """Quantize PyTorch model to INT8"""
        logger.info(f"🔧 Quantizing {model_path} to INT8...")
        
        try:
            import torch
            
            # Load model
            logger.info("   Loading model...")
            model = torch.load(model_path, map_location='cpu')
            
            # Dynamic quantization (fastest, good for inference)
            logger.info("   Applying INT8 quantization...")
            quantized_model = torch.quantization.quantize_dynamic(
                model,
                {torch.nn.Linear, torch.nn.LSTM, torch.nn.GRU},
                dtype=torch.qint8
            )
            
            # Save quantized model
            logger.info(f"   Saving to {output_path}...")
            torch.save(quantized_model, output_path)
            
            # Compare sizes
            original_size = os.path.getsize(model_path) / (1024**2)
            quantized_size = os.path.getsize(output_path) / (1024**2)
            reduction = (1 - quantized_size/original_size) * 100
            
            logger.info(f"   ✅ Success!")
            logger.info(f"   Original: {original_size:.1f} MB")
            logger.info(f"   Quantized: {quantized_size:.1f} MB")
            logger.info(f"   Reduction: {reduction:.1f}%")
            
        except ImportError:
            logger.error("❌ PyTorch not installed!")
            logger.info("Run: pip install torch")
            sys.exit(1)
    
    def convert_to_onnx(self, model_path: str, output_path: str):
        """Convert model to ONNX format for faster inference"""
        logger.info(f"🔧 Converting {model_path} to ONNX...")
        
        try:
            import torch
            import torch.onnx
            
            # Load model
            model = torch.load(model_path, map_location='cpu')
            model.eval()
            
            # Create dummy input
            dummy_input = torch.randn(1, 512)  # Adjust shape as needed
            
            # Export to ONNX
            torch.onnx.export(
                model,
                dummy_input,
                output_path,
                export_params=True,
                opset_version=13,
                do_constant_folding=True,
                input_names=['input'],
                output_names=['output'],
                dynamic_axes={
                    'input': {0: 'batch_size'},
                    'output': {0: 'batch_size'}
                }
            )
            
            logger.info(f"   ✅ ONNX model saved: {output_path}")
            logger.info("   Now 2-5x faster with onnxruntime!")
            
        except Exception as e:
            logger.error(f"❌ Error: {e}")
    
    def benchmark_model(self, model_path: str, model_type: str = "gguf"):
        """Benchmark model performance"""
        logger.info(f"📊 Benchmarking {model_path}...")
        
        import time
        
        if model_type == "gguf":
            try:
                from llama_cpp import Llama
                
                # Load model
                start = time.time()
                llm = Llama(
                    model_path=str(model_path),
                    n_ctx=2048,
                    n_threads=4
                )
                load_time = time.time() - start
                
                # Test inference
                test_prompt = "Hello, world!"
                start = time.time()
                response = llm(
                    test_prompt,
                    max_tokens=50,
                    temperature=0.7
                )
                inference_time = time.time() - start
                
                logger.info(f"   Load time: {load_time:.2f}s")
                logger.info(f"   Inference time: {inference_time:.2f}s")
                logger.info(f"   Tokens/sec: {50/inference_time:.1f}")
                
            except ImportError:
                logger.error("❌ llama-cpp-python not installed!")
                logger.info("Run: pip install llama-cpp-python")
    
    def optimize_all(self):
        """Run all optimization steps"""
        logger.info("=" * 60)
        logger.info("🚀 Universal Soul AI - Model Optimization")
        logger.info("=" * 60)
        
        # Step 1: Download optimized models
        self.download_optimized_models()
        
        # Step 2: Check what we have
        logger.info("\n📁 Models directory:")
        for file in self.models_dir.glob("*"):
            size_mb = file.stat().st_size / (1024**2)
            logger.info(f"   {file.name} ({size_mb:.1f} MB)")
        
        # Step 3: Benchmark
        logger.info("\n📊 Running benchmarks...")
        gguf_models = list(self.models_dir.glob("*.gguf"))
        if gguf_models:
            self.benchmark_model(gguf_models[0])
        
        logger.info("\n✅ Optimization complete!")
        logger.info("\n📝 Next steps:")
        logger.info("   1. Test models: python test_optimized_models.py")
        logger.info("   2. Update config to use optimized models")
        logger.info("   3. Build APK: buildozer android release")


def main():
    """Main entry point"""
    optimizer = ModelOptimizer()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "download":
            optimizer.download_optimized_models()
        elif command == "benchmark":
            if len(sys.argv) > 2:
                optimizer.benchmark_model(sys.argv[2])
            else:
                logger.error("Usage: python optimize_models.py benchmark <model_path>")
        elif command == "all":
            optimizer.optimize_all()
        else:
            logger.error(f"Unknown command: {command}")
            logger.info("Usage: python optimize_models.py [download|benchmark|all]")
    else:
        optimizer.optimize_all()


if __name__ == "__main__":
    main()
