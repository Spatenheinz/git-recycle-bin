#!/usr/bin/env python

from setuptools import setup, find_packages

setup(name='git-recycle-bin',
      # Modules to import from other scripts:
      packages=find_packages(),
      # Executables
      scripts=["src/artifact.py"],
     )

