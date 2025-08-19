# SPDX-License-Identifier: EUPL-1.2
#
# SPDX-FileCopyrightText: © 2025-present Jürgen Mülbert
#

"""
pytest-mock based tests for the DocChecker class.
"""
from pathlib import Path
from unittest.mock import MagicMock, mock_open

import pytest

from jm_reusable_scripts.doc_quality import DocChecker
from jm_reusable_scripts.utils.doc_config import DocConfig


@pytest.fixture
def mock_console(mocker):
    """Fixture to mock the rich console for silent testing."""
    return mocker.patch("jm_reusable_scripts.doc_quality.console", autospec=True)


@pytest.fixture
def mock_config(mocker):
    """Fixture to create a mock DocConfig object."""
    mocked_config = mocker.MagicMock(spec=DocConfig)
    mocked_config.min_length = 50
    mocked_config.code_example_required = True
    mocked_config.required_sections = {"Introduction", "Conclusion"}
    mocked_config.image_required = True
    mocked_config.supported_languages = {"en", "de"}
    return mocked_config


@pytest.fixture
def checker(mock_config):
    """Fixture to create a DocChecker instance with a mock config."""
    return DocChecker(config=mock_config)


def test_init_sets_correct_attributes(checker, mock_config):
    """Test that the DocChecker is initialized correctly."""
    assert checker.config == mock_config
    assert isinstance(checker.issues, dict)
    assert not checker.issues


# --- _read_file tests ---


def test_read_file_success(mocker, checker):
    """Test _read_file reads content successfully."""
    mock_file = "This is some test content for the file."
    mocker.patch("builtins.open", mock_open(read_data=mock_file))
    mock_path = Path("test.md")
    content = checker._read_file(mock_path)
    assert content == mock_file


def test_read_file_not_found(mocker, checker, mock_console):
    """Test _read_file handles FileNotFoundError."""
    mocker.patch("builtins.open", side_effect=FileNotFoundError)
    mock_path = Path("nonexistent.md")
    content = checker._read_file(mock_path)
    assert content is None
    assert checker.issues[str(mock_path)] == ["File not found"]
    mock_console.print.assert_called_with(
        "[error]File not found: nonexistent.md[/error]"
    )


def test_read_file_os_error(mocker, checker, mock_console):
    """Test _read_file handles OSError."""
    mocker.patch("builtins.open", side_effect=OSError("Permission denied"))
    mock_path = Path("protected.md")
    content = checker._read_file(mock_path)
    assert content is None
    assert "Error reading file" in checker.issues[str(mock_path)][0]
    mock_console.print.assert_called_with(
        "[error]Error reading file: protected.md - Permission denied[/error]"
    )


# --- _perform_checks tests ---


@pytest.mark.parametrize(
    "content, expected_issues",
    [
        ("A very short doc.", ["[warning]Content too short (14 chars)[/warning]"]),
        (
            "# Title\n\nThis is a longer doc.",
            [],
        ),  # Assuming it passes the length check
    ],
)
def test_perform_checks_min_length(checker, content, expected_issues):
    """Test min_length check."""
    checker.config.min_length = 50
    file_path = Path("test.md")
    issues = checker._perform_checks(file_path, content)
    # Filter for the specific issue we are testing
    assert (
        any("[warning]Content too short" in issue for issue in issues)
        == ("[warning]Content too short (14 chars)[/warning]" in expected_issues)
    )


@pytest.mark.parametrize(
    "content, expected_issue",
    [
        ("No header content.", "[error]Missing main header[/error]"),
        ("# My Header\nSome content.", None),
    ],
)
def test_perform_checks_main_header(checker, content, expected_issue):
    """Test main header check."""
    file_path = Path("test.md")
    issues = checker._perform_checks(file_path, content)
    if expected_issue:
        assert expected_issue in issues
    else:
        assert "[error]Missing main header[/error]" not in issues


def test_perform_checks_code_example_required(checker):
    """Test code example check."""
    checker.config.code_example_required = True
    content_no_code = "# Title\nNo code here."
    content_with_code = "# Title\n```python\nprint('hello')\n```"
    issues_no_code = checker._perform_checks(Path("test.md"), content_no_code)
    issues_with_code = checker._perform_checks(Path("test.md"), content_with_code)
    assert "[warning]No code examples found[/warning]" in issues_no_code
    assert "[warning]No code examples found[/warning]" not in issues_with_code


def test_perform_checks_required_sections(checker):
    """Test required sections check."""
    checker.config.required_sections = {"Introduction", "Conclusion"}
    content_missing = "# Title\n## Introduction"
    content_present = "# Title\n## Introduction\n\n## Conclusion"
    issues_missing = checker._perform_checks(Path("test.md"), content_missing)
    issues_present = checker._perform_checks(Path("test.md"), content_present)
    assert "[error]Missing required sections: Conclusion[/error]" in issues_missing
    assert "[error]Missing required sections" not in issues_present


def test_perform_checks_image_required(checker):
    """Test image check."""
    checker.config.image_required = True
    content_no_image = "# Title\nNo image here."
    content_with_image = "# Title\n![alt text](image.png)"
    issues_no_image = checker._perform_checks(Path("test.md"), content_no_image)
    issues_with_image = checker._perform_checks(Path("test.md"), content_with_image)
    assert "[warning]No images found[/warning]" in issues_no_image
    assert "[warning]No images found[/warning]" not in issues_with_image


def test_perform_checks_invalid_link(checker):
    """Test link validation."""
    content_invalid_link = "# Title\n[Link](invalid-link)"
    issues_invalid_link = checker._perform_checks(Path("test.md"), content_invalid_link)
    assert "[error]Invalid link: invalid-link[/error]" in issues_invalid_link


def test_perform_checks_supported_language(checker):
    """Test language support check."""
    checker.config.supported_languages = {"en", "de"}
    file_path_valid = Path("doc.en.md")
    file_path_invalid = Path("doc.fr.md")
    issues_valid = checker._perform_checks(file_path_valid, "# Title")
    issues_invalid = checker._perform_checks(file_path_invalid, "# Title")
    assert "[error]Unsupported language: fr[/error]" in issues_invalid
    assert "[error]Unsupported language" not in issues_valid


# --- _get_language_code tests ---


def test_get_language_code_returns_correct_code(checker):
    """Test _get_language_code returns the correct language."""
    checker.config.supported_languages = {"en", "de", "fr"}
    path = Path("docs/my-file.en.md")
    assert checker._get_language_code(path) == "en"


def test_get_language_code_returns_none_for_no_suffix(checker):
    """Test _get_language_code returns None for files without a language suffix."""
    path = Path("docs/my-file.md")
    assert checker._get_language_code(path) is None


def test_get_language_code_returns_none_for_unsupported_language(checker):
    """Test _get_language_code returns None for unsupported languages."""
    checker.config.supported_languages = {"en", "de"}
    path = Path("docs/my-file.es.md")
    assert checker._get_language_code(path) is None


# --- check_translations tests ---


def test_check_translations_finds_missing_translations(mocker, checker, mock_console):
    """Test check_translations correctly identifies missing files."""
    checker.config.supported_languages = {"de"}
    mock_docs_dir = Path("/mock/docs")
    mocker.patch.object(
        Path, "rglob", return_value=[Path("file.md"), Path("another.de.md")]
    )
    checker.check_translations(mock_docs_dir)
    assert checker.issues["Missing de translations"] == ["file.md"]
    mock_console.print.assert_any_call("[warning]Missing de translations:[/warning]")
    mock_console.print.assert_any_call("  - file.md")


def test_check_translations_finds_no_missing_translations(mocker, checker, mock_console):
    """Test check_translations finds no missing translations when all are present."""
    checker.config.supported_languages = {"de"}
    mock_docs_dir = Path("/mock/docs")
    mocker.patch.object(
        Path, "rglob", return_value=[Path("file.md"), Path("file.de.md")]
    )
    checker.check_translations(mock_docs_dir)
    assert not checker.issues
    mock_console.print.assert_not_called()


# --- check_markdown tests ---


def test_check_markdown_with_issues(mocker, checker, mock_console):
    """Test check_markdown for a file with issues."""
    content = "short doc."
    mock_read_file = mocker.patch.object(checker, "_read_file", return_value=content)
    mock_perform_checks = mocker.patch.object(
        checker, "_perform_checks", return_value=["Issue 1", "Issue 2"]
    )
    mock_path = Path("test.md")
    checker.check_markdown(mock_path)
    mock_read_file.assert_called_once_with(mock_path)
    mock_perform_checks.assert_called_once_with(mock_path, content)
    assert checker.issues[str(mock_path)] == ["Issue 1", "Issue 2"]
    mock_console.print.assert_any_call("[file]test.md[/file]:")
    mock_console.print.assert_any_call("  - Issue 1")
    mock_console.print.assert_any_call("  - Issue 2")


def test_check_markdown_without_issues(mocker, checker, mock_console):
    """Test check_markdown for a file with no issues."""
    content = "# Title\n\nThis is a long document with code:\n\n```python\nprint('hello')\n```"
    mocker.patch.object(checker, "_read_file", return_value=content)
    mocker.patch.object(checker, "_perform_checks", return_value=[])
    mock_path = Path("test.md")
    checker.check_markdown(mock_path)
    assert not checker.issues
    mock_console.print.assert_not_called()


def test_check_markdown_file_read_fails(mocker, checker, mock_console):
    """Test that check_markdown handles a failed file read."""
    mocker.patch.object(checker, "_read_file", return_value=None)
    mocker.patch.object(checker, "_perform_checks")
    mock_path = Path("test.md")
    checker.check_markdown(mock_path)
    # _perform_checks should not be called if _read_file returns None
    checker._perform_checks.assert_not_called()
    mock_console.print.assert_not_called()


# --- generate_report tests ---


def test_generate_report_with_issues(checker, mock_console):
    """Test generate_report with issues to report."""
    checker.issues = {"file1.md": ["Issue A"], "file2.md": ["Issue B", "Issue C"]}
    checker.generate_report()
    mock_console.print.assert_called_once()
    assert isinstance(mock_console.print.call_args[0][0], MagicMock)


def test_generate_report_no_issues(checker, mock_console):
    """Test generate_report with no issues found."""
    checker.issues = {}
    checker.generate_report()
    mock_console.print.assert_any_call(
        checker.console.Panel(
            "[success]Documentation quality check passed![/success]",
            border_style="success",
        )
    )
    mock_console.print.assert_any_call(
        checker.console.Panel(
            "[success]Documentation quality check passed![/success]",
            border_style="success",
        )
    )
    assert mock_console.print.call_count == 2
