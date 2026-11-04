"""The four constants 0.12 exported from llmslim.integrations.sarvam still import there, with a warning.

0.12 listed them in that module's ``__all__``, re-exported from ``sarvam_text`` and ``sarvam_documents``. They are
deprecated since 1.0.0rc1 and stay until 2.0, as docs/API_STABILITY.md and docs/UPGRADING.md say.
"""

from __future__ import annotations

import subprocess
import sys
import warnings

import pytest

from llmslim.integrations import sarvam, sarvam_documents, sarvam_text

MOVED = {
    "DEFAULT_TEXT_LIMITS": sarvam_text,
    "TEXT_GUARD_PREFIX": sarvam_text,
    "DEFAULT_DOCUMENT_LIMITS": sarvam_documents,
    "DOCUMENT_GUARD_PREFIX": sarvam_documents,
}


@pytest.mark.parametrize("name", sorted(MOVED))
def test_the_old_name_works_and_warns_naming_the_module_that_defines_it(name):
    module = MOVED[name]
    with pytest.warns(DeprecationWarning) as caught:
        value = getattr(sarvam, name)
    assert value is getattr(module, name)
    assert len(caught) == 1
    assert str(caught[0].message) == (
        f"llmslim.integrations.sarvam.{name} is deprecated since llmslim 1.0.0rc1 and will be removed in "
        f"2.0; use {module.__name__}.{name} instead."
    )
    assert caught[0].filename == __file__


def test_a_from_import_warns_at_the_import():
    with pytest.warns(
        DeprecationWarning, match=r"use llmslim\.integrations\.sarvam_documents\."
    ) as caught:
        from llmslim.integrations.sarvam import DEFAULT_DOCUMENT_LIMITS, DOCUMENT_GUARD_PREFIX
    assert DEFAULT_DOCUMENT_LIMITS == sarvam_documents.DEFAULT_DOCUMENT_LIMITS
    assert DOCUMENT_GUARD_PREFIX == "sarvam_document"
    assert [warning.filename for warning in caught] == [__file__, __file__]


def test_they_are_not_public_and_a_star_import_neither_takes_them_nor_warns():
    assert not set(MOVED) & set(sarvam.__all__)
    namespace: dict = {}
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        exec("from llmslim.integrations.sarvam import *", namespace)
    assert not set(MOVED) & set(namespace)
    assert "SarvamProvider" in namespace


def test_other_missing_names_still_fail():
    with pytest.raises(ImportError):
        exec("from llmslim.integrations.sarvam import DEFAULT_LIMITS", {})
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert not hasattr(sarvam, "DEFAULT_LIMITS")


def test_importing_the_module_does_not_warn():
    code = (
        "import warnings\n"
        "with warnings.catch_warnings(record=True) as caught:\n"
        "    warnings.simplefilter('always')\n"
        "    import llmslim.integrations.sarvam\n"
        "print(sum('deprecated since llmslim' in str(warning.message) for warning in caught))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, timeout=120
    )
    assert result.stdout.strip() == "0"
