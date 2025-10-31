"""
Continuous build monitor with notifications
Monitors until build completes or max time reached
"""
import requests
import time
from datetime import datetime, timedelta

REPO = "Awehbelekker/Universal-AI-Soul-Unlimited"
CHECK_INTERVAL = 60  # Check every 60 seconds
MAX_HOURS = 2  # Monitor for max 2 hours

def get_build_status():
    """Get current build status"""
    try:
        url = f"https://api.github.com/repos/{REPO}/actions/runs"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            run = response.json()['workflow_runs'][0]
            return {
                'number': run['run_number'],
                'status': run['status'],
                'conclusion': run.get('conclusion'),
                'url': run['html_url'],
                'created': run['created_at'],
                'updated': run['updated_at']
            }
    except Exception as e:
        print(f"Error: {e}")
    return None

def format_duration(start_time):
    """Format elapsed time"""
    elapsed = datetime.now() - start_time
    hours = int(elapsed.total_seconds() // 3600)
    minutes = int((elapsed.total_seconds() % 3600) // 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"

def main():
    start_time = datetime.now()
    max_time = start_time + timedelta(hours=MAX_HOURS)
    last_status = None
    queue_start = None
    
    print("=" * 70)
    print("🔍 CONTINUOUS BUILD MONITOR")
    print("=" * 70)
    print(f"Started: {start_time.strftime('%H:%M:%S')}")
    print(f"Max duration: {MAX_HOURS} hours")
    print(f"Check interval: {CHECK_INTERVAL}s")
    print("=" * 70)
    print()
    
    check_count = 0
    
    while datetime.now() < max_time:
        check_count += 1
        build = get_build_status()
        
        if build:
            current = f"{build['status']}:{build['conclusion']}"
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            # Track queue time
            if build['status'] == 'queued' and not queue_start:
                queue_start = datetime.now()
            elif build['status'] != 'queued' and queue_start:
                queue_duration = datetime.now() - queue_start
                print(f"\n🎯 Build started after {queue_duration.total_seconds()/60:.1f} minutes in queue!\n")
                queue_start = None
            
            # Print status if changed
            if current != last_status:
                elapsed = format_duration(start_time)
                
                if build['status'] == 'queued':
                    queue_time = format_duration(queue_start) if queue_start else "0m"
                    print(f"[{timestamp}] 🟡 Build #{build['number']}: QUEUED ({queue_time})")
                    
                elif build['status'] == 'in_progress':
                    print(f"[{timestamp}] 🔵 Build #{build['number']}: IN PROGRESS")
                    
                elif build['status'] == 'completed':
                    print(f"\n{'='*70}")
                    print(f"[{timestamp}] Build #{build['number']} COMPLETED")
                    print(f"Duration: {elapsed}")
                    print(f"Result: {build['conclusion'].upper()}")
                    
                    if build['conclusion'] == 'success':
                        print("✅ BUILD SUCCESSFUL!")
                        print("\n📦 APK should be available in artifacts")
                    elif build['conclusion'] == 'failure':
                        print("❌ BUILD FAILED")
                        print("\n💡 Run: python analyze_build.py latest")
                    
                    print(f"🔗 {build['url']}")
                    print("="*70)
                    return build['conclusion']
                
                last_status = current
            
            # Periodic update for long queues
            elif build['status'] == 'queued' and check_count % 5 == 0:
                queue_time = format_duration(queue_start) if queue_start else "0m"
                print(f"[{timestamp}] ⏳ Still queued... ({queue_time})")
        
        time.sleep(CHECK_INTERVAL)
    
    print(f"\n⏰ Max monitoring time ({MAX_HOURS}h) reached")
    return None

if __name__ == '__main__':
    result = main()
    
    if result == 'success':
        exit(0)
    elif result == 'failure':
        exit(1)
    else:
        exit(2)
