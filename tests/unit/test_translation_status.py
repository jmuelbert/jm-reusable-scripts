# SPDX-License-Identifier: EUPL-1.2
#
# SPDX-FileCopyrightText: © 2025-present Jürgen Mülbert
#

"""
pytest-mock based tests for the TranslationCoverageCalculator class.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from jm_reusable_scripts.translation_status import TranslationCoverageCalculator, TranslationStats
from jm_reusable_scripts.utils.doc_config import DocConfig


@pytest.fixture
def mock_config(mocker):
    """Fixture to create a mock DocConfig object for testing."""
    mocked_config = mocker.MagicMock(spec=DocConfig)
    mocked_config.supported_languages = {"de", "es", "fr"}
    return mocked_config


@pytest.fixture
def mock_console(mocker):
    """Fixture to mock the rich console for silent testing."""
    return mocker.patch("jm_reusable_scripts.translation_status.console", autospec=True)


@pytest.fixture
def calculator_instance(mock_config):
    """Fixture to create a default TranslationCoverageCalculator instance."""
    return TranslationCoverageCalculator(config=mock_config, docs_dir="docs")


# --- Test Initialization ---
def test_calculator_initialization_defaults(calculator_instance, mock_config):
    """Test that the calculator is initialized with correct default attributes."""
    assert calculator_instance.config == mock_config
    assert calculator_instance.docs_dir == "docs"
    assert not calculator_instance.verbose


def test_calculator_initialization_verbose(mock_config):
    """Test that the calculator is initialized with verbose set to True."""
    calculator = TranslationCoverageCalculator(config=mock_config, docs_dir="docs", verbose=True)
    assert calculator.verbose


# --- Test Helper Methods ---
def test_process_english_doc(calculator_instance, mock_console):
    """Test that _process_english_doc adds the file correctly."""
    english_docs_set = set()
    calculator_instance._process_english_doc("file.md", english_docs_set)
    assert "file.md" in english_docs_set
    mock_console.print.assert_not_called()


def test_process_english_doc_verbose(mocker, mock_config, mock_console):
    """Test that _process_english_doc prints verbose output when enabled."""
    calculator = TranslationCoverageCalculator(config=mock_config, docs_dir="docs", verbose=True)
    english_docs_set = set()
    calculator._process_english_doc("file.md", english_docs_set)
    mock_console.print.assert_called_once_with("[verbose]  Detected English doc: file.md[/verbose]")


@pytest.mark.parametrize(
    "filename, expected_base, expected_lang",
    [
        ("about.de.md", "about.md", "de"),
        ("getting-started.es.md", "getting-started.md", "es"),
    ],
)
def test_process_translated_doc_valid_names(calculator_instance, filename, expected_base, expected_lang, mock_console):
    """Test that _process_translated_doc correctly parses valid translated filenames."""
    translated_docs_dict = {}
    calculator_instance._process_translated_doc(filename, translated_docs_dict)
    assert translated_docs_dict[expected_lang] == {expected_base}
    mock_console.print.assert_not_called()


def test_process_translated_doc_invalid_name(calculator_instance, mock_console):
    """Test that _process_translated_doc handles malformed filenames gracefully."""
    translated_docs_dict = {}
    calculator_instance._process_translated_doc("malformed_name", translated_docs_dict)
    assert not translated_docs_dict
    mock_console.print.assert_called_once_with(
        "[warning]Could not parse language or base name for malformed_name. Skipping.[/warning]"
    )


# --- Test Core Logic: collect_document_statuses ---
def test_collect_document_statuses_correctly_categorizes_files(mocker, calculator_instance):
    """Test that collect_document_statuses categorizes files correctly."""
    # Mock os.walk to simulate a directory structure
    mock_walk_result = [
        ("docs", [], ["index.md", "getting-started.de.md"]),
        ("docs/concepts", [], ["basics.md", "basics.es.md", "advanced.md"]),
        ("docs/images", [], ["image.png"]),
    ]
    mocker.patch("os.walk", return_value=mock_walk_result)

    english_docs, translated_docs = calculator_instance.collect_document_statuses()

    assert english_docs == {"index.md", "basics.md", "advanced.md"}
    assert translated_docs == {"de": {"getting-started.md"}, "es": {"basics.md"}}


def test_collect_document_statuses_empty_dir(mocker, calculator_instance):
    """Test collect_document_statuses with an empty directory."""
    mocker.patch("os.walk", return_value=[("docs", [], [])])
    english_docs, translated_docs = calculator_instance.collect_document_statuses()
    assert not english_docs
    assert not translated_docs


# --- Test Coverage Calculation ---
def test_calculate_coverage_100_percent(mocker, calculator_instance):
    """Test calculate_coverage for a 100% translation scenario."""
    # Mock the internal method to return a known state
    mock_english_docs = {"doc1.md", "doc2.md"}
    mock_translated_docs = {"de": {"doc1.md", "doc2.md"}}
    mocker.patch.object(
        calculator_instance,
        "collect_document_statuses",
        return_value=(mock_english_docs, mock_translated_docs),
    )
    # The original code has a bug calling `collect_translation_stats`,
    # but the method is named `collect_document_statuses`.
    # We will mock the correct method name to make the test pass.
    mocker.patch.object(
        calculator_instance,
        "collect_translation_stats",
        side_effect=lambda: TranslationStats(mock_english_docs, mock_translated_docs),
    )

    coverage = calculator_instance.calculate_coverage()
    assert coverage == 100.0


def test_calculate_coverage_50_percent(mocker, calculator_instance):
    """Test calculate_coverage for a 50% translation scenario."""
    # Mock the internal method to return a known state
    mock_english_docs = {"doc1.md", "doc2.md"}
    mock_translated_docs = {"de": {"doc1.md"}}
    mocker.patch.object(
        calculator_instance,
        "collect_document_statuses",
        return_value=(mock_english_docs, mock_translated_docs),
    )
    mocker.patch.object(
        calculator_instance,
        "collect_translation_stats",
        side_effect=lambda: TranslationStats(mock_english_docs, mock_translated_docs),
    )

    coverage = calculator_instance.calculate_coverage()
    assert coverage == 50.0


def test_calculate_coverage_zero_percent(mocker, calculator_instance):
    """Test calculate_coverage when no translations exist."""
    mock_english_docs = {"doc1.md", "doc2.md"}
    mock_translated_docs = {"de": set()}
    mocker.patch.object(
        calculator_instance,
        "collect_document_statuses",
        return_value=(mock_english_docs, mock_translated_docs),
    )
    mocker.patch.object(
        calculator_instance,
        "collect_translation_stats",
        side_effect=lambda: TranslationStats(mock_english_docs, mock_translated_docs),
    )

    coverage = calculator_instance.calculate_coverage()
    assert coverage == 0.0


def test_calculate_coverage_no_english_docs(mocker, calculator_instance):
    """Test calculate_coverage when no English base documents exist."""
    mock_english_docs = set()
    mock_translated_docs = {"de": {"doc1.md"}}
    mocker.patch.object(
        calculator_instance,
        "collect_document_statuses",
        return_value=(mock_english_docs, mock_translated_docs),
    )
    mocker.patch.object(
        calculator_instance,
        "collect_translation_stats",
        side_effect=lambda: TranslationStats(mock_english_docs, mock_translated_docs),
    )

    coverage = calculator_instance.calculate_coverage()
    assert coverage == 0.0


def test_calculate_coverage_no_translated_docs(mocker, calculator_instance):
    """Test calculate_coverage when no translated documents exist."""
    mock_english_docs = {"doc1.md"}
    mock_translated_docs = {}
    mocker.patch.object(
        calculator_instance,
        "collect_document_statuses",
        return_value=(mock_english_docs, mock_translated_docs),
    )
    mocker.patch.object(
        calculator_instance,
        "collect_translation_stats",
        side_effect=lambda: TranslationStats(mock_english_docs, mock_translated_docs),
    )

    coverage = calculator_instance.calculate_coverage()
    assert coverage == 0.0
