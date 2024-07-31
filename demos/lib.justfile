_remove_artifacts:
    git ls-remote --refs . \
    | grep "artifact" \
    | awk '{print $2}' \
    | xargs -I _ git update-ref -d _
