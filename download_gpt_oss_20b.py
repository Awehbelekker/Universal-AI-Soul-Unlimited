#!/usr/bin/env python3
"""
Download and optimize GPT-OSS-20B for testing
Creates optimized version for Android deployment
"""

import os
import sys
from pathlib import Path
from huggingface_hub import snapshot_download, hf_hub_download
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GPTOSS20BDownloader:
    """Download and optimize GPT-OSS-20B model"""
    
    def __init__(self, models_dir="models/gpt-oss-20b"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
    def check_disk_space(self):
        """Check if enough disk space (need ~50GB)"""
        import shutil
        stat = shutil.disk_usage(self.models_dir.parent)
        free_gb = stat.free / (1024**3)
        
        logger.info(f"💾 Available disk space: {free_gb:.1f} GB")
        
        if free_gb < 50:
            logger.warning(f"⚠️  Low disk space! Need 50GB, have {free_gb:.1f}GB")
            response = input("Continue anyway? (y/n): ")
            return response.lower() == 'y'
        
        return True
    
    def download_quantized_version(self):
        """Download pre-quantized GGUF version (much smaller)"""
        logger.info("\n" + "="*70)
        logger.info("📥 Downloading GPT-OSS-20B Quantized Version")
        logger.info("="*70)
        
        # Try to find quantized versions
        quantized_repos = [
            "TheBloke/gpt-oss-20b-GGUF",
            "TheBloke/gpt-oss-20b-GPTQ",
            "gpt-oss/20b-gguf",
        ]
        
        logger.info("\n🔍 Searching for quantized versions...")
        
        for repo in quantized_repos:
            try:
                logger.info(f"\nTrying: {repo}")
                
                # Try to download Q4_K_M quantized version (best balance)
                filename = "gpt-oss-20b.Q4_K_M.gguf"
                
                output_path = self.models_dir / filename
                
                if output_path.exists():
                    logger.info(f"✅ Already exists: {output_path}")
                    return str(output_path)
                
                logger.info(f"📥 Downloading {filename} (~5.2GB)...")
                logger.info("⏱️  This will take 10-30 minutes...")
                
                hf_hub_download(
                    repo_id=repo,
                    filename=filename,
                    local_dir=str(self.models_dir),
                    resume_download=True
                )
                
                logger.info(f"✅ Downloaded to: {output_path}")
                return str(output_path)
                
            except Exception as e:
                logger.warning(f"❌ Not found in {repo}: {e}")
                continue
        
        logger.error("\n❌ No pre-quantized versions found")
        logger.info("\n💡 Alternative: Download full model (40GB) and quantize locally")
        return None
    
    def download_full_model(self):
        """Download full GPT-OSS-20B model (40GB)"""
        logger.info("\n" + "="*70)
        logger.info("📥 Downloading Full GPT-OSS-20B Model (40GB)")
        logger.info("="*70)
        
        logger.info("\n⚠️  WARNING:")
        logger.info("   • Download size: ~40GB")
        logger.info("   • Time estimate: 1-3 hours")
        logger.info("   • Requires quantization afterward")
        
        response = input("\nProceed with full download? (y/n): ")
        
        if response.lower() != 'y':
            logger.info("❌ Download cancelled")
            return None
        
        try:
            logger.info("\n📥 Downloading from openai/gpt-oss-20b...")
            
            model_path = snapshot_download(
                repo_id="openai/gpt-oss-20b",
                local_dir=str(self.models_dir / "full"),
                local_dir_use_symlinks=False,
                resume_download=True,
                ignore_patterns=["*.md", "*.txt", ".gitattributes"]
            )
            
            logger.info(f"\n✅ Downloaded to: {model_path}")
            logger.info("\n⏭️  Next: Run quantization script to compress to 5GB")
            
            return model_path
            
        except Exception as e:
            logger.error(f"\n❌ Download failed: {e}")
            logger.info("\n💡 Possible reasons:")
            logger.info("   1. Model is gated - try: huggingface-cli login")
            logger.info("   2. Model doesn't exist at this repo")
            logger.info("   3. Network issues")
            return None
    
    def create_model_config(self, model_path):
        """Create configuration for model integration"""
        config = {
            "model_id": "gpt-oss-20b",
            "path": str(model_path),
            "type": "gguf",
            "size": "5.2GB",
            "quantization": "Q4_K_M",
            "context_length": 8192,
            "recommended_for": "desktop_testing",
            "mobile_ready": False,
            "features": [
                "chat",
                "code_generation",
                "reasoning",
                "multilingual"
            ]
        }
        
        config_path = self.models_dir / "model_config.json"
        
        import json
        with open(config_path, 'w') as f:
            json.dump(config, indent=2, fp=f)
        
        logger.info(f"\n✅ Created config: {config_path}")
        return config


def main():
    """Main entry point"""
    
    print("\n" + "="*70)
    print("🚀 GPT-OSS-20B Download & Optimization")
    print("="*70)
    
    downloader = GPTOSS20BDownloader()
    
    # Check disk space
    if not downloader.check_disk_space():
        print("\n❌ Insufficient disk space")
        return
    
    print("\n📋 Download Options:\n")
    print("1. Download Quantized (Q4_K_M) - ~5.2GB (RECOMMENDED)")
    print("   • Ready to use immediately")
    print("   • Good quality with 87% size reduction")
    print("   • Best for testing on desktop")
    print()
    print("2. Download Full Model - ~40GB")
    print("   • Requires quantization afterward")
    print("   • Full quality, but huge size")
    print("   • Not recommended for mobile")
    print()
    print("3. Skip - Use existing Qwen2.5-3B (RECOMMENDED FOR APK)")
    print("   • Already optimized for mobile")
    print("   • 1.8GB size, perfect for Android")
    print("   • Works on 95% of devices")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        model_path = downloader.download_quantized_version()
        
        if model_path:
            config = downloader.create_model_config(model_path)
            
            print("\n" + "="*70)
            print("✅ GPT-OSS-20B Ready!")
            print("="*70)
            print(f"\n📍 Location: {model_path}")
            print(f"💾 Size: {config['size']}")
            print(f"🎯 Type: {config['type'].upper()}")
            print()
            print("🧪 Test with:")
            print(f"   python test_gpt_oss_20b.py")
            print()
            print("⚠️  Note: This is for DESKTOP TESTING only")
            print("    For Android APK, use Qwen2.5-3B (already integrated)")
        else:
            print("\n❌ Could not download quantized version")
            print("💡 Try option 2 to download full model")
    
    elif choice == "2":
        model_path = downloader.download_full_model()
        
        if model_path:
            print("\n⏭️  Next step: Quantize the model")
            print("Run: python quantize_model.py")
    
    elif choice == "3":
        print("\n✅ Great choice! Qwen2.5-3B is perfect for your Android APK")
        print("\n📱 Your APK build is ready:")
        print("   cd \"Universal AI Soul Unlimited\"")
        print("   buildozer -v android debug")
    
    else:
        print("\n❌ Invalid choice")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Download cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
