#!/usr/bin/env python
"""USAGE: cvs status | cvstatus [OPTIONS]

OPTIONS:
   -h / --help
        display this help message
   -u / --uptodate
        show status of up-to-date files
   -m / --module-level <num>
        display file name without the first <num> directories
        (default is 0)
"""

from logilab.devtools.vcslib.cvsparse import StatusLineHandler, parse
import sys
import getopt

def run(args):
    """parse 'cvs status' output according to command line arguments
    """
    l_opt = ['help', 'uptodate', 'module-level=']
    s_opt = 'hum:'
    opts, args = getopt.getopt(args, s_opt, l_opt)
    noup = 1
    mod_level = 0
    for opt, val in opts:
        if opt in ('-h','--help'):
            print __doc__
            return
        elif opt in ('-u','--uptodate'):
            noup = 0
        elif opt in ('-m','--module-level'):
            mod_level = int(val)
    handler = StatusLineHandler(noup, mod_level)
    unknowns = parse(sys.stdin, handler)
    if unknowns:
        print '----  Unknown files:'
        print '\n'.join(unknowns)

if __name__ == '__main__':
    run(sys.argv[1:])
