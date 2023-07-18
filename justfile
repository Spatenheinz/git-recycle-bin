
# Create a checkpoint - an artifact which has traceability and expiry
checkpoint  artifact_name  binpath:
    #!/usr/bin/env bash
    set -eu
    export PATH="${PATH}:{{justfile_directory()}}"
    cd "{{invocation_directory()}}"

    TTL="30 days" # from commiter date! so don't set this too-low

    SRC_SHA="$(git rev-parse HEAD)"
    SRC_SHA_SHORT="$(git rev-parse --short HEAD)"
    SRC_SHA_TITLE="$(git show --no-patch --format=%B ${SRC_SHA} | head -1)"
    SRC_REPO="$(basename $(git config --get remote.origin.url))"
    SRC_REPO_URL="$(git config --get remote.origin.url)"
    SRC_TREE_PWD="{{invocation_directory()}}"

    BRANCH_NAME="auto/checkpoint/${SRC_REPO}/${SRC_SHA}/{{artifact_name}}"

    NCA_DIR="$({{just_executable()}} -f {{justfile()}} nca_dir  ${SRC_TREE_PWD}  {{binpath}})"
    BINPATH_REL="$({{just_executable()}} -f {{justfile()}} rel_dir  ${SRC_TREE_PWD}  {{binpath}})"

    export RBGIT_DIR="${NCA_DIR}/.rbgit"
    export RBGIT_WORK_TREE="${NCA_DIR}"

    # Check if .rbgit folder exists, if not, init and configure
    rbgit rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
        rbgit init --initial-branch master "${RBGIT_WORK_TREE}"
        rbgit config --local core.autocrlf false  # preserve files with their own line-endings
        echo ".rbgit/" > "${RBGIT_DIR}/info/exclude"
    }

    # Check if the branch already exists
    if rbgit show-ref --verify --quiet "refs/heads/${BRANCH_NAME}"; then
        rbgit checkout "${BRANCH_NAME}"  # If it exists, just switch to that branch
    else
        rbgit checkout --orphan "${BRANCH_NAME}"  # If it doesn't exist, create it as an orphan branch
    fi

    echo "Adding '{{binpath}}' as '${BINPATH_REL}' ..." >&2
    rbgit add {{binpath}}

    if rbgit diff-index --quiet --cached HEAD >/dev/null 2>&1; then
        echo "No changes staged for the next commit" >&2
        exit 0
    fi

    echo "Committing" >&2
    {
        echo -n "auto: ${SRC_REPO}@${SRC_SHA_SHORT}: {{artifact_name}}: @(${SRC_SHA_TITLE}" | awk '{print substr($0,1,70)}' | awk '{$1=$1; print $0}' | awk '{print $0,")"}'
        echo ""
        echo "This is an automatically made commit which contains some artifacts built from the source repo."
        echo ""
        echo "artifact-name: {{artifact_name}}"
        echo "time-to-live: ${TTL}"
        echo "binpath-arg: {{binpath}}"
        echo "binpath-rel: ${BINPATH_REL}"
        echo "git-src-repo: ${SRC_REPO}"
        echo "git-src-repo-url: ${SRC_REPO_URL}"
        echo "git-src-branch: $(git rev-parse --abbrev-ref HEAD)"
        echo "git-src-commit-sha: ${SRC_SHA}"
        echo "git-src-commit-title: ${SRC_SHA_TITLE}"

        # Source commit may or may not have a Gerrit Change-ID
        git show --no-patch --format=%B ${SRC_SHA} | awk '/^Change-Id:/{print "git-src-commit-changeid:", $2}' | tail -1

        # Source workspace may be dirty
        git status --porcelain=1 --untracked-files=no | awk '{print "git-status:", $0}'  # Including untracked files gives too much noise
    } | (
        # Make our new commit reproducible: Do not sample the current time, but copy it from the source.
        export GIT_AUTHOR_DATE="$(git show -s --format=%aD ${SRC_SHA})"
        export GIT_COMMITTER_DATE="$(git show -s --format=%cD ${SRC_SHA})"
        rbgit commit --file - --quiet --no-status --untracked-files=no
    )




# Push to the remote repository
push sha remote:
    # Push the specified SHA to the specified remote
    git push {{remote}} {{sha}}



# NearestCommonAncestor(context.abs, query.abs)
nca_dir  pathA  pathB:
    #!/usr/bin/env python3
    import os
    from itertools import takewhile

    # Get absolute paths. Inputs may be relative, so chdir to invocation dir first, and split paths into components
    os.chdir('{{invocation_directory()}}')
    components1 = os.path.abspath('{{pathA}}').split(os.sep)
    components2 = os.path.abspath('{{pathB}}').split(os.sep)

    # Use zip to iterate over pairs of components
    # Stop when components differ, thanks to the use of itertools.takewhile
    common_components = list(takewhile(lambda x: x[0]==x[1], zip(components1, components2)))

    # The common path is the joined common components
    common_path = os.sep.join([x[0] for x in common_components])
    print(common_path)


# Relativize query path from NearestCommonAncestor(context.abs, query.abs)
rel_dir  context  query:
    #!/usr/bin/env python3
    import os
    from itertools import takewhile

    # Get absolute paths. Inputs may be relative, so chdir to invocation dir first, and split paths into components
    os.chdir('{{invocation_directory()}}')
    abs_context = os.path.abspath('{{context}}')
    abs_query = os.path.abspath('{{query}}')

    components1 = abs_context.split(os.sep)
    components2 = abs_query.split(os.sep)

    # Use zip to iterate over pairs of components
    # Stop when components differ, thanks to the use of itertools.takewhile
    common_components = list(takewhile(lambda x: x[0]==x[1], zip(components1, components2)))

    # The common path is the joined common components
    common_path = os.sep.join([x[0] for x in common_components])

    print(os.path.relpath(abs_query, common_path))
