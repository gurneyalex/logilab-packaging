# -*- coding: ISO-8859-1 -*-

# Copyright (c) 2003 Sylvain Thénault (thenault@gmail.com)
# Copyright (c) 2003-2006 LOGILAB S.A. (Paris, FRANCE).
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
"""check MANIFEST.in files
"""

__revision__ = '$Id: manifest.py,v 1.19 2005-07-26 09:41:16 syt Exp $'

import os
from os.path import isdir, exists, join, basename
from distutils.filelist import FileList
from distutils.text_file import TextFile
from distutils.errors import DistutilsTemplateError

from logilab.devtools.vcslib import BASE_EXCLUDE

JUNK_EXTENSIONS = ('~', '.pyc', '.pyo', '.fo', '.o', '.so', '.swp')

def match_extensions(filename, extensions):
    """return true if the given file match one of the given extensions"""
    for ext in extensions:
        if filename.endswith(ext):
            return True
    return False


def read_manifest_in(reporter,
                     filelist=None, dirname=os.getcwd(),
                     filename="MANIFEST.in",
                     exclude_patterns=(r'/(RCS|CVS|\.svn|\.hg)/.*',)):
    """return a list of files matching the MANIFEST.in"""
    absfile = join(dirname, filename)
    if not exists(absfile):
        return []
    orig_dir = os.getcwd()
    os.chdir(dirname)
    if filelist is None:
        filelist = FileList()
    filelist.warn = lambda msg, r=reporter, f=absfile: r.warning(f, None, msg)
    try:
        template = TextFile(filename, strip_comments=1,
                            skip_blanks=1, join_lines=1,
                            lstrip_ws=1, rstrip_ws=1,
                            collapse_join=1)
        while 1:
            line = template.readline()
            if line is None:            # end of file
                break
            try:
                filelist.process_template_line(line)
            except DistutilsTemplateError, msg:
                reporter.error(absfile, template.current_line, msg)
        filelist.sort()
        filelist.remove_duplicates()
        for pattern in exclude_patterns:
            filelist.exclude_pattern(pattern, is_regex=1)
        return [path.replace('./', '') for path in filelist.files]
    finally:
        os.chdir(orig_dir)

def get_manifest_files(dirname=os.getcwd(), junk_extensions=JUNK_EXTENSIONS,
                       ignored=(), prefix=None):
    """return a list of files which should be matched by the MANIFEST.in file

    FIXME: ignore registered C extensions
    """
    if prefix is None:
        prefix = dirname
        if prefix[-1] != os.sep:
            prefix += os.sep
        ignored += ('.coverage',
                    join(prefix, 'MANIFEST.in'), join(prefix, 'MANIFEST'),
                    join(prefix, 'dist'), join(prefix, 'build'), 
                    join(prefix, 'announce.txt'), join(prefix, 'announce_fr.txt'), 
                    join(prefix, 'setup.cfg'),
                    join(prefix, 'doc/makefile'), 
                    # no need to match README, automagically included by distutils
                    join(prefix, 'README'), join(prefix, 'README.txt'),
                    # we _must not_ match the debian directory
                    join(prefix, 'debian'),
		    # do not match mercurial files
                    join(prefix, '.hgignore'), join(prefix, '.hg'),
                    join(prefix, '.hgtags'), join(prefix, '.hgrc'),
                    )
    result = []
    if (exists(join(dirname, '__init__.py')) or
        basename(dirname) in ('test', 'tests')):
        ignore_py = 1
    else:
        ignore_py = 0
    for filename in os.listdir(dirname):
        absfile = join(dirname, filename)
        if absfile in ignored or filename in ignored or filename.endswith(',cover'):
            continue
        if isdir(absfile):
            if filename in BASE_EXCLUDE + ('deprecated',):
                continue
            result += get_manifest_files(absfile, junk_extensions, ignored,
                                         prefix)
        elif ignore_py:
            if not match_extensions(absfile, junk_extensions + ('.py', '.c')):
                result.append(absfile[len(prefix):])
        elif not match_extensions(absfile, junk_extensions):
            result.append(absfile[len(prefix):])
    return result


def check_manifest_in(reporter, dirname=os.getcwd(),
                      info_module=None, # avoid pb with check_package
                      junk_extensions=JUNK_EXTENSIONS):
    """checks MANIFEST.in file"""
    status = 1
    # check matched files
    should_be_in = get_manifest_files(dirname=dirname)
    matched = read_manifest_in(reporter, dirname=dirname)
    absfile = join(dirname, 'MANIFEST.in')
    for path in should_be_in:
        try:
            i = matched.index(path)
            matched.pop(i)
        except ValueError:
            reporter.error(absfile, None, '%s is not matched' % path)
            status = 0
    # check garbage
    for filename in matched:
        if match_extensions(filename, junk_extensions):
            reporter.warning(absfile, None, 'match %s' % filename)
    return status
