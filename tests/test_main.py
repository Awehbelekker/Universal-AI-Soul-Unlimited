"""
Comprehensive Test Suite for Universal Soul AI
===============================================

Main test runner and configuration for the complete system test suite.
"""

import pytest
import asyncio
import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from main import UniversalSoulAI
from core.engines.hrm_engine import HRMEngine
from core.engines.coact_engine import CoAct1AutomationEngine
from core.interfaces.data_structures import UserContext, PersonalityMode, AutomationTask


class TestUniversalSoulAI:
    """Test suite for the main Universal Soul AI system"""
    
    @pytest.fixture
    async def soul_ai(self):
        """Create and initialize Universal Soul AI instance for testing"""
        soul_ai = UniversalSoulAI()
        await soul_ai.initialize()
        yield soul_ai
        await soul_ai.shutdown()
    
    @pytest.mark.asyncio
    async def test_system_initialization(self, soul_ai):
        """Test system initialization"""
        assert soul_ai.is_initialized
        assert soul_ai.hrm_engine is not None
        assert soul_ai.coact_engine is not None
    
    @pytest.mark.asyncio
    async def test_basic_request_processing(self, soul_ai):
        """Test basic user request processing"""
        response = await soul_ai.process_user_request(
            "Hello, how are you?",
            user_id="test_user"
        )
        assert response is not None
        assert len(response) > 0
        assert "friendly" in response.lower()  # Should have personality indicator
    
    @pytest.mark.asyncio
    async def test_system_status(self, soul_ai):
        """Test system status reporting"""
        status = await soul_ai.get_system_status()
        assert status["system_initialized"] is True
        assert "hrm_engine" in status
        assert "coact_engine" in status
        assert "system_metrics" in status
    
    @pytest.mark.asyncio
    async def test_user_context_creation(self, soul_ai):
        """Test user context creation and management"""
        response1 = await soul_ai.process_user_request(
            "Remember my name is Alice",
            user_id="alice"
        )
        assert "alice" in soul_ai.active_sessions
        
        response2 = await soul_ai.process_user_request(
            "What's my name?",
            user_id="alice"
        )
        # User context should be maintained
        assert len(soul_ai.active_sessions["alice"].conversation_history) == 2


class TestHRMEngine:
    """Test suite for the HRM Engine"""
    
    @pytest.fixture
    async def hrm_engine(self):
        """Create and initialize HRM engine for testing"""
        engine = HRMEngine()
        await engine.initialize()
        yield engine
        await engine.shutdown()
    
    @pytest.mark.asyncio
    async def test_hrm_initialization(self, hrm_engine):
        """Test HRM engine initialization"""
        assert hrm_engine.is_initialized
        assert hrm_engine.model is not None
        assert hrm_engine.tokenizer is not None
    
    @pytest.mark.asyncio
    async def test_hrm_capabilities(self, hrm_engine):
        """Test HRM engine capabilities"""
        capabilities = await hrm_engine.get_capabilities()
        assert "hierarchical_reasoning" in capabilities
        assert "personality_adaptation" in capabilities
        assert "values_integration" in capabilities
        assert "27m_parameter_processing" in capabilities
    
    @pytest.mark.asyncio
    async def test_hrm_processing(self, hrm_engine):
        """Test HRM request processing"""
        context = UserContext(
            user_id="test",
            personality_mode=PersonalityMode.ANALYTICAL,
        )
        
        response = await hrm_engine.process_request(
            "Analyze the benefits of renewable energy",
            context
        )
        
        assert response is not None
        assert len(response) > 0
        assert "analytical" in response.lower()  # Should reflect personality
    
    @pytest.mark.asyncio
    async def test_hrm_performance_metrics(self, hrm_engine):
        """Test HRM performance metrics collection"""
        # Process a few requests
        context = UserContext(user_id="test")
        for i in range(3):
            await hrm_engine.process_request(f"Test request {i}", context)
        
        metrics = hrm_engine.get_performance_metrics()
        assert metrics["total_requests"] >= 3
        assert metrics["successful_requests"] >= 3
        assert metrics["success_rate"] > 0
        assert "model_type" in metrics


class TestCoActEngine:
    """Test suite for the CoAct-1 Automation Engine"""
    
    @pytest.fixture
    async def coact_engine(self):
        """Create and initialize CoAct-1 engine for testing"""
        engine = CoAct1AutomationEngine()
        await engine.initialize()
        yield engine
    
    @pytest.mark.asyncio
    async def test_coact_initialization(self, coact_engine):
        """Test CoAct-1 engine initialization"""
        assert coact_engine.is_initialized
        assert coact_engine.target_success_rate == 0.6076
    
    @pytest.mark.asyncio
    async def test_task_complexity_analysis(self, coact_engine):
        """Test task complexity analysis"""
        simple_analysis = await coact_engine.analyze_task_complexity(
            "Turn on the lights"
        )
        assert simple_analysis["complexity_level"].value == "simple"
        
        complex_analysis = await coact_engine.analyze_task_complexity(
            "Analyze and optimize the complex multi-threaded parallel processing system with advanced coordination and synthesis"
        )
        assert complex_analysis["complexity_level"].value in ["complex", "very_complex"]
    
    @pytest.mark.asyncio
    async def test_task_execution(self, coact_engine):
        """Test automation task execution"""
        task = AutomationTask(
            description="Simple test automation task",
            task_type="test",
            complexity=2.0
        )
        
        result = await coact_engine.execute_task(task, {})
        assert "success" in result
        assert "execution_time" in result
        assert "strategy_used" in result
        assert "confidence" in result
    
    @pytest.mark.asyncio
    async def test_success_rate_tracking(self, coact_engine):
        """Test success rate tracking"""
        initial_rate = await coact_engine.get_success_rate()
        
        # Execute multiple tasks
        for i in range(5):
            task = AutomationTask(
                description=f"Test task {i}",
                complexity=1.0 + i * 0.5
            )
            await coact_engine.execute_task(task, {})
        
        final_rate = await coact_engine.get_success_rate()
        assert final_rate >= 0.0
        assert final_rate <= 1.0
    
    @pytest.mark.asyncio
    async def test_performance_metrics(self, coact_engine):
        """Test CoAct-1 performance metrics"""
        # Execute some tasks first
        for i in range(3):
            task = AutomationTask(description=f"Metrics test {i}")
            await coact_engine.execute_task(task, {})
        
        metrics = coact_engine.get_performance_metrics()
        assert metrics["total_tasks"] >= 3
        assert "strategy_stats" in metrics
        assert "engine_type" in metrics
        assert metrics["engine_type"] == "CoAct-1_Hybrid_Automation"


class TestSystemIntegration:
    """Test suite for system integration"""
    
    @pytest.mark.asyncio
    async def test_automation_integration(self):
        """Test integration between HRM and CoAct-1"""
        soul_ai = UniversalSoulAI()
        await soul_ai.initialize()
        
        try:
            # Request that should trigger automation
            response = await soul_ai.process_user_request(
                "Please automate my daily morning routine",
                user_id="integration_test"
            )
            
            assert response is not None
            assert len(response) > 0
            # Should contain some indication of automation processing
            assert any(word in response.lower() for word in ["automat", "complet", "execut"])
        
        finally:
            await soul_ai.shutdown()
    
    @pytest.mark.asyncio
    async def test_personality_consistency(self):
        """Test personality consistency across interactions"""
        soul_ai = UniversalSoulAI()
        await soul_ai.initialize()
        
        try:
            # Set up user with specific personality
            user_context = UserContext(
                user_id="personality_test",
                personality_mode=PersonalityMode.PROFESSIONAL
            )
            soul_ai.active_sessions["personality_test"] = user_context
            
            response = await soul_ai.process_user_request(
                "Help me with a business proposal",
                user_id="personality_test"
            )
            
            assert "professional" in response.lower()
        
        finally:
            await soul_ai.shutdown()


class TestErrorHandling:
    """Test suite for error handling and edge cases"""
    
    @pytest.mark.asyncio
    async def test_invalid_request_handling(self):
        """Test handling of invalid requests"""
        soul_ai = UniversalSoulAI()
        await soul_ai.initialize()
        
        try:
            # Empty request
            response = await soul_ai.process_user_request("", user_id="error_test")
            assert response is not None  # Should handle gracefully
            
            # Very long request
            long_request = "a" * 10000
            response = await soul_ai.process_user_request(long_request, user_id="error_test")
            assert response is not None
        
        finally:
            await soul_ai.shutdown()
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test handling of concurrent requests"""
        soul_ai = UniversalSoulAI()
        await soul_ai.initialize()
        
        try:
            # Create multiple concurrent requests
            tasks = []
            for i in range(3):
                task = soul_ai.process_user_request(
                    f"Concurrent request {i}",
                    user_id=f"concurrent_user_{i}"
                )
                tasks.append(task)
            
            responses = await asyncio.gather(*tasks)
            
            # All responses should be valid
            for response in responses:
                assert response is not None
                assert len(response) > 0
        
        finally:
            await soul_ai.shutdown()


# Performance benchmarks
class TestPerformance:
    """Performance benchmarks for the system"""
    
    @pytest.mark.asyncio
    async def test_response_time_benchmark(self):
        """Benchmark response times"""
        soul_ai = UniversalSoulAI()
        await soul_ai.initialize()
        
        try:
            import time
            
            start_time = time.time()
            response = await soul_ai.process_user_request(
                "What's the weather like today?",
                user_id="benchmark_user"
            )
            end_time = time.time()
            
            response_time = end_time - start_time
            
            # Response should be reasonably fast (less than 5 seconds)
            assert response_time < 5.0
            assert response is not None
            
            print(f"Response time: {response_time:.2f}s")
        
        finally:
            await soul_ai.shutdown()
    
    @pytest.mark.asyncio
    async def test_memory_usage(self):
        """Test memory usage during operation"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        soul_ai = UniversalSoulAI()
        await soul_ai.initialize()
        
        try:
            # Process several requests
            for i in range(10):
                await soul_ai.process_user_request(
                    f"Memory test request {i}",
                    user_id="memory_test"
                )
            
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory
            
            # Memory increase should be reasonable (less than 500MB for this test)
            assert memory_increase < 500
            
            print(f"Memory usage: {final_memory:.1f}MB (increase: +{memory_increase:.1f}MB)")
        
        finally:
            await soul_ai.shutdown()


if __name__ == "__main__":
    """Run the test suite"""
    # Configure pytest
    pytest_args = [
        "-v",  # Verbose output
        "--tb=short",  # Shorter traceback format
        "-x",  # Stop on first failure
        "--asyncio-mode=auto",  # Handle async tests
        __file__  # Run this file
    ]
    
    # Run the tests
    exit_code = pytest.main(pytest_args)
    sys.exit(exit_code)