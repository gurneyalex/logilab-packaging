#!/usr/bin/python

from distutils.core import setup
from distutils.command import install_lib

import __pkginfo__

STD_BLACKLIST = ('CVS', '.svn', '.hg', 'debian', 'dist', 'build')

IGNORED_EXTENSIONS = ('.pyc', '.pyo', '.elc', '~')

if __name__ == '__main__':
    setup(name = __pkginfo__.distname,
          version = __pkginfo__.version,
         )
