#!/usr/bin/env python
"""
Build script for Universal Soul AI Android APK
Automates the buildozer build process
"""
import subprocess
import sys
import os
from pathlib import Path


def check_buildozer_installed():
    """Check if buildozer is installed"""
    try:
        result = subprocess.run(['buildozer', '--version'], 
                               capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Buildozer is installed: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    
    print("✗ Buildozer is not installed")
    print("\nInstall with: pip install buildozer")
    print("Also install dependencies:")
    print("  - Java JDK (openjdk-11 or newer)")
    print("  - Android SDK")
    print("  - Android NDK")
    return False


def check_dependencies():
    """Check if all build dependencies are met"""
    print("Checking build dependencies...")
    
    # Check Python version
    py_version = sys.version_info
    if py_version.major >= 3 and py_version.minor >= 8:
        print(f"✓ Python {py_version.major}.{py_version.minor}.{py_version.micro}")
    else:
        print(f"✗ Python {py_version.major}.{py_version.minor} (need 3.8+)")
        return False
    
    # Check buildozer
    if not check_buildozer_installed():
        return False
    
    # Check buildozer.spec exists
    if Path('buildozer.spec').exists():
        print("✓ buildozer.spec found")
    else:
        print("✗ buildozer.spec not found")
        return False
    
    return True


def clean_build():
    """Clean previous build artifacts"""
    print("\nCleaning previous builds...")
    subprocess.run(['buildozer', 'android', 'clean'], check=False)
    print("✓ Build cleaned")


def build_debug():
    """Build debug APK"""
    print("\n" + "="*60)
    print("Building DEBUG APK...")
    print("="*60)
    
    result = subprocess.run(['buildozer', 'android', 'debug'], check=False)
    
    if result.returncode == 0:
        print("\n" + "="*60)
        print("✓ DEBUG APK BUILD SUCCESSFUL!")
        print("="*60)
        print("\nAPK location: bin/universalsoulai-*.apk")
        return True
    else:
        print("\n" + "="*60)
        print("✗ DEBUG APK BUILD FAILED")
        print("="*60)
        return False


def build_release():
    """Build release APK"""
    print("\n" + "="*60)
    print("Building RELEASE APK...")
    print("="*60)
    print("\nNote: Release build requires signing configuration")
    
    result = subprocess.run(['buildozer', 'android', 'release'], check=False)
    
    if result.returncode == 0:
        print("\n" + "="*60)
        print("✓ RELEASE APK BUILD SUCCESSFUL!")
        print("="*60)
        print("\nAPK location: bin/universalsoulai-*.apk")
        print("\nNext steps:")
        print("  1. Sign the APK with your keystore")
        print("  2. Align the APK with zipalign")
        print("  3. Test on devices")
        print("  4. Upload to Play Store")
        return True
    else:
        print("\n" + "="*60)
        print("✗ RELEASE APK BUILD FAILED")
        print("="*60)
        return False


def deploy_to_device():
    """Deploy APK to connected Android device"""
    print("\n" + "="*60)
    print("Deploying to connected device...")
    print("="*60)
    
    result = subprocess.run(['buildozer', 'android', 'deploy', 'run'], 
                           check=False)
    
    if result.returncode == 0:
        print("\n✓ Deployed and running on device")
        return True
    else:
        print("\n✗ Deployment failed")
        print("\nMake sure:")
        print("  - Android device is connected via USB")
        print("  - USB debugging is enabled")
        print("  - Device is authorized (check device screen)")
        return False


def show_menu():
    """Show build options menu"""
    print("\n" + "="*60)
    print("Universal Soul AI - Android APK Build System")
    print("="*60)
    print("\nBuild Options:")
    print("  1. Build Debug APK (for testing)")
    print("  2. Build Release APK (for production)")
    print("  3. Deploy to connected device")
    print("  4. Clean build artifacts")
    print("  5. Check dependencies")
    print("  0. Exit")
    print()


def main():
    """Main build script entry point"""
    print("Universal Soul AI - Android Build System")
    print("="*60)
    
    # Check dependencies first
    if not check_dependencies():
        print("\n✗ Dependency check failed. Please install missing components.")
        sys.exit(1)
    
    while True:
        show_menu()
        choice = input("Select option (0-5): ").strip()
        
        if choice == '0':
            print("\nExiting build system. Goodbye!")
            break
        elif choice == '1':
            build_debug()
        elif choice == '2':
            build_release()
        elif choice == '3':
            deploy_to_device()
        elif choice == '4':
            clean_build()
        elif choice == '5':
            check_dependencies()
        else:
            print("\n✗ Invalid option. Please select 0-5.")
        
        input("\nPress Enter to continue...")


if __name__ == '__main__':
    main()
