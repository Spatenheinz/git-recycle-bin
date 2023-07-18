# What?
This project provides means for pushing artifacts from a git source repo to a git binary repo.

Say you/CI build the `sample_app`, you can publish your binary to git! Not to your same source code repo, but another *binary* repo.


# Why?
Unlike many artifact management systems out there, the artifacts published here will:
- Have full traceabillity back to their original source code.
- Support expiry and garbage collection via git's own gc after a Time-To-Live expiry.
- Let users or CI systems change/remove the TTL expiry via a simple git commit.


# Usage

TODO


# Usage example 1
```
eisbaw in kbnuxcsfw-mped in git on  HEAD (8bf06b0) [?]
❯ , just -f /scratch/git-recycle-bin/justfile checkpoint Documentation ../obj/doc
```

