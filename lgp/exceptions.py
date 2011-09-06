"""Exceptions package

:organization: Logilab
:copyright: 2008-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

import logging


class LGPException(Exception):
    """generic lgp exception"""
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return str(self.value)
    def exitcode(self):
        return 1

class LGPCommandException(LGPException):
    """subprocess lgp exception"""
    def __init__(self, value, cmd=None):
        LGPException.__init__(self, value)
        self.cmd = cmd
        if cmd:
            msg = "command '%s' returned non-zero exit status %s" \
                  % (' '.join(cmd.cmd), cmd.returncode)
            logging.warn(msg)
    def __str__(self):
        return self.value

    def exitcode(self):
        return self.cmd.returncode

class ArchitectureException(LGPException):
    """architecture availability exception"""

class DistributionException(LGPException):
    """distribution availability exception"""

class SetupException(LGPException):
    pass
