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

import glob
import sys
import os.path
from subprocess import Popen, PIPE
import logging

from logilab.devtools.lgp.exceptions import (ArchitectureException,
                                             DistributionException)


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

def cond_exec(cmd, confirm=False, retry=False, force=False):
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
            if not force:
                if retry:
                    answer = ask('Continue ?', 'yNr')
                else:
                    answer = ask('Continue ?', 'yN')
            else:
                answer = 'y'
            if answer == 'y':
                return True
            elif retry and answer == 'r':
                continue 
            else:
                sys.exit(0)
        else:
            return False

def get_distributions(distrib=None, basetgz=None, suites='/usr/share/cdebootstrap/suites'):
    """ensure that the target distributions exist or return all the valid distributions

    param distrib: specified distrib
                   'all' to retrieved created distributions on filesystem
                   'None' to detect available images by cdebootstrap
    param basetgz: location of the pbuilder images
    """
    if distrib is None:
        import email
        distrib = email.message_from_file(file(suites))
        distrib = [i.split()[1] for i in distrib.get_payload().split('\n\n') if i]
    elif 'all' in distrib:
        # this case fixes unittest_distributions.py when basetgz is None
        if basetgz is None:
            return get_distributions(basetgz=basetgz, suites=suites)
        distrib = [os.path.basename(f).split('-', 1)[0]
                   for f in glob.glob(os.path.join(basetgz,'*.tgz'))]
    elif distrib:
        mapped = ()
        # special setup case (all distribution names are available)
        if (len(sys.argv)>1 and sys.argv[1] in ["setup"]):
            distributions = get_distributions(basetgz=basetgz, suites=suites)
        # generic case: we retrieve distributions based on filesystem
        else:
            distributions = get_distributions('all', basetgz, suites)
        # check input distrib parameter and filter if really known
        for t in distrib:
            if t not in distributions:
                # Allow lgp check to be run without valid images
                if (len(sys.argv)>1 and sys.argv[1] in ["check", "tag", "project"]):
                    logging.debug("'%s' image not found in '%s'" % (t, basetgz))
                    logging.debug("act as if 'unstable' image was existing in filesystem")
                    return ('unstable',)
                logging.critical("'%s' image not found in '%s'" % (t, basetgz))
                raise DistributionException(t)
            mapped += (t,)
        distrib = mapped

    return tuple(set(distrib))

def get_architectures(archi=None, basetgz=None):
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
        if 'all' in archi:
            archi = [os.path.basename(f).split('-', 1)[1].split('.')[0]
                       for f in glob.glob(os.path.join(basetgz,'*.tgz'))]
            return set(known_archi) & set(archi)
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

