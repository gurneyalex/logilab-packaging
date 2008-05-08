# -*- coding: utf-8 -*-
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
"""Copyright (c) 2002-2008 LOGILAB S.A. (Paris, FRANCE).
 http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""

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

    # convenience methods to avoid importing level constants
    def warning(self, path, line, msg):
        self.log(WARNING, path, line, msg)

    def error(self, path, line, msg):
        self.log(ERROR, path, line, msg)

    def info(self, path, line, msg):
        self.log(INFO, path, line, msg)

    def fatal(self, path, line, msg):
        self.log(FATAL, path, line, msg)

    def errors(self):
        return self.counts[ERROR]
    errors = property(errors)
    
    def warnings(self):
        return self.counts[WARNING]
    warnings = property(warnings)

    def fatals(self):
        return self.counts[FATAL]
    fatals = property(fatals)

    def infos(self):
        return self.counts[INFO]
    infos = property(infos)
    
