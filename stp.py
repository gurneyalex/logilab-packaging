#!/usr/bin/env python
""" a Simple Text Preprocessor

USAGE: stp input-file PATTERN VALUE [PATTERN VALUE]...

will print the content of input-file where all occurencies of '%PATTERN%' will
be replaced by 'VALUE'
"""

import sys
import getopt

__revision__ = '$Id: stp.py,v 1.9 2005-07-25 22:44:21 syt Exp $'

def parse_stream(stream, patterns, output=sys.stdout):
    """parse the given input stream, replace patterns according to the
    <patterns> dictionnary and write result to the output stream (default to
    stdout)
    """
    real_patterns = {}
    for pattern, value in patterns.items():
        real_patterns['%%%s%%' % pattern] = str(value)
    for line in stream.readlines():
        for pattern, value in real_patterns.items():
            if line.find(pattern) > -1:
                line = line.replace(pattern, value)
        output.write(line)
    

def run(args):
    """run stp"""
    opts, args = getopt.getopt(args, 'h', 'help')
    if opts:
        print __doc__
        return
    patterns = {}
    for i in range(1, len(args), 2):
        patterns[args[i]] = args[i+1]
    parse_stream(open(args[0], 'r'), patterns)

if __name__ == '__main__':
    run(sys.argv[1:])
