#             Perforce Defect Tracking Integration Project
#              <http://www.ravenbrook.com/project/p4dti/>
#
#                   COVERAGE.PY -- COVERAGE TESTING
#
#             Gareth Rees, Ravenbrook Limited, 2001-12-04
#
#
# 1. INTRODUCTION
#
# This module provides coverage testing for Python code.
#
# The intended readership is all Python developers.
#
# This document is not confidential.
#
# See [GDR 2001-12-04a] for the command-line interface, programmatic
# interface and limitations.  See [GDR 2001-12-04b] for requirements and
# design.
#
#
# 2. IMPLEMENTATION
#
# The word "morf" means a module object (from which the source file can
# be deduced by suitable manipulation of the __file__ attribute) or a
# filename.
#
# When we generate a coverage report we have to canonicalize every
# filename in the coverage dictionary just in case it refers to the
# module we are reporting on.  It seems a shame to throw away this
# information so the data in the coverage dictionary is transferred to
# the 'cexecuted' dictionary under the canonical filenames.
#
# The coverage dictionary is called "c" and the trace function "t".  The
# reason for these short names is that Python looks up variables by name
# at runtime and so execution time depends on the length of variables!
# In the bottleneck of this application it's appropriate to abbreviate
# names to increase speed.
#
# A dictionary with an entry for (Python source file name, line number
# in that file) if that line has been executed.
#
# t(f, x, y).  This method is passed to sys.settrace as a trace
# function.  See [van Rossum 2001-07-20b, 9.2] for an explanation of
# sys.settrace and the arguments and return value of the trace function.
# See [van Rossum 2001-07-20a, 3.2] for a description of frame and code
# objects.

"""Usage:

pycoverage -x MODULE.py [ARG1 ARG2 ...]
    Execute module, passing the given command-line arguments, collecting
    coverage data.

pycoverage -e
    Erase collected coverage data.

pycoverage -r [-m] DIR1 FILE1 FILE2 ...
    Report on the statement coverage for the given files.  With the -m
    option, show line numbers of the statements that weren't executed.

pycoverage -a [-d dir] DIR1 FILE1 FILE2 ...
    Make annotated copies of the given files, marking statements that
    are executed with > and statements that are missed with !.  With
    the -d option, make the copies in that directory.  Without the -d
    option, make each copy in the same directory as the original.

Other Options:
    -i : ignore-errors
    -o  XXX : omit XXX prefix (comma separated)
    -p:XXX : project-root=XXX
                                                                    


Coverage data is saved in the file .coverage by default.  Set the
COVERAGE_FILE environment variable to save it somewhere else."""

__version__ = "2.5.20051204"    # see detailed history at the end of this file.


import compiler
import compiler.visitor
import os
import re
import sys
import types
import marshal
import parser
import symbol
import token
import getopt
import threading
from ConfigParser import SafeConfigParser as ConfigParser
from os.path import exists, isdir, isabs, splitext, walk, join, \
     abspath, basename, dirname, normcase, isfile, realpath, curdir


BASE_EXCLUDE = ('CVS', '.svn', '.hg', 'bzr')
RCFILE = ".pycoveragerc"
SECTIONAME = "coverage"


def modpath_from_file(filename):
    """given an absolute file path return the python module's path as a list
    """
    base, ext = splitext(abspath(filename))
    for path in sys.path:
        path = abspath(path)
        if path and base[:len(path)] == path:
            if filename.find('site-packages') != -1 and \
                   path.find('site-packages') == -1:
                continue
            mod_path = base[len(path):].split(os.sep)
            mod_path = [module for module in mod_path if module]
            # if the given filename has no extension, we  can suppose it's a 
            # directory,i.e. a python package. So check if there is a
            # __init__.py file
            if not (ext or exists(join(base[:len(path)],
                                       mod_path[0], '__init__.py'))):
                continue
            break
    else:
        raise ImportError('Unable to find module for %s in %s' % (
            base, ', \n'.join(sys.path)))
    return mod_path

def get_python_files(path, ignored=BASE_EXCLUDE + ('test', 'tests',
                                                   'setup.py',
                                                   '__pkginfo__.py')):
    """run the list of python files in <path>"""
    result = []
    def walk_handler(arg, directory, fnames):
        """walk callback handler"""
        for norecurs in ignored:
            try:
                fnames.remove(norecurs)
            except ValueError:
                continue
        # check for __init__.py
        if not '__init__.py' in fnames:
            while fnames:
                fnames.pop()
        for filename in fnames:
            if splitext(filename)[1] == '.py':
                result.append('%s/%s' % (directory, filename))
    walk(path, walk_handler, None)
    return result

def morf_name(morf):
    if isinstance(morf, types.ModuleType):
        return morf.__name__
    else:
        try:
            return '.'.join(modpath_from_file(morf))
        except ImportError:
            return splitext(morf)[0]

def morf_name_compare(x, y):
    return cmp(morf_name(x), morf_name(y))


def morfs_dir(morfs):
    """expand directory in morfs list
    """
    _morfs = []
    for morf in morfs:
        if isinstance(morf, types.ModuleType):
            morf = morf.__file__
        if isdir(morf):
            _morfs += get_python_files(morf)
        else:
            _morfs.append(morf)
    return _morfs

TOTAL_ENTRY = '1TOTAL' # no risk to conflict since it's not a valid module identifier

class StatementFindingAstVisitor(compiler.visitor.ASTVisitor):
    def __init__(self, statements, excluded, suite_spots):
        compiler.visitor.ASTVisitor.__init__(self)
        self.statements = statements
        self.excluded = excluded
        self.suite_spots = suite_spots
        self.excluding_suite = 0
        
    def doRecursive(self, node):
        self.recordNodeLine(node)
        for n in node.getChildNodes():
            self.dispatch(n)

    visitStmt = visitModule = doRecursive
    
    def doCode(self, node):
        if hasattr(node, 'decorators') and node.decorators:
            self.dispatch(node.decorators)
            self.recordAndDispatch(node.code)
        else:
            self.doSuite(node, node.code)
            
    visitFunction = visitClass = doCode

    def getFirstLine(self, node):
        # Find the first line in the tree node.
        lineno = node.lineno
        for n in node.getChildNodes():
            f = self.getFirstLine(n)
            if lineno and f:
                lineno = min(lineno, f)
            else:
                lineno = lineno or f
        return lineno

    def getLastLine(self, node):
        # Find the first line in the tree node.
        lineno = node.lineno
        for n in node.getChildNodes():
            lineno = max(lineno, self.getLastLine(n))
        return lineno
    
    def doStatement(self, node):
        self.recordLine(self.getFirstLine(node))

    visitAssert = visitAssign = visitAssTuple = visitPrint = \
        visitPrintnl = visitRaise = visitSubscript = visitDecorators = \
        doStatement
    
    def visitPass(self, node):
        # Pass statements have weird interactions with docstrings.  If this
        # pass statement is part of one of those pairs, claim that the statement
        # is on the later of the two lines.
        l = node.lineno
        if l:
            lines = self.suite_spots.get(l, [l,l])
            self.statements[lines[1]] = 1
        
    def visitDiscard(self, node):
        # Discard nodes are statements that execute an expression, but then
        # discard the results.  This includes function calls, so we can't 
        # ignore them all.  But if the expression is a constant, the statement
        # won't be "executed", so don't count it now.
        if node.expr.__class__.__name__ != 'Const':
            self.doStatement(node)

    def recordNodeLine(self, node):
        # Stmt nodes often have None, but shouldn't claim the first line of
        # their children (because the first child might be an ignorable line
        # like "global a").
        if node.__class__.__name__ != 'Stmt':
            return self.recordLine(self.getFirstLine(node))
        else:
            return 0
    
    def recordLine(self, lineno):
        # Returns a bool, whether the line is included or excluded.
        if lineno:
            # Multi-line tests introducing suites have to get charged to their
            # keyword.
            if lineno in self.suite_spots:
                lineno = self.suite_spots[lineno][0]
            # If we're inside an excluded suite, record that this line was
            # excluded.
            if self.excluding_suite:
                self.excluded[lineno] = 1
                return 0
            # If this line is excluded, or suite_spots maps this line to
            # another line that is exlcuded, then we're excluded.
            elif self.excluded.has_key(lineno) or \
                 self.suite_spots.has_key(lineno) and \
                 self.excluded.has_key(self.suite_spots[lineno][1]):
                return 0
            # Otherwise, this is an executable line.
            else:
                self.statements[lineno] = 1
                return 1
        return 0
    
    default = recordNodeLine
    
    def recordAndDispatch(self, node):
        self.recordNodeLine(node)
        self.dispatch(node)

    def doSuite(self, intro, body, exclude=0):
        exsuite = self.excluding_suite
        if exclude or (intro and not self.recordNodeLine(intro)):
            self.excluding_suite = 1
        self.recordAndDispatch(body)
        self.excluding_suite = exsuite
        
    def doPlainWordSuite(self, prevsuite, suite):
        # Finding the exclude lines for else's is tricky, because they aren't
        # present in the compiler parse tree.  Look at the previous suite,
        # and find its last line.  If any line between there and the else's
        # first line are excluded, then we exclude the else.
        lastprev = self.getLastLine(prevsuite)
        firstelse = self.getFirstLine(suite)
        for l in range(lastprev+1, firstelse):
            if self.suite_spots.has_key(l):
                self.doSuite(None, suite, exclude=self.excluded.has_key(l))
                break
        else:
            self.doSuite(None, suite)
        
    def doElse(self, prevsuite, node):
        if node.else_:
            self.doPlainWordSuite(prevsuite, node.else_)
    
    def visitFor(self, node):
        self.doSuite(node, node.body)
        self.doElse(node.body, node)

    visitWhile = visitFor

    def visitIf(self, node):
        # The first test has to be handled separately from the rest.
        # The first test is credited to the line with the "if", but the others
        # are credited to the line with the test for the elif.
        self.doSuite(node, node.tests[0][1])
        for t, n in node.tests[1:]:
            self.doSuite(t, n)
        self.doElse(node.tests[-1][1], node)

    def visitTryExcept(self, node):
        self.doSuite(node, node.body)
        for i in range(len(node.handlers)):
            a, b, h = node.handlers[i]
            if not a:
                # It's a plain "except:".  Find the previous suite.
                if i > 0:
                    prev = node.handlers[i-1][2]
                else:
                    prev = node.body
                self.doPlainWordSuite(prev, h)
            else:
                self.doSuite(a, h)
        self.doElse(node.handlers[-1][2], node)
    
    def visitTryFinally(self, node):
        self.doSuite(node, node.body)
        self.doPlainWordSuite(node.body, node.final)
        
    def visitWith(self, node):
        self.doSuite(node, node.body)
        
    def visitGlobal(self, node):
        # "global" statements don't execute like others (they don't call the
        # trace function), so don't record their line numbers.
        pass


class _SysProxy(object):
    def __init__(self, module, settrace):
        assert not isinstance(module,_SysProxy)
        self.__dict__["_mod"] = module
        self.__dict__["settrace"] = settrace
        
    def __getattr__(self, attr):
        if attr != 'settrace':
            return getattr(self._mod, attr)
        else:
            return self.__dict__['settrace']

    def __setattr__(self, attr, value):
        if attr != 'settrace':
            return setattr(self._mod, attr, value)

class CoverageError(RuntimeError):
    pass

class Coverage:
    error = CoverageError

    # Name of the cache file (unless environment variable is set).
    cache_default = ".coverage"

    # Environment variable naming the cache file.
    cache_env = "COVERAGE_FILE"

    # A dictionary with an entry for (Python source file name, line number
    # in that file) if that line has been executed.
    c = {}

    # A map from canonical Python source file name to a dictionary in
    # which there's an entry for each line number that has been
    # executed.
    cexecuted = {}

    # Cache of results of calling the analysis() method, so that you can
    # specify both -r and -a without doing double work.
    analysis_cache = {}

    # Cache of results of calling the canonical_filename() method, to
    # avoid duplicating work.
    canonical_filename_cache = {}

    DEFAULT_EXCLUDE = '(#pragma[: ]+[nN][oO] [cC][oO][vV][eE][rR])'

    def __init__(self, analyzeonly=None):
        self.usecache = 1
        self.cache = None
        self.exclude_re = ''
        self.nesting = 0
        self.cstack = []
        self.xstack = []
        self.get_ready()
        self.exclude(self.DEFAULT_EXCLUDE)
        if analyzeonly:
            self.analyzeonly = [realpath(path) for path in analyzeonly]
        else:
            self.analyzeonly = []
        
    # t(f, x, y).  This method is passed to sys.settrace as a trace function.  
    #def t(f, x, y):
    #    c[(f.f_code.co_filename, f.f_lineno)] = 1
    #    return t
    # See [van Rossum 2001-07-20b, 9.2] for an explanation of sys.settrace and 
    # the arguments and return value of the trace function.
    # See [van Rossum 2001-07-20a, 3.2] for a description of frame and code
    # objects.

    def t(self, f, w, a): #pragma: no cover
        if w == 'c_call': # do nothing on C calls
            return None
        elif w == 'call' and self.analyzeonly:
            if not isfile(f.f_code.co_filename):
                return None
            path = realpath(f.f_code.co_filename)
            for dirpath in self.analyzeonly:
                if path.startswith(dirpath):
                    # we *have* to analyze this file
                    break
            else:
                return None
        elif w == 'line':
            path = realpath(f.f_code.co_filename)
            self.c[(path, f.f_lineno)] = 1
            for c in self.cstack:
                c[(path, f.f_lineno)] = 1
        return self.t

    def get_ready(self):
        if self.usecache and not self.cache:
            self.cache = os.environ.get(self.cache_env, self.cache_default)
            self.restore()
        self.analysis_cache = {}

    def start(self):
        self.get_ready()
        if self.nesting == 0:                               #pragma: no cover
            self.settrace = sys.__settrace__ = sys.settrace
            self.settrace(self.t)
            sys.__tracer__ = self.t
            if hasattr(threading, 'settrace'):
                threading.settrace(self.t)
                threading._sys = _SysProxy(sys,self.settrace)
                threading.__settrace__ = threading.settrace
                threading.settrace = lambda *x: None
            sys.settrace = lambda *x: None # disable any other settrace while covering
        self.nesting += 1
	
    def stop(self):
        if self.nesting > 0:
            self.nesting -= 1
            if self.nesting <= 0:                               #pragma: no cover
                self.settrace(None)
                sys.settrace = self.settrace # enable any other settrace again

                if hasattr(threading, 'settrace'):
                    threading.settrace = threading.__settrace__
                    threading.settrace(None)
                    threading._sys = sys

    def erase(self):
        self.c = {}
        self.analysis_cache = {}
        self.cexecuted = {}
        if self.cache and os.path.exists(self.cache):
            os.remove(self.cache)
        self.exclude_re = self.DEFAULT_EXCLUDE

    def exclude(self, re):
        if self.exclude_re:
            self.exclude_re += "|"
        self.exclude_re += "(" + re + ")"

    def begin_recursive(self):
        self.cstack.append(self.c)
        self.xstack.append(self.exclude_re)
        
    def end_recursive(self):
        self.c = self.cstack.pop()
        self.exclude_re = self.xstack.pop()

    def save(self):
        """save().  Save coverage data to the coverage cache."""
        if self.usecache and self.cache:
            self.canonicalize_filenames()
            cache = open(self.cache, 'wb')
            marshal.dump(self.cexecuted, cache)
            cache.close()

    def restore(self, coverage_file=None):
        """
        restore().  Restore coverage data from the coverage cache (if it
        exists).
        """
        self.c = {}
        self.cexecuted = {}
        assert self.usecache
        if not exists(self.cache):
            return
        try:
            cache = open(self.cache, 'rb')
            cexecuted = marshal.load(cache)
            cache.close()
            if isinstance(cexecuted, types.DictType):
                self.cexecuted = cexecuted
        except:
            pass


    def canonical_filename(self, filename):
        """
        canonical_filename(filename).  Return a canonical filename for the
        file (that is, an absolute path with no redundant components and
        normalized case).  See [GDR 2001-12-04b, 3.3].
        """
        if not self.canonical_filename_cache.has_key(filename):
            f = filename
            if isabs(f) and not exists(f):
                f = basename(f)
            if not isabs(f):
                for path in [curdir] + sys.path:
                    g = join(path, f)
                    if exists(g):
                        f = g
                        break
            cf = normcase(abspath(f))
            self.canonical_filename_cache[filename] = cf
        return self.canonical_filename_cache[filename]


    def canonicalize_filenames(self):
        """
        canonicalize_filenames().  Copy results from "executed" to
        "cexecuted", canonicalizing filenames on the way.  Clear the
        "executed" map.
        """
        for filename, lineno in self.c.keys():
            f = self.canonical_filename(filename)
            if not self.cexecuted.has_key(f):
                self.cexecuted[f] = {}
            self.cexecuted[f][lineno] = 1
        self.c = {}

    def morf_filename(self, morf):
        """morf_filename(morf).  Return the filename for a module or file."""
        if isinstance(morf, types.ModuleType):
            if not hasattr(morf, '__file__'):
                raise self.error("Module has no __file__ attribute.")
            file = morf.__file__
        else:
            file = morf
        return self.canonical_filename(file)


    def analyze_morf(self, morf):
        """
        analyze_morf(morf).  Analyze the module or filename passed as
        the argument.  If the source code can't be found, raise an error.
        Otherwise, return a pair of (1) the canonical filename of the
        source code for the module, and (2) a list of lines of statements
        in the source code.
        """
        if self.analysis_cache.has_key(morf):
            return self.analysis_cache[morf]
        filename = self.morf_filename(morf)
        ext = splitext(filename)[1]
        if ext == '.pyc':
            if not exists(filename[0:-1]):
                raise self.error("No source for compiled code '%s'."
                                   % filename)
            filename = filename[0:-1]
        elif ext != '.py':
            raise self.error("File '%s' not Python source." % filename)
        try:
            source = open(filename, 'rU')
        except:
            source = open(filename, 'r')
        lines, excluded_lines, line_map = self.find_executable_statements(
            source.read(), exclude=self.exclude_re
            )
        source.close()
        result = filename, lines, excluded_lines, line_map
        self.analysis_cache[morf] = result
        return result

    def first_line_of_tree(self, tree):
        while True:
            if len(tree) == 3 and type(tree[2]) == type(1):
                return tree[2]
            tree = tree[1]
    
    def last_line_of_tree(self, tree):
        while True:
            if len(tree) == 3 and type(tree[2]) == type(1):
                return tree[2]
            tree = tree[-1]
    
    def find_docstring_pass_pair(self, tree, spots):
        for i in range(1, len(tree)):
            if self.is_string_constant(tree[i]) and self.is_pass_stmt(tree[i+1]):
                first_line = self.first_line_of_tree(tree[i])
                last_line = self.last_line_of_tree(tree[i+1])
                self.record_multiline(spots, first_line, last_line)
        
    def is_string_constant(self, tree):
        try:
            return tree[0] == symbol.stmt and tree[1][1][1][0] == symbol.expr_stmt
        except:
            return False
        
    def is_pass_stmt(self, tree):
        try:
            return tree[0] == symbol.stmt and tree[1][1][1][0] == symbol.pass_stmt
        except:
            return False

    def record_multiline(self, spots, i, j):
        for l in range(i, j+1):
            spots[l] = (i, j)
            
    def get_suite_spots(self, tree, spots):
        """ Analyze a parse tree to find suite introducers which span a number
            of lines.
        """
        for i in range(1, len(tree)):
            if type(tree[i]) == type(()):
                if tree[i][0] == symbol.suite:
                    # Found a suite, look back for the colon and keyword.
                    lineno_colon = lineno_word = None
                    for j in range(i-1, 0, -1):
                        if tree[j][0] == token.COLON:
                            # Colons are never executed themselves: we want the
                            # line number of the last token before the colon.
                            lineno_colon = self.last_line_of_tree(tree[j-1])
                        elif tree[j][0] == token.NAME:
                            if tree[j][1] == 'elif':
                                # Find the line number of the first non-terminal
                                # after the keyword.
                                t = tree[j+1]
                                while t and token.ISNONTERMINAL(t[0]):
                                    t = t[1]
                                if t:
                                    lineno_word = t[2]
                            else:
                                lineno_word = tree[j][2]
                            break
                        elif tree[j][0] == symbol.except_clause:
                            # "except" clauses look like:
                            # ('except_clause', ('NAME', 'except', lineno), ...)
                            if tree[j][1][0] == token.NAME:
                                lineno_word = tree[j][1][2]
                                break
                    if lineno_colon and lineno_word:
                        # Found colon and keyword, mark all the lines
                        # between the two with the two line numbers.
                        self.record_multiline(spots, lineno_word, lineno_colon)

                        #for l in range(lineno_word, lineno_colon+2):
                        #    spots[l] = (lineno_word, lineno_colon)
                    # "pass" statements are tricky: different versions of Python
                    # treat them differently, especially in the common case of a
                    # function with a doc string and a single pass statement.
                    self.find_docstring_pass_pair(tree[i], spots)
                    
                elif tree[i][0] == symbol.simple_stmt:
                    first_line = self.first_line_of_tree(tree[i])
                    last_line = self.last_line_of_tree(tree[i])
                    if first_line != last_line:
                        self.record_multiline(spots, first_line, last_line)
                self.get_suite_spots(tree[i], spots)

    def find_executable_statements(self, text, exclude=None):
        # Find lines which match an exclusion pattern.
        excluded = {}
        suite_spots = {}
        if exclude:
            reExclude = re.compile(exclude)
            lines = text.split('\n')
            for i in range(len(lines)):
                if reExclude.search(lines[i]):
                    excluded[i+1] = 1
        # Parse the code and analyze the parse tree to find out which statements
        # are multiline, and where suites begin and end.

        tree = parser.suite(text+'\n\n').totuple(1)
        self.get_suite_spots(tree, suite_spots)
            
        # Use the compiler module to parse the text and find the executable
        # statements.  We add newlines to be impervious to final partial lines.
        statements = {}
        ast = compiler.parse(text+'\n\n')
        visitor = StatementFindingAstVisitor(statements, excluded, suite_spots)
        compiler.walk(ast, visitor, walker=visitor)

        lines = statements.keys()
        lines.sort()
        excluded_lines = excluded.keys()
        excluded_lines.sort()
        return lines, excluded_lines, suite_spots


    def format_lines(self, statements, lines):
        """
        format_lines(statements, lines).  Format a list of line numbers
        for printing by coalescing groups of lines as long as the lines
        represent consecutive statements.  This will coalesce even if
        there are gaps between statements, so if statements =
        [1,2,3,4,5,10,11,12,13,14] and lines = [1,2,5,10,11,13,14] then
        format_lines will return "1-2, 5-11, 13-14".
        """
        pairs = []
        i = 0
        j = 0
        start = None
        pairs = []
        while i < len(statements) and j < len(lines):
            if statements[i] == lines[j]:
                if start == None:
                    start = lines[j]
                end = lines[j]
                j = j + 1
            elif start:
                pairs.append((start, end))
                start = None
            i = i + 1
        if start:
            pairs.append((start, end))
        def stringify(pair):
            start, end = pair
            if start == end:
                return "%d" % start
            else:
                return "%d-%d" % (start, end)
        return ", ".join(map(stringify, pairs))

    # Backward compatibility with version 1.
    def analysis(self, morf):
        """return the Analysis of a previously analysed morf
            return the following value ( filename, statements, excluded, 
                                                missing, formatted missing)
            - filename  : the file name
            - statement : the list of all unignored statement of the file
            - excluded  : the list of excluded statement
            - missing   : the list of noncovered statement
            - formatted mising : a formatted string of the <missing> list
                (see format_lines doc for details)"""
        filename, statement, _, missing, mis_formatted = self.analysis2(morf)
        return filename, statement, missing, mis_formatted

    def analysis2(self, morf):
        filename, statements, excluded, line_map = self.analyze_morf(morf)
        self.canonicalize_filenames()
        if not self.cexecuted.has_key(filename):
            self.cexecuted[filename] = {}
        missing = []
        for line in statements:
            lines = line_map.get(line, [line, line])
            for l in range(lines[0], lines[1]+1):
                if self.cexecuted[filename].has_key(l):
                    break
            else:
                missing.append(line)
        return (filename, statements, excluded, missing,
                self.format_lines(statements, missing))

    def filter_by_prefix(self, morfs, omit_prefixes):
        """ Return list of morfs where the morf name does not begin
            with any one of the omit_prefixes.
        """
        filtered_morfs = []
        for morf in morfs:
            for prefix in omit_prefixes:
                if morf_name(morf).startswith(prefix):
                    break
            else:
                filtered_morfs.append(morf)

        return filtered_morfs

    
    def report(self, morfs, show_missing=1, ignore_errors=0,
               sort_by='pc', file=None, omit_prefixes=()):
        """display a coverage report"""
        if not file:
            file = sys.stdout
        stats = self.report_stat(morfs, ignore_errors, omit_prefixes, file)
        modules = stats.keys()
        modules.sort()
        max_name = max([5] + map(len, modules))
        fmt_name = "%%- %ds  " % max_name
        header = fmt_name % "Name" + " Stmts   Exec  Cover %Missing"
        fmt_coverage = fmt_name + "% 6d % 6d % 5d%% % 5d%%"
        if show_missing:
            header = header + "   Missing"
            fmt_coverage = fmt_coverage + "   %s"
        print >> file, header
        print >> file, "-" * len(header)
        result = []
        for name in modules:
            if name == TOTAL_ENTRY:
                continue
            nb_stmts, nb_exec_stmts, pc, pc_missing, readable = stats[name]
            args = (pc_missing, pc,
                    name, nb_stmts, nb_exec_stmts, pc, pc_missing)
            if show_missing:
                args += (readable,)
            result.append(args)
        if sort_by != 'file':
            result.sort()
            result.reverse()
        for line in result:
            print >> file, fmt_coverage % line[2:]
        if len(stats) > 2:
            n, m, pc, readable = stats[TOTAL_ENTRY]
            print >> file, "-" * len(header)
            args = ("TOTAL", n, m, pc, 100)
            if show_missing:
                args = args + ("",)
            print >> file, fmt_coverage % args

    def report_stat(self, morfs, ignore_errors=0, omit_prefixes=(), file=None):
        """return a dictionnary containing coverage statistics
        """
        if not isinstance(morfs, types.ListType):
            morfs = [morfs]
        morfs = morfs_dir(morfs)
        morfs = self.filter_by_prefix(morfs, omit_prefixes)
        morfs.sort(morf_name_compare)
        total_statements = 0
        total_executed = 0
        result = {}
        for morf in morfs:
            name = morf_name(morf)
            try:
                _, statements, _, missing, readable  = self.analysis2(morf)
                nb_stmts = len(statements)
                nb_exec_stmts = nb_stmts - len(missing)
                if nb_stmts > 0:
                    pc = 100.0 * nb_exec_stmts / nb_stmts
                else:
                    pc = 100.0
                result[name] = (nb_stmts, nb_exec_stmts, pc, readable)
                total_statements = total_statements + nb_stmts
                total_executed = total_executed + nb_exec_stmts
            except KeyboardInterrupt:
                raise
            except:
                if not ignore_errors:
                    type, msg = sys.exc_info()[0:2]
                    print >> file, '%s %s: %s' % (name, type, msg)
        total_missing = total_statements - total_executed
        for name, (nb_stmts, nb_exec_stmts, pc, readable) in result.items():
            try:
                pc_missing = 100.0 * (nb_stmts - nb_exec_stmts) / total_missing
            except ZeroDivisionError:
                pc_missing = 0.
            result[name] = (nb_stmts, nb_exec_stmts, pc, pc_missing, readable)
        try:
            result[TOTAL_ENTRY] = (total_statements, total_executed,
                                   100.0 * total_executed / total_statements, '')
        except ZeroDivisionError:
            result[TOTAL_ENTRY] = (total_statements, total_executed,
                                       100.0, '')
        return result
        
    blank_re = re.compile(r"\s*(#|$)")
    else_re = re.compile(r"\s*else\s*:\s*(#|$)")

    def annotate(self, morfs, directory=None, ignore_errors=0, omit_prefixes=[]):
        """annotate(morfs, ignore_errors). annotate python source files with
        coverage information
        """
        morfs = self.filter_by_prefix(morfs_dir(morfs), omit_prefixes)
        for morf in morfs:
            try:
                filename, statements, excluded, missing, _ = self.analysis2(morf)
                self.annotate_file(filename, statements, excluded, missing, directory)
            except KeyboardInterrupt:
                raise
            except:
                if not ignore_errors:
                    raise
            
    def annotate_file(self, filename, statements, excluded, missing, directory=None):
        source = open(filename, 'r')
        if directory:
            dest_file = join(directory, basename(filename) + ',cover')
        else:
            dest_file = filename + ',cover'
        dest = open(dest_file, 'w')
        lineno = 0
        i = 0
        j = 0
        covered = 1
        while 1:
            line = source.readline()
            if line == '':
                break
            lineno = lineno + 1
            while i < len(statements) and statements[i] < lineno:
                i = i + 1
            while j < len(missing) and missing[j] < lineno:
                j = j + 1
            if i < len(statements) and statements[i] == lineno:
                covered = j >= len(missing) or missing[j] > lineno
            if self.blank_re.match(line):
                dest.write('  ')
            elif self.else_re.match(line):
                # Special logic for lines containing only
                # 'else:'.  See [GDR 2001-12-04b, 3.2].
                if i >= len(statements) and j >= len(missing):
                    dest.write('! ')
                elif i >= len(statements) or j >= len(missing):
                    dest.write('> ')
                elif statements[i] == missing[j]:
                    dest.write('! ')
                else:
                    dest.write('> ')
            elif lineno in excluded:
                dest.write('- ')
            elif covered:
                dest.write('> ')
            else:
                dest.write('! ')
            dest.write(line)
        source.close()
        dest.close()

def help(error=None, status=0):
    """display help message and exit"""
    if error:
        print error
        print
    print __doc__
    sys.exit(status)


def run(args):
    """Command line utility"""
    settings = {}
    optmap = {
        '-a': 'annotate',
        '-d:': 'directory=',
        '-e': 'erase',
        '-i': 'ignore-errors',
        '-m': 'show-missing',
        '-r': 'report',
        '-x': 'execute',
        '-o': 'omit=',
        '-p:': 'project-root=',
        }
    # list of option which might be define localy
    allowed_local_options = ("omit","directory")
    short_opts = ''.join(map(lambda o: o[1:], optmap.keys())) + 'h'
    long_opts = optmap.values() + ['help']
    options, args = getopt.getopt(args, short_opts, long_opts)
    for o, a in options:
        if o in ('-h', '--help'):
            help()
        if optmap.has_key(o):
            settings[optmap[o]] = 1
        elif optmap.has_key(o + ':'):
            settings[optmap[o + ':']] = a
        elif o[2:] in long_opts:
            settings[o[2:]] = 1
        elif o[2:] + '=' in long_opts:
            settings[o[2:]] = a
        else:
            help("Unknown option: '%s'." % o, 1)
    for i in ['erase', 'execute']:
        for j in ['annotate', 'report']:
            if settings.get(i) and settings.get(j):
                help("You can't specify the '%s' and '%s' "
                     "options at the same time." % (i, j), 1)
    args_needed = (settings.get('execute')
                   or settings.get('annotate')
                   or settings.get('report'))
    action = settings.get('erase') or args_needed
    if not action:
        help("You must specify at least one of -e, -x, -r, or -a.", 1)
    if not args_needed and args:
        help("Unexpected arguments %s." % args, 1)
    if args_needed and not args:
        help("Missing argument.", 1)
    projdir = settings.get('project-root=')
    if projdir:
        the_coverage = Coverage([projdir])
    else:
        the_coverage = Coverage()
        projdir = curdir


    local_conf_file = join(projdir, RCFILE)
    if exists(local_conf_file):
        local_conf =  ConfigParser()
        local_conf.read(local_conf_file)
        for opt in local_conf.options(SECTIONAME):
            if opt not in settings: # update only undefined one
                assert opt in allowed_local_options,\
                    "%s option can't be define localy. Allowed options are %s"\
                    % (opt, allowed_local_options)
                settings[opt] = local_conf.get("coverage",opt)

    if settings.get('erase'):
        the_coverage.erase()
    if settings.get('execute'):
        if not args:
            help("Nothing to do.")
        sys.argv = args
        the_coverage.start()
        import __main__
        sys.path[0] = dirname(sys.argv[0])
        __main__.__dict__['__file__'] = sys.argv[0]
        try:
            execfile(sys.argv[0], __main__.__dict__)
        except SystemExit:
            pass
        the_coverage.save()
    if not args:
        args = the_coverage.cexecuted.keys()
    ignore_errors = settings.get('ignore-errors')
    show_missing = settings.get('show-missing')
    directory = settings.get('directory')
    omit = settings.get('omit')
    if omit is not None:
        omit = omit.split(',')
    else:
        omit = () #tuple
    if settings.get('report'):
        the_coverage.report(args, show_missing, ignore_errors, omit_prefixes=omit)
    if settings.get('annotate'):
        the_coverage.annotate(args, directory, ignore_errors, omit_prefixes=omit)


# Command-line interface.
if __name__ == '__main__':
    run(sys.argv[1:])


# A. REFERENCES
#
# [GDR 2001-12-04a] "Statement coverage for Python"; Gareth Rees;
# Ravenbrook Limited; 2001-12-04;
# <http://www.garethrees.org/2001/12/04/python-coverage/>.
#
# [GDR 2001-12-04b] "Statement coverage for Python: design and
# analysis"; Gareth Rees; Ravenbrook Limited; 2001-12-04;
# <http://www.garethrees.org/2001/12/04/python-coverage/design.html>.
#
# [van Rossum 2001-07-20a] "Python Reference Manual (releae 2.1.1)";
# Guide van Rossum; 2001-07-20;
# <http://www.python.org/doc/2.1.1/ref/ref.html>.
#
# [van Rossum 2001-07-20b] "Python Library Reference"; Guido van Rossum;
# 2001-07-20; <http://www.python.org/doc/2.1.1/lib/lib.html>.
#
#
# B. DOCUMENT HISTORY
#
# 2001-12-04 GDR Created.
#
# 2001-12-06 GDR Added command-line interface and source code
# annotation.
#
# 2001-12-09 GDR Moved design and interface to separate documents.
#
# 2001-12-10 GDR Open cache file as binary on Windows.  Allow
# simultaneous -e and -x, or -a and -r.
#
# 2001-12-12 GDR Added command-line help.  Cache analysis so that it
# only needs to be done once when you specify -a and -r.
#
# 2001-12-13 GDR Improved speed while recording.  Portable between
# Python 1.5.2 and 2.1.1.
#
# 2002-01-03 GDR Module-level functions work correctly.
#
# 2002-01-07 GDR Update sys.path when running a file with the -x option,
# so that it matches the value the program would get if it were run on
# its own.
#
# 2003-11-20 Syt * added support for directory in report and annotate
#                * removed use of the string module (ie drop python < 2.0
#                  compat)
#                * turned some comments into docstrings
#                * fixed morf name function using modpath_from_file from common
#                * moved command line stuff outside the coverage class
#                * added report_stat method, and refactor report to use it
#                * added kwargs support to module functions, and use python 2
#                  syntax instead of apply
#
# 2003-11-24 Syt * fix to avoid pb with "non executed" docstrings
#                * support --help, and exit with status = 0 with -h or --help
#
# 2004-02-13 Syt * build report sorted by percent of coverage
#
# 2004-10-20 Syt * fixed __file__ problem
#                * remove singleton inforcement
#
# 2004-11-09 Syt * instantiate the_coverage in the run() function, and so remove
#                  global functions delegating to the previous global object
#
# 2005-01-20 Syt * added %missing colum to report
#
# 2005-12-31 Syt: merged with Ned Batchelder version :
#
# 2004-12-14 NMB Minor tweaks.  Return 'analysis' to its original behavior
# and add 'analysis2'.  Add a global for 'annotate', and factor it, adding
# 'annotate_file'.
#
# 2004-12-31 NMB Allow for keyword arguments in the module global functions.
# Thanks, Allen.
#
# 2005-12-02 NMB Call threading.settrace so that all threads are measured.
# Thanks Martin Fuzzey. Add a file argument to report so that reports can be 
# captured to a different destination.
#
# 2005-12-03 NMB coverage.py can now measure itself.
#
# 2005-12-04 NMB Adapted Greg Rogers' patch for using relative filenames,
# and sorting and omitting files to report on.
#
# C. COPYRIGHT AND LICENCE
#
# Copyright 2001 Gareth Rees.  All rights reserved.
# Copyright 2003-2008 LOGILAB S.A. (Paris, FRANCE).  All rights reserved.
# Copyright 2004-2005 Ned Batchelder.  All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDERS AND CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS
# OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR
# TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
# USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
# DAMAGE.
