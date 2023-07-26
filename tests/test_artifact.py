
import pytest
from src import artifact

def test_trim_all_lines():
    assert artifact.trim_all_lines("  hello\n  world\n") == "hello\nworld\n"

def test_prefix_lines():
    assert artifact.prefix_lines("hello\nworld\n", "prefix: ") == "prefix: hello\nprefix: world"

def test_extract_gerrit_change_id():
    commit_message = "Some changes\n\nChange-Id: I8473b920f2b0d34f2ef5ddbfdf3bea5db12c99d7"
    assert artifact.extract_gerrit_change_id(commit_message) == "I8473b920f2b0d34f2ef5ddbfdf3bea5db12c99d7"

def test_string_trunc_ellipsis():
    assert artifact.string_trunc_ellipsis(5, "hello world") == "he..."

def test_date_formatted2unix():
	assert artifact.date_formatted2unix("Wed, 21 Jun 2023 14:13:31 +0200", "%a, %d %b %Y %H:%M:%S %z") == 1687349611
