"""
Monitor GitHub Actions Build Status
Checks the build status and provides real-time updates
"""
import requests
import time
import json
from datetime import datetime

# GitHub API configuration
REPO_OWNER = "Awehbelekker"
REPO_NAME = "Universal-AI-Soul-Unlimited"
API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/runs"

def check_build_status():
    """Check the latest GitHub Actions workflow run status"""
    try:
        # Get latest workflow runs
        response = requests.get(
            API_URL,
            headers={"Accept": "application/vnd.github.v3+json"},
            params={"per_page": 1}
        )
        
        if response.status_code != 200:
            print(f"❌ API Error: {response.status_code}")
            return None
        
        data = response.json()
        
        if not data.get("workflow_runs"):
            print("⚠️  No workflow runs found")
            return None
        
        run = data["workflow_runs"][0]
        
        return {
            "id": run["id"],
            "name": run["name"],
            "status": run["status"],
            "conclusion": run["conclusion"],
            "created_at": run["created_at"],
            "updated_at": run["updated_at"],
            "html_url": run["html_url"],
            "run_number": run["run_number"]
        }
    
    except Exception as e:
        print(f"❌ Error checking build: {e}")
        return None

def format_time_elapsed(created_at):
    """Calculate time elapsed since build started"""
    try:
        created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        now = datetime.now(created.tzinfo)
        elapsed = now - created
        
        minutes = int(elapsed.total_seconds() / 60)
        seconds = int(elapsed.total_seconds() % 60)
        
        return f"{minutes}m {seconds}s"
    except:
        return "unknown"

def display_status(build_info):
    """Display formatted build status"""
    if not build_info:
        return
    
    print("\n" + "="*60)
    print(f"🏗️  BUILD STATUS - Run #{build_info['run_number']}")
    print("="*60)
    
    status = build_info["status"]
    conclusion = build_info["conclusion"]
    
    # Status indicator
    if status == "completed":
        if conclusion == "success":
            print("✅ Status: COMPLETED SUCCESSFULLY")
        elif conclusion == "failure":
            print("❌ Status: FAILED")
        else:
            print(f"⚠️  Status: COMPLETED ({conclusion})")
    elif status == "in_progress":
        print("🔄 Status: IN PROGRESS")
    else:
        print(f"🟡 Status: {status.upper()}")
    
    # Workflow name
    print(f"📋 Workflow: {build_info['name']}")
    
    # Time elapsed
    elapsed = format_time_elapsed(build_info['created_at'])
    print(f"⏱️  Time Elapsed: {elapsed}")
    
    # URL
    print(f"🔗 View Details: {build_info['html_url']}")
    
    print("="*60)
    
    return status, conclusion

def monitor_build(interval=30, max_checks=60):
    """
    Monitor build with automatic updates
    
    Args:
        interval: Seconds between checks (default: 30)
        max_checks: Maximum number of checks before stopping (default: 60 = 30min)
    """
    print("🚀 Starting Build Monitor...")
    print(f"📊 Checking every {interval} seconds")
    print(f"⏰ Max monitoring time: {max_checks * interval / 60:.0f} minutes")
    print("\nPress Ctrl+C to stop monitoring\n")
    
    check_count = 0
    
    try:
        while check_count < max_checks:
            check_count += 1
            
            print(f"\n[Check {check_count}/{max_checks}] {datetime.now().strftime('%H:%M:%S')}")
            
            build_info = check_build_status()
            
            if build_info:
                status, conclusion = display_status(build_info)
                
                # Stop monitoring if build is complete
                if status == "completed":
                    print("\n" + "="*60)
                    if conclusion == "success":
                        print("🎉 BUILD COMPLETED SUCCESSFULLY!")
                        print("\n📥 Next Steps:")
                        print("1. Go to: " + build_info['html_url'])
                        print("2. Scroll to 'Artifacts' section")
                        print("3. Download 'universal-soul-ai-debug.zip'")
                        print("4. Extract and install APK on your device")
                    elif conclusion == "failure":
                        print("⚠️  BUILD FAILED")
                        print("\n🔍 Troubleshooting:")
                        print("1. Click: " + build_info['html_url'])
                        print("2. Expand failed steps to see error logs")
                        print("3. Check buildozer.spec for dependency issues")
                        print("4. Retry by pushing a new commit")
                    else:
                        print(f"ℹ️  Build completed with status: {conclusion}")
                    
                    print("="*60 + "\n")
                    break
                
                # Show progress indicator for in-progress builds
                if status == "in_progress":
                    print("\n⏳ Build still running... Will check again in 30 seconds")
                    print("💡 Tip: You can view live logs at the URL above")
            
            else:
                print("⚠️  Could not fetch build status")
            
            # Wait before next check (unless this was the last check)
            if check_count < max_checks and status != "completed":
                time.sleep(interval)
    
    except KeyboardInterrupt:
        print("\n\n⏹️  Monitoring stopped by user")
        print(f"🔗 Check status manually: https://github.com/{REPO_OWNER}/{REPO_NAME}/actions")
    
    except Exception as e:
        print(f"\n❌ Monitoring error: {e}")

def quick_check():
    """Quick one-time status check"""
    print("🔍 Checking build status...\n")
    build_info = check_build_status()
    
    if build_info:
        display_status(build_info)
        
        status = build_info["status"]
        conclusion = build_info["conclusion"]
        
        if status == "completed":
            if conclusion == "success":
                print("\n✅ Your APK is ready to download!")
                print(f"📥 Visit: {build_info['html_url']}")
            elif conclusion == "failure":
                print("\n❌ Build failed. Check logs for details.")
                print(f"🔍 Visit: {build_info['html_url']}")
        elif status == "in_progress":
            print("\n⏳ Build is still running...")
            print("💡 Run 'python monitor_build.py --watch' to monitor continuously")
        else:
            print(f"\nℹ️  Build status: {status}")
    else:
        print("❌ Could not retrieve build information")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] in ["--watch", "-w", "--monitor", "-m"]:
        # Continuous monitoring mode
        monitor_build(interval=30, max_checks=80)  # Monitor for up to 40 minutes
    else:
        # Quick check mode
        quick_check()
        print("\n💡 For continuous monitoring, run:")
        print("   python monitor_build.py --watch")
