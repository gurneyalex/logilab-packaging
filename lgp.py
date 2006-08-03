# -*- encoding: iso-8859-15 -*-

import sys
from optparse import OptionParser as OP

USAGE = """lgp - logilab packaging tool

lgp prepare - process to prepare distrib (pylint, checkpkg, check vcs, etc.)
lgp make - process to build distrib (build, tag, etc.)
lgp test - test distrib (linda, lintian, piuparts)

lgp tag - tag package
lgp build - build debian package
lgp check - check package 
lgp info - gives package information

"""

class OptionParser(OP):

    def __init__(self, *args, **kwargs):
        OP.__init__(self, *args, **kwargs)
        self._commands = {}
        self.min_args, self.max_args = 0, 0
        
    def add_command(self, name, module, help=''):
        self._commands[name] = (module, help)

    def parse_command(self, args):
        if len(args) == 0:
            self.error('no command given')
        cmd = args[0]
	args = args[1:]
        if cmd not in self._commands:
            self.error('unknow command')
        self.prog = '%s %s' % (self.prog, cmd)
        exec('from %s import run, add_options'%self._commands[cmd][0])
        add_options(self)
        (options, args) = self.parse_args(args)        
        if not (self.min_args <= len(args) <= self.max_args):
            self.error('incorrect number of arguments')
        return run, options, args
        

def run(args):
    parser = OptionParser()
    parser.usage = 'lgp COMMAND [options] <arg> ...'
    COMMANDS = [('prepare','logilab.devtools.preparedist'),
                ('make','logilab.devtools.makedist'),
                ('test','logilab.devtools.testdist'),
                ('build','logilab.devtools.buildpackage'),
                ('tag','logilab.devtools.tagpackage'),
                ('check', 'logilab.devtools.checkpackage'),
                ('info', 'logilab.devtools.pkginfo'),
                ]
    for item in COMMANDS:
        parser.add_command(*item)
    run, options, args = parser.parse_command(sys.argv[1:])
    run(options, args)

if __name__ == '__main__':
    run(sys.argv[1:])

