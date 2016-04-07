# Copyright 2012 Al Cramer
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

class Source:
    """
    This class encapuslates access to the text to be parsed: 
    either contents of a file, or a string representation of the text.
    """
    def __init__(self,content_provider):
	# "contentProvider" can be either a file or a string
        self.fp = None
        self.string = None
        if isinstance(content_provider,str):
            self.string = content_provider
        else:
            self.fp = content_provider
        self.ix = 0
        self.eofsrc = False
        # line number and indent for current line
        self.lno = 0
        self.indent = 0
        # text for current section
        self.sect_text = None
        # line number and indent for current sect
        self.sect_lno = 0
        self.sect_indent = 0
        # number of blank lines preceding the section
        self.sect_blank = 0
        # look-ahead line. This line belongs to the
        # NEXT section that will be returned by "getSection".
        self.peek_li = None
        self.peek_li_lno = 0
        self.peek_li_indent = 0

    def getline(self):
        """
        Get (stripped) next line from source (None if at end-of-source).
        self.lno and self.ident give the line-number and indent of the
        line.
        """
        if self.eofsrc:
            return None
        if self.fp is not None:
            li = self.fp.readline();
            if len(li) == 0:
                self.eofsrc = True
                return None
        else:
            S = E = self.ix
            while E<len(self.string) and self.string[E] != '\n':
                E += 1
            li = self.string[S:E]
            # the newline is considered part of this line
            self.ix = E + 1
            if self.ix >= len(self.string):
                self.eofsrc = True
        self.lno += 1
        self.indent = 0
        for c in li:
            if c == ' ':
                self.indent += 1
            elif c == '\t':
                self.indent += 4
            else:
                break
        return li.strip()

    def get_section(self):
        """
        Get section of source for parsing: returns false if
        end-of-source. Text for section is written to "sectText".
        """
        # get "li": first line in this section. It may have been read-in
        # in the preceding call to "getSection".
        if self.peek_li is None:
            li = self.getline()
            if li is None:
                # source has been exhausted
                return False
            self.sect_lno = self.lno
            self.sect_indent = self.indent
        else:
            li = self.peek_li
            self.sect_lno = self.peek_li_lno
            self.sect_indent = self.peek_li_indent
        # skip over initial blank lines (but keep count)
        self.sect_blank = 0
        while li is not None and len(li) == 0:
            li = self.getline()
            self.sect_lno = self.lno
            self.sect_indent = self.indent
            self.sect_blank += 1
        if li is None:
            # source has been exhausted
            return False
        # "li" is the first line of the section
        sect = [li.strip()]
        while True:
            li = self.getline()
            if li is None:
                # done
                break
            # if the line is blank or indented, it will be the
            # first line of the next section.
            if len(li)==0 or self.indent > self.sect_indent:
                self.peek_li = li
                self.peek_li_lno = self.lno
                self.peek_li_indent = self.indent
                break
            # this line is part of the current section
            sect.append(li.strip())
        self.sect_text = '\n'.join(sect)
        return True

if __name__== '__main__':
    txt = \
"""

Para1, line1.
Para1, line2.

Para2, line1.
Para2, line2.
    Para3, line1.
Para3, line2.
Para3, line3.


    Para4, line1

"""
    # string version
    src = Source(txt)
    tmp = []
    while src.get_section():
        desc = 'blank:%d lno:%d indent:%d txt:\n%s\n' % \
            (src.sect_blank,src.sect_lno,
             src.sect_indent,src.sect_text)
        tmp.append(desc)
    version1 = '\n'.join(tmp)
    print version1
    # file version
    fp = open("ut.txt","w")
    fp.writelines(txt)
    fp.close()
    fp = open("ut.txt","r")
    src = Source(fp)
    tmp = []
    while src.get_section():
        desc = 'blank:%d lno:%d indent:%d txt:\n%s\n' % \
            (src.sect_blank,src.sect_lno,
             src.sect_indent,src.sect_text)
        tmp.append(desc)
    version2 = '\n'.join(tmp)
    if version2 == version2:
        print "PASS unit test"
    else:
        print "FAIL unit test"
        print 'version1\n%s\n' % version1
        print 'version2\n%s\n' % version2







