# -*- coding: utf-8 -*-

# Copyright (c) 2003 Sylvain Thénault (thenault@gmail.com)
# Copyright (c) 2003-2008 LOGILAB S.A. (Paris, FRANCE).
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
# 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA.
"""check MANIFEST.in files
"""

import os
from os.path import isdir, exists, join, basename
from distutils.filelist import FileList
from distutils.text_file import TextFile
from distutils.errors import DistutilsTemplateError
import distutils

from logilab.devtools import BASE_EXCLUDE

JUNK_EXTENSIONS = ('~', '.pyc', '.pyo', '.fo', '.o', '.so', '.swp', '.orig')

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

    def warn(msg, *args):
        if args:
            try:
                msg %= args
            except TypeError, ex:
                raise TypeError(str((ex, msg, args)))
        #reporter.warning(absfile,None,msg)
    filelist.warn = warn
    __warn = distutils.log.warn
    distutils.log.warn = warn

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
            except DistutilsTemplateError:
                #reporter.error(absfile, template.current_line, msg)
                pass
        filelist.sort()
        filelist.remove_duplicates()
        for pattern in exclude_patterns:
            filelist.exclude_pattern(pattern, is_regex=1)
        return [path.replace('./', '') for path in filelist.files]
    finally:
        distutils.log.warn = __warn
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
                    join(prefix, 'setup.cfg'),
                    join(prefix, 'doc/makefile'),
                    # no need to match README, automagically included by distutils
                    join(prefix, 'README'), join(prefix, 'README.txt'),
                    # we _must not_ match the debian directory
                    join(prefix, 'debian'),
                    # we _must not_ match apycot config
                    join(prefix, 'apycot.ini'),
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
