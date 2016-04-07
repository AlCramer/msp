# Copyright 2012,2014 Al Cramer
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
import vcb
from vcb import sc_dct
import serializer
import xfrm
from xfrm import Xfrm
from seqmap import FSM
import pg
import sys

"""
This code establishes syntax relations. The parse graph consists
of a linked list of parse nodes (class "Pn"), representing words
and punctuation. Each node has a "sc"(syntax class) attribute:
this is our generalization of part-of-speach. At this point the
graph is a simple linear sequence of nodes. We now
create the tree structure by assigning each node an "sr" (syntax
relation) attribute. This is an int value encoding the pair
(syntax-relation, parent-spec). "syntax-relation"
is an enumerator drawn from the SR_xxx constants. "parent-spec"
specifies the node to which this relation obtains.

Here's an overview of the key concepts.

SrRegion, SrMap, scseq and srseq:
An SrRegion is a sequence of nodes (in the parse graph)
that may be syntactically related. Each node
has an sc attribute, so the node sequence defines a sequence
of sc-values. This is called an "scseq". Given an scseq, our task
is to find a parallel sequence of "sr-values". An sr-value specifies
a node's parent in the parse tree, and what relation
obtains between that node and its parent. A sequence of sr-values
is called an "srseq".

We treat this task as a mapping: given some arbitrary scseq,
find the best corresponding srseq. To emphasize that this is a
mapping relation, we use "x_i" to designate some specific scseq,
and "y_i" to designate some specific srseq. "X" means a set
of x values (that is, a set of scseq's); "Y" means a set of
y values (that is, a set of srseq's). So we're concerned with
a set of mappings, from X to Y. This set of mappings is called
an "SrMap". In our parse model, these mappings are many-to-1.
So a given x maps to exactly one y, and multiple x's can map
to the same y.

Parse Model:
Our parse model breaks the nodes of the parse graph up into
3 regions, designated 0,1, and 2. Each has an associated SrMap.
SrMap1 describes the region [subject+rootVerb]. SrMap2 describes
the region [rootVerb+object]. SrMap0 describes the optional
prelude that can appear before the subject in an SVO structure
("[On Monday] we saw mermaids"; "[When did] she leave?"). Note
how the 3 regions compose (fit together): region1 immediately
follows region0, but region1 and region2 overlap by one node
(the root node of the tree). This kind of composition
defines the algebra of our syntax.

For some given SrRegion, there will in general be multiple ways
to decompose it into x's. Suppose there are 2 possible compositions.
We must choose between them. The rule is:
1. If one composition is longer than the other, choose that one.
2. If they are equal in length, choose the one with greater composit
weight. Each mapping x->y has an associated weight, which gives the
frequency with which that mapping was observed over a large corpus.
Since weights are probabilities, the weight assigned to the
composition (x1_i,x2_j) is weight(x1_i) * weight(x2_j).
"""

def sr_tostr(t):
    """ dump an sr value """
    if t == 0xff:
        return '0xff'
    else:
        # hi 4 bits gives rel, low 4 bits give scope spec.
        scope_spec = 0xf & t
        scope_sign = scope_spec >> 3
        scope_mag = 0x7 & scope_spec
        if scope_sign == 0:
            scope_sp = '%d' % scope_mag
        else:
            scope_sp = '-%d' % scope_mag
        sr_sp = SRids[0xf & (t>>4)]
        return '%s:%s' % (sr_sp,scope_sp)

def srseq_tostr(seq):
    """ dump a sequence of sr values """
    l = []
    for t in seq:
        l.append(sr_tostr(t))
    res = ' '.join(l)
    # shorten the listings...
    res = res.replace('auxTheme','auxTh')
    res = res.replace('theme','th')
    res = res.replace('agent','ag')
    return res

def get_ext_sc(e):
    """ get extended sc for node """
    if e.is_verb():
        # query heads are retained as is
        if e.check_sc(WP_qhead|WP_beqhead):
            return e.sc
        # root form...
        sp_sc = 'V'
        if e.test_vroot("be"):
            sp_sc = "be"
        elif e.check_vp(VP_inf):
            sp_sc = 'Inf'
        elif e.check_vp(VP_gerund):
            sp_sc = 'Ger'
        elif e.check_vp(VP_participle):
            sp_sc = 'Part'
        elif e.check_vp(VP_passive):
            sp_sc = 'Pas'
        # extension
        if e.test_verb_form(VP_avgt):
            sp_sc += "AVGT"
        elif e.test_verb_form(VP_ave):
            sp_sc += "AVE" 
        elif e.test_verb_form(VP_evt):
            sp_sc += "EVT"
        sc_ext = vcb.lkup_sc(sp_sc)
        assert sc_ext > 0
        return sc_ext
    
    scProps = vcb.sc_dct.props[e.sc]
    if scProps == WP_n or scProps == WP_noun:
        return vcb.lkup_sc('X')
    
    if vcb.spell_sc(e.sc) == "her":
        return vcb.lkup_sc('X')

    return e.sc

def get_sr_region(e):
    """
    Get next region of graph, starting at "e", over which we
    establish syntax relations.
    """
    # conjunctions and puctuation delimit the regions
    delim = WP_punct|WP_conj
    while e is not None:
        # conjunctions and puctuation delimit the regions
        if e.check_sc(delim):
            e = e.nxt
            continue
        terms = [e]
        # extend to next delimitor
        while e.nxt is not None:
            if e.nxt.check_sc(delim):
                break
            terms.append(e.nxt)
            e = e.nxt
        return terms
    return None

class SrFSM(FSM):
    """
    FSM for SrMap. We override the "print" methods to get better
    listings
    """
    def __init__(self, nbits_seq_term,left_to_right,srmap):
        FSM.__init__(self, nbits_seq_term,left_to_right)
        self.srmap = srmap
        
    def print_match(self,m):
        if len(m) == 0:
            print "no matches"
            return
        print 'N match results: %d' % len(m)
        for i in range(0,len(m)):
            mx = m[i]
            nds = mx[0]
            v = mx[1]
            tmp = [e.sc for e in nds]
            scseq_sp = vcb.spell_sc( [e.sc for e in nds] )
            srseq = srmap.ydct.sequences[srmap.x_to_y[v]]
            srseq_sp = srseq_tostr(srseq)
            print 'match %d.\n%s -> %s\n' % \
                (i,scseq_sp,srseq_sp)

    def printme(self,fp):
        if fp is None:
            fp = sys.stdout
        # states
        for i in range(0,len(self.states)):
            # inputs
            fp.write('state %d. ' % i)
            s = list(self.states[i])
            s.sort();                    
            fp.write('inputs: %s\n' % s)
            fp.write(' %s\n' % vcb.spell_sc(list(s)))
        # seq->v
        fp.write('mappings. scseq->srseq:\n')
        lst = []
        for key,v in self.seq_to_v.iteritems():
            # skip the null entry
            if key == '_null_':
                continue
            scseq = [int(e) for e in key.split(' ')]
            scseq_sp = vcb.spell_sc(scseq)
            y = self.srmap.x_to_y[v]
            if y == 0:
                # skip: sequence not used in this map
                continue
            srseq = self.srmap.ydct.sequences[y]
            srseq_sp = srseq_tostr(srseq)
            hd = '%s -> %s\n' % (scseq_sp,srseq_sp)
            lst.append(hd + '    %s -> %s\n' % (key,str(srseq)))
        lst.sort()
        for e in lst:
            fp.write(e)
            
class SrMap:
    """
    A SrMap defines the mappings scseq->srseq.
    """
    def __init__(self,name,fsm_left_to_right,xdct,ydct):
        self.name = name
        self.xdct = xdct
        self.ydct = ydct
        # finite state machine for recognizing scseq's
        self.fsm = SrFSM(8,fsm_left_to_right,self)
        # mapping, scseq -> best (most likely)srseq
        self.x_to_y = []
        # weight assigned to this mapping
        self.w = []

    def serialize(self,mode):
        self.fsm.serialize(mode)
        if mode == 'w':
            serializer.encode_intlst(self.x_to_y,16)
            serializer.encode_intlst(self.w,16)
        else:
            self.x_to_y = serializer.decode_intlst(16)
            self.w = serializer.decode_intlst(16)

    def get_n(self):
        N = 0
        for w in self.w:
            if w > 0:
                N += 1
        return N

    def get_w(self,x):
        return float(self.w[x])/float(0xffff)

    def fsm_v_to_str_func(self,v):
        # "v" is the index for an x-sequence
        if self.x_to_y[v] == 0:
            print 'debug!'
        yseq = self.ydct.sequences[self.x_to_y[v]]
        return srseq_tostr(yseq)
    
    def printme(self,fp):
        if fp is None:
            fp = sys.stdout
        fp.write('%s:\n' % self.name)
        for i in range(0,len(self.w)):
            if self.w[i] == 0:
                continue
            seq = self.xdct.sequences[i]
            fp.write('x%d. %s %s\n' % \
                (i,str(seq),vcb.spell_sc(seq)))
            seq = self.ydct.sequences[self.x_to_y[i]]
            fp.write('y%d. %s %s\n' % \
                (i,str(seq),srseq_tostr(seq)))
            fp.write('Weight: %d\n\n' % self.w[i])
        # enable this code to print the FSM
        if True:
            fp.write("begin %s FSM\n" % self.name)
            self.fsm.printme(fp)
            fp.write("end %s FSM\n" % self.name)

        
class ParseTerm:
    def __init__(self,x,srmap):
        self.x = x
        self.srmap = srmap
        
class ParseRec:
    """
    Parse record.
    """
    def __init__(self,scseq,ixroot):
        # Sequence of syntax-class values: the source for the
        # parse.
        self.scseq = scseq
        # index of root
        self.ixroot = ixroot
        # The parse conists of a left and right side, meeting at the
        # root. These sides are represented as lists of ParseTerms.
        self.left = []
        self.right = []
        # Length of the parse (number of terms, in scseq, covered
        # by this parse).
        self._len = 0
        # weight assigned to this value (0 .. 1.0)
        self.w = 0.0

class SeqDct():
    """
    Mapping, seq -> index
    """
    def __init__(self,seq_tostr,name=''):
        self.seq_tostr = seq_tostr
        self.name = name
        # index 0 is reserved for the null (empty) sequence
        self.dct = {}
        self.dct['_null_'] = 0
        self.sequences = [[]]

    def serialize(self,mode):
        if mode == 'w':
            serializer.encode_lstlst(self.sequences,16)
        else:
            self.sequences = serializer.decode_lstlst(16)
            # serialization decodes empty list as None: fix that
            # for null sequence
            self.sequences[0] = []
            for i in range(1,len(self.sequences)):
                key = ' '.join([str(e) for e in self.sequences[i]])
                self.dct[key] = i

    def get_n(self):
        # return number of sequences. This does NOT include the
        # null (empty) sequence that is always included in the
        # in the dictionary as entry0.
        return len(self.sequences)-1

    def get_lseq(self,i):
        # get length of sequence
        return len(self.sequences[i])

    def printstats(self,fp):
        if fp is None:
            fp = sys.stdout
        fp.write('\n--> %s\n' % self.name)
        print '%d entries\n' % len(self.dct)

    def printme(self,fp):
        if fp is None:
            fp = sys.stdout
        fp.write('\n--> %s\n' % self.name)
        for i in range(0,len(self.sequences)):
            seq = self.sequences[i]
            fp.write('%d. %s %s\n' % (i,str(seq),self.seq_tostr(seq)))

    def get_seq(self,i):
        return self.sequences[i]

    def lkup(self,seq, create_if_missing=False):
        if seq is None or len(seq)==0:
            return 0
        key = ' '.join([str(e) for e in seq])
        ix = self.dct.get(key)
        if ix is not None:
            return ix
        if not create_if_missing:
            return 0
        ix = len(self.sequences)
        self.sequences.append(seq)
        self.dct[key] = ix
        return ix

class SrXfrm(Xfrm):
    """
    This code established syntax relations. The parse graph
    consists of a linked list of parse nodes (class "Pn"),
    representing words and punctuation. Each node has a "sc"
    (syntax class) attribute: this is our generalization of
    part-of-speach. In this phase of the parse, we assign an
    "sr" (syntax relation) to each node.
    """
    def __init__(self,_name=''):
        Xfrm.__init__(self,_name)
        # debug toggles
        self.trace = False
        self.trace_best = False
        # mappings, x and y sequences -> index
        self.xdct = SeqDct(vcb.spell_sc,'xdct')
        self.ydct = SeqDct(srseq_tostr,'ydct')
        # The parse maps
        self.srmap = []
        self.srmap.append(SrMap("prelude",False,self.xdct,self.ydct))
        self.srmap.append(SrMap("chain",False,self.xdct,self.ydct))
        self.srmap.append(SrMap("subv",False,self.xdct,self.ydct))
        self.srmap.append(SrMap("vobj",True,self.xdct,self.ydct))
        self.srmap.append(SrMap("postlude",True,self.xdct,self.ydct))
        
    def serialize(self,mode):
        self.xdct.serialize(mode)
        self.ydct.serialize(mode)
        for p in self.srmap:
            p.serialize(mode)
            if mode == 'r':
                p.fsm.seq_to_v = self.xdct.dct

    def printstats(self,fp,title=None):
        if fp is None:
            fp = sys.stdout
        if title is not None:
            fp.write('\n** %s **\n' % title)
        n_x = self.xdct.get_n()
        fp.write('N X-elements (total): %d\n' % n_x)
        for srm in self.srmap:
            fp.write('N X %s: %d\n' % (srm.name,srm.get_n()))
        fp.write('N Y-elements: %d\n' % self.ydct.get_n())

    def printme(self,fp):
        if fp is None:
            fp = sys.stdout
        fp.write('Xfrm %s\n' % self.name)
        for srm in self.srmap:
            srm.printme(fp)
            
    # "print_x" and "print_y" are provided for the make tool.
    def print_x(self,fp,ix,title=None):
        if fp is None:
            fp = sys.stdout
        if title is not None:
            fp.write('%s ' % title)
        seq = self.xdct.sequences[ix]
        fp.write('x%d. %s %s\n' % \
            (ix,str(seq),vcb.spell_sc(seq)))

    def print_y(self,fp,ix,title=None):
        if fp is None:
            fp = sys.stdout
        if title is not None:
            fp.write('%s ' % title)
        seq = self.ydct.sequences[ix]
        fp.write('y%d. %s %s\n' % \
            (ix,str(seq),srseq_tostr(seq)))


    def sum_path_len(self,path):
        s = 0
        for e in path:
            if e.x != 0:
                s += self.xdct.get_lseq(e.x)
        return s

    def get_path_w(self,path):
        w = 1.0
        for i in range(0,len(path)):
            e = path[i]
            if e.x != 0:
                w *= e.srmap.get_w(e.x)
        return w

    def get_best_path(self,paths):
        assert len(paths) > 0
        best = paths[0]
        l = self.sum_path_len(paths[0])
        w = self.get_path_w(paths[0])
        for i in range(1,len(paths)):
            if i == 2:
                debug1 = 1
            _l = self.sum_path_len(paths[i])
            _w = self.get_path_w(paths[i])
            if (_l > l) or \
                ((_l == l) and (_w > w)):
                best = paths[i]
                l = _l
                w = _w
        return best

    def print_path(self,path):
        w = self.get_path_w(path)
        w *= 0xffff
        tmp = ['w: %.1f' % w]
        for e in path:
            scseq =  self.xdct.sequences[e.x]
            xtostr = vcb.spell_sc(scseq)
            y = e.srmap.x_to_y[e.x]
            ytostr = srseq_tostr( self.ydct.sequences[y] )
            w = e.srmap.get_w(e.x)
            w*= 0xffff
            #w = int(w)
            tmp.append('[(%s)%d. w=%.1f: %s -> %d. %s]' %
                       (e.srmap.name,e.x,w,xtostr,y,ytostr))
        print '\n'.join(tmp)            
            
    def print_pathset(self,pathset,title=None):
        if title is not None:
            print title
        if len(pathset) == 0:
            print "empty pathset"
            return
        for i in range(0,len(pathset)):
            print '-----'
            self.print_path(pathset[i])
            if i == len(pathset)-1:
                print '-----' 
            

    def print_parserec(self,pr,title=None):
        if title is not None:
            print title
        print 'ixroot: %d' % pr.ixroot
        print 'scseq: %s' % ' '.join( [str(e) for e in pr.scseq] )
        print '     : %s' % vcb.spell_sc(pr.scseq)
        print 'left:'
        self.print_path(pr.left)
        print 'right:'
        self.print_path(pr.right)
        print 'len: %d' % pr._len
        print 'w X 0xffff: %f' % pr.w
        

    def pathset_contains(self,pathset,p):
        for px in pathset:
            if len(px) != len(p):
                continue
            equals = True
            for i in range(0,len(p)):
                if p[i].x != px[i].x:
                    equals = False
                    break
            if equals:
                return True
        return False

    def extend_left(self,paths,scseq,ixroot,srmap):
        if self.trace:
            print 'extend left %s.' % srmap.name
            self.print_pathset(paths,'pre-extend')
        delta = []
        for p in paths:
            l = self.sum_path_len(p)
            x_set = srmap.fsm.get_sequences(scseq,ixroot-l)
            for x in x_set:
                if srmap.get_w(x) == 0.0:
                    continue
                new_path = [ParseTerm(x,srmap)]
                new_path.extend(p)
                if not self.pathset_contains(paths,new_path):
                    delta.append(new_path)
        paths.extend(delta)
        if self.trace:
            self.print_pathset(paths,'post-extend')
            print ''
                    
    def extend_right(self,paths,scseq,ixroot,srmap):
        if self.trace:
            print 'extend right %s.' % srmap.name
            self.print_pathset(paths,'pre-extend')
        delta = []
        for p in paths:
            l = self.sum_path_len(p)
            x_set = srmap.fsm.get_sequences(scseq,ixroot+l)
            for x in x_set:
                if srmap.get_w(x) == 0.0:
                    continue
                new_path = p[:]
                new_path.append(ParseTerm(x,srmap))
                if not self.pathset_contains(paths,new_path):
                    delta.append(new_path)
        paths.extend(delta)
        if self.trace:
            self.print_pathset(paths,'post-extend')
            print ''
            
    def _get_srseq(self,scseq,ixroot):
        if ixroot == 2:
            debug1 = 1
        # X-domaine id's
        XRid_prelude = 0
        XRid_chain = 1
        XRid_subv = 2
        XRid_vobj = 3
        XRid_postlude = 4
        best = ParseRec(scseq,ixroot)
        subv_set = self.srmap[XRid_subv].fsm.get_sequences(scseq,ixroot)
        vobj_set = self.srmap[XRid_vobj].fsm.get_sequences(scseq,ixroot)
        if len(subv_set) == 0 or len(vobj_set) == 0:
            return best
        # start debug
##        print 'debug: %d' % len(vobj_set)
##        self.srmap[3].printme(None)
        # end debug
        # parse left from scseq[ixroot]
        paths = []
        for x in subv_set:
            paths.append([ParseTerm(x,self.srmap[XRid_subv])])
        # make 2 extensions for the chain domaine
        self.extend_left(paths,scseq,ixroot,self.srmap[XRid_chain])
        self.extend_left(paths,scseq,ixroot,self.srmap[XRid_chain])
        self.extend_left(paths,scseq,ixroot,self.srmap[XRid_prelude])
        best.left = self.get_best_path(paths)
        # parse right from scseq[ixroot]
        paths = []
        for x in vobj_set:
            paths.append([ParseTerm(x,self.srmap[XRid_vobj])])
        self.extend_right(paths,scseq,ixroot,self.srmap[XRid_postlude])
        best.right = self.get_best_path(paths)
        # set length and weight of the parse
        best._len = self.sum_path_len(best.left) + \
                    self.sum_path_len(best.right) - 1
        best.w = self.get_path_w(best.left) * \
                    self.get_path_w(best.right)
        return best

    def get_srseq(self,scseq):
        best = ParseRec(scseq,-1)
        for ixroot in range(0,len(scseq)):
            if not vcb.is_sc_for_verb(scseq[ixroot]):
                continue
##            if ixroot == 5:
##                self.trace = self.trace_best = True
            _best = self._get_srseq(scseq,ixroot)
            if _best._len > best._len or \
                (_best._len == best._len and _best.w > best.w):
                best = _best
                if self.trace_best:
                    self.print_parserec(best,'***\nSet best:')
        srseq = [0xff] * len(scseq)
        if best.w == 0.0:
            # the parse failed
            return srseq
        # define left region of the parse
        i = best.ixroot
        for ix_path in range(len(best.left)-1,-1,-1):
            e = best.left[ix_path]
            y = e.srmap.x_to_y[e.x]
            srseq_delta = self.ydct.get_seq(y)
            for j in range(len(srseq_delta) - 1,-1,-1):
                srseq[i] = srseq_delta[j]
                i -= 1
        # define right region of the parse
        i = best.ixroot
        for ix_path in range(0,len(best.right)):
            e = best.right[ix_path]
            y = e.srmap.x_to_y[e.x]
            srseq_delta = self.ydct.get_seq(y)
            for j in range(0,len(srseq_delta)):
                srseq[i] = srseq_delta[j]
                i += 1
        # parse is defined over the sub-sequence S..E. Indices
        # follow python convention: S inclusive, E exclusive.
        S = best.ixroot - self.sum_path_len(best.left) + 1
        E = best.ixroot + self.sum_path_len(best.right)
        self.validate_scopes(scseq,srseq,S,E)        
        return srseq
    

    def validate_scopes(self,scseq,srseq,S,E):
        """
        Correct srseq[S..E] so scope encoding are correct.
        TODO: document
        """
        # get "ixroot": index of parse tree root. This is the
        # lefttmost unscoped verb.
        ixroot = -1
        for i in range(S,E):
            if vcb.is_sc_for_verb(scseq[i]) and srseq[i] == 0xff:
                ixroot = i
                break
        if ixroot == -1:
            # no action
            return
        for i in range(S,E):
            # scope encoded: low 4 bits of srseq[i]. We want
            # scope undefined (by convention, 0xf)
            scope_enc = srseq[i] & 0xf
            if i == ixroot or scope_enc != 0xf:
                continue
            # resolve scope for term "i"
            n_v = 0
            sign = 0
            if i < ixroot:
                # scope node is to the right of "i"
                j = i+1
                while j < ixroot:
                    if vcb.is_sc_for_verb(scseq[j]):
                        n_v += 1
                    j += 1
            else:
                # scope node is to the left of "i"
                sign = 1
                j = i-1
                while j > ixroot:
                    if vcb.is_sc_for_verb(scseq[j]):
                        n_v += 1
                    j -= 1
            # rel encoded is hi 4 bits of srseq[i]. If this is
            # undefined (0xf), we change it to SR_theme. This is
            # the convention for scope chains.
            rel = 0xf & (srseq[i] >> 4)
            if rel == 0xf:
                rel = SR_theme
            srseq[i] = (rel << 4) | ((sign<<3) | n_v)

    def find_v(self,i,terms,srseq):
        """
        for i_th term in list of terms, find it scope node
        (a verb) as encoded in "srseq[i]"
        """
        sr = srseq[i]
        # sign/mag encoding.
        scope_sign = (0x8 & sr) >> 3
        scope_mag = 0x7 & sr
        n_v = 0
        if scope_sign == 0:
            # search right
            j = i+1
            while j < len(terms):
                ex = terms[j]
                if ex.is_verb():
                    n_v += 1
                    if n_v > scope_mag:
                        return ex
                j += 1
        else:
            # search left
            j = i-1
            while j >= 0:
                ex = terms[j]
                if ex.is_verb():
                    n_v += 1
                    if n_v > scope_mag:
                        return ex
                j -= 1
        return None

    def do_xfrm(self):
        """ Establish syntax relations, node->verb  """
        # set grammatical relations for subject, object, and qual
        terms = get_sr_region(pg.eS)
        while terms is not None:
            debug = [e.sc for e in terms]
            scseq = [get_ext_sc(e) for e in terms]
            srseq = self.get_srseq(scseq)
            for i in range(0,len(terms)):
                sr = srseq[i]
                if sr == 0xff:
                    continue
                v = self.find_v(i,terms,srseq)
                if v is not None:
                    # relation is hi 4 bits of "sr"
                    rel = 0xf & (sr>>4)
                    terms[i].set_scope(v,rel)
            terms = get_sr_region(terms[-1].nxt)        





