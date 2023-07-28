import pytest
import datetime
from dateutil.tz import tzlocal

from src import artifact  # DUT

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

def test_absolute_date():
    assert artifact.date_fuzzy2expiryformat("2023-07-27 CEST") == "2023-07-27/00.00+0200"
    assert artifact.date_fuzzy2expiryformat("Mon, 1 Feb 1994 21:21:42 GMT") == "1994-02-01/22.21+0100"

def test_relative_date():
    assert artifact.date_fuzzy2expiryformat("now") == datetime.datetime.now(tzlocal()).strftime(artifact.date_fmt_expire)
    assert artifact.date_fuzzy2expiryformat("today") == datetime.datetime.now(tzlocal()).strftime(artifact.date_fmt_expire)

    assert artifact.date_fuzzy2expiryformat("tomorrow") == (datetime.datetime.now(tzlocal()) + datetime.timedelta(days=1)).strftime(artifact.date_fmt_expire)

    assert artifact.date_fuzzy2expiryformat("now in 3 weeks") == (datetime.datetime.now(tzlocal()) + datetime.timedelta(days=21)).strftime(artifact.date_fmt_expire)
    assert artifact.date_fuzzy2expiryformat("now in 3 week") == (datetime.datetime.now(tzlocal()) + datetime.timedelta(days=21)).strftime(artifact.date_fmt_expire)
    assert artifact.date_fuzzy2expiryformat("now in 3weeks") == (datetime.datetime.now(tzlocal()) + datetime.timedelta(days=21)).strftime(artifact.date_fmt_expire)
    assert artifact.date_fuzzy2expiryformat("in 3 weeks") == (datetime.datetime.now(tzlocal()) + datetime.timedelta(days=21)).strftime(artifact.date_fmt_expire)
    assert artifact.date_fuzzy2expiryformat("in 3weeks") == (datetime.datetime.now(tzlocal()) + datetime.timedelta(days=21)).strftime(artifact.date_fmt_expire)
    assert artifact.date_fuzzy2expiryformat("in 3week") == (datetime.datetime.now(tzlocal()) + datetime.timedelta(days=21)).strftime(artifact.date_fmt_expire)
    assert artifact.date_fuzzy2expiryformat("in 3w") == (datetime.datetime.now(tzlocal()) + datetime.timedelta(days=21)).strftime(artifact.date_fmt_expire)

    assert artifact.date_fuzzy2expiryformat("in 30 days") == (datetime.datetime.now(tzlocal()) + datetime.timedelta(days=30)).strftime(artifact.date_fmt_expire)
    assert artifact.date_fuzzy2expiryformat("in 30 day") == (datetime.datetime.now(tzlocal()) + datetime.timedelta(days=30)).strftime(artifact.date_fmt_expire)
    assert artifact.date_fuzzy2expiryformat("in 30days") == (datetime.datetime.now(tzlocal()) + datetime.timedelta(days=30)).strftime(artifact.date_fmt_expire)
    assert artifact.date_fuzzy2expiryformat("in 30day") == (datetime.datetime.now(tzlocal()) + datetime.timedelta(days=30)).strftime(artifact.date_fmt_expire)

    assert artifact.date_fuzzy2expiryformat("next month") == artifact.date_fuzzy2expiryformat("now in 1 month")

    assert artifact.date_fuzzy2expiryformat("2 weeks and 1 day ago") == (datetime.datetime.now(tzlocal()) - datetime.timedelta(days=15)).strftime(artifact.date_fmt_expire)

def test_invalid_date():
    with pytest.raises(ValueError):
        artifact.date_fuzzy2expiryformat("invalid")
    with pytest.raises(ValueError):
        assert artifact.date_fuzzy2expiryformat("Mon, 32 Feb 1994 21:21:42 GMT") == "there is no Feb 32"

def test_parse_expire_datetime():
    p = "artifact/expire/"
    assert artifact.parse_expire_date(prefix_discard=p, expiry_formatted="artifact/expire/2023-07-27/16.12")       == {"date":"2023-07-27", "time":"16.12", "tzoffset":None}
    assert artifact.parse_expire_date(prefix_discard=p, expiry_formatted="artifact/expire/2023-07-27/16.12/")      == {"date":"2023-07-27", "time":"16.12", "tzoffset":None}
    assert artifact.parse_expire_date(prefix_discard=p, expiry_formatted="artifact/expire/2023-07-27/16.12/foo")   == {"date":"2023-07-27", "time":"16.12", "tzoffset":None}
    assert artifact.parse_expire_date(prefix_discard=p, expiry_formatted="artifact/expire/2023-07-27/16.12/2023-08-17/06.02/foo")   == {"date":"2023-07-27", "time":"16.12", "tzoffset":None}
    assert artifact.parse_expire_date(prefix_discard=p, expiry_formatted="artifact/expire/2023-07-27/16.12+0200")  == {"date":"2023-07-27", "time":"16.12", "tzoffset":"+0200"}
    assert artifact.parse_expire_date(prefix_discard=p, expiry_formatted="artifact/expire/2023-07-27/16.12+0200/") == {"date":"2023-07-27", "time":"16.12", "tzoffset":"+0200"}
    assert artifact.parse_expire_date(prefix_discard=p, expiry_formatted="artifact/expire/2023-07-27/16.12-0200")  == {"date":"2023-07-27", "time":"16.12", "tzoffset":"-0200"}
    assert artifact.parse_expire_date(prefix_discard=p, expiry_formatted="artifact/expire/2023-07-27/16.12-03")    == {"date":"2023-07-27", "time":"16.12", "tzoffset":None}
    assert artifact.parse_expire_date(prefix_discard="", expiry_formatted="2023-07-27/16.12")  == {"date":"2023-07-27", "time":"16.12", "tzoffset":None}
    assert artifact.parse_expire_date(prefix_discard="", expiry_formatted="2023-07-27/16.12/") == {"date":"2023-07-27", "time":"16.12", "tzoffset":None}

def test_parse_expire_datetime_invalid():
    assert artifact.parse_expire_date(prefix_discard="artifact/expire/", expiry_formatted="artifact/expire/30d/") == {"date":None, "time":None, "tzoffset":None}
