# What?
This project provides means for pushing artifacts from a git source repo to a git binary repo.

Say you/CI build the `sample_app`, you can publish your binary to git! Not to your same source code repo, but another *binary* repo.


# Why?
Unlike many artifact management systems out there, the artifacts published here will:
- Have full traceabillity back to their original source code.
- Support expiry and garbage collection via git's own gc after a Time-To-Live expiry.
- Let users or CI systems change/remove the TTL expiry via a simple git commit.


# Usage
* Locally or CI-side, this tool creates and pushes artifacts, see `--help` and examples below.
* Garbage collection of expired artifacts is done at CI-side. TBD.
* Setting of current latest tags is done at CI-side. TBD.


# Usage example 1
```
artifact.py --path ../obj/doc/html --name "Aurora-RST-Documentation" --remote "git@gitlab.ci.demant.com:csfw/documentation/generated/aurora_rst_html_mpeddemo.git" --push
```

This will:

  1. Create a new git repo locally, to ensure non-interference with source repo.
  2. Create a new binary artifact git commit for the HTML folder and assign it a name and expiry.
  3. Push the artifact commit to the remote.

