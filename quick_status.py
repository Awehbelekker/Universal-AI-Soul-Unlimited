"""Quick build status check - Run this every few minutes"""
import requests
from datetime import datetime

def check_now():
    try:
        url = "https://api.github.com/repos/Awehbelekker/Universal-AI-Soul-Unlimited/actions/runs"
        response = requests.get(url, headers={"Accept": "application/vnd.github.v3+json"}, params={"per_page": 1})
        
        if response.status_code == 200:
            run = response.json()["workflow_runs"][0]
            
            status = run["status"]
            conclusion = run["conclusion"]
            run_number = run["run_number"]
            url = run["html_url"]
            
            print(f"\n🏗️  BUILD #{run_number}")
            print(f"📊 Status: {status.upper()}")
            
            if status == "completed":
                if conclusion == "success":
                    print("✅ Result: SUCCESS!")
                    print(f"\n📥 Download APK:")
                    print(f"   {url}")
                    print("\n   1. Click the link above")
                    print("   2. Scroll to 'Artifacts' section")
                    print("   3. Download 'universal-soul-ai-apk'")
                else:
                    print(f"❌ Result: {conclusion.upper()}")
                    print(f"🔍 Check logs: {url}")
            elif status == "in_progress":
                print("⏳ Build is running...")
                print(f"🔗 Watch live: {url}")
            elif status == "queued":
                print("🟡 Waiting in queue...")
                print(f"🔗 View: {url}")
            
            print("")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_now()
