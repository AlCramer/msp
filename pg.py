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
import nd
import vcb
import lexer
import sys

"""
The parse graph ("pg") is the main data structure used in parsing.
After reading in the source text, we break it up into a sequence of
lexemes, each corresponding to a word or punctuation mark. Each lexeme
then becomes a node in the graph. This is a doubly linked list of "Pn"
nodes. Initially the graph is a 1-dimensional structure.

Parsing then becomes a matter of deciding: what short sequences of
words ("the girl", "didn't go") can be combined into a single node, to
form a single parse unit? And then: what are the syntax relations
between these parsemes? These tasks are handled by the module
"parser".
"""
# Nodes for parse graph

class Pn (nd.Nd):
    """
    A "Pn" represents a punctuation mark, word, or short sequence of
    words ("the boy"), linked together in a doubly-linked list to
    represent the source text.
    """
    def __init__(self,tok_v,S,E):
        nd.Nd.__init__(self,S,E)
        # identifier ("handle") for test/dev
        self.h = -1
        # subnodes for reductions
        self.sublst = []
        # our scope
        self.scope = None
         # verb qualifiers
        self.vqual = []
        # verbs props
        self.vprops = 0
        # start and end indices for the verb structure
        self.vS = -1
        self.vE = -1
        # syntax class and relation.
        self.sc = 0
        self.sr = SR_undef
        # text associated with this node
        self.wrds = []
        # verb roots associated with this node
        self.verbs = []
        # adverbs associated with this node
        self.adverbs = []
        # preposition, etc. which precede this node
        self.head = []
        # syntax relations, verb->word
        self.rel = []
        # "vnxt" is first verb to our right, and "vprv" is
        # first verb to our left.
        self.vnxt = self.vprv = None
	# preceeding verb domain
	self.vd_left = None
        for i in range(0,SR_nwordtoverb):
            self.rel.append([])
        if tok_v != -1:
            self.wrds.append(tok_v)
            self.sc = self.compute_synclass(tok_v)
            if vcb.is_sc_for_verb(self.sc):
                # "Is" is defined as "is", which is in turn defined
                # as "be".
                _def = vcb.get_def(tok_v)
                _def = vcb.get_def(_def)
                self.verbs.append(_def)
                self.vprops = self.compute_verb_props(tok_v)
        # In general the "extent" of a node is just the node. But if
        # this is the verb in a verb expression, then its extent runs
        # from its left-most scope term to its right-most scope term.
        self.extent = [self,self]
        # Conjoined verb expressions: if "vIsoSub" is defined,
        # it gives the verb expression whose subject roles 
        # provide the subject roles for this node.
        self.v_iso_sub = None
        # final tree generation: the msnode that corresponds to this
        # parse graph node
        self.msnode = None

    def compute_synclass(self,tok_v):
        """ compute the "sc" value for a node """
        sp = vcb.spell(tok_v).lower()
        c = sp[0]
        if sp == '\'s':
            return vcb.lkup_sc("TickS")
        if sp == 'and' or sp == 'or':
            return vcb.lkup_sc("AndOr")
        if c == ',':
            return vcb.lkup_sc("Comma")
        if not (c.isalnum() or c=="_" or c=='\''):
            return vcb.lkup_sc("Punct")
        if c.isdigit():
            # numerals lex as weak-determinants: "I saw 123,000 people"
            return vcb.lkup_sc("Num")
        # a vocabulary word
        return vcb.synclass[tok_v]

    def compute_verb_props(self,tok):
        """ get verb props (VP_xxx) for a parse node """
	# MUSTDO: rewrite. Simple assignment?
        p = 0
        if vcb.check_vp(tok,VP_root):
            p |= VP_root
        elif vcb.check_vp(tok,VP_negcontraction):
            p |= VP_neg
        if  vcb.check_vp(tok,VP_past|VP_participle):
            p |= VP_past
        else:
            p |= VP_present
        if vcb.check_vp(tok,VP_gerund):
            p |= VP_gerund
        if vcb.check_vp(tok,VP_adj):
            p |= VP_adj
        if vcb.check_vp(tok,VP_participle):
            p |= VP_participle
        # remaining verb props are based on the root of the verb. This
        # is given by its definition.
        tok_def = vcb.get_def(tok)
        if vcb.check_vp(tok_def,VP_vpq):
            p |= VP_prelude
        return p

    def get_wrd(self,i):
        """ get wrd "i" """
        return self.wrds[i]

    def test_wrd(self,sp):
        """
        Does node match a word? If > 1 word, the test
        is performed on the first word.
        """
        if len(self.wrds)>0:
            _def = vcb.get_def(self.get_wrd(0))
            sp_def = vcb.spell(_def)
            if isinstance(sp,list):
                for _sp in sp:
                    if sp_def == _sp:
                        return True
                return False
            return sp_def == sp
        return False

    def set_vp(self,v):
        """ set a prop """
        self.vprops |= v

    def check_vp(self,m):
        """ check verb props """
        return (self.vprops & m) != 0

    def check_wrd_prop(self,m):
        """ check word props """
        if len(self.wrds) > 0:
            return vcb.check_prop(self.wrds[0],m)
        return False

    def get_vroot(self):
        """ get root form for verb """
        return None if len(self.verbs) == 0 else self.verbs[0]

    def test_vroot(self,sp_test):
        """ test verb-root against spelling """
        if len(self.verbs) > 0:
            sp_root = vcb.spell(self.get_vroot())
            if isinstance(sp_test,list):
                for sp in sp_test:
                    if sp == sp_root:
                        return True
            elif sp_root == sp_test:
                return True
        return False

    def test_verb_form(self,form):
        """
        Test form of verb. "form" can be:
	VP_avgt, VP_evt, VP_ave, VP_vpq
        """
        return len(self.verbs)>0 and \
            vcb.check_vp(self.verbs[0],form)

    def is_verb(self):
        """ is this a verb? """
        return vcb.is_sc_for_verb(self.sc)

    def is_container(self):
        """ quote- and paren- blocks are "container" """
        sc_sp = vcb.spell_sc(self.sc)
        return sc_sp == "QuoteBlk" or sc_sp == "ParenBlk"


    def is_leaf(self):
        """ is this a leaf? (no descendents) """
        for lst in self.rel:
            if len(lst) > 0:
                return False
        return True

##    def linearize(self,leaves):
##        """ append leaves to "leaves" """
##        if len(self.sublst) == 0:
##            leaves.append(self)
##            return
##        for e in self.sublst:
##            e.linearize(leaves)

    def get_subnodes(self,sr_accept):
        """
        get specified subnodes of this node: relation must be in
        "srAccept"
        """
        nds = []
        for i in sr_accept:
            nds.extend(self.rel[i])
        return nds

    def check_sc(self,m):
        """ check sc props """
        return vcb.sc_dct.check_prop(self.sc,m)

    def get_rel(self,e):
        """ find relation of "e" to this node """
        for i in range(SR_nwordtoverb):
            if e in self.rel[i]:
                return i
        return -1

    def unset_scope(self):
        """
        Unset scope for "e". This erases any existing relations from
        verbs to e.
        """
        if self.scope != None:
            for rset in self.scope.rel:
                if self in rset:
                    rset.remove(self)
                    break
        self.scope = None
        self.sr = SR_undef

    def set_scope(self,v,i):
        """
        Set an edge from "v" to "e". "None" is a legal value for "v"
        -- this just unsets any "i" relations to e
        """
        # setting scope to self is illegal
        assert self != v
        # for all our relations, setting v->x erases any existing
        # relations vold->x. If "x" is currently in some relation with
        # "vold", then "vold" is given by "e.scope"
        self.unset_scope()
        if v != None:
            if v.scope == self:
                # this call is considered legal: it requires us to unset
                # v's scope.
                v.unset_scope()
            # we order the terms left-to-right by "e.S"
            ix = -1
            rset = v.rel[i]
            for j in range(0,len(rset)):
                if self.S <= rset[j].S:
                    ix = j
                    break
            if ix == -1:
                rset.append(self)
            else:
                rset.insert(ix,self)
            self.scope = v
            self.sr = i

    def reset_rel(self,old_rel,new_rel):
        """ reset a relation """
        self.rel[new_rel] = self.rel[old_rel]
        self.rel[old_rel] = []
        for t in self.rel[new_rel]:
            t.sr = new_rel

    def dump_nd_lst(self,label,lst):
        """ return a list of "h" (handles) for a list of nodes """
        l = [str(e.h) for e in lst]
        l = ','.join(l)
        return ' %s:%s' % (label,l)

    def dump_attr(self):
        tmp = [('%d. [%d.%d]' % (self.h,self.S,self.E))]
        if len(self.wrds) > 0:
            tmp.append('"%s"' % vcb.spell(self.wrds))
        if len(self.head) > 0:
            tmp.append('head: "%s"' % vcb.spell(self.head))
        if self.vprops != 0:
            tmp.append('VP:' + VPtoStr(self.vprops,'|'))
        tmp.append('sc:' + vcb.sc_tostr(self.sc))
        if self.sr != 0xff:
            tmp.append('sr:' + SRids[self.sr])
        if self.scope != None:
            tmp.append("Scp:" + str(self.scope.h))
        if self.v_iso_sub != None:
            tmp.append("vIsoSub:" + str(self.v_iso_sub.h))
        return ' '.join(tmp)

    def printme(self,fp):
	if fp is None:
	    fp = sys.stdout
        fp.write(self.dump_attr())
        for i in range(0,SR_nwordtoverb):
            if len(self.rel[i]) > 0:
                fp.write(self.dump_nd_lst(SRids[i],self.rel[i]))
	fp.write('\n')

# phrase factory. Do not inline this code -- you will break the tools
# that build the parse tables.
pn_enum = 0
def pn_factory(tok_v,S,E):
    """ create phrase with given props """
    global pn_enum
    e = Pn(tok_v,S,E)
    e.h = pn_enum
    pn_enum += 1
    return e
# first phr in sequence
eS = None
# last phr in sequence
eE = None

def reset_span(S,E):
    """ reset span of graph, returning restore info """
    global eS,eE
    rinfo = []
    rinfo.append(S.prv)
    rinfo.append(E.nxt)
    rinfo.append(eS)
    rinfo.append(eE)
    eS = S
    eE = E
    eS.prv = None
    eE.nxt = None
    return rinfo

def restore_span(rinfo):
    """ restore span of graph, using info from "rinfo" """
    global eS,eE
    eS.prv = rinfo[0]
    eE.nxt = rinfo[1]
    eS = rinfo[2]
    eE = rinfo[3]

def printme(fp=None,title=None):
    """ print the graph """
    if fp is None:
        fp = sys.stdout
    if title != None:
        fp.write(title+'\n')
    e = eS
    while e != None:
        e.printme(fp)
        e = e.nxt
    fp.write('\n')

def print_pnlst(lst):
    """ print list of nodes """
    for e in lst:
        e.printme(None)
        if e.is_container():
            print "* START CONTENTS *"
            print_pnlst(e.sublst)
            print "* END CONTENTS *"

def build_graph(parseblk):
    """
    build parse graph for source text in the region specified by
    "parseblk"
    """
    global pn_enum, eS, eE, n_toks
    # tokenize the text
    toks = parseblk.toks
    tok_loc = parseblk.tok_loc
    pn_enum = 0
    eS = eE = None
    for i in range(0,len(toks)):
        # The span of a node gives start and end index of the region
        # in the source text spanned by e.
        ixS = tok_loc[i]
        sp = vcb.spell(toks[i])
        e = pn_factory(toks[i], ixS, ixS+len(sp)-1)
        # linked-list bookkeeping
        if eS == None:
            eS = eE = e
        else:
            Pn.connect(eE,e)
            eE = e

def remove_node(e):
    """ remove a node from the graph """
    global eS, eE
    if e == eS and e == eE:
        eS = eE = None
    elif e == eS:
        eS = e.nxt
    elif e == eE:
        eE = e.prv
    Pn.connect(e.prv,e.nxt)

def reduce_terms(S,E,vprops,sc):
    """
    replace nodes S..E with a single node, "R". S..E become the
    sublist of R. R's "wrds" attribute is the concatenation of the
    words for S..E. if R is a verb expression, its "verbs" attribute
    is derived likewise from S..E
    """
    global eS, eE
    R = pn_factory(-1,S.S,E.E)
    R.vprops = vprops
    R.sc = sc
    # words for the reduction is the concatenation of the words for
    # eS..eE
    e = S
    while True:
        R.sublst.append(e)
        R.wrds.extend(e.wrds)
        R.verbs.extend(e.verbs)
        if e == E:
            break
        e = e.nxt
    if not vcb.is_sc_for_verb(sc):
        # kill the verbs
        R.verbs = []
    # insert R into the region S..E
    left = S.prv
    right = E.nxt
    Pn.connect(left,R)
    Pn.connect(R,right)
    if R.prv == None:
        eS = R
    if R.nxt == None:
        eE = R
    return R

def reduce_head(S,E):
    """
    The head reduction: terms from S up to (but not including) E
    are removed the graph; the text content is appended to the
    "head" attribute of E.
    """
    e = S
    while e != E:
        E.head.extend(e.wrds)
        nxt = e.nxt
        remove_node(e)
        e = nxt

def get_root_nodes():
    """
    Walk the graph and get all "root" nodes: these are nodes with null
    scope.
    """
    global eS
    root_nds = []
    e = eS
    while e != None:
        if e.scope == None:
            root_nds.append(e)
        e = e.nxt
    return root_nds

def validate_rel():
    """
    Clear the "rel" attributes of nodes, then recompute using scope
    and sr attributes.
    """
    # clear any currently defined relations
    e = eS
    while e != None:
        for lst in e.rel:
            del lst[:]
        e = e.nxt
    # rebuild using scope and sr attributes
    e = eS
    while e != None:
        if e.scope is not None and e.sr < SR_nwordtoverb:
            e.scope.rel[e.sr].append(e)
        e = e.nxt

def validate_span():
    """
    Validate the "span" attribute of nodes: if "e" is in the scope of
    "ex", increase ex's span as needed to include e.
    """
    e = eS
    while e != None:
        ex = e.scope
        # Walk up the scope tree.
        while ex is not None:
            if ex.is_verb():
                if e.S < ex.S:
                    ex.S = e.S
                if e.E > ex.E:
                    ex.E = e.E
            ex = ex.scope
        e = e.nxt

