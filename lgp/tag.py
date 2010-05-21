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
""" lgp tag [-f | --force] [-t | --template <tag template>] [project directory]

    Tag the source repository
"""
__docformat__ = "restructuredtext en"

from string import Template
import logging
import ConfigParser
from subprocess import check_call

from logilab.devtools.lgp import LGP_CONFIG_FILE
from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.exceptions import LGPException


def run(args):
    """ Main function of lgp tag command """
    try :
        tagger = Tagger(args)

        # deprecates the old 'format' attribute in config file
        if getattr(tagger.config, "format", None):
            import warnings
            msg = '"format" field key definitions must be renamed to "default" in /etc/lgp/lgprc'
            warnings.warn(msg, DeprecationWarning)
            tagger.config.default = tagger.config.format

        # FIXME tagger.config.default should not be None if defined in lgprc
        config = ConfigParser.ConfigParser()
        config.readfp(open(LGP_CONFIG_FILE))
        tags = tagger.config.default
        if tagger.config.default is None:
            if config.has_option("LGP-TAG", "default"):
                tags = config.get("LGP-TAG", "default").split(',')
            else:
                tags = ['$version']
        while tags:
            tag = tags.pop(0).strip()
            try:
                if tag == "default":
                    raise Exception('"default" target not allowed')
                if config.has_option("LGP-TAG", tag):
                    new_tags = config.get("LGP-TAG", tag).split(',')
                    if new_tags:
                        logging.debug("detected alias '%s' expanded to '%s'" % (tag, new_tags))
                        tags.extend(new_tags)
                else:
                    tagger.apply(tag)
            except (AttributeError, KeyError), err:
                raise LGPException('cannot substitute tag template %s' % err)
            except Exception, err:
                raise LGPException('an error occured in tag process: %s' % err)
    except LGPException, exc:
        logging.critical(exc)
        return exc.exitcode()

class Tagger(SetupInfo):
    """Lgp tagger class

    Specific options are added. See lgp tag --help
    """
    name = "lgp-tag"
    options = (('template',
                {'type': 'csv',
                 'dest' : "default",
                 'short': 't',
                 'metavar': "<comma separated of tag templates>",
                 'help': "list of tag templates to apply"
                }),
               ('force',
                {'action': 'store_true',
                 'default' : False,
                 'dest' : "force",
                 'short': 'f',
                 'help': "replace existing tag"
                }),
               ('format',
                {'type': 'csv',
                })
              ),

    def __init__(self, args):
        # Retrieve upstream information
        super(Tagger, self).__init__(arguments=args, options=self.options,
                                     usage=__doc__)

        try:
            from logilab.devtools.vcslib import get_vcs_agent
        except ImportError:
            raise LGPException('you have to install python-vcslib package to use this command')
        self.vcs_agent = get_vcs_agent(self.config.pkg_dir)
        self.version = self.get_upstream_version()
        self.project = self.get_upstream_name()
        self.debian_version = self.debian_revision = None
        try:
            self.debian_version = self.get_debian_version()
            self.debian_revision = self.debian_version.rsplit('-', 1)[-1]
        except IndexError:
            # can be a false positive due to native package
            logging.warn('Debian version info cannot be retrieved')

        # poor cleaning for having unique string
        self.distrib = '+'.join(self.distributions)
        self.archi   = '+'.join(self.architectures)

        # don't continue if version mismatch
        self._check_version_mismatch()

    def apply(self, tag):
        tag = Template(tag)
        tag = tag.substitute(version=self.version,
                             debian_version=self.debian_version,
                             debian_revision=self.debian_revision,
                             distrib=self.distrib,
                             arch=self.archi,
                             project=self.project
                            )

        command = self.vcs_agent.tag(self.config.pkg_dir, tag,
                                     force=bool(self.config.force))
        logging.debug('run command: %s' % command)
        check_call(command, shell=True)
        logging.info("add tag to repository: %s" % tag)
