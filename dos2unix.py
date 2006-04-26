#!/usr/bin/python2.3
# Copyright (c) 2004 LOGILAB S.A. (Paris, FRANCE).
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
"""dos2unix -[l|c|t] [-r] [-nk] FILE DIR ...

example: dos2unix [-l] projman/projman.py
         dos2unix -lr proman
         dos2unix -ck projman/projman.py
         dos2unix -crn' ' proman
         
dos2unix converts ends-of-file from dos to unix, removing(replacing) '\\r'"""

__revision__ = "$ Id: $"

from os.path import isdir, exists
from os import walk, listdir
from optparse import OptionParser
from shutil import copyfile
import logging, logging.config
import os.path
import sys

# create logger
def create_logger():
    logger = logging.getLogger(os.path.basename(__file__))
    directory = os.path.dirname(os.path.abspath(__file__))
    conf_file = os.path.normpath(os.path.join(directory,
                                              "logging.conf"))
    try:
        logging.config.fileConfig(conf_file)
    except:
        print >> sys.stderr, "could not configure logger: %s"\
              % os.path.basename(__file__)
        logging.basicConfig()
    return logger

#lowest level func: replacement
def _dos2unix(filename, options):
    """heart-function wich applies conversion of  '\r\n' to '\n'
    
    @param filename: name of the file which '\r\n' will be replaced by \n
    @type filename : str"""
    if options.keep:
        options.logger.debug("file renamed %s"% (filename+"~"))
        copyfile(filename, filename+"~")
    # array of converted lines
    output = []
    for line in open(filename):
        output.append(line.replace('\r\n', options.new_char))
    # write result. 
    open(filename,'w').writelines(output)

# browsing functions
def convert_file(file_name, options):
    """ check that file exists and apply conversion if so.
    
    @param file_name: name of the file to convert
    @type file_name : str
    
    >>> # FAILURES
    >>> convert_file()
    Traceback (most recent call last):
      File "<stdin>", line 1, in ?
    TypeError: convert_file() takes exactly 2 arguments (0 given)
    """
    # check is file
    if exists(file_name):
        #convert
        _dos2unix(file_name, options)
        options.logger.info("%s converted"% file_name)
        return True
    else:
        options.logger.warning("%s not a valid file"% file_name)
        return False

def list_file(file_name, options):
    """ display lines containing a return cariage """
    # check is file
    if exists(file_name):
        #convert
        for index, line in enumerate(open(file_name)):
            if '\r\n' in line:
                options.logger.debug("[%s] @%i #%i"% (file_name, index, line.count('\r\n')))
    else:
        options.logger.warning("%s not a valid file"% file_name)

def visit_file(file_name, options):
    """take action according to option. """
    if options.do_listing:
        list_file(file_name, options)
    else:
        convert_file(file_name, options)  
    
def visit_dir(dir_name, options):
    """ check that directory exists and apply conversion to its content.
    
    @param dir_name: name of the directory to convert
    @type file_name : str
    @param options: contain all options parsed from command line
    @type options : OptionParser
    
    >>> # FAILURES
    >>> visit_dir()
    Traceback (most recent call last):
    File "<stdin>", line 1, in ?
    TypeError: visit_dir() takes exactly 2 arguments (0 given)
    """
    if isdir(dir_name):
        if options.recursive:
            # walk through all dirs
            for root, dirnames, filenames in walk(dir_name):
                # apply convert to all files
                for file_name in [os.path.join(root, name) for name in  filenames]:
                    visit_file(file_name, options)
                options.logger.info("%s browsed"% root)
        else :
            # get content on root dir only
            sub_names = listdir(dir_name)
            # for each name, checks type (file|dir)
            for sub_name in sub_names:
                if isdir(os.path.join(dir_name, sub_name)):
                    options.logger.info("%s skipped"% os.path.join(dir_name, sub_name))
                else:
                    visit_file(os.path.join(dir_name, sub_name), options)
            options.logger.info("%s browsed"% dir_name)
    else:
        options.logger.warning("%s not a  valid directory"% dir_name)
        return False
    return True

def visit(name, options):
    """calls convert function according type of 'name' (file|dir)"""
    options.logger.info("visiting %s. recurse=%s"\
                % (str(name), str(options.recursive)))
    # check is directory
    if isdir(name):
        visit_dir(name, options)
    else:
        visit_file(name, options)    

def _test():
    """runs all tests in docstrings, returns (#failures, #tests)"""
    import doctest
    from logilab.devtools import dos2unix
    return doctest.testmod(dos2unix)

def run(args):
    """High level function called with a set of options including
    files/path to convert.
    
    @param args: options wich includes:
        -r: recursive mode when present
        path: files / directories to convert
    """
    # define options
    parser = OptionParser(__doc__, version = '%prog v0.2')
    parser.add_option("-l", "--list", dest = "do_listing",
                      action="store_true",
                      default=True,
                      help="list lines with return cariage")
    parser.add_option("-c", "--convert", dest = "do_listing",
                      action="store_false",
                      help="supress/replace return cariages")
    parser.add_option("-t", "--test", dest = "do_testing",
                      action="store_true",
                      default=False,
                      help="launch unit tests and exit")
    parser.add_option("-r", "--recursive", dest = "recursive",
                      action="store_true",
                      default=False,
                      help="recurse directories")
    parser.add_option("-o", "--overwrite", dest = "keep",
                      action="store_false",
                      default=True,
                      help="overwrite original file")
    parser.add_option("-n", "--new-char", dest = "new_char",
                      action="store",
                      default='\n',
                      help="replace '\\r\\n' with given character. ['\\n']",
                      metavar="CHAR")
    # parse options
    options, args = parser.parse_args()
    options.logger = create_logger()
    options.logger.info("action=%s recurse=%s overwrite=%s"\
                        % (options.do_testing and "test" or \
                           (options.do_listing and "list" or "convert"),
                           str(options.recursive),
                           str(not options.keep)))
    # run doctests
    if options.do_testing:
        fails, tests = _test()
        # print result
        options.logger.info("%i/%i failures"% (fails, tests))
        sys.exit(0)
    # left-out arguments are paths
    for path in args:
        visit(path, options)
    
if __name__ == "__main__":
    run(sys.argv[1:])
