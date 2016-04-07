# Copyright 2011 Al Cramer
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from defs import *
import parser
import vcb
import serializer
import re
import sys
import os

"""
Main script for the msparse package. To parse source text represented
as a string, use "parseString". To parse the entire contents of a file,
use "parseFile". To parse and process the contents of a very large
file use "processFile".
"""

# read the serialized vocabulary and grammar rules in "msp.dat".
# This code expects the file to reside in the same directory
# as this file.
try:
    serializer.init('msp.dat','r')
    parser.serialize('r')
    serializer.fini()
except:
    print "could not read initialization file \"msp.dat\""
    print "Exception: %s\n" % sys.exc_info()[0]
    sys.exit(1)

def parse_string(text):
    """
    Parse input text. Returns list of parse nodes. 
    """
    return parser.parse_src(text)

def parse_file(fn):
    """
    Parse input file. Returns list of parse nodes. 
    """
    fp = open(fn,"r")
    nds = parser.parse_src(fp);
    fp.close()
    return nds

def process_file(fn,delegate=None,maxlines=-1):
    """
    Read and parse the file "fn" in sections, passing the parse
    of each section over to a delegate for processing. "maxlines"
    determines the size of the sections: if a given section
    exceeds "maxlines", we continue reading and parsing until
    we hit a blank or indented line, then declare the section
    complete and parse it. The object here is to support the
    processing of very large files, without blowing the host
    memory resources.
    """
    fp = open(fn,"r")
    nds = parser.parse_src(fp,delegate,maxlines);
    fp.close()


def to_xml(nds,loc):
    """
    Convert a list of parse nodes into XML. "loc" is a boolean:
    True means include location attributes in the xml,
    """
    xml = ["<?xml version=\"1.0\" standalone=\"yes\"?>\n"]
    xml.append("<msp>\n")
    for nd in nds:
        xml.append(nd.to_xml(loc))
        xml.append('\n')
    xml.append("</msp>\n");
    return ''.join(xml)

def msp_test():
    """
    Test harness for msparse package. 
    """
    # option: do we show location info in the xml?
    showloc = False
    # usage msg.
    usage = \
    """
Usage:
python msp.py options* [-i] [-f fn] [-qa]

"-i" means loop interactively, displaying the parse
for text entered by the user.

"-f" means parse contents of the file "fn", writing
the results to "<fn-root>.xml" as XML.

"-qa" parses "qasrc.txt" and compares against "qaref.xml

"-lst" writes a listing of parse data tables to "msp.lst"

options:
    -loc: include source locations attributes in xml nodes
    -trace: trace the parse (dev/test)

    """
    # start dev code
    # vcb.print_wrd_info('lines')
    # end dev code

    
    # process args
    # Undocumented args are:
    # -printrules : print parse rules
    # -process inFile outFile : dev test for process file
    action = ''
    fn_in = None
    fn_out = None
    if len(sys.argv) == 1:
        print usage
        sys.exit(1)
    i =1
    while i<len(sys.argv):  
        a = sys.argv[i]
        if a == '-h' or a == '-help' or a == '-0':
            print usage
            sys.exit(1)
        if a == '-lst':
            fplst = open('msp.lst','w')
            parser.printme(fplst)
            fplst.close()
            sys.exit(1)
        if a == '-loc':
            showloc = True
            i += 1
            continue
        if a == '-trace':
            parser.set_trace_parse(True)
            i += 1
            continue
        if a == '-f' or a == '-process':
            action = a
            i += 1
            if i >= len(sys.argv):
                print 'Error: expected file name'
                print usage
                sys.exit(1)
            fn_in = sys.argv[i]
            fn_out = sys.argv[i].split('.')[0] + '.xml'
            i += 1
            continue
        if a == '-i' or a == '-qa':
            action = a
            i += 1
            continue
        print 'unknown option: ' + a
        print usage
        sys.exit(1)
    if action == '':
        print usage
        sys.exit(1)
    if action == '-qa':
        fp = open('qaref.xml','r')
        ref_lines = fp.readlines()
        fp.close()
        xml = to_xml(parse_file('qasrc.txt'),False)
        xml_lines = xml.split("\n")
        i = 0
        pass_test = True
        while i < len(ref_lines):
            li_ref = ref_lines[i].strip()
            li_xml = xml_lines[i].strip()
            if len(li_ref) > 0:
                if li_ref != li_xml:
                    pass_test = False
                    break
            i += 1
        if pass_test:
            print "Pass QA test"
        else:
            fp = open("qasrc.xml",'w')
            fp.write(xml)
            fp.close()
            print "Fail QA test"
            print 'See \"qasrc.xml\" line %d' % (i+1)
        sys.exit(1)
    if action == '-f' or action == '-process':
        fp = open(fn_out,'w')
        if action == '-f':
            fp.write(to_xml(parse_file(fn_in),showloc))
        else:
            def process_parse(nds):
                for nd in nds:
                    if nd.get_subnode("exper") != None:
                        fp.write(nd.text + '\n')
                        fp.write(nd.summary() + '\n')
            process_file(fn_in,process_parse,2)
        print 'Created %s' % fn_out
        sys.exit(1)
    # Interactive mode
    print 'Enter text ("q" to quit):'
    while True:
        src = raw_input()
        if src == 'q' or src == 'quit':
            break
        print to_xml(parse_string(src),showloc)

if __name__== '__main__':
    msp_test()

