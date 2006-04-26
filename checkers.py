# Copyright (c) 2003-2005 LOGILAB S.A. (Paris, FRANCE).
# http://www.logilab.fr/ -- mailto:contact@logilab.fr

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.

# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
"""Some APyCoT extensions

those extensions will be incorporated in the tester distribution, they are
only there to provide backward compat for some time.
"""

__revision__ = "$Id: checkers.py,v 1.10 2005-06-20 10:35:21 syt Exp $"


from time import localtime, time, strftime

try:
    from apycot.interfaces import IChecker
    from apycot.utils import SimpleOptionsManagerMixIn
    from apycot.checkers import register_checker
except ImportError:
    from tester.interfaces import IChecker
    from tester.utils import SimpleOptionsManagerMixIn
    from tester.checkers import register_checker

from logilab.devtools.check_package import *

class ReporterWrapper:
    """ report messages and layouts in plain text
    """
    
    def __init__(self, writer):
        self.writer = writer
        self.counts = None
        self.reset()
        
    def reset(self):
        """reset counters"""
        self.counts = {}
        for sev in (INFO, WARNING, ERROR, FATAL):
            self.counts[sev] = 0
        
    def log(self, severity, path, line, msg):
        """log a message of a given severity
        
        line may be None if unknown
        """
        self.counts[severity] += 1
        self.writer.log(severity, path, line, msg)


# Tester checkers #############################################################

class ZopePackageChecker(SimpleOptionsManagerMixIn):
    """check standard zope package :
    
    * __pkginfo__.py
    
    * release number mismatch
    
    * test directory structure

    * announce.txt template
    """
    
    __implements__ = IChecker
    __name__ = 'zope_pkg'
    __checks__ = (check_info_module, check_release_number, check_test,
                  check_announce)
        
    def run(self, test, writer):
        """run the checker against <path> (usually a directory)"""
        status = 1
        reporter = ReporterWrapper(writer)
        for check_func in self.__checks__:
            reporter.reset()
            _status = check_func(reporter, test.path)
            status = status and _status
        return status


class PythonPackageChecker(ZopePackageChecker):
    """check standard python package :

    * __pkginfo__.py
    
    * release number mismatch
    
    * test directory structure

    * MANIFEST.in

    * setup.py

    * executable scripts ('bin' directory)

    * announce.txt template
    """
    
    __implements__ = IChecker
    __name__ = 'python_pkg'
    
    __checks__ = (check_info_module, check_release_number, check_manifest_in,
                  check_bin, check_test, check_setup_py, check_announce)


register_checker(ZopePackageChecker)
register_checker(PythonPackageChecker)
