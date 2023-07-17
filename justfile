

# Prepare the git repository, if it doesn't already exist
prep:
    #!/usr/bin/env bash
    set -eu
    export PATH="${PATH}:{{justfile_directory()}}"
    cd "{{invocation_directory()}}"
    export RBGIT_DIR="${PWD}/.rbgit"
    export RBGIT_WORK_TREE="${PWD}"

    # Check if .rbgit folder exists, if not, init git
    rbgit rev-parse --is-inside-work-tree >/dev/null 2>&1 && { echo "OK: .rbgit already exists" >&2; exit 0; }
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

    BRANCH_NAME="auto/checkpoint/${SRC_REPO}/${SRC_SHA}/{{artifactname}}"


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
            echo "auto: ${SRC_REPO}@${SRC_SHA_SHORT}: Build of {{binpath}}"
        } | rbgit commit-tree -F - "$treeish"
    )
    echo "Wrote commit: ${commit}"

    rbgit update-ref refs/heads/${BRANCH_NAME} ${commit}
    echo "Wrote ref '${BRANCH_NAME}' pointing to ${commit}"



# Push to the remote repository
push sha remote:
    # Push the specified SHA to the specified remote
    git push {{remote}} {{sha}}

