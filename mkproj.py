""" create an python project hierarchy, conforming to the one described in
standard_source_tree.

USAGE: mkproj [OPTIONS] <PACKAGENAME>

OPTIONS:
  -h / --help
       display this help message
"""

__revision__ = "$Id $"

import os
import sys
import getopt

from os.path import join, isdir, exists
from logilab.devtools import TEMPLATE_DIR, stp

STD_DIRS = ['bin', 'doc', 'dtd', 'examples', 'man', 'test', 'xsl']

TEMPLATED = ['__init__.py', 'setup.py', 'announce.txt', '__pkginfo__.py',
             'test/runtests.py']


def run(args):
    """create a new package skeleton
    """
    options, args = getopt.getopt(args, 'h', ['help'])
    if options:
        print __doc__
        sys.exit(0)
            
    if not args:
        print __doc__
        sys.exit(1)
        
    modname = args[0]
    patterns = {'MODNAME': modname}

    try:
        os.mkdir(modname)
    except OSError:
        assert isdir(modname)
    
    for directory in STD_DIRS:
        directory = join(modname, directory)
        try:
            os.mkdir(directory)
        except OSError:
            assert isdir(directory)
        
    for template in TEMPLATED:
        filepath = join(modname, template)
        if not exists(filepath):
            output = open(filepath, 'w')
            stp.parse_stream(open(join(TEMPLATE_DIR, template)),
                             patterns, output)
            output.close()
        
if __name__ == '__main__':
    run(sys.argv[1:])
