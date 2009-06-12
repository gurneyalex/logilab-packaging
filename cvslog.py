#!/usr/bin/env python
""" CVS Log analysis tool

USAGE: cvslog [COMMAND] [OPTIONS] [-- [CVS OPTIONS] [-- CVS LOG OPTION]]

COMMANDS:
    info
    stats

OPTIONS:
    -h / --help
    -r / --rlog
    -d / --days
"""

import os
import sys
import getopt
from time import localtime, time, strftime
from logilab.devtools.vcslib.cvsparse import parse, LogLineHandler

def print_info(loginfo):
    for file in loginfo:
        print '*'*80
        print file
        for revision in file.children:
            print '-'*40
            print revision

def print_stats(loginfo, html=0, mincommit=None):
    if mincommit:
        mincommit = int(mincommit)

    results = {'authors': {}}

    for file in loginfo:
        for revision in file.children:
            author = revision.author
            results['authors'].setdefault(author, {'+': 0, '-': 0,
                                                   'new': 0, 'author': author,
                                                   'commit': 0, 'files': {}})
            d = results['authors'][author]
            d['files'][file.repo_file] = 1
            d['commit'] += 1
            if revision.initial:
                d['new'] += 1
            else:
                d['+'] += revision.lines[0]
                d['-'] -= revision.lines[1]

    nb_lines = 0
    winner = None
    max_commit = 0
    for author, data in results['authors'].items():
        if mincommit is not None and data['commit'] < mincommit:
            del results['authors'][author]
            continue
        if data['commit'] > max_commit:
            max_commit = data['commit']
            winner = author
        data['+commit'] = round(float(data['+'])/data['commit'])
        data['-commit'] = round(float(data['-'])/data['commit'])
        data['changed'] = data['+']-data['-']
        nb_lines += data['changed']
        data['changedcommit'] = round(float(data['changed'])/data['commit'])
        data['newcommit'] = round(float(data['new'])/data['commit'])
    results['winner'] = winner
    for author, data in results['authors'].items():
        data['%'] = round(float(data['changed']*100)/nb_lines)

    if html:
        from logilab.devtools.vcslib.cvsparse import LogResultHTMLPrinter
        LogResultHTMLPrinter().format(results)
    else:
        from logilab.devtools.vcslib.cvsparse import LogResultTextPrinter
        LogResultTextPrinter().format(results)


COMMANDS = {
    'info' : ( print_info,
               []
               ),
    'stats' : ( print_stats,
                ['date=', 'days=', 'html', 'min-commit=']
                )
    }

def get_logs(cvsoptions, cvscommandoptions, rlog=''):
    """extract an object log representation from a pipe with cvs
    """
    # construct cvs arguments
    if rlog:
        cvsargs = '%s rlog %s %s' % (' '.join(cvsoptions),
                                     ' '.join(cvscommandoptions), rlog)
    else:
        cvsargs = '%s log %s' % (' '.join(cvsoptions),
                                 ' '.join(cvscommandoptions))
    command = 'TZ=UTC cvs -Q %s' % (cvsargs)
    # spawn the cvs command
    (p_input, p_output, p_err) = os.popen3(command)
    p_input.close()
    # and construct log info from its output
    phandler = LogLineHandler()
    parse(p_output, phandler)
    p_err.close()
    p_output.close()
    return phandler.root

def run(args):
    # split args
    i = 0
    myoptions = []
    cvsoptions = []
    cvscommandoptions = []
    order = (myoptions, cvsoptions, cvscommandoptions)
    for arg in args:
        if arg == '--':
            i += 1
        else:
            order[i].append(arg)
    # get command
    command = 'info'
    if myoptions and myoptions[0][0] != '-':
        command = myoptions.pop(0)
    command_handler, l_opt = COMMANDS[command]
    rlog = None
    options = {}
    date = None
    # parse my options
    l_opt = ['help', 'rlog=', 'days='] + l_opt
    opts, args = getopt.getopt(myoptions, 'hr:d:', l_opt)
    for opt, val in opts:
        if opt in ('-h','--help'):
            print __doc__
            return
        if opt in ('-r', '--rlog'):
            rlog = val
        elif opt in ('-d', '--days'):
            date = strftime("%Y/%m/%d", localtime(time()-int(val)*60*60*24))
            today = strftime("%Y/%m/%d", localtime(time()))
            cvscommandoptions.insert(0, '%s\<%s'%(date, today))
            cvscommandoptions.insert(0, '-d')
        else:
            options[opt.replace('-', '')] = val or 1
    loginfo = get_logs(cvsoptions, cvscommandoptions, rlog)
    # now do something with log info according to command
    command_handler(loginfo, **options)


if __name__ == '__main__':
    run(sys.argv[1:])
