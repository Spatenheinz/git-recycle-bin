import sys
import subprocess
from printer import printer

def exec(command):
    printer.debug("Run:", command, file=sys.stderr)
    return subprocess.check_output(command, text=True).strip()
