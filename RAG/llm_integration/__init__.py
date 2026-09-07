"""Existing LLM components, loaded only when requested.

A provider client must not require the legacy database-backed orchestrator.
"""
from importlib import import_module

_EXPORTS = {
    'LLMClientFactory': ('factory', 'LLMClientFactory'),
    'BaseLLMClient': ('base_client', 'BaseLLMClient'),
    'PromptBuilder': ('prompt_builder', 'PromptBuilder'),
    'ResponseFormatter': ('response_formatter', 'ResponseFormatter'),
    'LLMOrchestrator': ('orchestrator', 'LLMOrchestrator'),
    'QueryComplexityDetector': ('query_decomposition', 'QueryComplexityDetector'),
    'LLMQueryDecomposer': ('query_decomposition', 'LLMQueryDecomposer'),
    'AnswerSynthesizer': ('query_decomposition', 'AnswerSynthesizer'),
    'SubQuery': ('query_decomposition', 'SubQuery'),
    'SubQueryResult': ('query_decomposition', 'SubQueryResult'),
    'DecompositionResult': ('query_decomposition', 'DecompositionResult'),
    'QueryType': ('query_decomposition', 'QueryType'),
    'DecompositionStrategy': ('query_decomposition', 'DecompositionStrategy'),
    'DecompositionHandler': ('decomposition_handler', 'DecompositionHandler'),
    'ProcessingStatus': ('decomposition_handler', 'ProcessingStatus'),
    'ProcessingMetrics': ('decomposition_handler', 'ProcessingMetrics'),
    'ProcessingContext': ('decomposition_handler', 'ProcessingContext'),
    'SubQueryProcessor': ('sub_query_processor', 'SubQueryProcessor'),
    'ProcessingMode': ('sub_query_processor', 'ProcessingMode'),
    'ValidationResult': ('sub_query_processor', 'ValidationResult'),
    'ValidationMetrics': ('sub_query_processor', 'ValidationMetrics'),
    'ProcessingConfig': ('sub_query_processor', 'ProcessingConfig'),
}
__all__ = list(_EXPORTS)


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module, attribute = _EXPORTS[name]
    value = getattr(import_module(f'.{module}', __name__), attribute)
    globals()[name] = value
    return value
