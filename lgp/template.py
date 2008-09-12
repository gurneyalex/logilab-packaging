# -*- coding: utf-8 -*-
# Copyright (c) 2003-2008 LOGILAB S.A. (Paris, FRANCE).
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
""" lgp template [options]

    Provides some template output during the configuration
"""
__docformat__ = "restructuredtext en"

import sys
import os.path
from string import Template
from cStringIO import StringIO

import logilab
from logilab.devtools.lib.pkginfo import PackageInfo, PKGINFO, PKGINFO_ATTRIBUTES
from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.changelog import ChangeLog


TEMPLATE_DIR = os.path.join(logilab.devtools.__path__[0], 'templates')
TEMPLATES = ('announce',)

ANNOUNCE = """I'm pleased to announce the ${VERSION} release of ${DISTNAME}.

What's new ?
------------
${CHANGELOG}


What is ${DISTNAME} ?
------------------------
${LONG_DESC}


Home page
---------
${WEB}

Download
--------
${FTP}

Mailing list
------------
${MAILINGLIST}

${ADDITIONAL_DESCR}
"""

ADDITIONAL_DESCR = """LOGILAB provides services in the fields of XML techniques and advanced
computing (implementation of intelligent agents, knowledge management,
natural language processing, statistical analysis, data mining, etc.),
and also trainings on Python, XML, UML, Object Oriented design, design
patterns use and other cutting edge topics. To know more about
Logilab, visit http://www.logilab.com/.

Logilab is also a strong supporter of the Free Software movement, and an
active member of the Python and Debian communities. Logilab's open 
source projects can be found on http://www.logilab.org/."""


def run(args):
    """ Main function of lgp template command """
    templater = Templater(args)
    try:
        templater.output()
    except Exception, err:
        templater.logger.critical(err)
        return 1


class Templater(SetupInfo):
    """ Templater class

    Specific options are added. See lgp template --help
    """
    options = (('style',
                {'type': 'choice',
                 'choices': TEMPLATES,
                 'dest': 'style',
                 'default': 'announce',
                 'metavar' : "<template style>",
                 'help': "a specific template %s" % str(TEMPLATES)
                }),
              ),

    def __init__(self, args):
        # Retrieve upstream information
        super(Templater, self).__init__(arguments=args, options=self.options, usage=__doc__)
        # FIXME logilab.common.configuration doesn't like default values :-(
        # FIXME Duplicated code between commands
        # Be sure to have absolute path here
        if self.config.style is None:
            self.config.style = 'announce'
        elif self.config.style not in TEMPLATES:
            raise Exception('template not available')

    def output(self):
        func = getattr(self, "get_%s" % self.config.style)
        func()
        return 1

    def get_announce(self):
        content = Template(ANNOUNCE)
        content.delimiter = '%'
        stream = StringIO()
        chglog = ChangeLog('ChangeLog')
        chglog.extract(stream=stream)
        whatsnew = stream.getvalue()
        pkginfo = self._package
        values = dict(CHANGELOG=whatsnew, VERSION=pkginfo.version,
                      WEB=pkginfo.web, FTP=pkginfo.ftp,
                      MAILINGLIST=pkginfo.mailinglist,
                      LONG_DESC=pkginfo.long_desc, DISTNAME=pkginfo.name,
                      ADDITIONAL_DESCR=ADDITIONAL_DESCR)
        print content.substitute(values)
