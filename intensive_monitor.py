"""
INTENSIVE Build Monitor - Checks every 60 seconds with detailed status
"""
import requests
import time
from datetime import datetime

def get_latest_run():
    try:
        url = "https://api.github.com/repos/Awehbelekker/Universal-AI-Soul-Unlimited/actions/runs"
        response = requests.get(url, params={"per_page": 1})
        if response.status_code == 200:
            runs = response.json().get("workflow_runs", [])
            return runs[0] if runs else None
    except:
        return None

def get_jobs(run_id):
    try:
        url = f"https://api.github.com/repos/Awehbelekker/Universal-AI-Soul-Unlimited/actions/runs/{run_id}/jobs"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json().get("jobs", [])
    except:
        return []

def monitor_intensive():
    print("🚀 INTENSIVE MONITORING STARTED")
    print("=" * 70)
    print("Checking every 60 seconds for errors")
    print("Will alert IMMEDIATELY on any failure\n")
    
    last_status = None
    check_count = 0
    
    while True:
        check_count += 1
        now = datetime.now().strftime("%H:%M:%S")
        
        print(f"\n[Check #{check_count}] {now}")
        print("-" * 70)
        
        run = get_latest_run()
        
        if not run:
            print("⚠️  Could not fetch run data")
            time.sleep(60)
            continue
        
        status = run["status"]
        conclusion = run["conclusion"]
        run_number = run["run_number"]
        url = run["html_url"]
        created = run["created_at"]
        
        # Calculate elapsed time
        try:
            created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
            now_dt = datetime.now(created_dt.tzinfo)
            elapsed = now_dt - created_dt
            elapsed_mins = int(elapsed.total_seconds() / 60)
        except:
            elapsed_mins = 0
        
        print(f"🏗️  Build #{run_number}")
        print(f"📊 Status: {status.upper()}")
        print(f"⏱️  Elapsed: {elapsed_mins} minutes")
        
        # Status changed - show details
        if status != last_status:
            print(f"\n🔔 STATUS CHANGE: {last_status} → {status}")
            last_status = status
        
        # Get detailed job info
        jobs = get_jobs(run["id"])
        if jobs:
            for job in jobs:
                job_status = job["status"]
                job_conclusion = job["conclusion"]
                
                print(f"\n   Job: {job['name']}")
                print(f"   Status: {job_status}")
                
                # Show current step
                if job_status == "in_progress":
                    steps = job.get("steps", [])
                    for step in steps:
                        if step["status"] == "in_progress":
                            print(f"   🔄 Current: {step['name']}")
                        elif step["conclusion"] == "failure":
                            print(f"   ❌ FAILED: {step['name']}")
                            print(f"   ⚠️  ERROR DETECTED!")
                            print(f"   🔗 View: {url}")
        
        # Handle different statuses
        if status == "completed":
            if conclusion == "success":
                print(f"\n{'='*70}")
                print("🎉 BUILD SUCCESSFUL!")
                print(f"{'='*70}")
                print(f"\n📥 Download APK:")
                print(f"   1. Go to: {url}")
                print(f"   2. Scroll to 'Artifacts'")
                print(f"   3. Download 'universal-soul-ai-apk'\n")
                break
            else:
                print(f"\n{'='*70}")
                print(f"❌ BUILD FAILED: {conclusion}")
                print(f"{'='*70}")
                print(f"\n🔍 Check logs: {url}\n")
                break
        elif status == "in_progress":
            print(f"⏳ Building... ({elapsed_mins} min)")
        elif status == "queued":
            print("🟡 Waiting in queue...")
        
        print(f"\n🔗 Live: {url}")
        
        # Wait 60 seconds
        print(f"\nNext check in 60 seconds...")
        time.sleep(60)

if __name__ == "__main__":
    try:
        monitor_intensive()
    except KeyboardInterrupt:
        print("\n\n⏹️  Monitoring stopped")
