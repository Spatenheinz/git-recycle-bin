#!/usr/bin/env python3
import os
import sys
import shutil
import argparse
import subprocess

from rbgit import RbGit
from printer import Printer
from util_string import *
from util_file import *
from util_date import *


printer = Printer(verbosity=2, colorize=True)



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


def exec(command):
    printer.debug("Run:", command, file=sys.stderr)
    return subprocess.check_output(command, text=True).strip()





def emit_commit_msg(d: dict):
    commit_msg_title = f"""
        artifact: {d['src_repo']}@{d['src_sha_short']}: {d['artifact_name']} @({string_trunc_ellipsis(30, d['src_sha_title']).strip()})
    """

    commit_msg_body = """
        This is a (binary) artifact with expiry. Expiry can be changed.
        See https://gitlab.ci.demant.com/csfw/flow/git-recycle-bin#usage
    """

    commit_msg_trailers = f"""
        artifact-schema-version: 1
        artifact-name: {d['artifact_name']}
        artifact-mime-type: {d['artifact_mime']}
        artifact-tree-prefix: {d['artifact_relpath_nca']}
        src-git-relpath: {d['artifact_relpath_src']}
        src-git-commit-title: {d['src_sha_title']}
        src-git-commit-sha: {d['src_sha']}
        {prefix_lines(prefix="src-git-commit-changeid: ", lines=extract_gerrit_change_id(d['src_sha_msg']))}
        src-git-commit-time-author: {d['src_time_author']}
        src-git-commit-time-commit: {d['src_time_commit']}
        src-git-branch: {d['src_branch'] if d['src_branch'] != "HEAD" else "Detached HEAD"}
        src-git-repo-name: {d['src_repo']}
        src-git-repo-url: {url_redact(d['src_repo_url'])}
        src-git-commits-ahead: {d['src_commits_ahead'] if d['src_commits_ahead'] != "" else "?"}
        src-git-commits-behind: {d['src_commits_behind'] if d['src_commits_behind'] != "" else "?"}
        {prefix_lines(prefix="src-git-status: ", lines=trim_all_lines(d['src_status'] if d['src_status'] != "" else "clean"))}
    """

    commit_msg = f"""
        {commit_msg_title}

        {commit_msg_body}

        {remove_empty_lines(trim_all_lines(commit_msg_trailers))}
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



def create_artifact_commit(rbgit, artifact_name: str, binpath: str, expire_branch: str, add_ignored: bool, src_remote_name: str) -> str:
    """ Create Artifact: A binary commit, with builtin traceability and expiry """
    if not os.path.exists(binpath):
        raise RuntimeError(f"Artifact '{binpath}' does not exist!")

    artifact_name_sane = sanitize_branch_name(artifact_name)
    if artifact_name != artifact_name_sane:
        printer.always(f"Warning: Sanitized '{artifact_name}' to '{artifact_name_sane}'.", file=sys.stderr)
        artifact_name = artifact_name_sane

    d = {}
    d['artifact_name'] = artifact_name
    d['binpath'] = binpath
    d['bin_branch_expire'] = date_fuzzy2expiryformat(expire_branch)

    d['artifact_mime'] = classify_path(binpath)

    d['src_remote_name']  = src_remote_name
    d['src_sha']          = exec(["git", "rev-parse", "HEAD"])  # full sha
    d['src_sha_short']    = exec(["git", "rev-parse", "--short", "HEAD"])  # human readable
    d['src_sha_msg']      = exec(["git", "show", "--no-patch", "--format=%B", d['src_sha']]);
    d['src_sha_title']    = d['src_sha_msg'].split('\n')[0]  # title is first line of commit-msg

    # Author time is when the commit was first committed.
    # Author time is easily set with `git commit --date`.
    d['src_time_author']  = exec(["git", "show", "-s", "--format=%ad", f"--date=format:{DATE_FMT_GIT}", d['src_sha']])

    # Commiter time changes every time the commit-SHA changes, for example {rebasing, amending, ...}.
    # Commiter time can be set with $GIT_COMMITTER_DATE or `git rebase --committer-date-is-author-date`.
    # Commiter time is monotonically increasing but sampled locally, so graph could still be non-monotonic if a collaborator has a very wrong clock.
    d['src_time_commit']  = exec(["git", "show", "-s", "--format=%cd", f"--date=format:{DATE_FMT_GIT}", d['src_sha']])

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

    d['bin_branch_name'] = f"artifact/expire/{d['bin_branch_expire']}/{d['src_repo']}@{d['src_sha']}/{{{d['artifact_relpath_nca']}}}"
    d['bin_tag_name']    = f"artifact/latest/{d['src_repo']}@{d['src_branch']}/{{{d['artifact_relpath_nca']}}}" if d['src_branch'] != "HEAD" else None

    d['bin_commit_msg'] = emit_commit_msg(d)

    rbgit.checkout_orphan_idempotent(d['bin_branch_name'])

    printer.high_level(f"Adding '{binpath}' as '{d['artifact_relpath_nca']}' ...", file=sys.stderr)
    changes = rbgit.add(binpath, force=add_ignored)
    if changes == True:
        # Set {author,committer}-dates: Make our new commit reproducible by copying from the source; do not sample the current time.
        # Sampling the current time would lead to new commit SHA every time, thus not idempotent.
        os.environ['GIT_AUTHOR_DATE'] = d['src_time_author']
        os.environ['GIT_COMMITTER_DATE'] = d['src_time_commit']
        rbgit.cmd("commit", "--file", "-", "--quiet", "--no-status", "--untracked-files=no", input=d['bin_commit_msg'])
        d['bin_sha_commit'] = rbgit.cmd("rev-parse", "HEAD").strip()
    else:
        d['bin_sha_commit'] = rbgit.cmd("rev-parse", "HEAD").strip()  # We already checked-out idempotently
        printer.high_level(f"No changes for the next commit. Already at {d['bin_sha_commit']}", file=sys.stderr)

    # Fetching a commit implies fetching its whole tree too, which may be big!
    # We want light-weight access to the meta-data stored in the commit's message, so we
    # copy meta-data to a new object which can be fetched standalone - without downloading the whole tree.
    # NOTE: This meta-data could be augmented with convenient/unstable information - this would not compromise the commit-SHA's stability.
    d['bin_sha_only_metadata'] = rbgit.cmd("hash-object", "--stdin", "-w", input=d['bin_commit_msg']).strip()
    # Create new ref for the artifact-commit, pointing to [Meta data]-only.
    d['bin_ref_only_metadata'] = f"refs/artifact/meta-for-commit/{d['bin_sha_commit']}"
    rbgit.cmd("update-ref", d['bin_ref_only_metadata'], d['bin_sha_only_metadata'])

    printer.high_level(f"Artifact branch: {d['bin_branch_name']}", file=sys.stderr)
    printer.high_level(f"Artifact commit: {d['bin_sha_commit']}", file=sys.stderr)
    printer.high_level(f"Artifact [meta data]-only ref: {d['bin_ref_only_metadata']}", file=sys.stderr)
    printer.high_level(f"Artifact [meta data]-only obj: {d['bin_sha_only_metadata']}", file=sys.stderr)

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
    class CustomHelpFormatter(argparse.HelpFormatter):
        def __init__(self, prog):
            super().__init__(prog, indent_increment=2, max_help_position=30)

    parser = argparse.ArgumentParser(description="Create and push artifacts in git - with expiry and traceability.", formatter_class=CustomHelpFormatter)

    g = parser.add_argument_group('Typical arguments')
    g.add_argument(                   "--path",   metavar='file|dir', required=True,  type=str, default=os.getenv('GITRB_PATH'),       help="Path to artifact in src-repo. Directory or file.")
    g.add_argument(                   "--name",   metavar='string',   required=True,  type=str, default=os.getenv('GITRB_NAME'),       help="Name to assign to the artifact. Will be sanitized.")
    g.add_argument(                   "--remote", metavar='URL',      required=False, type=str, default=os.getenv('GITRB_REMOTE'),     help="Git remote URL to push artifact to.")
    dv = 'in 30 days'; g.add_argument("--expire", metavar='fuzz',     required=False, type=str, default=os.getenv('GITRB_EXPIRE', dv), help=f"Expiry of artifact's branch. Fuzzy date. Default '{dv}'.")
    dv = 'False'; g.add_argument("--push",       metavar='bool', type=str2bool, nargs='?', const=True, default=os.getenv('GITRB_PUSH', dv),     help=f"Push artifact-commit to remote. Default {dv}.")
    dv = 'False'; g.add_argument("--push-tag",   metavar='bool', type=str2bool, nargs='?', const=True, default=os.getenv('GITRB_PUSH_TAG', dv), help=f"Push tag to artifact to remote. Default {dv}.")
    dv = 'False'; g.add_argument("--rm-expired", metavar='bool', type=str2bool, nargs='?', const=True, default=os.getenv('GITRB_RM_EXPIRED', dv), help=f"Delete expired artifact branches. Default {dv}.")

    g = parser.add_argument_group('Niche arguments')
    g.add_argument("--user-name",  metavar='fullname', required=False, type=str, default=os.getenv('GITRB_USERNAME'), help="Author of artifact commit. Defaults to yourself.")
    g.add_argument("--user-email", metavar='address',  required=False, type=str, default=os.getenv('GITRB_EMAIL'),    help="Author's email of artifact commit. Defaults to your own.")
    dv = 'origin'; g.add_argument("--src-remote-name", metavar='name', required=False, type=str, default=os.getenv('GITRB_SRC_REMOTE', dv), help=f"Name of src repo's remote. Defaults {dv}.")
    dv = 'False'; g.add_argument("--add-ignored",  metavar='bool', type=str2bool, nargs='?', const=True, default=os.getenv('GITRB_ADD_IGNORED', dv),  help=f"Add despite gitignore. Default {dv}.")
    dv = 'False'; g.add_argument("--force-branch", metavar='bool', type=str2bool, nargs='?', const=True, default=os.getenv('GITRB_FORCE_BRANCH', dv), help=f"Force push of branch. Default {dv}.")
    dv = 'False'; g.add_argument("--force-tag",    metavar='bool', type=str2bool, nargs='?', const=True, default=os.getenv('GITRB_FORCE_TAG', dv),    help=f"Force push of tag. Default {dv}.")
    dv = 'True';  g.add_argument("--rm-tmp",       metavar='bool', type=str2bool, nargs='?', const=True, default=os.getenv('GITRB_RM_TMP', dv),       help=f"Remove local bin-repo. Default {dv}.")

    g = parser.add_argument_group('Terminal output style')
    dv = 'True'; g.add_argument("--color", metavar='bool', type=str2bool, nargs='?', const=True, default=os.getenv('GITRB_COLOR', dv), help=f"Colorized output. Default {dv}.")
    g.add_argument('-v', '--verbose', action='count', dest='verbosity', default=1, help="Increase output verbosity. Can be repeated, e.g. -vv.")
    g.add_argument('-q', '--quiet', action='store_const', dest='verbosity', const=0, help="Suppress output.")

    # TODO: Add --add-submodule to add src-git as a {update=none, shallow, nonrecursive} submodule in artifact-commit.
    # TODO: Add --src-note to add+push a git-note in src-repo, that we have this artifact available.
    # TODO: Add --delete-expired to delete expired branches. Unreferenced objects can then be git-gc'd remote-side.

    args = parser.parse_args()
    printer.verbosity = args.verbosity
    printer.colorize = args.color

    printer.debug("Arguments:")
    for arg in vars(args):
        printer.debug(f"  '{arg}': '{getattr(args, arg)}'")

    # Sanity-check
    if args.push and not args.remote:
        printer.error("Error: `--push` requires `--remote`")
        return 1
    if args.push_tag and not args.push:
        printer.error("Error: `--push-tag` requires `--push`")
        return 1
    if args.force_tag and not args.force_branch:
        printer.error("Error: `--force-tag` requires `--force-branch`")
        return 1

    src_tree_root = exec(["git", "rev-parse", "--show-toplevel"])
    nca_dir = nca_path(src_tree_root, args.path)
    rbgit_dir=f"{nca_dir}/.rbgit"

    if args.rm_tmp and os.path.exists(rbgit_dir):
        printer.high_level(f"Deleting local bin repo, {rbgit_dir}, to start from clean-slate.", file=sys.stderr)
        shutil.rmtree(rbgit_dir)

    rbgit = RbGit(printer, rbgit_dir=rbgit_dir, rbgit_work_tree=nca_dir)
    if args.user_name:
        rbgit.cmd("config", "--local", "user.name", args.user_name)
    if args.user_email:
        rbgit.cmd("config", "--local", "user.email", args.user_email)

    printer.high_level(f"Making local commit of artifact {args.path} in artifact-repo at {rbgit.rbgit_dir}", file=sys.stderr)
    d = create_artifact_commit(rbgit, args.name, args.path, args.expire, args.add_ignored, args.src_remote_name)
    if d['bin_tag_name']:
        rbgit.set_tag(tag_name=d['bin_tag_name'], tag_val=d['bin_sha_commit'])
    printer.detail(rbgit.cmd("branch", "-vv"))
    printer.detail(rbgit.cmd("log", "-1", d['bin_branch_name']))

    remote_bin_name = "recyclebin"

    if args.remote:
        if args.remote == ".":
            src_git_dir = exec(["git", "rev-parse", "--absolute-git-dir"])
            printer.high_level(f"Will push artifact to local src-git, {src_git_dir}")
            args.remote = src_git_dir

        rbgit.add_remote_idempotent(name=remote_bin_name, url=args.remote)

    if args.push:
        push_branch(args, d, rbgit, remote_bin_name)

    if args.push_tag:
        push_tag(args, d, rbgit, remote_bin_name)

    if args.rm_expired:
        remote_delete_expired_branches(args, d, rbgit, remote_bin_name)

    if args.rm_tmp and os.path.exists(rbgit_dir):
        printer.high_level(f"Deleting local bin repo, {rbgit_dir}, to free-up disk-space.", file=sys.stderr)
        shutil.rmtree(rbgit_dir, ignore_errors=True)

    return 0


def push_branch(args, d, rbgit, remote_bin_name):
    # Push branch first, then meta-data (we don't want meta-data to be pushed if branch push fails).
    # Branch might exist already upstream.
    # Pushing may take long, so always show stdout and stderr without capture.
    printer.high_level(f"Pushing to remote artifact-repo: Artifact data on branch {d['bin_branch_name']}", file=sys.stderr)
    if args.force_branch:
        rbgit.cmd("push", "--force", remote_bin_name, d['bin_branch_name'], capture_output=False)
    else:
        if rbgit.remote_already_has_ref(remote_bin_name, d['bin_branch_name']):
            printer.always(f"Remote artifact-repo already has {d['bin_branch_name']} -- and we won't force push.")
        else:
            rbgit.cmd("push",        remote_bin_name, d['bin_branch_name'], capture_output=False)

    printer.high_level(f"Pushing to remote artifact-repo: Artifact meta-data {d['bin_ref_only_metadata']}", file=sys.stderr)
    if args.force_branch:
        rbgit.cmd("push", "--force", remote_bin_name, d['bin_ref_only_metadata'], capture_output=False)
    else:
        if rbgit.remote_already_has_ref(remote_bin_name, d['bin_ref_only_metadata']):
            printer.always(f"Remote artifact-repo already has {d['bin_ref_only_metadata']} -- and we won't force push.")
        else:
            rbgit.cmd("push",        remote_bin_name, d['bin_ref_only_metadata'], capture_output=False)


def push_tag(args, d, rbgit, remote_bin_name):
    if not d['bin_tag_name']:
        printer.error("Error: You are in Detached HEAD, so you can't push a tag to bin-remote with name of your source branch.", file=sys.stderr)
        return

    if d['src_commits_ahead'] != "" and int(d['src_commits_ahead']) >= 1:
        printer.error(f"Error: Your local branch is ahead by {d['src_commits_ahead']} commits of its upstream authoritative branch. Won't push tag to bin-remote.", file=sys.stderr)
        return

    remote_bin_sha_commit = rbgit.fetch_current_tag_value(remote_bin_name, d['bin_tag_name'])
    if remote_bin_sha_commit:
        printer.high_level(f"Bin-remote already has a tag named {d['bin_tag_name']} pointing to {remote_bin_sha_commit[:8]}.", file=sys.stderr)
        remote_meta = rbgit.fetch_cat_pretty(remote_bin_name, f"refs/artifact/meta-for-commit/{remote_bin_sha_commit}")

        commit_time_theirs = parse_commit_msg(remote_meta)['src-git-commit-time-commit']
        commit_time_ours = d['src_time_commit']
        commit_time_theirs_u = date_formatted2unix(commit_time_theirs, DATE_FMT_GIT)
        commit_time_ours_u = date_formatted2unix(commit_time_ours, DATE_FMT_GIT)
        printer.high_level(f"Our artifact {d['bin_sha_commit'][:8]} has src committer-time:   {commit_time_ours} ({commit_time_theirs_u})", file=sys.stderr)
        printer.high_level(f"Their artifact {remote_bin_sha_commit[:8]} has src committer-time: {commit_time_theirs} ({commit_time_ours_u})", file=sys.stderr)

        if commit_time_ours_u > commit_time_theirs_u:
            printer.high_level(f"Our artifact is newer than theirs. Updating...", file=sys.stderr)
            rbgit.cmd("push", "--force", remote_bin_name, d['bin_tag_name'])  # Push with force is necessary to update existing tag
        else:
            if not args.force_tag:
                printer.high_level(f"Our artifact is not newer than theirs. Leaving remote tag as-is.", file=sys.stderr)
            else:
                printer.high_level(f"Our artifact is not newer than theirs. Forcing update to remote tag.", file=sys.stderr)
                rbgit.cmd("push", "--force", remote_bin_name, d['bin_tag_name'])  # Push with force is necessary to update existing tag

    else:
        printer.high_level(f"Bin-remote does not have a tag named {d['bin_tag_name']} -- we'll publish it.", file=sys.stderr)
        rbgit.cmd("push", remote_bin_name, d['bin_tag_name'])  # Create new tag; push with force is not necessary


def remote_delete_expired_branches(args, d, rbgit, remote_bin_name):
    """
        Delete refs of expired branches on remote. Artifacts may still be kept alive by other refs, e.g. by latest-tag.
        Reclaiming disk-space on remote, requires running `git gc` or its equivalent -- _Housekeeping_ on GitLab.
        See https://docs.gitlab.com/ee/administration/housekeeping.html
        TODO: Library to RPC trigger housekeeping/GC for {gitlab, github, gittea, gerrit, gitetcetc}?
    """
    branch_prefix = "artifact/expire/"
    lines = rbgit.cmd("ls-remote", "--heads", remote_bin_name, f"refs/heads/{branch_prefix}*").splitlines()

    now = datetime.datetime.now(tzlocal())

    for line in lines:
        _, branch = line.split(maxsplit=1)

        # Timezone may be absent, but we insist on date and time
        date_time_tz = parse_expire_date(branch)
        if date_time_tz['date'] == None: continue
        if date_time_tz['time'] == None: continue
        if date_time_tz['tzoffset'] == None:
            date_time_tz['tzoffset'] = datetime.datetime.strftime(now, "%z")

        compliant_expire_string = f"{date_time_tz['date']}/{date_time_tz['time']}{date_time_tz['tzoffset']}"
        expiry = date_parse_formatted(date_string=compliant_expire_string, date_format=DATE_FMT_EXPIRE)
        delta_formatted = format_timespan(dt_from=now, dt_to=expiry)

        if expiry.timestamp() > now.timestamp():
            printer.detail("Active", delta_formatted, branch)
            continue

        printer.high_level("Expired", delta_formatted, branch)
        rbgit.cmd("push", remote_bin_name, "--delete", branch)


if __name__ == "__main__":
    ret = main()
    sys.exit(ret)
