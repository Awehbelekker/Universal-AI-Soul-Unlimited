"""
Model Manager for Universal Soul AI
Handles on-demand downloading and management of AI models
"""
import os
import json
import hashlib
import requests
from pathlib import Path
from typing import Optional, Callable, Dict
from dataclasses import dataclass


@dataclass
class ModelInfo:
    """Information about an AI model"""
    name: str
    url: str
    size_mb: float
    checksum: str
    description: str
    filename: str


class ModelManager:
    """Manages AI model downloads and verification"""
    
    # Available models for download
    MODELS = {
        "qwen2.5-3b": ModelInfo(
            name="Qwen2.5-3B",
            url="https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf",
            size_mb=1536.0,  # ~1.5GB
            checksum="",  # Add actual SHA256 checksum
            description="Advanced 3B parameter model for enhanced reasoning",
            filename="qwen2.5-3b-instruct-q4_k_m.gguf"
        ),
        "placeholder": ModelInfo(
            name="Placeholder 27M",
            url="",  # Built-in, no download needed
            size_mb=27.0,
            checksum="",
            description="Built-in lightweight model (included)",
            filename="placeholder_27m.bin"
        )
    }
    
    def __init__(self, models_dir: str = "models"):
        """Initialize model manager
        
        Args:
            models_dir: Directory to store downloaded models
        """
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.models_dir / "models_config.json"
        self.load_config()
    
    def load_config(self):
        """Load model configuration"""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {"installed_models": []}
    
    def save_config(self):
        """Save model configuration"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def is_model_installed(self, model_key: str) -> bool:
        """Check if a model is installed
        
        Args:
            model_key: Model identifier (e.g., "qwen2.5-3b")
            
        Returns:
            True if model is installed and verified
        """
        if model_key not in self.MODELS:
            return False
        
        model_info = self.MODELS[model_key]
        model_path = self.models_dir / model_info.filename
        
        # Check if file exists
        if not model_path.exists():
            return False
        
        # Verify file size
        file_size_mb = model_path.stat().st_size / (1024 * 1024)
        if abs(file_size_mb - model_info.size_mb) > 10:  # Allow 10MB tolerance
            return False
        
        return True
    
    def get_model_path(self, model_key: str) -> Optional[Path]:
        """Get path to installed model
        
        Args:
            model_key: Model identifier
            
        Returns:
            Path to model file if installed, None otherwise
        """
        if not self.is_model_installed(model_key):
            return None
        
        model_info = self.MODELS[model_key]
        return self.models_dir / model_info.filename
    
    def download_model(
        self, 
        model_key: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """Download a model from HuggingFace
        
        Args:
            model_key: Model identifier
            progress_callback: Optional callback(downloaded_bytes, total_bytes)
            
        Returns:
            True if download successful
        """
        if model_key not in self.MODELS:
            raise ValueError(f"Unknown model: {model_key}")
        
        model_info = self.MODELS[model_key]
        if not model_info.url:
            # Built-in model, no download needed
            return True
        
        model_path = self.models_dir / model_info.filename
        
        # Check if already downloaded
        if self.is_model_installed(model_key):
            return True
        
        try:
            # Download with progress tracking
            response = requests.get(model_info.url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(model_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback:
                            progress_callback(downloaded, total_size)
            
            # Verify download
            if self.is_model_installed(model_key):
                # Update config
                if model_key not in self.config["installed_models"]:
                    self.config["installed_models"].append(model_key)
                    self.save_config()
                return True
            else:
                # Download failed verification
                model_path.unlink(missing_ok=True)
                return False
                
        except Exception as e:
            print(f"Download failed: {e}")
            model_path.unlink(missing_ok=True)
            return False
    
    def get_available_storage_mb(self) -> float:
        """Get available storage space in MB
        
        Returns:
            Available space in megabytes
        """
        try:
            import shutil
            stat = shutil.disk_usage(self.models_dir)
            return stat.free / (1024 * 1024)
        except Exception:
            return 0.0
    
    def can_download_model(self, model_key: str) -> tuple[bool, str]:
        """Check if model can be downloaded
        
        Args:
            model_key: Model identifier
            
        Returns:
            (can_download, reason_if_not)
        """
        if model_key not in self.MODELS:
            return False, "Unknown model"
        
        model_info = self.MODELS[model_key]
        
        # Check if already installed
        if self.is_model_installed(model_key):
            return False, "Model already installed"
        
        # Check storage space (need 1.5x model size for safety)
        required_space = model_info.size_mb * 1.5
        available_space = self.get_available_storage_mb()
        
        if available_space < required_space:
            return False, f"Insufficient storage: need {required_space:.0f}MB, have {available_space:.0f}MB"
        
        return True, ""
    
    def delete_model(self, model_key: str) -> bool:
        """Delete an installed model
        
        Args:
            model_key: Model identifier
            
        Returns:
            True if deleted successfully
        """
        if model_key not in self.MODELS:
            return False
        
        model_info = self.MODELS[model_key]
        model_path = self.models_dir / model_info.filename
        
        try:
            model_path.unlink(missing_ok=True)
            
            # Update config
            if model_key in self.config["installed_models"]:
                self.config["installed_models"].remove(model_key)
                self.save_config()
            
            return True
        except Exception:
            return False
    
    def get_installed_models(self) -> list[str]:
        """Get list of installed models
        
        Returns:
            List of model keys
        """
        return [
            key for key in self.MODELS.keys()
            if self.is_model_installed(key)
        ]
    
    def get_model_info(self, model_key: str) -> Optional[ModelInfo]:
        """Get information about a model
        
        Args:
            model_key: Model identifier
            
        Returns:
            ModelInfo if model exists, None otherwise
        """
        return self.MODELS.get(model_key)
