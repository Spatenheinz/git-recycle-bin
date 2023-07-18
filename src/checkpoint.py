#!/usr/bin/env python3
import os
import re
import sys
import argparse
import subprocess
from itertools import takewhile

from rbgit import RbGit

def trim_all_lines(input_string):
    lines = input_string.split('\n')
    trimmed_lines = [line.strip() for line in lines]
    return '\n'.join(trimmed_lines)


def prefix_lines(lines: str, prefix: str) -> str:
    return "\n".join([prefix+line for line in lines.split('\n')])


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


def rel_dir(context, query):
    """ Get relative path to query from NCA(context,query) """
    abs_context = os.path.abspath(context)
    abs_query = os.path.abspath(query)
    common_path = nca_path(abs_context, abs_query)
    return os.path.relpath(abs_query, common_path)





def create_artifact_commit(rbgit, artifact_name: str, binpath: str) -> str:
    """ Create Artifact: A binary commit, with builtin traceability and expiry """
    artifact_name_sane = sanitize_branch_name(artifact_name)
    if artifact_name != artifact_name_sane:
        print(f"Warning: Sanitized '{artifact_name}' to '{artifact_name_sane}'.", file=sys.stderr)
        artifact_name = artifact_name_sane

    ttl = "30 days"

    # TODO: Test for binpath existence
    src_remote_name = "origin"    # TODO: Expose as argument
    src_sha       = exec(["git", "rev-parse", "HEAD"])  # full sha
    src_sha_short = exec(["git", "rev-parse", "--short", "HEAD"])  # human readable
    src_sha_msg   = exec(["git", "show", "--no-patch", "--format=%B", src_sha])
    src_sha_title = src_sha_msg.split('\n')[0]  # title is first line of commit-msg
    src_branch    = exec(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    src_repo_url  = exec(["git", "config", "--get", f"remote.{src_remote_name}.url"])
    src_repo      = os.path.basename(src_repo_url)
    src_tree_pwd  = os.getcwd()
    src_status    = exec(["git", "status", "--porcelain=1", "--untracked-files=no"]); src_status = src_status if src_status != "" else "clean"

    branch_name = f"auto/checkpoint/{src_repo}/{src_sha}/{artifact_name}"

    binpath_rel = rel_dir(src_tree_pwd, binpath)

    rbgit.checkout_orphan_idempotent(branch_name)

    print(f"Adding '{binpath}' as '{binpath_rel}' ...", file=sys.stderr)
    changes = rbgit.add(binpath)
    if changes == False:
        print("No changes for the next commit", file=sys.stderr)
        return None

    commit_msg = f"""
        artifact: {src_repo}@{src_sha_short}: {artifact_name} @({string_trunc_ellipsis(30, src_sha_title).strip()})

        This is a (binary) artifact with expiry. Expiry can be changed.
        See https://gitlab.ci.demant.com/csfw/flow/git-recycle-bin#usage

        artifact-scheme-version: 1
        artifact-name: {artifact_name}
        artifact-path: {binpath_rel}
        artifact-time-to-live: {ttl}
        src-git-commit-title: {src_sha_title}
        src-git-commit-sha: {src_sha}
        src-git-branch: {src_branch}
        src-git-repo: {src_repo}
        src-git-repo-url: {src_repo_url}
        {extract_gerrit_change_id(src_sha_msg, "src-git-commit-changeid: ")}
        {prefix_lines(prefix="src-git-status: ", lines=trim_all_lines(src_status))}
    """

    # Set {author,committer}-dates: Make our new commit reproducible by copying from the source; do not sample the current time.
    os.environ['GIT_AUTHOR_DATE'] = exec(["git", "show", "-s", "--format=%aD", src_sha])
    os.environ['GIT_COMMITTER_DATE'] = exec(["git", "show", "-s", "--format=%cD", src_sha])
    rbgit.cmd("commit", "--file", "-", "--quiet", "--no-status", "--untracked-files=no", input=trim_all_lines(commit_msg))

    artifact_sha = rbgit.cmd("rev-parse", "HEAD").strip()
    print(f"Committed {artifact_sha}", file=sys.stderr)
    return artifact_sha





def main():
    parser = argparse.ArgumentParser(description="Create and push artifacts - which have traceability and expiry")
    parser.add_argument("--name", required=True, help="Name to assign to the artifact. Will be sanitized")
    parser.add_argument("--path", required=True, help="Path to artifact in src-repo.")

    args = parser.parse_args()

    src_tree_pwd = os.getcwd()
    nca_dir = nca_path(src_tree_pwd, args.path)
    rbgit = RbGit(rbgit_dir=f"{nca_dir}/.rbgit", rbgit_work_tree=nca_dir)

    rbgit.add_remote_idempotent(name="recyclebin", url="git@gitlab.ci.demant.com:csfw/documentation/generated/aurora_rst_html_mpeddemo.git")

    artifact_sha = create_artifact_commit(rbgit, args.name, args.path)
    if artifact_sha:
        print(rbgit.cmd("log", "-1", artifact_sha))
    print(rbgit.cmd("branch", "-vv"))


if __name__ == "__main__":
    main()
