import os
import subprocess

class RbGit:
    def __init__(self, rbgit_dir=None, rbgit_work_tree=None):
        self.rbgit_dir = rbgit_dir if rbgit_dir else os.environ["RBGIT_DIR"]
        self.rbgit_work_tree = rbgit_work_tree if rbgit_work_tree else os.environ["RBGIT_WORK_TREE"]
        self.init_idempotent()

    def cmd(self, *args, input=None, capture_output=True):
        # Override environment variables
        envcopy = os.environ.copy()
        envcopy["GIT_DIR"] = self.rbgit_dir
        envcopy["GIT_WORK_TREE"] = self.rbgit_work_tree

        # execute the git command with the modified environment
        print("Run:", ["rbgit", *args])
        result = subprocess.run(["git", *args], input=input, env=envcopy, capture_output=capture_output, text=True)

        # If the subprocess exited with a non-zero return code, raise an error
        if result.returncode != 0:
            raise RuntimeError(f"RbGit command failed with error: {result.stderr}")

        # return the result of the command
        return result.stdout

    def init_idempotent(self):
        try:
            # Check if inside git work tree
            self.cmd("rev-parse", "--is-inside-work-tree")
        except RuntimeError:
            # Initialize git and configure
            self.cmd("init", "--initial-branch", "master", self.rbgit_work_tree)
            self.cmd("config", "--local", "core.autocrlf", "false")

        # Exclude .rbgit from version control
        with open(f"{self.rbgit_dir}/info/exclude", "w") as file:
            file.write(".rbgit/\n")

    def checkout_orphan_idempotent(self, branch_name: str):
        try:
            # Try to checkout the branch, if it exists
            self.cmd("show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}")
            self.cmd("checkout", branch_name)
        except RuntimeError:
            # If the branch doesn't exist, create it as an orphan
            self.cmd("checkout", "--orphan", branch_name)

    def add(self, binpath: str) -> bool:
        # TODO: Check binpath exists
        changes = False
        self.cmd("add", binpath)

        try:
            # Check if there are any changes staged for the next commit
            self.cmd("diff-index", "--quiet", "--cached", "HEAD")
        except RuntimeError:
            # If diff-index command failed, it means there are changes staged for the next commit
            changes = True

        return changes

    def add_remote_idempotent(self, name: str, url: str):
        try:
            self.cmd("remote", "add", name, url)
        except RuntimeError:
            # If the remote already exists, set its URL
            self.cmd("remote", "set-url", name, url)

    def fetch_only_tags(self, remote: str):
        self.cmd("fetch", remote, 'refs/tags/*:refs/tags/*')

    def set_tag(self, tag_name: str, tag_val: str):
        self.cmd("tag", "--force", tag_name, tag_val)

    def tree_size(self, ref: str = "HEAD") -> int:
        """ Accumulated recursively-walked size of tree. Git stores sparsely and compressed which is not accounted for here """
        lines = self.cmd("ls-tree", "-lr", ref)

        # Parse output:
        # - Split into lines
        # - Extract the 4th column (size) from each line
        # - Convert to int
        # - Sum the sizes
        sizes = [int(re.split(r'\s+', line)[3]) for line in lines.splitlines()]
        return sum(sizes)
