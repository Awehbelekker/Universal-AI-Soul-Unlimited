"""
LocalAI Service Update for CPT-OSS 20B Integration
==================================================

This file updates the LocalAI service to include CPT-OSS 20B support.
Apply these changes to thinkmesh_core/localai/service.py
"""

# Add this import at the top of service.py
"""
from .cpt_oss_integration import CPTOSSIntegration, ModelTier
"""

# Add this to the LocalAIService.__init__ method
"""
# CPT-OSS 20B integration
self.cpt_oss: Optional[CPTOSSIntegration] = None
self.cpt_oss_enabled = config.__dict__.get('cpt_oss_enabled', True)
"""

# Add this to the LocalAIService.initialize method
"""
# Initialize CPT-OSS 20B integration if enabled
if self.cpt_oss_enabled:
    try:
        from .cpt_oss_integration import CPTOSSIntegration
        self.cpt_oss = CPTOSSIntegration()
        await self.cpt_oss.initialize()
        logger.info("CPT-OSS 20B integration initialized")
    except Exception as e:
        logger.warning(f"CPT-OSS 20B not available: {e}")
        self.cpt_oss_enabled = False
"""

# Update the _select_model method to include CPT-OSS tiers
"""
async def _select_model(self, request: InferenceRequest) -> str:
    '''Select optimal model for the request'''
    if request.model_name:
        # Use specified model if available
        available_models = await self.model_manager.get_available_models()
        if request.model_name in available_models:
            return request.model_name
    
    # Use CPT-OSS intelligent routing if available
    if self.cpt_oss and self.cpt_oss.is_initialized:
        try:
            routing_info = await self.cpt_oss.intelligent_routing(
                request.prompt,
                privacy_mode="strict" if request.context.privacy_settings.get('local_only') else "balanced"
            )
            
            selected_tier = routing_info['selected_tier']
            model_config = routing_info['model_config']
            
            logger.info(f"CPT-OSS routing: tier={selected_tier.value}, complexity={routing_info['task_complexity'].value}")
            
            return model_config.name
            
        except Exception as e:
            logger.warning(f"CPT-OSS routing failed, using fallback: {e}")
    
    # Fallback to original model selection logic
    if request.mode == InferenceMode.FAST:
        return await self._select_fast_model(request)
    elif request.mode == InferenceMode.QUALITY:
        return await self._select_quality_model(request)
    elif request.mode == InferenceMode.MOBILE_OPTIMIZED:
        return await self._select_mobile_model(request)
    else:
        # Balanced mode
        return await self._select_balanced_model(request)
"""

# Update _perform_inference to use CPT-OSS when appropriate
"""
async def _perform_inference(self, request: InferenceRequest) -> InferenceResult:
    '''Perform the actual inference'''
    try:
        # Check if we should use CPT-OSS directly
        if self.cpt_oss and self.cpt_oss.is_initialized:
            model_name = await self._select_model(request)
            
            # If model is CPT-OSS variant, use CPT-OSS integration
            if 'cpt-oss' in model_name.lower():
                try:
                    response_text = await self.cpt_oss.generate(
                        prompt=request.prompt,
                        max_tokens=request.max_tokens,
                        temperature=request.temperature
                    )
                    
                    return InferenceResult(
                        response=response_text,
                        model_used=model_name,
                        tokens_generated=len(response_text.split()),  # Approximate
                        inference_time_ms=(time.time() - time.time()) * 1000,
                        confidence_score=0.85,
                        mode_used=request.mode,
                        mobile_optimizations={},
                        metadata={'via_cpt_oss': True}
                    )
                except Exception as e:
                    logger.error(f"CPT-OSS generation failed: {e}, falling back to standard inference")
        
        # Standard inference path (existing code)
        model_name = await self._select_model(request)
        
        # Apply mobile optimizations
        optimized_request = await self.model_optimizer.optimize_request(
            request, self.mobile_constraints
        )
        
        # Perform inference
        inference_result = await self.inference_engine.infer(
            model_name=model_name,
            prompt=optimized_request.prompt,
            max_tokens=optimized_request.max_tokens,
            temperature=optimized_request.temperature,
            mode=optimized_request.mode
        )
        
        # Update model usage
        self.model_usage[model_name] = self.model_usage.get(model_name, 0) + 1
        
        return inference_result
        
    except Exception as e:
        logger.error(f"Inference execution failed: {e}")
        raise
"""

print("""
CPT-OSS 20B Integration Instructions
=====================================

To integrate CPT-OSS 20B into the LocalAI service:

1. The cpt_oss_integration.py file has been created in thinkmesh_core/localai/

2. Update thinkmesh_core/localai/service.py by adding the code snippets above

3. Update thinkmesh_core/config.py to add CPT-OSS configuration:

@dataclass
class LocalAIConfig:
    # ... existing fields ...
    
    # CPT-OSS 20B configuration
    cpt_oss_enabled: bool = True
    cpt_oss_model_path: str = "models/cpt-oss-20b.Q4_K_M.gguf"
    cpt_oss_auto_download: bool = False

4. Download the CPT-OSS 20B model:

   # For Q4 quantization (recommended for most devices)
   huggingface-cli download TheBloke/CPT-OSS-20B-GGUF cpt-oss-20b.Q4_K_M.gguf --local-dir models/

   # For Q8 quantization (high-end devices)
   huggingface-cli download TheBloke/CPT-OSS-20B-GGUF cpt-oss-20b.Q8_0.gguf --local-dir models/

5. Install dependencies:

   pip install llama-cpp-python psutil

6. Test the integration:

   python thinkmesh_core/localai/cpt_oss_integration.py

That's it! The system will now automatically use CPT-OSS 20B on capable devices.
""")
