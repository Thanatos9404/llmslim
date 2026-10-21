"""LLMSlim context engine for Hermes Agent.

The engine ships in the ``llmslim`` package, which Hermes installs from PyPI as
this plugin's Python dependency. Select it with ``context.engine: llmslim`` in
config.yaml.
"""

from llmslim.integrations.hermes import LLMSlimContextEngine, register

__all__ = ["LLMSlimContextEngine", "register"]
