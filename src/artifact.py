#!/usr/bin/env python3
import os
import re
import sys
import argparse
import subprocess
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


def extract_gerrit_change_id(commit_message: str, prefix: str) -> str:
    # Find the Change-Id line(s)
    change_id_lines = [line for line in commit_message.split('\n') if line.startswith("Change-Id:")]

    # Extract the Change ID from the last matching line, if any
    if change_id_lines:
        last_change_id_line = change_id_lines[-1]
        _, change_id = last_change_id_line.split(maxsplit=1)
        return f"{prefix}{change_id}"

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


def nca_rel_dir(context, query):
    """ Get relative path to query from NCA(context,query) """
    abs_context = os.path.abspath(context)
    abs_query = os.path.abspath(query)
    common_path = nca_path(abs_context, abs_query)
    return os.path.relpath(abs_query, common_path)


def date_formatted2unix(date_string: str, date_format: str):
    """
        E.g.
            date_formatted2unix("Wed, 21 Jun 2023 14:13:31 +0200", "%a, %d %b %Y %H:%M:%S %z")
    """
    unix_time = datetime.strptime(date_string, date_format).timestamp()
    return unix_time



def emit_commit_msg(artifact_name,artifact_path,ttl,
                    src_branch,src_repo,src_repo_url,src_sha,src_sha_msg,src_sha_short,src_sha_title,src_status,src_time_author,src_time_commit):
    commit_msg = f"""
        artifact: {src_repo}@{src_sha_short}: {artifact_name} @({string_trunc_ellipsis(30, src_sha_title).strip()})

        This is a (binary) artifact with expiry. Expiry can be changed.
        See https://gitlab.ci.demant.com/csfw/flow/git-recycle-bin#usage

        artifact-schema-version: 1
        artifact-name: {artifact_name}
        artifact-path: {artifact_path}
        artifact-time-to-live: {ttl}
        src-git-commit-title: {src_sha_title}
        src-git-commit-time-author: {src_time_author}
        src-git-commit-time-commit: {src_time_commit}
        src-git-commit-sha: {src_sha}
        src-git-branch: {src_branch}
        src-git-repo: {src_repo}
        src-git-repo-url: {src_repo_url}
        {extract_gerrit_change_id(src_sha_msg, "src-git-commit-changeid: ")}
        {prefix_lines(prefix="src-git-status: ", lines=trim_all_lines(src_status))}
    """
    return trim_all_lines(commit_msg)


def parse_commit_msg(commit_msg):
    lines = commit_msg.strip().split('\n')
    # Create a dictionary by splitting each line at the colon and stripping the results
    # NOTE: This does not handle multi-line git trailers correctly, e.g. src-git-status
    commit_dict = {key.strip(): value.strip() for key, value in (line.split(':', 1) for line in lines)}
    return commit_dict



def create_artifact_commit(rbgit, artifact_name: str, binpath: str) -> str:
    """ Create Artifact: A binary commit, with builtin traceability and expiry """
    artifact_name_sane = sanitize_branch_name(artifact_name)
    if artifact_name != artifact_name_sane:
        print(f"Warning: Sanitized '{artifact_name}' to '{artifact_name_sane}'.", file=sys.stderr)
        artifact_name = artifact_name_sane

    ttl = "30 days"

    # TODO: Test for binpath existence
    src_remote_name = "origin"    # TODO: Expose as argument
    src_sha          = exec(["git", "rev-parse", "HEAD"])  # full sha
    src_sha_short    = exec(["git", "rev-parse", "--short", "HEAD"])  # human readable
    src_sha_msg      = exec(["git", "show", "--no-patch", "--format=%B", src_sha]); src_sha_title = src_sha_msg.split('\n')[0]  # title is first line of commit-msg

    # Author time is when the commit was first committed.
    # Author time is easily set with `git commit --date`.
    src_time_author  = exec(["git", "show", "-s", "--format=%ad", f"--date=format:{date_fmt}", src_sha])

    # Commiter time changes every time the commit-SHA changes, for example {rebasing, amending, ...}.
    # Commiter time can be set with $GIT_COMMITTER_DATE or `git rebase --committer-date-is-author-date`.
    # Commiter time is monotonically increasing but sampled locally, so graph could still be non-monotonic if a collaborator has a very wrong clock.
    src_time_commit  = exec(["git", "show", "-s", "--format=%cd", f"--date=format:{date_fmt}", src_sha])

    src_branch       = exec(["git", "rev-parse", "--abbrev-ref", "HEAD"]); src_branch = src_branch if src_branch != "HEAD" else "Detached HEAD"
    src_repo_url     = exec(["git", "config", "--get", f"remote.{src_remote_name}.url"])
    src_repo         = os.path.basename(src_repo_url)
    src_tree_root    = exec(["git", "rev-parse", "--show-toplevel"])
    src_status       = exec(["git", "status", "--porcelain=1", "--untracked-files=no"]); src_status = src_status if src_status != "" else "clean"

    bin_branch_name = f"auto/checkpoint/{src_repo}/{src_sha}/{artifact_name}"

    nca_dir = nca_path(src_tree_root, binpath)
    binpath_rel = nca_rel_dir(src_tree_root, binpath)

    rbgit.checkout_orphan_idempotent(bin_branch_name)

    print(f"Adding '{binpath}' as '{binpath_rel}' ...", file=sys.stderr)
    changes = rbgit.add(binpath)
    if changes == False:
        print("No changes for the next commit", file=sys.stderr)
        return None, bin_branch_name

    commit_msg = emit_commit_msg(
        artifact_name = artifact_name,
        artifact_path = binpath_rel,
        ttl = ttl,
        src_branch = src_branch,
        src_repo = src_repo,
        src_repo_url = src_repo_url,
        src_sha = src_sha,
        src_sha_msg = src_sha_msg,
        src_sha_short = src_sha_short,
        src_sha_title = src_sha_title,
        src_status = src_status,
        src_time_author = src_time_author,
        src_time_commit = src_time_commit,
    )

    # Set {author,committer}-dates: Make our new commit reproducible by copying from the source; do not sample the current time.
    # Sampling the current time would lead to new commit SHA every time, thus not idempotent.
    os.environ['GIT_AUTHOR_DATE'] = src_time_author
    os.environ['GIT_COMMITTER_DATE'] = src_time_commit
    rbgit.cmd("commit", "--file", "-", "--quiet", "--no-status", "--untracked-files=no", input=commit_msg)

    artifact_sha = rbgit.cmd("rev-parse", "HEAD").strip()
    print(f"Committed {artifact_sha}", file=sys.stderr)
    return artifact_sha, branch_name




def str2bool(v):
    if isinstance(v, bool):
       return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


def main():
    parser = argparse.ArgumentParser(description="Create and push artifacts - which have traceability and expiry")
    parser.add_argument("--name",   required=True,  type=str, default=os.getenv('GITRB_NAME'), help="Name to assign to the artifact. Will be sanitized.")
    parser.add_argument("--path",   required=True,  type=str, default=os.getenv('GITRB_PATH'), help="Path to artifact in src-repo. File or folder.")
    parser.add_argument("--remote", required=False, type=str, default=os.getenv('GITRB_REMOTE'), help="Git remote URL to push artifact to.")
    parser.add_argument("--push", type=str2bool, nargs='?', const=True, default=os.getenv('GITRB_PUSH', 'False'), help="Perform push to remote.")
    parser.add_argument("--verbose", type=str2bool, nargs='?', const=True, default=os.getenv('GITRB_VERBOSE', 'False'), help="Enable verbose mode.")
    # TODO: Implement verbose mode
    # TODO: Add --clean to delete the .rbgit repo, or like docker's --rm
    # TODO: Add --submodule to add a src/ submodule back to the src-repo.
    # TODO: Create other script for the bin-side: CI expiry / branch-deletion.
    # TODO: Create other script for the bin-side: Setting latest tag

    args = parser.parse_args()

    src_tree_root = exec(["git", "rev-parse", "--show-toplevel"])
    nca_dir = nca_path(src_tree_root, args.path)
    rbgit = RbGit(rbgit_dir=f"{nca_dir}/.rbgit", rbgit_work_tree=nca_dir)

    artifact_sha, branch_name = create_artifact_commit(rbgit, args.name, args.path)
    print(rbgit.cmd("branch", "-vv"))
    if artifact_sha:
        print(rbgit.cmd("log", "-1", branch_name))

    remote_bin_name = "recyclebin"
    if args.remote:
        rbgit.add_remote_idempotent(name=remote_bin_name, url=args.remote)
    if args.push:
        rbgit.cmd("push", remote_bin_name, branch_name, capture_output=False)  # pushing may take long, so always show stdout and stderr without capture


if __name__ == "__main__":
    main()
