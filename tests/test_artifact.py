
import pytest
from src import artifact

def test_trim_all_lines():
    assert artifact.trim_all_lines("  hello\n  world\n") == "hello\nworld\n"

def test_prefix_lines():
    assert artifact.prefix_lines("hello\nworld\n", "prefix: ") == "prefix: hello\nprefix: world"

def test_extract_gerrit_change_id():
    commit_message = "Some changes\n\nChange-Id: I8473b920f2b0d34f2ef5ddbfdf3bea5db12c99d7"
    assert artifact.extract_gerrit_change_id(commit_message, "Change Id: ") == "Change Id: I8473b920f2b0d34f2ef5ddbfdf3bea5db12c99d7"

def test_string_trunc_ellipsis():
    assert artifact.string_trunc_ellipsis(5, "hello world") == "he..."
