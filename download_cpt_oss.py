#!/usr/bin/env python3
"""
Download CPT-OSS 20B Models
Optimized GGUF quantized models for fast inference
"""

import os
import sys
from pathlib import Path
from huggingface_hub import hf_hub_download, list_repo_files
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def check_available_models():
    """Check what CPT-OSS models are available"""
    
    logger.info("\n" + "="*70)
    logger.info("🔍 Searching for CPT-OSS 20B Models on HuggingFace")
    logger.info("="*70)
    
    # Common repositories that might have CPT-OSS or similar models
    repos_to_check = [
        "TheBloke/CPT-OSS-20B-GGUF",
        "opencsg/cpt-oss-20b",
        "OpenCSG/cpt-oss-20b-v0.3-gguf",
        "TheBloke/Mixtral-8x7B-Instruct-v0.1-GGUF",  # Alternative
        "TheBloke/Mistral-7B-Instruct-v0.2-GGUF",  # Alternative
    ]
    
    available_repos = []
    
    for repo in repos_to_check:
        try:
            logger.info(f"\n📦 Checking {repo}...")
            files = list_repo_files(repo)
            gguf_files = [f for f in files if f.endswith('.gguf')]
            
            if gguf_files:
                logger.info(f"   ✅ Found {len(gguf_files)} GGUF files")
                available_repos.append({
                    'repo': repo,
                    'files': gguf_files
                })
                
                # Show first 5 files
                for i, f in enumerate(gguf_files[:5], 1):
                    size = "Unknown"
                    logger.info(f"   {i}. {f}")
                
                if len(gguf_files) > 5:
                    logger.info(f"   ... and {len(gguf_files) - 5} more")
            else:
                logger.info(f"   ⚠️  No GGUF files found")
                
        except Exception as e:
            logger.info(f"   ❌ Not accessible: {str(e)[:50]}")
    
    return available_repos


def download_model(repo_id: str, filename: str, output_dir: str = "models"):
    """
    Download a specific model file
    
    Args:
        repo_id: HuggingFace repository ID
        filename: Model filename to download
        output_dir: Local directory to save model
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    logger.info("\n" + "="*70)
    logger.info(f"⬇️  Downloading Model")
    logger.info("="*70)
    logger.info(f"Repository: {repo_id}")
    logger.info(f"File: {filename}")
    logger.info(f"Destination: {output_path / filename}")
    logger.info("")
    
    try:
        local_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=str(output_path),
            local_dir_use_symlinks=False
        )
        
        # Get file size
        size_bytes = Path(local_path).stat().st_size
        size_gb = size_bytes / (1024**3)
        
        logger.info("\n" + "="*70)
        logger.info("✅ Download Complete!")
        logger.info("="*70)
        logger.info(f"Location: {local_path}")
        logger.info(f"Size: {size_gb:.2f} GB")
        logger.info("")
        
        return local_path
        
    except Exception as e:
        logger.error(f"\n❌ Download failed: {e}")
        return None


def recommend_models():
    """Recommend best models for different use cases"""
    
    logger.info("\n" + "="*70)
    logger.info("💡 Model Recommendations")
    logger.info("="*70)
    
    recommendations = [
        {
            'use_case': 'Mobile/Android (Best for your APK)',
            'model': 'Qwen2.5-3B-Instruct Q4_K_M',
            'repo': 'Qwen/Qwen2.5-3B-Instruct-GGUF',
            'file': 'qwen2.5-3b-instruct-q4_k_m.gguf',
            'size': '~1.8GB',
            'speed': '5-10x faster than full precision',
            'quality': 'Excellent for mobile'
        },
        {
            'use_case': 'Desktop (Balanced)',
            'model': 'Mixtral-8x7B Q4_K_M',
            'repo': 'TheBloke/Mixtral-8x7B-Instruct-v0.1-GGUF',
            'file': 'mixtral-8x7b-instruct-v0.1.Q4_K_M.gguf',
            'size': '~26GB',
            'speed': 'Fast with good quality',
            'quality': 'Very high'
        },
        {
            'use_case': 'Laptop/Small Desktop',
            'model': 'Mistral-7B Q4_K_M',
            'repo': 'TheBloke/Mistral-7B-Instruct-v0.2-GGUF',
            'file': 'mistral-7b-instruct-v0.2.Q4_K_M.gguf',
            'size': '~4.1GB',
            'speed': 'Very fast',
            'quality': 'High'
        }
    ]
    
    for i, rec in enumerate(recommendations, 1):
        logger.info(f"\n{i}. {rec['use_case']}")
        logger.info(f"   Model: {rec['model']}")
        logger.info(f"   Repository: {rec['repo']}")
        logger.info(f"   File: {rec['file']}")
        logger.info(f"   Size: {rec['size']}")
        logger.info(f"   Speed: {rec['speed']}")
        logger.info(f"   Quality: {rec['quality']}")
    
    return recommendations


def main():
    """Main entry point"""
    
    logger.info("\n" + "="*70)
    logger.info("🤗 HuggingFace Model Downloader")
    logger.info("   Universal Soul AI - Optimized Models")
    logger.info("="*70)
    
    # Check for available models
    available = check_available_models()
    
    # Show recommendations
    recommendations = recommend_models()
    
    # Interactive download
    logger.info("\n" + "="*70)
    logger.info("📥 Quick Download Options")
    logger.info("="*70)
    
    logger.info("\nRecommended for Android APK:")
    logger.info("  Model: Qwen2.5-3B-Instruct (Q4_K_M)")
    logger.info("  Size: ~1.8GB")
    logger.info("  Best balance of speed/quality for mobile")
    
    logger.info("\nTo download, run:")
    logger.info('  python download_cpt_oss.py --download qwen')
    
    logger.info("\nOr download manually:")
    logger.info('  python download_cpt_oss.py --repo "Qwen/Qwen2.5-3B-Instruct-GGUF" --file "qwen2.5-3b-instruct-q4_k_m.gguf"')
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if '--download' in sys.argv:
            idx = sys.argv.index('--download')
            if idx + 1 < len(sys.argv):
                choice = sys.argv[idx + 1].lower()
                
                if choice == 'qwen':
                    logger.info("\n🚀 Downloading Qwen2.5-3B-Instruct Q4_K_M...")
                    download_model(
                        repo_id="Qwen/Qwen2.5-3B-Instruct-GGUF",
                        filename="qwen2.5-3b-instruct-q4_k_m.gguf"
                    )
                elif choice == 'mistral':
                    logger.info("\n🚀 Downloading Mistral-7B Q4_K_M...")
                    download_model(
                        repo_id="TheBloke/Mistral-7B-Instruct-v0.2-GGUF",
                        filename="mistral-7b-instruct-v0.2.Q4_K_M.gguf"
                    )
                elif choice == 'mixtral':
                    logger.info("\n🚀 Downloading Mixtral-8x7B Q4_K_M...")
                    download_model(
                        repo_id="TheBloke/Mixtral-8x7B-Instruct-v0.1-GGUF",
                        filename="mixtral-8x7b-instruct-v0.1.Q4_K_M.gguf"
                    )
        
        elif '--repo' in sys.argv and '--file' in sys.argv:
            repo_idx = sys.argv.index('--repo')
            file_idx = sys.argv.index('--file')
            
            if repo_idx + 1 < len(sys.argv) and file_idx + 1 < len(sys.argv):
                repo = sys.argv[repo_idx + 1]
                filename = sys.argv[file_idx + 1]
                download_model(repo, filename)
    
    logger.info("\n" + "="*70)
    logger.info("✨ Ready to optimize your AI!")
    logger.info("="*70 + "\n")


if __name__ == "__main__":
    main()
