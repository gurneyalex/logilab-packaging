
import sys
import os, os.path as osp
import logging

from narvalbot.prototype import input, output
from narvalbot.elements import FilePath

import cubes.apycot
import apycotlib as apycot
from apycotlib.checkers import BaseChecker, AbstractFilteredFileChecker

STEP_DEBIANPKG = 3

from logilab.devtools.lgp import *

@apycot.apycotaction('lgp.check', 'CHECKEDOUT in elmt.done_steps')
def act_lgp_check(inputs):
    test = inputs['apycot']
    cwd = os.getcwd()
    os.chdir(test.project_path())
    try:
        checker, status = test.run_checker('lgp.check', inputs.get('options'))
    finally:
        os.chdir(cwd)
    return {}

@output('changes-files', 'isinstance(elmt, FilePath)', 'elmt.type == "debian.changes"', list=True)
@apycot.apycotaction('lgp.build', 'CHECKEDOUT in elmt.done_steps')
def act_lgp_build(inputs):
    test = inputs['apycot']
    checker, status = test.run_checker('lgp.build', inputs.get('options'))
    return {'changes-files': checker.debian_changes}

class LgpLogHandler(logging.Handler):
    def __init__(self, writer):
        logging.Handler.__init__(self)
        self.writer = writer
        self.path = None
        self.status = apycot.SUCCESS

    def emit(self, record):
        if record.levelno >= logging.CRITICAL:
            f = self.writer.fatal
            self.status = apycot.FAILURE
        elif record.levelno >= logging.ERROR:
            f = self.writer.error
            self.status = apycot.FAILURE
        elif record.levelno >= logging.WARNING:
            f = self.writer.warning
        elif record.levelno >= logging.INFO:
            f = self.writer.info
        else:
            f = self.writer.debug
        f(record.getMessage(), path=self.path)

class LgpCheckChecker(BaseChecker):
    """run tests on a project with lgp"""

    id = 'lgp.check'
    command = 'check'
    options_def = {
    }

    def do_check(self, test):
        cmd = LGP.get_command(self.command)
        handler = LgpLogHandler(self.writer)
        cmd.logger.addHandler(handler)
        exit_status = cmd.main_run(['-vv'], LGP.rcfile)
        if exit_status:
            self.writer.fatal('lgp %s exited with status %s', self.command, exit_status)
            self.set_status(apycot.ERROR)
        return apycot.SUCCESS

apycot.register('checker', LgpCheckChecker)

class LgpBuildChecker(BaseChecker):
    """build debian packages with lgp"""

    id = 'lgp.build'
    command = 'build'
    options_def = {
        'lgp_build_distrib': {
            'type': 'csv',
            'help': ('comma-separated list of distributions to build against'),
        },
        'lgp_sign': {
            'help': ('whether to sign packages'),
            'default': 'no',
        },
        'lgp_suffix': {
            'help': ('append vcs revision to the package version'),
        },
    }

    def do_check(self, test):
        dist = self.options.get('lgp_build_distrib') or ['all']
        sign = self.options.get('lgp_sign')
        suffix = self.options.get('lgp_suffix')
        cwd = os.getcwd()
        os.chdir(test.project_path())
        repo = test.apycot_repository()
        try:
                handler = LgpLogHandler(self.writer)
                cmd = LGP.get_command(self.command)
                cmd.logger.addHandler(handler)
                args = ['-v', '-s', sign, '-d', ','.join(dist), '-r', os.path.join(test.project_path(), '..')]
                if suffix:
                    args += ['--suffix', '~rev%s' % repo.revision()]
                exit_status = cmd.main_run(args, LGP.rcfile)
                self.debian_changes = [FilePath(changes, type='debian.changes', distribution=os.path.basename(os.path.dirname(changes)))
                                       for changes in cmd.packages if changes.endswith('.changes')]
                if exit_status:
                    self.writer.fatal('lgp %s exited with status %s', self.command, exit_status)
                    self.set_status(apycot.ERROR)
                else:
                    test.done_steps.add(STEP_DEBIANPKG)
        finally:
            os.chdir(cwd)
        return handler.status

apycot.register('checker', LgpBuildChecker)
