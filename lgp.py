# -*- encoding: iso-8859-15 -*-

import sys
from optparse import OptionParser

USAGE = """lgp - logilab packaging tool

lgp prepare - process to prepare distrib (pylint, checkpkg, check vcs, etc.)
lgp make - process to build distrib (build, tag, etc.)
lgp checkd - check distribution

lgp tag - tag package
lgp build - build debian package
lgp check - check package 

"""

def get_parser():
    """
    make option parser with standard/shared options
    """
    parser = OptionParser()
    parser.usage = 'lgp COMMAND [options] <arg> ...'
    parser.min_args, parser.max_args = 0, 0
    return parser

def run(args):
    if len(args) > 0:
        cmd = args[0]
	args = args[1:]
    else:
        cmd = '--help'
    if 'new'.startswith(cmd):
        from logilab.devtools.mkproj import run, add_options
    elif 'prepare'.startswith(cmd):
        from logilab.devtools.preparedist import run, add_options
    elif 'make'.startswith(cmd):
        from logilab.devtools.makedist import run, add_options
    elif 'checkd' == cmd:
        from logilab.devtools.checkdist import run, add_options
    elif 'build'.startswith(cmd):
        from logilab.devtools.buildpackage import run, add_options
    elif 'tag'.startswith(cmd):
        from logilab.devtools.tagpackage import run, add_options
    elif 'check' == cmd:
        from logilab.devtools.checkpackage import run, add_options
    else:
        print USAGE
	sys.exit(1)

    parser = get_parser()
    add_options(parser)
    (options, args) = parser.parse_args(args)
    if not (parser.min_args <= len(args) <= parser.max_args):
        parser.error('incorrect number of arguments')

    run(options, args)

if __name__ == '__main__':
    run(sys.argv[1:])

