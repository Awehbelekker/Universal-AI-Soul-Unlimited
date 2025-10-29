"""
Hybrid Model Manager - Ship with small model, download large models on-demand
Qwen2.5-3B (1.8GB) ships with APK, GPT-OSS-20B (5.2GB) downloads in-app
"""

import asyncio
import logging
from typing import Dict, List, Optional
from pathlib import Path
from enum import Enum
import json

logger = logging.getLogger(__name__)


class ModelTier(Enum):
    """Model tiers for different use cases"""
    LITE = "lite"  # Ships with APK (Qwen2.5-3B)
    PRO = "pro"  # Optional download (GPT-OSS-20B)
    ULTRA = "ultra"  # Cloud-only (GPT-4/Claude)


class ModelDownloadStatus(Enum):
    """Download status"""
    NOT_DOWNLOADED = "not_downloaded"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    FAILED = "failed"


class HybridModelManager:
    """
    Manage multiple model tiers with smart downloading

    Features:
    - Ship with Qwen2.5-3B (1.8GB) for offline use
    - Download GPT-OSS-20B (5.2GB) on WiFi
    - Cloud fallback for premium features
    - Automatic tier selection based on device
    """

    def __init__(self, models_dir: str = "models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # Model catalog
        self.models = {
            "qwen2.5-3b": {
                "tier": ModelTier.LITE,
                "size_mb": 1800,
                "ships_with_apk": True,
                "status": ModelDownloadStatus.DOWNLOADED,
                "path": self.models_dir / "qwen2.5-3b",
                "features": [
                    "chat",
                    "reasoning",
                    "code",
                    "multilingual"
                ],
                "device_requirements": {
                    "min_ram_mb": 2048,
                    "min_storage_mb": 2000,
                    "supported_archs": ["arm64-v8a", "armeabi-v7a"]
                }
            },
            "gpt-oss-20b": {
                "tier": ModelTier.PRO,
                "size_mb": 5200,
                "ships_with_apk": False,
                "status": ModelDownloadStatus.NOT_DOWNLOADED,
                "path": self.models_dir / "gpt-oss-20b",
                "download_url": "huggingface.co/TheBloke/gpt-oss-20b-GGUF",
                "features": [
                    "advanced_chat",
                    "complex_reasoning",
                    "expert_code",
                    "research"
                ],
                "device_requirements": {
                    "min_ram_mb": 6144,
                    "min_storage_mb": 6000,
                    "supported_archs": ["arm64-v8a"],
                    "recommended_only": True
                }
            }
        }

        # Download progress tracking
        self.download_progress = {}

        logger.info("HybridModelManager initialized")
        logger.info("Default model: qwen2.5-3b (LITE tier)")

    def get_recommended_model(self, device_info: Dict) -> str:
        """
        Recommend model based on device capabilities

        Args:
            device_info: {
                'ram_mb': int,
                'storage_mb': int,
                'arch': str,
                'on_wifi': bool
            }

        Returns:
            Recommended model ID
        """
        ram_mb = device_info.get('ram_mb', 0)
        storage_mb = device_info.get('storage_mb', 0)
        on_wifi = device_info.get('on_wifi', False)

        # Check if device can handle PRO tier
        if ram_mb >= 6144 and storage_mb >= 6000:
            # Check if already downloaded
            gpt_oss = self.models['gpt-oss-20b']
            if gpt_oss['status'] == ModelDownloadStatus.DOWNLOADED:
                logger.info(
                    "📱 Recommending: gpt-oss-20b "
                    "(PRO - already downloaded)"
                )
                return 'gpt-oss-20b'

            # Suggest download if on WiFi
            if on_wifi:
                logger.info(
                    "📱 Recommending: gpt-oss-20b "
                    "(PRO - download available)"
                )
                return 'gpt-oss-20b'

        # Default to LITE tier
        logger.info("📱 Recommending: qwen2.5-3b (LITE - works on all devices)")
        return 'qwen2.5-3b'

    async def download_model(
        self,
        model_id: str,
        progress_callback=None
    ) -> bool:
        """
        Download model in background

        Args:
            model_id: Model to download
            progress_callback: Function(percent: int, status: str)

        Returns:
            Success status
        """
        if model_id not in self.models:
            raise ValueError(f"Unknown model: {model_id}")

        model = self.models[model_id]

        # Check if already downloaded
        if model['status'] == ModelDownloadStatus.DOWNLOADED:
            logger.info(f"✅ {model_id} already downloaded")
            return True

        # Check if already downloading
        if model['status'] == ModelDownloadStatus.DOWNLOADING:
            logger.info(f"⏳ {model_id} already downloading...")
            return False

        try:
            logger.info(f"📥 Starting download: {model_id}")
            logger.info(f"   Size: {model['size_mb']}MB")
            logger.info(f"   Tier: {model['tier'].value}")

            model['status'] = ModelDownloadStatus.DOWNLOADING

            # Simulate download with progress
            total_mb = model['size_mb']

            for mb_downloaded in range(0, total_mb, 100):
                # Simulate download chunk
                await asyncio.sleep(0.1)

                percent = int((mb_downloaded / total_mb) * 100)
                status = f"Downloading {model_id}: {mb_downloaded}/{total_mb}MB"

                if progress_callback:
                    progress_callback(percent, status)

                # Store progress
                self.download_progress[model_id] = {
                    'percent': percent,
                    'mb_downloaded': mb_downloaded,
                    'total_mb': total_mb
                }

            # Mark as complete
            model['status'] = ModelDownloadStatus.DOWNLOADED

            if progress_callback:
                progress_callback(100, f"{model_id} downloaded successfully!")

            logger.info(f"✅ Download complete: {model_id}")

            # Save status to disk
            self._save_model_status()

            return True

        except Exception as e:
            logger.error(f"❌ Download failed: {e}")
            model['status'] = ModelDownloadStatus.FAILED
            return False

    def check_download_requirements(self, model_id: str) -> Dict:
        """
        Check if device meets requirements for model download

        Returns:
            {
                'can_download': bool,
                'warnings': List[str],
                'requirements': Dict
            }
        """
        if model_id not in self.models:
            return {
                'can_download': False,
                'warnings': [f"Unknown model: {model_id}"],
                'requirements': {}
            }

        model = self.models[model_id]
        warnings = []

        # Check storage
        import shutil
        stat = shutil.disk_usage(self.models_dir)
        free_mb = stat.free / (1024**2)

        required_mb = model['size_mb'] * 1.5  # Need 50% extra for temp files

        if free_mb < required_mb:
            warnings.append(
                f"Insufficient storage: need {required_mb:.0f}MB, "
                f"have {free_mb:.0f}MB"
            )

        # Check RAM (basic heuristic)
        req_ram = model['device_requirements']['min_ram_mb']
        warnings.append(f"Requires {req_ram}MB RAM")

        # Check if on WiFi (recommended)
        warnings.append(
            "Download on WiFi recommended (large file)"
        )

        return {
            'can_download': len(
                [w for w in warnings if 'Insufficient' in w]
            ) == 0,
            'warnings': warnings,
            'requirements': model['device_requirements']
        }

    def get_available_models(self) -> List[Dict]:
        """Get list of all available models with status"""
        return [
            {
                'id': model_id,
                'tier': model['tier'].value,
                'size_mb': model['size_mb'],
                'status': model['status'].value,
                'ships_with_apk': model['ships_with_apk'],
                'features': model['features']
            }
            for model_id, model in self.models.items()
        ]

    def delete_model(self, model_id: str) -> bool:
        """Delete downloaded model to free space"""
        if model_id not in self.models:
            return False

        model = self.models[model_id]

        # Can't delete shipped model
        if model['ships_with_apk']:
            logger.warning(f"Cannot delete shipped model: {model_id}")
            return False

        # Delete model files
        model_path = model['path']
        if model_path.exists():
            import shutil
            shutil.rmtree(model_path)
            logger.info(f"🗑️  Deleted: {model_id}")

        # Update status
        model['status'] = ModelDownloadStatus.NOT_DOWNLOADED
        self._save_model_status()

        return True

    def _save_model_status(self):
        """Save model download status to disk"""
        status_file = self.models_dir / "model_status.json"

        status = {
            model_id: {
                'status': model['status'].value,
                'downloaded': model['status'] == ModelDownloadStatus.DOWNLOADED
            }
            for model_id, model in self.models.items()
        }

        with open(status_file, 'w') as f:
            json.dump(status, f, indent=2)

        logger.info(f"💾 Saved status: {status_file}")

    def _load_model_status(self):
        """Load model download status from disk"""
        status_file = self.models_dir / "model_status.json"

        if not status_file.exists():
            return

        try:
            with open(status_file, 'r') as f:
                status = json.load(f)

            for model_id, model_status in status.items():
                if model_id in self.models:
                    status_value = model_status.get(
                        'status', 'not_downloaded'
                    )
                    self.models[model_id]['status'] = (
                        ModelDownloadStatus(status_value)
                    )

            logger.info("📂 Loaded model status from disk")

        except Exception as e:
            logger.error(f"Failed to load status: {e}")

    async def infer(
        self,
        prompt: str,
        model_id: Optional[str] = None,
        device_info: Optional[Dict] = None
    ) -> Dict:
        """
        Run inference with automatic model selection

        Args:
            prompt: Input text
            model_id: Specific model (or auto-select)
            device_info: Device capabilities

        Returns:
            Inference result
        """
        # Auto-select model if not specified
        if model_id is None:
            if device_info:
                model_id = self.get_recommended_model(device_info)
            else:
                model_id = 'qwen2.5-3b'  # Default to LITE

        # Check if model is available
        model = self.models[model_id]

        if model['status'] != ModelDownloadStatus.DOWNLOADED:
            return {
                'error': f"Model {model_id} not downloaded",
                'suggestion': 'Use qwen2.5-3b or download gpt-oss-20b',
                'can_download': (
                    model['status'] == ModelDownloadStatus.NOT_DOWNLOADED
                )
            }

        # Run inference (placeholder - integrate with actual model)
        logger.info(f"🤖 Running inference on {model_id}")

        return {
            'model': model_id,
            'tier': model['tier'].value,
            'response': f"[{model_id}] Response to: {prompt[:50]}...",
            'success': True
        }


# Example UI integration
async def demo_hybrid_app():
    """Demo of hybrid app with model management"""

    print("\n" + "="*70)
    print("📱 Universal Soul AI - Hybrid Model Demo")
    print("="*70)

    manager = HybridModelManager()

    # Simulate device info
    device_info = {
        'ram_mb': 8192,  # 8GB RAM
        'storage_mb': 20000,  # 20GB free
        'arch': 'arm64-v8a',
        'on_wifi': True
    }

    # Show available models
    print("\n📦 Available Models:")
    print("-" * 70)

    for model in manager.get_available_models():
        status_icon = "✅" if model['status'] == 'downloaded' else "📥"
        tier_icon = "🌟" if model['tier'] == 'pro' else "⚡"

        print(f"\n{status_icon} {tier_icon} {model['id'].upper()}")
        print(f"   Tier: {model['tier']}")
        print(f"   Size: {model['size_mb']}MB")
        print(f"   Status: {model['status']}")
        print(f"   Ships with APK: {model['ships_with_apk']}")

    # Get recommendation
    print("\n" + "="*70)
    print("🎯 Model Recommendation")
    print("="*70)

    recommended = manager.get_recommended_model(device_info)
    print("\nBased on your device:")
    print(f"  RAM: {device_info['ram_mb']}MB")
    print(f"  Storage: {device_info['storage_mb']}MB")
    print(f"  WiFi: {device_info['on_wifi']}")
    print(f"\n→ Recommended: {recommended}")

    # Demo download
    print("\n" + "="*70)
    print("📥 Download GPT-OSS-20B Demo")
    print("="*70)

    # Check requirements
    check = manager.check_download_requirements('gpt-oss-20b')

    print(f"\nCan download: {check['can_download']}")
    if check['warnings']:
        print("\n⚠️  Warnings:")
        for warning in check['warnings']:
            print(f"   • {warning}")

    # Simulate download with progress
    def progress_callback(percent, status):
        print(f"\r{status} [{percent}%]", end='', flush=True)

    print("\n\nStarting download...")
    success = await manager.download_model('gpt-oss-20b', progress_callback)
    print(f"\n\n{'✅ Success!' if success else '❌ Failed'}")

    # Demo inference
    print("\n" + "="*70)
    print("🤖 Inference Demo")
    print("="*70)

    prompts = [
        "Explain quantum computing",
        "Write a Python function for sorting"
    ]

    for prompt in prompts:
        print(f"\n📝 Prompt: {prompt}")

        # Try both models
        for model_id in ['qwen2.5-3b', 'gpt-oss-20b']:
            result = await manager.infer(prompt, model_id=model_id)

            if 'error' in result:
                print(f"   ❌ {model_id}: {result['error']}")
            else:
                print(f"   ✅ {model_id}: {result['response'][:60]}...")

    print("\n" + "="*70)
    print("✨ Demo Complete!")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(demo_hybrid_app())
