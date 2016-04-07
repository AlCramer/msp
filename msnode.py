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

class NdKind:
    """
    Enumerators for a node's "kind" attribute.
    """
    # Root nodes have one of these values: 
    x = 0
    punct = 1
    query = 2
    imper = 3
    assertion = 4
    quote = 5
    paren = 6
    # Child nodes of verbs are given one of these values: these
    # define thematic relations.
    agent = 7
    topic = 8
    exper = 9
    theme = 10
    auxtheme = 11
    # The "qualification" relation. Any node (root or child)
    # can have a child node that qualifies it.
    qual = 12
    # This node kind identifies the attribution for a quote
    attribution = 13

    # Total number of NdKind.xxx values
    nkinds = 14

    # mapping, kind enumerator -> text descriptor 
    ids = ['X',\
        'punct','query','imperative','assert','quote',\
        'paren','agent','topic','exper','theme',\
        'auxtheme','qual','attribution']

class NdForm:
    """
    Enumerators for a node's "form" attribute.
    """
    x = 0
    action = 1
    verbclause = 2
    queryclause = 3
    queryphrase = 4
    queryword = 5
    mod = 6
    conjphrase = 7
    conjword = 8
    n = 9
    # We provide three differant forms for punctuation. "terminator" is
    # any in the set {.!/;:}. "comma" is a single ","; all other
    # punctuation is lumped together into "punct".
    terminator = 10
    comma = 11
    punct = 12

    # mapping, form enumerator -> text descriptor 
    ids = ['X','action','verbclause','queryclause','queryphrase',\
        'queryword','mod','conjphrase','conjword','N',\
        'terminator','comma','punct']

class VP:
    """
    Verb props -- tense and negation.
    In MSP, constructs like "would not have gone" are recognized,
    analyzed, and represented by a single node in the parse tree.
    Nodes representing verb constructs have a "vprops" attribute
    giving information about the construct.  We use bit-masks
    to represent props; use the node's "checkVP" method to
    interrogate its props. 
    """
    neg = 0x1
    past = 0x2
    present = 0x4
    future = 0x8
    subjunctive = 0x10
    perfect = 0x20

    @classmethod
    def tostr(cls,m):
        """ dump a bitset of verb props """
        tmp = []
        if (m & VP.neg) != 0:
            tmp.append('neg')
        if (m & VP.past) != 0:
            tmp.append('past')
        if (m & VP.present) != 0:
            tmp.append('present')
        if (m & VP.future) != 0:
            tmp.append('future')
        if (m & VP.subjunctive) != 0:
            tmp.append('subjunctive')
        if (m & VP.perfect) != 0:
            tmp.append('perfect')
        return ' '.join(tmp)

class Nd:
    """
    Parse node for msparse package.
    """
    def __init__(self,kind,form,text,parent):
        # What kind of node is this? Value is one of NdKind.xxx 
        self.kind = kind
        # syntax form: a noun, modifier, verb expression, etc.
        # Value is one of NdForm.xxx
        self.form = form
        # source text for this node
        self.text = text
        # tree structure
        self.parent = parent
        self.subnodes = []
        # depth of this node in the parse tree
        self.depth = 0
        e = parent
        while e is not None:
            self.depth += 1
            e = e.parent
        # prepositions, etc. that immediately precede the phrase
        # represented by this node.
        self.head = ''
        # These attributes are defined for verb expressions. root form
        # of the verb(s).
        self.vroots = ''
        # qualifiers in a complex verb phrase ("couldn't go").
        self.vqual = ''
        # adverbs in a verb phrase: "... left [very quickly]"
        self.adverbs = ''
        # properties -- tense, negation, etc.
        self.vprops = 0
        # These attributes specify the location in the source of
        # the text associated with this node. We use a line/column
        # scheme: (lineS,colS) give the line and column numbers for
        # the start of the text, and (lineE,colE) give the line and
        # column numbers for the end of the text.
        self.lineS = -1
        self.colS = -1
        self.lineE = -1
        self.colE = -1
        self.blank = -1

    def check_vp(self,bitmask):
        """ test verb props """
        return (self.vprops & mask) != 0

    def get_subnodes(self,kind):
        """ 
        Get child node(s) of specified kind.
        """
        nds = []
        for nd in self.subnodes:
            if nd.kind == kind:
                nds.append(nd)
        return nds

    def to_xml(self,loc=False):
        """
        Return a string containing an XML representation of the parse
        tree rooted at this node. "loc" means: include location
        information in nodes. This allows you to map a parse node back
        to the location in the source text from which it came. If you
        don't need this information, specify "false" to reduce visual
        clutter.
        """
        return self._to_xml(loc)

    def _to_xml(self,loc):
        """
        Private implementation of the public method "toXml".
        """
        # compute indentation
        indent = '  '
        for cnt in range(self.depth):
            indent += '  '
        sb = []
        # opener
        sb.append('%s<%s form="%s"' %\
            (indent,NdKind.ids[self.kind],NdForm.ids[self.form]))
        if len(self.vroots) > 0:
            sb.append(' vroots="%s"' % self.vroots)
        if len(self.vqual) > 0:
            sb.append(' vqual="%s"' % self.vqual)
        if len(self.adverbs) > 0:
            sb.append(' adverbs="%s"' % self.adverbs)
        if self.vprops != 0:
            sb.append(' vprops="%s"' % VP.tostr(self.vprops))
        if len(self.head) > 0:
            sb.append(' head="%s"' % self.head)
        if loc:
            v = '%d %d %d %d' % \
                (self.lineS,self.colS,self.lineE,self.colE)
            sb.append(' loc="%s"' % v)
            if self.blank != -1:
                sb.append(' blank="%d"' % self.blank)
        sb.append('>')
        if self.text=='':
            sb.append('\n')
        # compute the closer
        closer = "</" + NdKind.ids[self.kind] + ">\n"
        if len(self.subnodes) == 0:
            if len(self.text) > 0:
                sb.append(" " + self.text + " ")
                sb.append(closer)
            return ''.join(sb)
        # text
        if len(self.text) > 0:
            sb.append('\n%s  %s\n' % (indent,self.text))
        # subnodes
        for nd in self.subnodes:
            sb.append(nd._to_xml(loc))
        # closer
        sb.append(indent + closer)
        return ''.join(sb)


