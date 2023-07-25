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


## Schema
Artifacts come with meta-data, for {expiry, traceabillity, audit, placement} purposes. \
Meta-data is stored as trailer fields in the commit message, forming a schema, e.g.:

`artifact-schema-version: 1` : Integer. The version of the schema.
`artifact-name: Aurora-RST-Documentation` : String. Name of the artifact.
`artifact-mime-type: directory` : String or tuple. MIME type of the artifact.
`artifact-tree-prefix: obj/doc/html` : String. Files in this artifact commit all share this directory-prefix. Either `.` or some directory-prefix. A directory-prefix can make merges of artifact-commits conflict-free.
`artifact-time-to-live: 30 days` : Life-time of artifact-branch from `src-git-commit-time-commit`. After this, the automatic artifact-branch may be deleted - thus eligible for garbage collection (`git gc`).
`src-git-relpath: ../obj/doc/html` : String. Relative path to artifact from source-git's root. Leading `../ ` means artifact resided outside the source-git.
`src-git-commit-title: rf: twister wrapper WIP` : String. Artifact was built from this commit in source git repo.
`src-git-commit-sha: ed6267ee5b84c894fc8490d93db0525fb2f167eb` : String. Artifact was built from this commit in source git repo.
`src-git-commit-changeid: Ie3eb7af86c3e578d2c18631f15cf0a12e7d0f80d` : String. Artifact was built from this commit in source git repo. Optional.
`src-git-commit-time-author: Wed, 21 Jun 2023 14:13:31 +0200` : Date. Artifact was built from this commit in source git repo.
`src-git-commit-time-commit: Wed, 21 Jun 2023 15:42:49 +0200` : Date. Artifact was built from this commit in source git repo.
`src-git-branch: feature/wrk_le_audio_7.0` : String. Locally-checked out branch in source git repo or `Detached HEAD`.
`src-git-repo-name: firmware` : String. Basename of `src-git-repo-url`.
`src-git-repo-url: ssh://gerrit.ci.demant.com:29418/firmware` : String. URL of remote in source git repo.
`src-git-commits-ahead: ?`: Integer or `?`. How many commits source git repo branch was locally ahead of its remote upstream tracking branch.
`src-git-commits-behind: ?`: Integer or `?`. How many commits source git repo branch was locally behind of its remote upstream tracking branch.
`src-git-status: clean` : String or strings. Either `clean` or list of locally {modified, deleted} files in source git repo. Untracked files are ignored.

This scheme captures only what is intrinsically tied to the artifact and the sources it comes from.
Adding further meta-data should be carefully considered, so as to not compromise the repeatability of the artifact's commit SHA.


### Other schema ideas
It may be tempting to extend the schema above with further convenient meta-data, see below for more ideas.
However, adding such _convenient_ meta-data means we mix-in ever-changing non-reproducible machine-specific side-effects.
These could still be useful but do no belong in the artifact's commit message; would fit better as a `git-note` attached to the artifact's commitish or treeish -- this remains as possible future work.

`artifact-outputs`: List of files/artifacts generated. Would give more insight into what's included beyond just the tree prefix.
`artifact-dependencies`: List of other artifacts this one depends on. Useful for dependency management.
`build-job`: ID of any associated CI job/build pipeline.
`build-host`: Name/ID of machine that built the artifact.
`build-duration`: How long the build took. Performance metric.
`build-timestamp`: Exact UTC timestamp of when build occurred.
`artifact-hash`: Hash or checksum of the artifact output. Improves integrity checking.
`artifact-url`: Direct URL to download the artifact.
`artifact-notes`: Any other information about the build - logs, warnings, etc.





# Usage example 1
```
artifact.py --path ../obj/doc/html --name "Aurora-RST-Documentation" --remote "git@gitlab.ci.demant.com:csfw/documentation/generated/aurora_rst_html_mpeddemo.git" --push
```

This will:

  1. Create a new git repo locally, to ensure non-interference with source repo.
  2. Create a new binary artifact git commit for the HTML folder and assign it a name and expiry.
  3. Push the artifact commit to the remote.

