#!/usr/bin/env python3
"""
Quick test script to verify Qwen2.5-3B optimization
Run this after applying optimizations to confirm improvements
"""

import time
import sys

try:
    import ollama
except ImportError:
    print("❌ Error: ollama package not installed")
    print("Install with: pip install ollama")
    sys.exit(1)

def test_model(model_name="qwen2.5:3b"):
    """Quick test of model performance"""
    print(f"\n{'='*60}")
    print(f"Testing: {model_name}")
    print(f"{'='*60}\n")
    
    test_prompt = "Explain artificial intelligence in exactly 2 sentences."
    
    try:
        print("Sending test query...")
        start_time = time.time()
        
        response = ollama.chat(
            model=model_name,
            messages=[{"role": "user", "content": test_prompt}]
        )
        
        elapsed = time.time() - start_time
        response_text = response['message']['content']
        token_count = len(response_text) // 4  # Rough estimate
        tokens_per_sec = token_count / elapsed if elapsed > 0 else 0
        
        print(f"\n📝 Response:\n{response_text}\n")
        print(f"{'='*60}")
        print(f"⏱️  Time: {elapsed:.2f} seconds")
        print(f"📊 Tokens: ~{token_count}")
        print(f"🚀 Speed: {tokens_per_sec:.1f} tokens/second")
        print(f"{'='*60}\n")
        
        # Evaluation
        if elapsed < 1.5:
            print("✅ Excellent performance!")
        elif elapsed < 3:
            print("✅ Good performance")
        elif elapsed < 5:
            print("⚠️  Moderate performance - consider optimizations")
        else:
            print("❌ Poor performance - optimization needed")
        
        if tokens_per_sec > 50:
            print("✅ Excellent throughput!")
        elif tokens_per_sec > 30:
            print("✅ Good throughput")
        elif tokens_per_sec > 15:
            print("⚠️  Moderate throughput")
        else:
            print("❌ Low throughput - check GPU/CPU settings")
        
        return {
            "latency": elapsed,
            "tokens": token_count,
            "tokens_per_second": tokens_per_sec,
            "response": response_text
        }
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def compare_models():
    """Compare performance between models"""
    print("\n" + "="*60)
    print("Model Performance Comparison")
    print("="*60)
    
    models_to_test = []
    
    # Check what models are available
    try:
        available = ollama.list()
        model_names = [m['name'] for m in available.get('models', [])]
        
        # Test base and optimized if available
        if 'qwen2.5:3b' in model_names:
            models_to_test.append('qwen2.5:3b')
        if 'qwen2.5-optimized:latest' in model_names:
            models_to_test.append('qwen2.5-optimized')
        
        if not models_to_test:
            print("❌ No Qwen2.5 models found")
            print("Run: ollama pull qwen2.5:3b")
            return
            
    except Exception as e:
        print(f"❌ Error listing models: {e}")
        return
    
    results = {}
    for model in models_to_test:
        result = test_model(model)
        if result:
            results[model] = result
        print()
    
    # Show comparison if we have multiple results
    if len(results) > 1:
        print("\n" + "="*60)
        print("📊 Comparison Summary")
        print("="*60 + "\n")
        
        for model, data in results.items():
            print(f"{model:30} | {data['latency']:.2f}s | {data['tokens_per_second']:.1f} t/s")
        
        # Calculate improvement
        base_key = 'qwen2.5:3b'
        opt_key = 'qwen2.5-optimized'
        
        if base_key in results and opt_key in results:
            base_time = results[base_key]['latency']
            opt_time = results[opt_key]['latency']
            improvement = ((base_time - opt_time) / base_time) * 100
            
            print(f"\n🚀 Optimization Impact:")
            print(f"   Speed improvement: {improvement:.1f}% faster")
            
            base_tps = results[base_key]['tokens_per_second']
            opt_tps = results[opt_key]['tokens_per_second']
            tps_improvement = ((opt_tps - base_tps) / base_tps) * 100
            print(f"   Throughput improvement: {tps_improvement:.1f}% higher")

def main():
    """Main test execution"""
    print("\n🧪 Qwen2.5-3B Quick Performance Test")
    print("="*60)
    
    choice = input("\n1. Test specific model\n2. Compare models\n\nChoice (1/2): ").strip()
    
    if choice == "1":
        model = input("\nEnter model name (default: qwen2.5:3b): ").strip()
        model = model if model else "qwen2.5:3b"
        test_model(model)
    elif choice == "2":
        compare_models()
    else:
        print("Invalid choice")
        return
    
    print("\n💡 Tips:")
    print("  • For full benchmark: python benchmark_qwen_performance.py")
    print("  • For optimization: .\\optimize_qwen.ps1")
    print("  • For guide: see QWEN2.5_OPTIMIZATION_GUIDE.md\n")

if __name__ == "__main__":
    main()
