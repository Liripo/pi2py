from __future__ import annotations

import importlib
import logging
import sys

from pi2py.core.litellm_client import _quiet_litellm_optional_dependency_warnings


def test_quiet_litellm_optional_dependency_warnings(monkeypatch) -> None:
    monkeypatch.delenv("LITELLM_LOG", raising=False)
    logging.getLogger("LiteLLM").setLevel(logging.NOTSET)

    _quiet_litellm_optional_dependency_warnings()

    assert logging.getLogger("LiteLLM").level == logging.ERROR


def test_litellm_import_does_not_print_optional_dependency_warnings(monkeypatch, capsys) -> None:
    monkeypatch.delenv("LITELLM_LOG", raising=False)
    sys.modules.pop("litellm", None)

    _quiet_litellm_optional_dependency_warnings()
    importlib.import_module("litellm")

    captured = capsys.readouterr()
    assert "could not pre-load bedrock-runtime response stream shape" not in captured.err
    assert "could not pre-load sagemaker-runtime response stream shape" not in captured.err
    assert logging.getLogger("LiteLLM").level == logging.ERROR
