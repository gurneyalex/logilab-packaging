# Copyright (c) 2003 Sylvain Thenault (thenault@gmail.com)
# Copyright (c) 2003-2008 Logilab (devel@logilab.fr)
#
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
"""miscellaneous utilities, mostly shared by package'checkers
"""

import re
import os
import glob
import sys
from os.path import basename, join, split, exists
from subprocess import Popen, PIPE
import logging

from logilab.devtools.lgp.exceptions import (ArchitectureException,
                                             DistributionException)

#from logilab.devtools.vcslib import BASE_EXCLUDE
BASE_EXCLUDE = ('CVS', '.svn', '.hg', 'bzr')

PUBLIC_RGX = re.compile('PUBLIC\s+"-//(?P<group>.*)//DTD (?P<pubid>.*)//(?P<lang>\w\w)(//XML)?"\s*"(?P<dtd>.*)"')

# The known distribution are depending on the pbuilder setup in /opt/buildd
# Find a way to retrieve dynamically
# f = email.message_from_file(file('/usr/share/cdebootstrap/suites'))
# [i.split() for i in f.get_payload().split('\n\n') if i]
KNOWN_DISTRIBUTIONS = {'etch': 'oldstable',
                       'oldstable': 'oldstable',
                       'lenny': 'stable',
                       'stable': 'stable',
                       'unstable': 'unstable',
                       'sid': 'unstable',
                       'squeeze': 'testing',
                       'testing': 'testing',
                       'feisty':'feisty',
                       'gutsy':'gutsy',
                       'hardy':'hardy',
                       'intrepid':'intrepid',
                       'jaunty':'jaunty',
                       'dapper':'dapper',
                       'experimental': 'unstable',
                      }


class SGMLCatalog:
    """ handle SGML catalog information
    i.e. map dtds to their public id
    """
    def __init__(self, path, stream):
        self.path = path
        self.id = basename(path)
        self.dtds = {}
        for m in PUBLIC_RGX.finditer(stream.read()):
            dtd = m.group('dtd').split('/')[-1]
            self.dtds[dtd] = (m.group('group'), m.group('pubid'))

    def dtd_infos(self, dtd):
        """return infos for a dtd file"""
        return self.dtds[dtd]

    def check_dtds(self, dtds, reporter):
        """check given dtd files are registered"""
        for dtd in dtds:
            dtddir, dtdname = split(dtd)
            try:
                self.dtd_infos(dtdname)
            except KeyError:
                msg = 'DTD %s is not registered by the main catalog' % dtd
                reporter.error(dtd, None, msg)

def glob_match(pattern, prefix=None):
    """return a list of files matching <pattern> from the <prefix> directory
    """
    cwd = os.getcwd()
    if prefix:
        try:
            os.chdir(prefix)
        except OSError:
            return []
    try: 
        return glob.glob(pattern)
    finally:
        if prefix:
            os.chdir(cwd)

def get_scripts(dirname, include_bat=0):
    """return a list of executable scripts
    """
    bindir = join(dirname, 'bin')
    if not exists(bindir):
        return ()
    result = []
    for filename in os.listdir(bindir):
        if filename in BASE_EXCLUDE:
            continue
        if include_bat or filename[-4:] != '.bat':
            result.append(join('bin', filename))
    return result


def ask(msg, options): 
    default = [opt for opt in options if opt.isupper()]
    assert len(default) == 1, "should have one (and only one) default value"
    default = default[0]
    answer = None
    while str(answer) not in options.lower():
        try:
            answer = raw_input('%s [%s] ' % (msg, '/'.join(options)))
        except (EOFError, KeyboardInterrupt):
            print
            sys.exit(0)
        answer = answer.strip().lower() or default.lower()
    return answer

def confirm(msg):
    return ask(msg, 'Yn') == 'y'

def cond_exec(cmd, confirm=False, retry=False):
    """demande confirmation, retourne 0 si oui, 1 si non"""
    # ask confirmation before execution
    if confirm:
        answer = ask("Execute %s ?" % cmd, 'Ynq')
        if answer == 'q':
            sys.exit(0)
        if answer == 'n':
            return False
    while True:
        # if execution failed ask wether to continue or retry
        if os.system(cmd):
            if retry:
                answer = ask('Continue ?', 'yNr')
            else:
                answer = ask('Continue ?', 'yN')
            if answer == 'y':
                return True
            elif retry and answer == 'r':
                continue 
            else:
                sys.exit(0)
        else:
            return False

def get_distributions(distrib=None, basetgz=None):
    """ensure that the target distributions exist or return all the valid distributions
    """
    distributions = KNOWN_DISTRIBUTIONS
    if distrib is None or distrib == 'known':
        distrib = KNOWN_DISTRIBUTIONS.keys()
        return tuple(set(distrib))
    elif distrib == 'target':
        distrib = KNOWN_DISTRIBUTIONS.values()
        return tuple(set(distrib))
    elif 'all' in distrib:
        # this case fixes unittest_distributions.py when basetgz is None
        if basetgz is None:
            return set(KNOWN_DISTRIBUTIONS)
        distrib = [os.path.basename(f).split('-', 1)[0]
                   for f in glob.glob(os.path.join(basetgz,'*.tgz'))]
        return set(KNOWN_DISTRIBUTIONS) & set(distrib)

    mapped = ()
    # check and filter if known
    for t in distrib:
        if (len(sys.argv)>1 and sys.argv[1] not in ["setup"]):
            distributions = get_distributions('all', basetgz)
        if t not in distributions:
            logging.critical("'%s' image not found in '%s'" % (t, basetgz))
            raise DistributionException(t)
        mapped += (t,)
    distrib = mapped

    return tuple(set(distrib))

def get_architectures(archi=None):
    """ Ensure that the architectures exist

        :param:
            archi: str or list
                name of a architecture
        :return:
            list of architecture
    """
    known_archi = Popen(["dpkg-architecture", "-L"], stdout=PIPE).communicate()[0].split()
    if archi is None or archi == ["current"]:
        archi = Popen(["dpkg", "--print-architecture"], stdout=PIPE).communicate()[0].split()
    else:
        if archi == ["all"]:
            return archi
        for a in archi:
            if a not in known_archi:
                raise ArchitectureException(a)
    return archi

def cached(func):
    """run a function only once and return always the same cache

       This decorator is used to reduce the overheads due to many system calls
    """
    def decorated(*args, **kwargs):
        try:
            return decorated._once_result
        except AttributeError:
            decorated._once_result = func(*args, **kwargs)
            return decorated._once_result
    return decorated

