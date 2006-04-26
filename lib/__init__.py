# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
""" Copyright (c) 2002-2003 LOGILAB S.A. (Paris, FRANCE).
 http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""

__revision__ = "$Id: __init__.py,v 1.3 2004-10-05 21:59:59 syt Exp $"

import sys

INFO = 0
WARNING = 10
ERROR = 20
FATAL = 30

SEVERITIES = {
    'INFO' : INFO,
    'WARNING' : WARNING,
    'ERROR' : ERROR,
    'FATAL' : FATAL
    }

REVERSE_SEVERITIES = {
    INFO : 'INFO',
    WARNING : 'WARNING',
    ERROR : 'ERROR',
    FATAL : 'FATAL'
    }

__builtins__.update(SEVERITIES)

class TextReporter:
    """ report messages and layouts in plain text
    """
    
    def __init__(self, output=sys.stdout):
        self.out = output
        self.reset()
        
    def reset(self):
        self.counts = {}
        for sev in (INFO, WARNING, ERROR, FATAL):
            self.counts[sev] = 0
        
    def log(self, severity, path, line, msg):
        """log a message of a given severity
        
        line may be None if unknown
        """
        self.counts[severity] += 1
        self.out.write('%s:%s:%s:%s\n' % (REVERSE_SEVERITIES[severity][0], path,
                                          line or '', msg))
