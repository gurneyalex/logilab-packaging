"""Exceptions package

:organization: Logilab
:copyright: 2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

import logging


class LGPException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return self.value

class LGPCommandException(LGPException):
    def __init__(self, value, cmd=None):
        self.value = value
        if cmd:
            msg = "command '%s' returned non-zero exit status %s" \
                  % (' '.join(cmd.cmd), cmd.returncode)
            logging.error(msg)
    def __str__(self):
        return self.value
 
class ArchitectureException(LGPException):
   def __str__(self):
        return "unknown architecture '%s'" % self.value

class DistributionException(LGPException):
    def __str__(self):
        return "unknown distribution '%s'" % self.value
