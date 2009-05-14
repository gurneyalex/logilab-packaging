#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2004-2008 LOGILAB S.A. (Paris, FRANCE).
# http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
""" lgp tag [options]

    Tag the source repository
"""
__docformat__ = "restructuredtext en"

import os
from string import Template
import logging

from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.exceptions import LGPException, LGPCommandException


def run(args):
    """ Main function of lgp tag command """
    try :
        tagger = Tagger(args)
        for tag in tagger.config.format:
            try:
                tagger.apply(tag)
            except (AttributeError, KeyError), err:
                raise LGPException('cannot substitute format %s' % err)
            except Exception, err:
                raise
                #raise LGPCommandException('an error occured in tag process', err)
                raise LGPException('an error occured in tag process')
    except LGPException, exc:
        logging.critical(exc)
        return 1

class Tagger(SetupInfo):
    """Tagger class

    Specific options are added. See lgp tag --help
    """
    name = "lgp-tag"
    options = (('format',
                {'type': 'csv',
                 'default' : ['$version'],
                 'dest' : "format",
                 'short': 'f',
                 'metavar': "<comma separated of tag formats>",
                 'help': "list of tag formats to apply"
                }),
              ),

    def __init__(self, args):
        # Retrieve upstream information
        super(Tagger, self).__init__(arguments=args, options=self.options, usage=__doc__)

        try:
            from logilab.devtools.vcslib import get_vcs_agent
        except ImportError:
            raise LGPException('you have to install python-vcslib package to use this command')
        self.vcs_agent = get_vcs_agent(self.config.pkg_dir)
        self.version = self.get_upstream_version()
        self.debian_revision = self.get_debian_version().rsplit('-', 1)[1]

        # cleaning for unique entries
        self.config.distrib = '+'.join(self.config.distrib)
        self.config.archi   = '+'.join(self.config.archi)

    def apply(self, tag):
        tag = Template(tag)
        tag = tag.substitute(version=self.version,
                             debian_revision=self.debian_revision,
                             distrib=self.config.distrib,
                             arch=self.config.archi,
                            )

        logging.info("add tag to repository: %s" % tag)
        logging.debug('run command: %s' % self.vcs_agent.tag(self.config.pkg_dir, tag))
        os.system(self.vcs_agent.tag(self.config.pkg_dir, tag))
