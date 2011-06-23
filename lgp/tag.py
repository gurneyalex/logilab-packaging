# -*- coding: utf-8 -*-
#
# Copyright (c) 2004-2011 LOGILAB S.A. (Paris, FRANCE).
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
# 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA.

import os, os.path as osp
import ConfigParser
from string import Template
from subprocess import check_call

from logilab.devtools.lgp import LGP, LGP_CONFIG_FILE
from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.exceptions import LGPException


@LGP.register
class Tagger(SetupInfo):
    """Tag the project source repository.

    A basic template system can be used in configuration
    (please refer to the documentation for this usage)
    Some tag templates are already provided by Lgp:

      $project, $version, $debian_version, $debian_revision, $distrib
    """
    name = "tag"
    arguments = "[-f | --force] [-t | --template <tag template>] [project directory]"
    options = SetupInfo.options + [
               ('template',
                {'type': 'csv',
                 'default' : ['$version'],
                 'short': 't',
                 'metavar': "<comma separated list of tag templates>",
                 'help': "list of tag templates to apply",
                 'group': 'tag'
                }),
               ('force',
                {'action': 'store_true',
                 'default' : False,
                 'dest' : "force",
                 'short': 'f',
                 'help': "force writing of the tag",
                 'group': 'tag'
                }),
              ]

    def apply(self, tag):
        tag = Template(tag)
        tag = tag.substitute(version=self.version,
                             debian_version=self.debian_version,
                             debian_revision=self.debian_revision,
                             distrib=self.distrib,
                             project=self.project)

        command = self.vcs_agent.tag(self.config.pkg_dir, tag,
                                     force=bool(self.config.force))
        self.logger.debug('run command: %s' % command)
        check_call(command, shell=True)
        self.logger.info("add tag to repository: %s" % tag)

    def run(self, args):
        # Not even try to continue if version mismatch (dangerous command)
        self._check_version_mismatch()

        self.vcs_agent = get_vcs_agent(self.config.pkg_dir)
        self.version = self.get_upstream_version()
        self.project = self.get_upstream_name()
        self.debian_version = self.debian_revision = None
        try:
            self.debian_version = self.get_debian_version()
            self.debian_revision = self.debian_version.rsplit('-', 1)[-1]
        except IndexError:
            # can be a false positive due to native package
            self.logger.warn('Debian version info cannot be retrieved')

        # poor cleaning for having unique string
        self.distrib = '+'.join(self.distributions)

        config = ConfigParser.ConfigParser()
        if osp.isfile(LGP_CONFIG_FILE):
            config.readfp(open(LGP_CONFIG_FILE))

        tags = self.config.template
        if not tags:
            raise LGPException('template tag cannot be empty')
        while tags:
            tag = tags.pop(0).strip()
            self.logger.debug("processing... '%s'", tag)
            try:
                if tag.startswith('$'):
                    if config.has_option("TAG", tag.lstrip('$')):
                        new_tags = config.get("TAG", tag.lstrip('$')).split(',')
                        # XXX white-spaces are stripped later but will be printed here
                        if new_tags:
                            self.logger.debug("template '%s' expanded to: '%s'"
                                              % (tag, ", ".join(new_tags)))
                            tags.extend(new_tags)
                            self.logger.debug("pending templates:\n* %s" % "\n* ".join(tags))
                            continue
                # apply if string only or combined tags not found in lgprc
                self.apply(tag)
            except (AttributeError, KeyError), err:
                raise LGPException("cannot substitute tag template '%s'" % err)
            except Exception, err:
                raise LGPException("an error occured in tag process: '%s'" % err)

    def guess_environment(self):
        # if no default value for distribution, try to retrieve it from changelog
        if self.config.distrib is None or 'changelog' in self.config.distrib:
            self.config.distrib = 'changelog'
        super(Tagger, self).guess_environment()


try:
    from logilab.common.hg import find_repository as find_hg_repository
except ImportError:
    # hg not installed
    find_hg_repository = lambda x: False

def get_vcs_agent(directory):
    """returns the appropriate VCS agent according to the version control system
    detected in the given directory
    """
    if osp.isfile(directory):
        directory = osp.dirname(directory)
    if osp.exists(osp.join(directory, '.svn')):
        return SVNAgent()
    elif find_hg_repository(directory):
        return HGAgent()
    return None

class ElementURLNotFound(Exception): pass
class ElementURLFound(Exception): pass

def _get_svn_url(path):
    from xml.sax import make_parser, ContentHandler

    class SVNSAXHandler(ContentHandler):
        def __init__(self, name):
            self._look_for = name

        def startElement(self, name, attrs):
            if name == 'entry' and attrs['name'] == self._look_for:
                raise ElementURLFound(attrs['url'])

    if osp.isdir(path):
        dirpath, filename = path, ''
    else:
        dirpath, filename = osp.split(path)
    p = make_parser()
    print 'looking for', filename, 'in', dirpath
    p.setContentHandler(SVNSAXHandler(filename))
    try:
        p.parse(file(osp.join(dirpath, '.svn', 'entries')))
    except ElementURLFound, ex:
        return ex.args[0]
    except KeyError:
        assert filename
        return '%s/%s' % (_get_svn_url(dirpath), filename)
    raise ElementURLNotFound()

class SVNAgent(object):
    """A SVN specific agent"""

    def tag(self, filepath, tagname):
        """return a shell command string to tag the given file in the vc
        repository using the given tag name
        """
        url = _get_svn_url(filepath)
        tag_url = url.split('/')
        for special in ('trunk', 'tags', 'branches'):
            if special in tag_url:
                special_index = tag_url.index(special)
                tag_url = tag_url[:special_index]
                tag_url.append('tags/%s' % tagname)
                tag_url = '/'.join(tag_url)
                break
        else:
            raise Exception('Unable to compute file path in the repository')
        cmd = 'svn rm -m "moving tag" %s ; svn copy -m "tagging" %s %s' % (
            tag_url, filepath, tag_url)
        return cmd

class HGAgent(object):
    """A hg specific agent"""

    def tag(self, filepath, tagname, force=True):
        """return a shell command string to tag the given file in the vc
        repository using the given tag name
        """
        if not isinstance(filepath, basestring):
            filepath = filepath[0] #' '.join(filepath)
        if force:
            force = "-f"
        else:
            force = ""
        assert osp.abspath(filepath).startswith(os.getcwd()), \
               "I don't know how to deal with filepath and <hg tag>"
        return "hg tag %s %s" % (force, tagname)
