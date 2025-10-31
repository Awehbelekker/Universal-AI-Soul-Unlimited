"""
Monitor GitHub Actions build until completion
"""
import requests
import time
import sys
from datetime import datetime

REPO = "Awehbelekker/Universal-AI-Soul-Unlimited"
API_URL = f"https://api.github.com/repos/{REPO}/actions/runs"

def get_latest_build():
    """Get latest workflow run"""
    try:
        response = requests.get(API_URL, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data['workflow_runs']:
                return data['workflow_runs'][0]
    except Exception as e:
        print(f"Error fetching build: {e}")
    return None

def monitor_build(check_interval=30, max_wait=5400):
    """Monitor build until completion (max 90 minutes)"""
    start_time = time.time()
    last_status = None
    
    print("🔍 Monitoring build status...")
    print(f"⏱️  Max wait time: {max_wait // 60} minutes")
    print(f"🔄 Check interval: {check_interval} seconds\n")
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait:
            print(f"\n⏰ Max wait time exceeded ({max_wait // 60} min)")
            return None
        
        build = get_latest_build()
        if not build:
            print("❌ Failed to fetch build info")
            time.sleep(check_interval)
            continue
        
        status = build['status']
        conclusion = build.get('conclusion')
        build_num = build['run_number']
        url = build['html_url']
        
        # Print status update if changed
        current_status = f"{status}:{conclusion}"
        if current_status != last_status:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] 🏗️  Build #{build_num}")
            print(f"           📊 Status: {status.upper()}")
            if conclusion:
                emoji = "✅" if conclusion == "success" else "❌"
                print(f"           {emoji} Result: {conclusion.upper()}")
            print(f"           🔗 {url}\n")
            last_status = current_status
        
        # Check if completed
        if status == 'completed':
            print("=" * 60)
            if conclusion == 'success':
                print("✅ BUILD SUCCESSFUL!")
                print("=" * 60)
                return {'status': 'success', 'build': build}
            elif conclusion == 'failure':
                print("❌ BUILD FAILED!")
                print("=" * 60)
                return {'status': 'failure', 'build': build}
            else:
                print(f"⚠️  BUILD COMPLETED: {conclusion}")
                print("=" * 60)
                return {'status': conclusion, 'build': build}
        
        # Wait before next check
        time.sleep(check_interval)

if __name__ == '__main__':
    result = monitor_build(check_interval=30, max_wait=5400)
    
    if result:
        sys.exit(0 if result['status'] == 'success' else 1)
    else:
        sys.exit(2)
