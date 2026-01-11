"""
LLM Configuration for Ollama - Ensemble System

Supports role-based LLM configuration for multi-model ensemble evaluation.
"""
from langchain_ollama import ChatOllama
from typing import Optional


# Role-specific LLM configurations
# Each role uses a model optimized for its task
LLM_ROLES = {
    "factor_analyzer": {
        "model": "qwen2.5:7b",  # Optimized for math and numeric analysis
        "base_url": "http://localhost:11434",
        "temperature": 0.1  # Low temperature for precise numeric comparisons
    },
    "risk_synthesizer": {
        "model": "llama3.1:8b",  # Good at reasoning and pattern recognition
        "base_url": "http://localhost:11434",
        "temperature": 0.2  # Slightly higher for contextual reasoning
    },
    "decision_maker": {
        "model": "mistral:7b",  # Good at decision-making and recommendations
        "base_url": "http://localhost:11434",
        "temperature": 0.15  # Balanced for clear decisions
    }
}


class LLMConfig:
    """Configuration for local LLM."""
    
    def __init__(
        self,
        model: str = "llama3.1:8b",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.1
    ):
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
    
    def get_llm(self) -> ChatOllama:
        """Get LLM instance for single-model use (legacy compatibility)."""
        return ChatOllama(
            model=self.model,
            base_url=self.base_url,
            temperature=self.temperature,
            num_ctx=4096,  # Smaller context since prompts are simple
        )


def get_llm_for_role(role: str) -> ChatOllama:
    """
    Get LLM instance configured for a specific role.
    
    Args:
        role: One of "factor_analyzer", "risk_synthesizer", "decision_maker"
    
    Returns:
        ChatOllama instance configured for the role
    """
    if role not in LLM_ROLES:
        # Default to factor_analyzer config if role unknown
        role = "factor_analyzer"
    
    config = LLM_ROLES[role]
    return ChatOllama(
        model=config["model"],
        base_url=config["base_url"],
        temperature=config["temperature"],
        num_ctx=4096,
    )
