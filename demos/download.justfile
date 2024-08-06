demo1:
    @mkdir -p ../tmp
    touch ../tmp/{1..3} && ls ../tmp
    git_recycle_bin.py push \
        . \
        --path ../tmp \
        --name tmp \
        --add-ignored \
        --user-name "foo" --user-email "a@b"
    rm ../tmp/{1..2} && ls ../tmp
    git_recycle_bin.py list . \
    | xargs -I _ git_recycle_bin.py download --force . _
    ls ../tmp
    ls .
    @rm -rf ../tmp
