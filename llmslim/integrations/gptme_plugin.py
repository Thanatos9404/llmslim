"""gptme plugin that makes LLMSlim gptme's compaction provider when asked to.

gptme loads the plugins of every installed package at startup (unless the user
keeps an allowlist), so this module only imports gptme's plugin manifest. It
does nothing unless the gptme config says so::

    [plugin.llmslim]
    compaction = true
    keep_recent = 6        # optional provider options
    min_tokens = 200

With ``compaction = true`` it registers
:class:`llmslim.integrations.gptme.LLMSlimContextProvider` as gptme's
``"default"`` provider, which gptme's automatic compaction and ``/compact
trim`` use. The project's ``gptme.toml`` overrides the user's
``config.toml`` key by key.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Mapping

__all__ = ["PLUGIN_NAME", "init_plugin", "plugin", "plugin_settings"]

logger = logging.getLogger(__name__)

PLUGIN_NAME = "llmslim"


def plugin_settings(config: Any) -> Dict[str, Any]:
    """``[plugin.llmslim]`` from the user config, overridden by the project config."""
    settings: Dict[str, Any] = {}
    for layer in (getattr(config, "user", None), getattr(config, "project", None)):
        section = getattr(layer, "plugin", None) if layer is not None else None
        value = section.get(PLUGIN_NAME) if isinstance(section, Mapping) else None
        if isinstance(value, Mapping):
            settings.update(value)
    return settings


def init_plugin(config: Any) -> None:
    """gptme plugin hook: with ``[plugin.llmslim] compaction = true``, make LLMSlim the default."""
    settings = plugin_settings(config)
    if not settings.get("compaction", False):
        return
    from gptme.tools.autocompact.context_provider import register_provider

    from .gptme import LLMSlimContextProvider

    options = {key: value for key, value in settings.items() if key != "compaction"}
    register_provider("default", LLMSlimContextProvider.configured(**options))
    logger.info("LLMSlim is gptme's compaction provider ([plugin.llmslim] compaction = true)")


try:
    from gptme.plugins.plugin import GptmePlugin
except ImportError:  # pragma: no cover - without gptme, or before gptme had plugin manifests.
    plugin: Any = None
else:
    plugin = GptmePlugin(name=PLUGIN_NAME, init=init_plugin)
