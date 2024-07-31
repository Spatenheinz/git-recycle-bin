import argparse
import os

def str2bool(v):
    if isinstance(v, bool):
       return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

def parse_args():
    class CustomHelpFormatter(argparse.HelpFormatter):
        def __init__(self, prog):
            super().__init__(prog, indent_increment=2, max_help_position=40)

    def bool_arg(parser, option: str, env_variable: str, default_value, help=""):
        parser.add_argument(option, metavar='bool', type=str2bool, nargs='?', const=True, default=os.getenv(env_variable, default_value), help=help)

    # top parser describes the options which should be available for all commands
    top_parser = argparse.ArgumentParser(description="Generic", add_help=False, formatter_class=CustomHelpFormatter)

    g = top_parser.add_argument_group('niche options')
    g.add_argument(               "--user-name",       metavar='fullname', required=False, type=str, default=os.getenv('GITRB_USERNAME'), help="Author of artifact commit. Defaults to yourself.")
    g.add_argument(               "--user-email",      metavar='address',  required=False, type=str, default=os.getenv('GITRB_EMAIL'),    help="Author's email of artifact commit. Defaults to your own.")
    dv = 'origin'; g.add_argument("--src-remote-name", metavar='name',     required=False, type=str, default=os.getenv('GITRB_SRC_REMOTE', dv), help=f"Name of src repo's remote. Defaults {dv}.")
    dv = 'False';  g.add_argument("--add_ignored",     metavar='bool', type=str2bool, nargs='?', const=True, default=os.getenv('GITRB_ADD_IGNORED', dv), help=f"Add despite gitignore. Default {dv}.")
    dv = 'False';  g.add_argument("--force-branch",    metavar='bool', type=str2bool, nargs='?', const=True, default=os.getenv('GITRB_FORCE_BRANCH', dv), help=f"Force push of branch. Default {dv}.")
    dv = 'False';  g.add_argument("--force-tag",       metavar='bool', type=str2bool, nargs='?', const=True, default=os.getenv('GITRB_FORCE_TAG', dv), help=f"Force push of tag. Default {dv}.")
    dv = 'True' ;  g.add_argument("--rm-tmp",          metavar='bool', type=str2bool, nargs='?', const=True, default=os.getenv('GITRB_RM_TMP', dv), help=f"Remove local bin-repo. Default {dv}.")

    g = top_parser.add_argument_group('terminal output style')
    g.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS, help="Show this help message and exit.")
    g.add_argument('-v', '--verbose', action='count', dest='verbosity', default=1, help="Increase output verbosity. Can be repeated, e.g. -vv.")
    g.add_argument('-q', '--quiet', action='store_const', dest='verbosity', const=0, help="Suppress output.")
    dv = 'True' ;  g.add_argument("--color", metavar='bool', type=str2bool, nargs='?', const=True, default=os.getenv('GITRB_COLOR', dv), help=f"Colorized output. Default {dv}.")

    parser = argparse.ArgumentParser(description="Create and push artifacts in git - with expiry and traceability.", parents=[top_parser], add_help=False)

    commands = parser.add_subparsers(dest='command')
    commands.required = True
    g = commands.add_parser("push", parents=[top_parser], add_help=False, help="push artifact")
    g.add_argument(                   "remote",       metavar='URL', type=str, help="Git remote URL")
    g.add_argument(                   "--path",       metavar='file|dir', required=True,  type=str, default=os.getenv('GITRB_PATH'),       help="Path to artifact in src-repo. Directory or file.")
    g.add_argument(                   "--name",       metavar='string',   required=True,  type=str, default=os.getenv('GITRB_NAME'),       help="Name to assign to the artifact. Will be sanitized.")
    dv = 'in 30 days'; g.add_argument("--expire",     metavar='fuzz',     required=False, type=str, default=os.getenv('GITRB_EXPIRE', dv), help=f"Expiry of artifact's branch. Fuzzy date. Default '{dv}'.")
    dv = 'False';      g.add_argument("--tag",        metavar='bool', type=str2bool, nargs='?', const=True, default=os.getenv('GITRB_PUSH_TAG', dv), help=f"Push tag to artifact to remote. Default {dv}.")
    dv = 'False';      g.add_argument("--push-note",  metavar='bool', type=str2bool, nargs='?', const=True, default=os.getenv('GITRB_PUSH_NOTE', dv),     help=f"Push note to src remote. Default {dv}.")
    dv = 'False';      g.add_argument("--rm-expired", metavar='bool', type=str2bool, nargs='?', const=True, default=os.getenv('GITRB_RM_EXPIRED', dv), help=f"Delete expired artifact branches. Default {dv}.")
    dv = 'False';      g.add_argument("--flush-meta", metavar='bool', type=str2bool, nargs='?', const=True, default=os.getenv('GITRB_RM_FLUSH_META', dv), help=f"Delete expired meta-for-commit refs. Default {dv}.")

    g = commands.add_parser("clean", parents=[top_parser], add_help=False, help="clean expired artifacts")
    g.add_argument("remote", metavar='URL', type=str, help="Git remote URL")
    return parser.parse_args()
