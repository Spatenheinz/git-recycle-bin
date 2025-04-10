import pytest
import datetime
from dateutil.tz import tzlocal
import os
from contextlib import contextmanager
import subprocess
from typing import Set

from src import git_recycle_bin as grb  # DUT

def test_trim_all_lines():
    assert grb.trim_all_lines("  hello\n  world\n") == "hello\nworld\n"

def test_prefix_lines():
    assert grb.prefix_lines("hello\nworld\n", "prefix: ") == "prefix: hello\nprefix: world"

def test_extract_gerrit_change_id():
    commit_message = "Some changes\n\nChange-Id: I8473b920f2b0d34f2ef5ddbfdf3bea5db12c99d7"
    assert grb.extract_gerrit_change_id(commit_message) == "I8473b920f2b0d34f2ef5ddbfdf3bea5db12c99d7"

def test_string_trunc_ellipsis():
    assert grb.string_trunc_ellipsis(5, "hello world") == "he..."

def test_date_formatted2unix():
    assert grb.date_formatted2unix("Wed, 21 Jun 2023 14:13:31 +0200", "%a, %d %b %Y %H:%M:%S %z") == 1687349611

def test_absolute_date():
    assert grb.date_fuzzy2expiryformat("2023-07-27 CEST") == "2023-07-27/00.00+0200"
    assert grb.date_fuzzy2expiryformat("Mon, 1 Feb 1994 21:21:42 GMT") == "1994-02-01/22.21+0100"

def test_relative_date():
    assert grb.date_fuzzy2expiryformat("now") == datetime.datetime.now(tzlocal()).strftime(grb.DATE_FMT_EXPIRE)
    assert grb.date_fuzzy2expiryformat("today") == datetime.datetime.now(tzlocal()).strftime(grb.DATE_FMT_EXPIRE)

    assert grb.date_fuzzy2expiryformat("tomorrow") == (datetime.datetime.now(tzlocal()) + datetime.timedelta(days=1)).strftime(grb.DATE_FMT_EXPIRE)

    assert grb.date_fuzzy2expiryformat("now in 3 weeks") == (datetime.datetime.now(tzlocal()) + datetime.timedelta(days=21)).strftime(grb.DATE_FMT_EXPIRE)
    assert grb.date_fuzzy2expiryformat("now in 3 week") == (datetime.datetime.now(tzlocal()) + datetime.timedelta(days=21)).strftime(grb.DATE_FMT_EXPIRE)
    assert grb.date_fuzzy2expiryformat("now in 3weeks") == (datetime.datetime.now(tzlocal()) + datetime.timedelta(days=21)).strftime(grb.DATE_FMT_EXPIRE)
    assert grb.date_fuzzy2expiryformat("in 3 weeks") == (datetime.datetime.now(tzlocal()) + datetime.timedelta(days=21)).strftime(grb.DATE_FMT_EXPIRE)
    assert grb.date_fuzzy2expiryformat("in 3weeks") == (datetime.datetime.now(tzlocal()) + datetime.timedelta(days=21)).strftime(grb.DATE_FMT_EXPIRE)
    assert grb.date_fuzzy2expiryformat("in 3week") == (datetime.datetime.now(tzlocal()) + datetime.timedelta(days=21)).strftime(grb.DATE_FMT_EXPIRE)
    assert grb.date_fuzzy2expiryformat("in 3w") == (datetime.datetime.now(tzlocal()) + datetime.timedelta(days=21)).strftime(grb.DATE_FMT_EXPIRE)

    assert grb.date_fuzzy2expiryformat("in 30 days") == (datetime.datetime.now(tzlocal()) + datetime.timedelta(days=30)).strftime(grb.DATE_FMT_EXPIRE)
    assert grb.date_fuzzy2expiryformat("in 30 day") == (datetime.datetime.now(tzlocal()) + datetime.timedelta(days=30)).strftime(grb.DATE_FMT_EXPIRE)
    assert grb.date_fuzzy2expiryformat("in 30days") == (datetime.datetime.now(tzlocal()) + datetime.timedelta(days=30)).strftime(grb.DATE_FMT_EXPIRE)
    assert grb.date_fuzzy2expiryformat("in 30day") == (datetime.datetime.now(tzlocal()) + datetime.timedelta(days=30)).strftime(grb.DATE_FMT_EXPIRE)

    assert grb.date_fuzzy2expiryformat("next month") == grb.date_fuzzy2expiryformat("now in 1 month")

def test_invalid_date():
    with pytest.raises(ValueError):
        grb.date_fuzzy2expiryformat("invalid")
    with pytest.raises(ValueError):
        assert grb.date_fuzzy2expiryformat("Mon, 32 Feb 1994 21:21:42 GMT") == "there is no Feb 32"

def test_parse_expire_datetime():
    p = "artifact/expire/"
    assert grb.parse_expire_date(prefix_discard=p, expiry_formatted="artifact/expire/2023-07-27/16.12")       == {"date":"2023-07-27", "time":"16.12", "tzoffset":None}
    assert grb.parse_expire_date(prefix_discard=p, expiry_formatted="artifact/expire/2023-07-27/16.12/")      == {"date":"2023-07-27", "time":"16.12", "tzoffset":None}
    assert grb.parse_expire_date(prefix_discard=p, expiry_formatted="artifact/expire/2023-07-27/16.12/foo")   == {"date":"2023-07-27", "time":"16.12", "tzoffset":None}
    assert grb.parse_expire_date(prefix_discard=p, expiry_formatted="artifact/expire/2023-07-27/16.12/2023-08-17/06.02/foo")   == {"date":"2023-07-27", "time":"16.12", "tzoffset":None}
    assert grb.parse_expire_date(prefix_discard=p, expiry_formatted="artifact/expire/2023-07-27/16.12+0200")  == {"date":"2023-07-27", "time":"16.12", "tzoffset":"+0200"}
    assert grb.parse_expire_date(prefix_discard=p, expiry_formatted="artifact/expire/2023-07-27/16.12+0200/") == {"date":"2023-07-27", "time":"16.12", "tzoffset":"+0200"}
    assert grb.parse_expire_date(prefix_discard=p, expiry_formatted="artifact/expire/2023-07-27/16.12-0200")  == {"date":"2023-07-27", "time":"16.12", "tzoffset":"-0200"}
    assert grb.parse_expire_date(prefix_discard=p, expiry_formatted="artifact/expire/2023-07-27/16.12-03")    == {"date":"2023-07-27", "time":"16.12", "tzoffset":None}
    assert grb.parse_expire_date(prefix_discard="", expiry_formatted="2023-07-27/16.12")  == {"date":"2023-07-27", "time":"16.12", "tzoffset":None}
    assert grb.parse_expire_date(prefix_discard="", expiry_formatted="2023-07-27/16.12/") == {"date":"2023-07-27", "time":"16.12", "tzoffset":None}

def test_parse_expire_datetime_invalid():
    assert grb.parse_expire_date(prefix_discard="artifact/expire/", expiry_formatted="artifact/expire/30d/") == {"date":None, "time":None, "tzoffset":None}

def test_url_redact():
    assert grb.url_redact(url="https://foo:pass@service/my/repo.git", replacement="REDACTED") == "https://foo:REDACTED@service/my/repo.git"
    assert grb.url_redact(url="https://foo@service/my/repo.git", replacement="REDACTED")      == "https://foo@service/my/repo.git"
    assert grb.url_redact(url="https://service/my/repo.git", replacement="REDACTED")          == "https://service/my/repo.git"
    assert grb.url_redact(url="https://service/my/re:po.git", replacement="REDACTED")         == "https://service/my/re:po.git"
    assert grb.url_redact(url="https://service/my/re:po@hmm.git", replacement="REDACTED")     == "https://service/my/re:po@hmm.git"

    assert grb.url_redact(url="ssh://foo:pass@service/my/repo.git", replacement="REDACTED")   == "ssh://foo:REDACTED@service/my/repo.git"
    assert grb.url_redact(url="ssh://foo@service/my/repo.git", replacement="REDACTED")        == "ssh://foo@service/my/repo.git"
    assert grb.url_redact(url="ssh://service/my/repo.git", replacement="REDACTED")            == "ssh://service/my/repo.git"
    assert grb.url_redact(url="ssh://service/my/re:po.git", replacement="REDACTED")           == "ssh://service/my/re:po.git"
    assert grb.url_redact(url="ssh://service/my/re:po@hmm.git", replacement="REDACTED")       == "ssh://service/my/re:po@hmm.git"

    assert grb.url_redact(url="foo:pass@service/my/repo.git", replacement="REDACTED") == "foo:pass@service/my/repo.git"
    assert grb.url_redact(url="foo@service/my/repo.git", replacement="REDACTED")      == "foo@service/my/repo.git"
    assert grb.url_redact(url="service/my/repo.git", replacement="REDACTED")          == "service/my/repo.git"
    assert grb.url_redact(url="service/my/re:po.git", replacement="REDACTED")         == "service/my/re:po.git"
    assert grb.url_redact(url="service/my/re:po@hmm.git", replacement="REDACTED")     == "service/my/re:po@hmm.git"


@pytest.fixture
def temp_git_setup(tmpdir):
    # Create temporary directories
    local_repo = tmpdir.mkdir("local_repo")
    remote_repo = tmpdir.mkdir("remote_repo")
    artifact_repo = tmpdir.mkdir("artifact_repo")

    # Initialize the 'remote' repository
    subprocess.run(['git', 'init', '--bare'], cwd=remote_repo, check=True)

    # Initialize the local repository
    subprocess.run(['git', 'init'], cwd=local_repo, check=True)

    # Initialize the artifact repository
    subprocess.run(['git', 'init', '--bare'], cwd=artifact_repo, check=True)

    # Add the remote
    remote_url = f"file://{remote_repo}"
    subprocess.run(['git', 'remote', 'add', 'origin', remote_url], cwd=local_repo, check=True)

    # add some files to the local repository
    local_file = local_repo.join("example.txt")
    local_file.write("This is a test file.")
    with git_user_info():
        subprocess.run(['git', 'add', 'example.txt'], cwd=local_repo, check=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=local_repo, check=True)
        subprocess.run(['git', 'push', 'origin', 'master'], cwd=local_repo, check=True)

    # Return both directories as a tuple to be used in tests
    yield (local_repo, remote_repo, artifact_repo, [(local_file, "example.txt")])


@contextmanager
def change_dir(path):
    original_dir = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(original_dir)

@contextmanager
def git_user_info():
    old_env = os.environ.copy()
    os.environ["GIT_AUTHOR_NAME"] = "mock"
    os.environ["GIT_AUTHOR_EMAIL"] = "mock@mock.mock"
    os.environ["GIT_COMMITTER_NAME"] = "mock"
    os.environ["GIT_COMMITTER_EMAIL"] = "mock@mock.mock"
    try:
        yield
    finally:
        os.environ = old_env


def contains_metas(rbgit: grb.RbGit, remote: str, commit_shas: Set[str]) -> bool:
    metas = rbgit.meta_for_commit_refs(remote)
    assert commit_shas == { meta[-40:] for meta in metas }
    # return True to allow us to do assert contains_metas which reads better than
    # just contains_metas
    return True

def test_flush_meta_for_commit(temp_git_setup):
    local, _, artifact_remote, artifacts = temp_git_setup
    artifact_path, artifact_name = artifacts[0]

    _args = ["push", f"{artifact_remote}",
             "--path", f"{artifact_path}",
             "--name", artifact_name,
             ]
    _dead = _args + ["--expire", "2 hours ago"]
    dead = grb.parse_args(_dead)
    longlived = grb.parse_args(_args + ["--expire", "in 30 days"])
    dead_flush = grb.parse_args(_dead + ["--flush-meta"])
    dead_rm_flush = grb.parse_args(_dead + ["--rm-expired", "--flush-meta"])
    dead_rm = grb.parse_args(_dead + ["--rm-expired"])

    rbgit=grb.create_rbgit(local, dead.path, clean=True)
    rb_remote="rbgit"

    def push(args):
        return grb.push(args, rbgit, rb_remote, artifact_name)['bin_sha_commit']

    with change_dir(local), git_user_info():
        bin_commit = push(dead)
        assert contains_metas(rbgit, rb_remote, {bin_commit})

        # without --remove-expired the refs should still exist
        bin_commit2 = push(dead_flush)
        assert contains_metas(rbgit, rb_remote, {bin_commit, bin_commit2})

        # with --remove-expired the refs should be removed
        push(dead_rm_flush)
        assert contains_metas(rbgit, rb_remote, set())

        # with only --remove-expired the refs should not be removed
        bin_commit = push(dead_rm)
        assert contains_metas(rbgit, rb_remote, {bin_commit})

        # with --flush-meta the new artifact should not be removed but the old one should
        bin_commit = push(dead_flush)
        assert contains_metas(rbgit, rb_remote, {bin_commit})

        # only the longlived artifact should be present
        bin_commit = push(longlived)
        push(dead_rm_flush)
        assert contains_metas(rbgit, rb_remote, {bin_commit})
