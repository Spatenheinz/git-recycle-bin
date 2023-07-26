#!/usr/bin/env python3
import os
import re
import sys
import argparse
import subprocess
import mimetypes
from itertools import takewhile
from datetime import datetime

from rbgit import RbGit

# Don't change the date format! This could break parsing
date_fmt = "%a, %d %b %Y %H:%M:%S %z"


def trim_all_lines(input_string):
    lines = input_string.split('\n')
    trimmed_lines = [line.strip() for line in lines]
    return '\n'.join(trimmed_lines)


def prefix_lines(lines: str, prefix: str) -> str:
    return "\n".join(f"{prefix}{line}" for line in lines.split("\n") if line)


def extract_gerrit_change_id(commit_message: str) -> str:
    # Find the Change-Id line(s)
    change_id_lines = [line for line in commit_message.split('\n') if line.startswith("Change-Id:")]

    # Extract the Change ID from the last matching line, if any
    if change_id_lines:
        last_change_id_line = change_id_lines[-1]
        _, change_id = last_change_id_line.split(maxsplit=1)
        return change_id

    # If there is no Change-Id line, return an empty string
    return ""

def string_trunc_ellipsis(maxlen: int, longstr: str) -> str:
    if len(longstr) <= maxlen:
        return longstr

    shortstr = longstr[:maxlen]
    if len(shortstr) == maxlen:
        return shortstr[:(maxlen-3)] + "..."
    else:
        return shortstr


def sanitize_branch_name(name: str) -> str:
    """
        Git branch names cannot contain: whitespace characters, ~, ^, :, [, ? or *.
        Also they cannot start with / or -, end with ., or contain multiple consecutive /
        Finally, they cannot be @, @{, or have two consecutive dots ..
    """

    # replace unsafe characters with _
    sanitized_name = re.sub(r'[\s~^:\[\]?*]', '_', name)

    # replace starting / or - with _
    sanitized_name = re.sub(r'^[-/]', '_', sanitized_name)

    # replace ending . with _
    sanitized_name = re.sub(r'\.$', '_', sanitized_name)

    # replace // with /
    sanitized_name = re.sub(r'//', '/', sanitized_name)

    # replace .. with .
    sanitized_name = re.sub(r'\.\.', '.', sanitized_name)

    # replace @ and @{ with _
    if sanitized_name in ('@', '@{'):
        sanitized_name = '_'

    return sanitized_name



def exec(command):
    print("Run:", command)
    return subprocess.check_output(command, text=True).strip()


def nca_path(pathA, pathB):
    """ Get nearest common ancestor of two paths """

    # Get absolute paths. Inputs may be relative.
    components1 = os.path.abspath(pathA).split(os.sep)
    components2 = os.path.abspath(pathB).split(os.sep)

    # Use zip to iterate over pairs of components
    # Stop when components differ, thanks to the use of itertools.takewhile
    common_components = list(takewhile(lambda x: x[0]==x[1], zip(components1, components2)))

    # The common path is the joined common components
    common_path = os.sep.join([x[0] for x in common_components])
    return common_path


def rel_dir(pfrom, pto):
    """ Get relative path to `pto` from `pfrom` """
    abs_pfrom = os.path.abspath(pfrom)
    abs_pto = os.path.abspath(pto)
    return os.path.relpath(abs_pto, abs_pfrom)



def date_formatted2unix(date_string: str, date_format: str):
    """
        E.g.
            date_formatted2unix("Wed, 21 Jun 2023 14:13:31 +0200", "%a, %d %b %Y %H:%M:%S %z")
    """
    unix_time = datetime.strptime(date_string, date_format).timestamp()
    return unix_time



def emit_commit_msg(d: dict):
    commit_msg = f"""
        artifact: {d['src_repo']}@{d['src_sha_short']}: {d['artifact_name']} @({string_trunc_ellipsis(30, d['src_sha_title']).strip()})

        This is a (binary) artifact with expiry. Expiry can be changed.
        See https://gitlab.ci.demant.com/csfw/flow/git-recycle-bin#usage

        artifact-schema-version: 1
        artifact-name: {d['artifact_name']}
        artifact-mime-type: {d['artifact_mime']}
        artifact-tree-prefix: {d['artifact_relpath_nca']}
        artifact-time-to-live: {d['ttl']}
        src-git-relpath: {d['artifact_relpath_src']}
        src-git-commit-title: {d['src_sha_title']}
        src-git-commit-sha: {d['src_sha']}
        {prefix_lines(prefix="src-git-commit-changeid: ", lines=extract_gerrit_change_id(d['src_sha_msg']))}
        src-git-commit-time-author: {d['src_time_author']}
        src-git-commit-time-commit: {d['src_time_commit']}
        src-git-branch: {d['src_branch'] if d['src_branch'] != "HEAD" else "Detached HEAD"}
        src-git-repo-name: {d['src_repo']}
        src-git-repo-url: {d['src_repo_url']}
        src-git-commits-ahead: {d['src_commits_ahead'] if d['src_commits_ahead'] != "" else "?"}
        src-git-commits-behind: {d['src_commits_behind'] if d['src_commits_behind'] != "" else "?"}
        {prefix_lines(prefix="src-git-status: ", lines=trim_all_lines(d['src_status'] if d['src_status'] != "" else "clean"))}
    """
    return trim_all_lines(commit_msg)


def parse_commit_msg(commit_msg):
    # Regex breakdown:
    #   ^([\w-]+) matches the key made up of word chars and dashes from line-start, captured in group 1
    #   :         matches the colon delimiter
    #   (.*)      matches the rest of the line as the value, captured in group 2
    pattern = r'^([\w-]+):(.*)'

    ## NOTE: This does not handle multi-line git trailers correctly, e.g. src-git-status
    ret_dict = {}
    for line in commit_msg.strip().splitlines():
        match = re.match(pattern, line)
        if match:
            key, val = match.group(1), match.group(2)
            ret_dict[key.strip()] = val.strip()
    return ret_dict



def create_artifact_commit(rbgit, artifact_name: str, binpath: str, ttl: str = "30 days") -> str:
    """ Create Artifact: A binary commit, with builtin traceability and expiry """
    if not os.path.exists(binpath):
        raise RuntimeError(f"Artifact '{binpath}' does not exist!")

    artifact_name_sane = sanitize_branch_name(artifact_name)
    if artifact_name != artifact_name_sane:
        print(f"Warning: Sanitized '{artifact_name}' to '{artifact_name_sane}'.", file=sys.stderr)
        artifact_name = artifact_name_sane

    d = {}
    d['artifact_name'] = artifact_name
    d['binpath'] = binpath
    d['ttl'] = ttl

    if os.path.isfile(binpath): d['artifact_mime'] = mimetypes.guess_type(binpath)
    elif os.path.isdir(binpath): d['artifact_mime'] = "directory"
    elif os.path.islink(binpath): d['artifact_mime'] = "link"
    elif os.path.ismount(binpath): d['artifact_mime'] = "mount"
    else: d['artifact_mime'] = "unknown"

    d['src_remote_name'] = "origin"    # TODO: Expose as argument
    d['src_sha']          = exec(["git", "rev-parse", "HEAD"])  # full sha
    d['src_sha_short']    = exec(["git", "rev-parse", "--short", "HEAD"])  # human readable
    d['src_sha_msg']      = exec(["git", "show", "--no-patch", "--format=%B", d['src_sha']]);
    d['src_sha_title']    = d['src_sha_msg'].split('\n')[0]  # title is first line of commit-msg

    # Author time is when the commit was first committed.
    # Author time is easily set with `git commit --date`.
    d['src_time_author']  = exec(["git", "show", "-s", "--format=%ad", f"--date=format:{date_fmt}", d['src_sha']])

    # Commiter time changes every time the commit-SHA changes, for example {rebasing, amending, ...}.
    # Commiter time can be set with $GIT_COMMITTER_DATE or `git rebase --committer-date-is-author-date`.
    # Commiter time is monotonically increasing but sampled locally, so graph could still be non-monotonic if a collaborator has a very wrong clock.
    d['src_time_commit']  = exec(["git", "show", "-s", "--format=%cd", f"--date=format:{date_fmt}", d['src_sha']])

    d['src_branch']       = exec(["git", "rev-parse", "--abbrev-ref", "HEAD"]);
    d['src_repo_url']     = exec(["git", "config", "--get", f"remote.{d['src_remote_name']}.url"])
    d['src_repo']         = os.path.basename(d['src_repo_url'])
    d['src_tree_root']    = exec(["git", "rev-parse", "--show-toplevel"])
    d['src_status']       = exec(["git", "status", "--porcelain=1", "--untracked-files=no"]);

    if d['src_branch'] == "HEAD":
        d['src_branch_upstream'] = ""
        d['src_commits_ahead']   = ""
        d['src_commits_behind']  = ""
    else:
        d['src_branch_upstream'] = exec(["git", "for-each-ref", "--format=%(upstream:short)", f"refs/heads/{d['src_branch']}"])
        if d['src_branch_upstream'] == "":
            d['src_commits_ahead']  = ""
            d['src_commits_behind'] = ""
        else:
            d['src_commits_ahead']   = exec(["git", "rev-list", "--count", f"{d['src_branch_upstream']}..{d['src_branch']}"])
            d['src_commits_behind']  = exec(["git", "rev-list", "--count", f"{d['src_branch']}..{d['src_branch_upstream']}"])

    d['nca_dir'] = nca_path(d['src_tree_root'], binpath)                        # Longest shared path between gitroot and artifact. Is either {gitroot, something outside gitroot}
    d['artifact_relpath_nca'] = rel_dir(pto=binpath, pfrom=d['nca_dir'])        # Relative path to artifact from nca_dir. Artifact is always within nca_dir
    d['artifact_relpath_src'] = rel_dir(pto=binpath, pfrom=d['src_tree_root'])  # Relative path to artifact from src-git-root. Artifact might be outside of source git.

    d['bin_branch_name'] = f"auto/artifact/{d['src_repo']}@{d['src_sha']}/{{{d['artifact_relpath_nca']}}}"
    d['bin_tag_name']    = f"auto/artifact/{d['src_repo']}@{d['src_branch']}/{{{d['artifact_relpath_nca']}}}" if d['src_branch'] != "HEAD" else None

    d['bin_commit_msg'] = emit_commit_msg(d)

    rbgit.checkout_orphan_idempotent(d['bin_branch_name'])

    print(f"Adding '{binpath}' as '{d['artifact_relpath_nca']}' ...", file=sys.stderr)
    changes = rbgit.add(binpath)
    if changes == True:
        # Set {author,committer}-dates: Make our new commit reproducible by copying from the source; do not sample the current time.
        # Sampling the current time would lead to new commit SHA every time, thus not idempotent.
        os.environ['GIT_AUTHOR_DATE'] = d['src_time_author']
        os.environ['GIT_COMMITTER_DATE'] = d['src_time_commit']
        rbgit.cmd("commit", "--file", "-", "--quiet", "--no-status", "--untracked-files=no", input=d['bin_commit_msg'])
        d['bin_sha_commit'] = rbgit.cmd("rev-parse", "HEAD").strip()
    else:
        d['bin_sha_commit'] = rbgit.cmd("rev-parse", "HEAD").strip()  # We already checked-out idempotently
        print(f"No changes for the next commit. Already at {d['bin_sha_commit']}", file=sys.stderr)

    # Fetching a commit implies fetching its whole tree too, which may be big!
    # We want light-weight access to the meta-data stored in the commit's message, so we
    # copy meta-data to a new object which can be fetched standalone - without downloading the whole tree.
    # NOTE: This meta-data could be augmented with convenient/unstable information - this would not compromise the commit-SHA's stability.
    d['bin_sha_only_metadata'] = rbgit.cmd("hash-object", "--stdin", "-w", input=d['bin_commit_msg']).strip()
    # Create new ref for the artifact-commit, pointing to [Meta data]-only.
    d['bin_ref_only_metadata'] = f"refs/artifact/meta-for-commit/{d['bin_sha_commit']}"
    rbgit.cmd("update-ref", d['bin_ref_only_metadata'], d['bin_sha_only_metadata'])

    print(f"Artifact branch: {d['bin_branch_name']}", file=sys.stderr)
    print(f"Artifact commit: {d['bin_sha_commit']}", file=sys.stderr)
    print(f"Artifact [meta data]-only ref: {d['bin_ref_only_metadata']}", file=sys.stderr)
    print(f"Artifact [meta data]-only obj: {d['bin_sha_only_metadata']}", file=sys.stderr)

    return d




def str2bool(v):
    if isinstance(v, bool):
       return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and push artifacts - which have traceability and expiry")
    parser.add_argument("--name",   required=True,  type=str, default=os.getenv('GITRB_NAME'), help="Name to assign to the artifact. Will be sanitized.")
    parser.add_argument("--path",   required=True,  type=str, default=os.getenv('GITRB_PATH'), help="Path to artifact in src-repo. File or folder.")
    parser.add_argument("--remote", required=False, type=str, default=os.getenv('GITRB_REMOTE'), help="Git remote URL to push artifact to.")
    parser.add_argument("--push", type=str2bool, nargs='?', const=True, default=os.getenv('GITRB_PUSH', 'False'), help="Push artifact-commit to remote.")
    parser.add_argument("--push-tag", type=str2bool, nargs='?', const=True, default=os.getenv('GITRB_PUSH_TAG', 'False'), help="Push tag to artifact to remote.")
    parser.add_argument("--verbose", type=str2bool, nargs='?', const=True, default=os.getenv('GITRB_VERBOSE', 'False'), help="Enable verbose mode.")
    # TODO: Implement verbose mode
    # TODO: Add --clean to delete the .rbgit repo, or like docker's --rm
    # TODO: Add --submodule to add a src/ submodule back to the src-repo.
    # TODO: Create other script for the bin-side: CI expiry / branch-deletion.
    # TODO: Create other script for the bin-side: Setting latest tag

    args = parser.parse_args()

    # Sanity-check
    if args.push_tag and not args.push:
        print("Error: `--push-tag` requires `--push`")
        return 1

    src_tree_root = exec(["git", "rev-parse", "--show-toplevel"])
    nca_dir = nca_path(src_tree_root, args.path)
    rbgit = RbGit(rbgit_dir=f"{nca_dir}/.rbgit", rbgit_work_tree=nca_dir)

    print(f"Making local commit of artifact {args.path} in artifact-repo at {rbgit.rbgit_dir}", file=sys.stderr)
    d = create_artifact_commit(rbgit, args.name, args.path)
    if d['bin_tag_name']:
        rbgit.set_tag(tag_name=d['bin_tag_name'], tag_val=d['bin_sha_commit'])
    print(rbgit.cmd("branch", "-vv"))
    print(rbgit.cmd("log", "-1", d['bin_branch_name']))

    remote_bin_name = "recyclebin"
    if args.remote:
        rbgit.add_remote_idempotent(name=remote_bin_name, url=args.remote)
    if args.push:
        # Push branch first, then meta-data (we don't want meta-data to be pushed if branch push fails).
        # Pushing may take long, so always show stdout and stderr without capture.
        print(f"Pushing to remote artifact-repo: Artifact data on branch {d['bin_branch_name']}", file=sys.stderr)
        rbgit.cmd("push", "--force", remote_bin_name, d['bin_branch_name'], capture_output=False)  # Branch might exist already upstream. Policy TODO
        print(f"Pushing to remote artifact-repo: Artifact meta-data {d['bin_ref_only_metadata']}", file=sys.stderr)
        rbgit.cmd("push", "--force", remote_bin_name, d['bin_ref_only_metadata'], capture_output=False)
    if args.push_tag:
        if not d['bin_tag_name']:
            print("Error: You are in Detached HEAD, so you can't push a tag to bin-remote with name of your source branch.", file=sys.stderr)
            return 1

        remote_bin_sha_commit = rbgit.fetch_current_tag_value(remote_bin_name, d['bin_tag_name'])
        if remote_bin_sha_commit:
            print(f"Bin-remote already has a tag named {d['bin_tag_name']} pointing to {remote_bin_sha_commit[:8]}.", file=sys.stderr)
            print(f"We'll check if our artifact is newer than {remote_bin_sha_commit[:8]}...", file=sys.stderr)
            remote_meta = rbgit.fetch_cat_pretty(remote_bin_name, f"refs/artifact/meta-for-commit/{remote_bin_sha_commit}")
            print(remote_meta)
            # TODO Arbitrate
        else:
            print(f"Bin-remote does not have a tag named {d['bin_tag_name']} -- we'll publish it.", file=sys.stderr)
            # TODO push tag

    return 0

if __name__ == "__main__":
    ret = main()
    sys.exit(ret)
