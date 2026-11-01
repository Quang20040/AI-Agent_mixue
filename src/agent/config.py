"""Explicit model configuration. Reading settings never calls a provider."""
import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr

ROOT = Path(__file__).resolve().parents[2]


class AgentSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    llm_enabled: bool = False
    provider: str = ''
    model: str = ''
    api_key: SecretStr = SecretStr('')
    base_url: str = ''
    allow_external_transfer: bool = False
    model_timeout: float = Field(default=45, gt=0, le=120)
    run_timeout: float = Field(default=120, gt=0, le=300)
    max_tool_calls: int = Field(default=8, ge=1, le=20)
    max_model_calls: int = Field(default=10, ge=1, le=25)
    max_retries: int = Field(default=1, ge=0, le=3)
    max_history_messages: int = Field(default=40, ge=6, le=200)
    max_output_tokens: int = Field(default=1400, ge=128, le=4096)
    # Defaults honour the same environment variables as from_env(), so directly built
    # settings (tests, scripts) never fall back to the shared store by accident.
    checkpoint_path: str = Field(default_factory=lambda: os.environ.get('AGENT_CHECKPOINT_PATH')
                                 or str(ROOT / 'data' / 'agent_private' / 'checkpoints.sqlite'))
    audit_path: str = Field(default_factory=lambda: os.environ.get('AGENT_AUDIT_PATH')
                            or str(ROOT / 'data' / 'agent_private' / 'audit.jsonl'))

    @classmethod
    def from_env(cls, env_file=None):
        values = {**dotenv_values(env_file or ROOT / '.env'), **os.environ}
        mapping = {
            'llm_enabled': 'LLM_ENABLED', 'provider': 'LLM_PROVIDER', 'model': 'LLM_MODEL',
            'api_key': 'LLM_API_KEY', 'base_url': 'LLM_BASE_URL',
            'allow_external_transfer': 'ALLOW_EXTERNAL_DATA_TRANSFER',
            'model_timeout': 'LLM_TIMEOUT_SECONDS', 'run_timeout': 'AGENT_TIMEOUT_SECONDS',
            'max_tool_calls': 'AGENT_MAX_TOOL_CALLS', 'max_model_calls': 'AGENT_MAX_MODEL_CALLS',
            'max_retries': 'AGENT_MAX_RETRIES', 'max_history_messages': 'AGENT_MAX_HISTORY_MESSAGES',
            'max_output_tokens': 'LLM_MAX_OUTPUT_TOKENS',
            'checkpoint_path': 'AGENT_CHECKPOINT_PATH', 'audit_path': 'AGENT_AUDIT_PATH',
        }
        config = {field: values[key] for field, key in mapping.items() if values.get(key) not in (None, '')}
        provider = str(config.get('provider', '')).lower()
        config['provider'] = provider
        if not config.get('api_key'):
            if provider == 'openrouter':
                key_name = 'OPENROUTER_API_KEY'
            elif provider in {'gemini', 'google', 'google_genai'}:
                key_name = 'GEMINI_API_KEY'
            else:
                key_name = 'OPENAI_API_KEY'
            config['api_key'] = values.get(key_name) or ''
        if provider == 'openrouter' and not config.get('base_url'):
            config['base_url'] = 'https://openrouter.ai/api/v1'
        elif provider in {'gemini', 'google', 'google_genai'} and not config.get('base_url'):
            config['base_url'] = 'https://generativelanguage.googleapis.com/v1beta/openai/'
        return cls(**config)

    def build_model(self):
        if not self.llm_enabled:
            return None
        if not self.provider or not self.model:
            raise ValueError('MODEL_NOT_CONFIGURED')
        local = bool(self.base_url) and urlparse(self.base_url).hostname in {'127.0.0.1', 'localhost', '::1'}
        if not local and not self.allow_external_transfer:
            raise ValueError('EXTERNAL_TRANSFER_DISABLED')
        if not local and not self.api_key.get_secret_value():
            raise ValueError('MISSING_API_KEY')
        from langchain.chat_models import init_chat_model
        kwargs = {'timeout': min(self.model_timeout, self.run_timeout), 'max_retries': self.max_retries,
                  'max_tokens': self.max_output_tokens}
        if self.api_key.get_secret_value():
            kwargs['api_key'] = self.api_key.get_secret_value()
        if self.base_url:
            kwargs['base_url'] = self.base_url
        provider = 'openai' if self.provider in {'openrouter', 'gemini', 'google', 'google_genai'} else self.provider
        if self.provider == 'openrouter':
            kwargs['extra_body'] = {'provider': {'require_parameters': True}}
        return init_chat_model(self.model, model_provider=provider, **kwargs)
