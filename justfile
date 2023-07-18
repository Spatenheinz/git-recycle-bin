

# Prepare the git repository, if it doesn't already exist
prep:
    #!/usr/bin/env bash
    set -eu
    export PATH="${PATH}:{{justfile_directory()}}"
    cd "{{invocation_directory()}}"
    export RBGIT_DIR="${PWD}/.rbgit"
    export RBGIT_WORK_TREE="${PWD}"

    # Check if .rbgit folder exists, if not, init and configure
    rbgit rev-parse --is-inside-work-tree >/dev/null 2>&1 && exit 0
    rbgit init .
    rbgit config --local core.autocrlf false  # preserve files with their own line-endings


# Create a checkpoint - an artifact which has traceability and expiry
checkpoint  artifactname  binpath: prep
    #!/usr/bin/env bash
    set -eu
    export PATH="${PATH}:{{justfile_directory()}}"
    cd "{{invocation_directory()}}"
    export RBGIT_DIR="${PWD}/.rbgit"
    export RBGIT_WORK_TREE="${PWD}"

    # Set the source SHA to the current SHA of the local repo
    SRC_SHA="$(git rev-parse HEAD)"
    SRC_SHA_SHORT="$(git rev-parse --short HEAD)"

    # Set the source repo to the basename of git remote origin
    SRC_REPO="$(basename $(git config --get remote.origin.url))"
    SRC_REPO_URL="$(git config --get remote.origin.url)"

    BRANCH_NAME="auto/checkpoint/${SRC_REPO}/${SRC_SHA}/{{artifactname}}"

    BINPATH_REL="$({{just_executable()}} -f {{justfile()}} rel_dir  ${PWD}  {{binpath}})"

    # Find all files under directory, create blob objects for them, and add them to the Git index
    (
        # Change directory first so update-index gets a rooted path.
        cd {{binpath}}
        find . -type f -printf "%P\n" | while read file; do
            blobhash="$(rbgit hash-object -w "${file}")"
            rbgit update-index --add --cacheinfo 100644,${blobhash},"${file}"  # TODO: Fix perms
        done
    )

    # Create a tree object with the content of the Git index
    treeish="$(rbgit write-tree)"
    echo "Wrote treeish: ${treeish}" >&2

    # NOTE: The treeish will always be the same, but the commit will always change due to date.
    #       This means pushes of same bin content will always give new commit-SHA.
    #       To fix this, we could set the date to that of the SRC_REPO's commit time or ask the remote if already has the treeish.
    # Create a new commit with the new tree object
    commit=$(
        # Make our new commit reproducible: Do not sample the current time, but copy it from the source.
        export GIT_AUTHOR_DATE="$(git show -s --format=%aD ${SRC_SHA})"
        export GIT_COMMITTER_DATE="$(git show -s --format=%cD ${SRC_SHA})"

        {
            echo "auto: ${SRC_REPO}@${SRC_SHA_SHORT}: {{artifactname}}"
            echo ""
            echo "This is an automatically made commit which contains some artifacts"
            echo "built from the source repo."
            echo ""
            echo "artifactname: {{artifactname}}"
            echo "binpath_arg: {{binpath}}"
            echo "binpath_rel: ${BINPATH_REL}"
            echo "TTL: 30 days"  # from commiter date! so don't set this too-low
            echo ""
            echo "git_src_repo:     ${SRC_REPO}"
            echo "git_src_repo_url: ${SRC_REPO_URL}"
            echo "git_src_sha:      ${SRC_SHA}"
            echo "git_src_branch:   $(git rev-parse --abbrev-ref HEAD)"
            echo ""
            git status --porcelain=1 --untracked-files=no | awk '{print "git_status:", $0}'  # Including untracked files gives too much noise
        } | rbgit commit-tree -F - "$treeish"
    )
    echo "Wrote commit: ${commit}" >&2

    rbgit update-ref refs/heads/${BRANCH_NAME} ${commit}
    echo "Wrote ref '${BRANCH_NAME}' pointing to ${commit}" >&2



# Push to the remote repository
push sha remote:
    # Push the specified SHA to the specified remote
    git push {{remote}} {{sha}}



# Relativize query path from NearestCommonAncestor(context.abs, query.abs)
rel_dir  context  query:
    #!/usr/bin/env python3
    import os
    from itertools import takewhile

    abs_context = os.path.abspath('{{context}}')
    abs_query = os.path.abspath('{{query}}')

    # Get absolute paths and split paths into components
    components1 = abs_context.split(os.sep)
    components2 = abs_query.split(os.sep)

    # Use zip to iterate over pairs of components
    # Stop when components differ, thanks to the use of itertools.takewhile
    common_components = list(takewhile(lambda x: x[0]==x[1], zip(components1, components2)))

    # The common path is the joined common components
    common_path = os.sep.join([x[0] for x in common_components])

    print(os.path.relpath(abs_query, common_path))
