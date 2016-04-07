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

import pg
from defs import *
import vcb
from vcb import sc_dct
import serializer
from seqmap import FSM
from rematch import pnRE
import xfrm
from xfrm import Xfrm
import sys

"""
This code performs phrase reductions. At this point the parse graph
consists of a linked list of parse nodes (class "Pn"), representing
words and punctuation. Each node has a "sc" (syntax class) attribute:
this is our generalization of part-of-speach. In reduction, we replace
short sequences of nodes with a single node, so simple phrases like
"the girl" and "didn't go" are parsed as units.

A reduction rule maps a sequence of "sc" values to a value
[offS,offE,vprops,sc,action]. We walk the graph until we see a node 
sequence whose sc values match the sc sequence of some rule "r". 
We then perform "action" on the nodes. "offS" and "offE" specify
which which of the nodes in the sequence are affected: offS == 1
means "exclude first node", offE == 2 means "exclude the last 2
nodes", etc.

Supported actions are:
reduce -- remove nodes from graph & replace with a new node
setprops -- set props of nodes

"""
# dev/test
trace_rules = False

def is_vqual(e):
    """ can "e" be a verb-qualifier? """
    return e is not None and \
        e.is_verb() and \
        not e.test_vroot(['be','have','do','will','shall','use'])

def reduce_terms(S,E,vprops,sc):
    """ reduce a phrase, S..E. """
    # If this is not a verb phrase reduction, just call graph's
    # reduction method
    if not vcb.is_sc_for_verb(sc):
        return pg.reduce_terms(S,E,vprops,sc)
    # get list of verb terms S..E (skip modfiers). Catch negations
    # ("have not seen")
    vprops = 0
    is_neg = False
    terms = []
    adverbs = []
    e = S
    while e is not None:
        if vcb.check_sc_prop(e.sc,WP_verb):
            terms.append(e)
        elif len(e.wrds) > 0:
            sp = vcb.spell(e.wrds[0]).lower()
            if sp == "not" or sp == "never":
                is_neg = True
            elif sp == "to":
                # include this in "terms"
                terms.append(e)
            elif e.check_sc(WP_adv):
                adverbs.extend(e.wrds)
        if e == E:
            break
        e = e.nxt
    # Initial analysis: get first cut at props for the verb phrase.
    # "be" forms
    if pnRE.match(terms,"VAdj? Have|TickS _been|_being V"):
        # "has been struck" -> passive case
        # "has been going" -> perfect case
        v = pnRE.match_result[3][0]
        vprops = VP_passive
        if v.check_vp(VP_gerund):
            vprops = VP_perfect
    elif pnRE.match(terms,"Be|TickS _being|_been V"):
        # "he's been killed" -> passive case
        # "I am being killed" -> passive case
        # "he's been walking" -> perfect case
        v = pnRE.match_result[2][0]
        vprops = VP_passive
        if v.check_vp(VP_gerund):
            vprops = VP_perfect
    elif pnRE.match(terms,"VAdj? Be|TickS V"):
        # "will be struck" -> passive case
        # "will be going" -> future tense (caught later)
        v = pnRE.match_result[2][0]
        vprops = VP_passive
        if v.check_vp(VP_gerund):
            vprops = 0
    elif pnRE.match(terms,"_being V"):
        # "being choosen was a surprise"
        # This is passive case with no primary theme. Class
        # this as a gerund: it will then be parsed as an action.
        vprops = VP_gerund

    # "have" forms
    elif pnRE.match(terms,"VAdj? _to? Have V"):
        # "may have seen" -> perfect case
        # "ought to have loved" -> perfect case
        vprops = VP_perfect

    # do forms
    elif pnRE.match(terms,"Do V"):
        pass

    # "to" forms.
    elif pnRE.match(terms,"VAdj? _to Be|Get V"):
        # "to be" and "to get" are equivalent. Cases include:
        # "to get very tired" (a passive form)
        # "to get going" (an action form)
        # "ought to have left"
        # "to be eating" is translated as "to eat", an
        # an infinitive form. "to be eaten" is translated
        # as passive construct
        vprops = VP_passive
        v = pnRE.match_result[3][0]
        if v.check_vp(VP_gerund):
            vprops = VP_inf
    elif pnRE.match(terms,"Be _to V"):
        # past-future construct: "how she was to get out".
        # Class this as subjunctive
        vprops = VP_subjunctive
    elif pnRE.match(terms,"_used _to V"):
        # "used to go"
        vprops = VP_past
    elif pnRE.match(terms,"VAdj? _to V"):
        # standard infinitive: "to not go", "to see"
        vprops = VP_inf

    elif pnRE.match(terms,"VAdj V"):
        # "would go"
        # "pass" needed, because we'll match subsequent cases
        pass

    # "she will"
    elif pnRE.match(terms,"VAdj"):
        vprops = VP_adj

    if is_neg:
        vprops |= VP_neg

    # Get additional props (tense, etc.)
    # "vS" and "vE": first/last verb in list
    N = len(terms)
    vS = terms[0]
    vE = terms[N-1]

    # tense is derived from first term. Semantic props are inherited
    # from the last verb.
    vprops |= (vS.vprops & VP_tensemask)
    vprops |= (vE.vprops & VP_semanticmask)
    # If this is the reduction of an atomic verb phrase, get
    # additional props from vS.
    sc_sp = vcb.spell_sc(sc)
    if len(terms) == 1:
        mask = VP_gerund|VP_participle|VP_root|VP_semanticmask
        vprops |= (vS.vprops & mask)
        if sc_sp in ["BeQuery","VAdjQuery"]:
            vprops |= VP_query
    # If input syntax is "V", we extend it using "vprops" and facts
    # about the main verb.
    if sc_sp == "V":
        if vprops & VP_inf:
            sc_sp = "Inf"
        elif vprops & VP_gerund:
            sc_sp = "Ger"
        elif vprops & VP_participle:
            sc_sp = "Part"
        elif vprops & VP_passive:
            sc_sp = "Pas"
        sc = vcb.lkup_sc(sc_sp)     


    # call the graph's reduction method
    R = pg.reduce_terms(S,E,vprops,sc)
    # last term gives the root verbs(s)
    R.verbs = vE.verbs[:]
    # save any adverbs
    R.adverbs = adverbs
    # vS and vE gives indices for start and end of verb construct
    R.vS = S.S
    R.vE = E.E
    # some complex forms ("have gone") are purely syntactic; others
    # ("might go") are considered to represent a qualified form for a
    # verb, and we save the qualifier.
    for i in range(0,len(terms)):
        ex = terms[i]
        if len(ex.vqual) > 0:
            R.vqual.extend(ex.vqual)
        if ex != vE and is_vqual(ex):
            R.vqual.append(ex.verbs[0])
    # Reduce "[was beginning][to understand]
    left = R.prv
    if left is not None and \
        left.is_verb() and \
        left.test_verb_form(VP_vpq):
        vprops = R.vprops & VP_semanticmask
        R = reduce_terms(left,R,vprops,vcb.lkup_sc('V'))
    return R

class ReductXfrm(Xfrm):
    """
    Reduction transform. We make several passes over the graph,
    performing different kind of reductions. Each pass is implemented
    by a ReductXfrm.
    """

    # actions
    act_reduce = 0x1
    act_set_prop = 0x2
    act_skip = 0x4

    def __init__(self,_name=''):
        Xfrm.__init__(self,_name)
        # finite-state-machine for recognizing node sequences	
        self.fsm = FSM(8,True)
	# reduction rules are represented by a set of parrallel arrays
        self.offS = []
        self.offE = []
        self.props = []
        self.sc = []
        self.act = []

    def v_tostr(self,i):
            l = []
            if self.offS[i] != 0:
                l.append("offS: %d" % self.offS[i])
            if self.offE[i] != 0:
                l.append("offE: %d:" % self.offE[i])
            if self.props[i] != 0:
                l.append("props: %s" % VPtoStr(self.props[i],'|'))
            if self.sc[i] != 0:
                l.append("sc: %s" % vcb.spell_sc(self.sc[i]))
            if self.act[i] != 0:
                l.append("act: %d" % self.act[i])
            return ' '.join(l)

    def printme(self,fp):
        fp.write('Xfrm %s\n' % self.name)
        for i in range(len(self.offS)):
            fp.write("%d. %s\n" % (i, self.v_tostr(i)))

    def printstats(self,fp,title=None):
        if fp is None:
            fp = sys.stdout
        if title is not None:
            fp.write('\n** %s **\n' % title)
        self.fsm.printstats(fp,'fsm:')

    def serialize(self,mode):
        self.fsm.serialize(mode)
        if mode == 'w':
            serializer.encode_str_to_int(self.fsm.seq_to_v)
            serializer.encode_intlst(self.offS,8)
            serializer.encode_intlst(self.offE,8)
            serializer.encode_intlst(self.props,32)
            serializer.encode_intlst(self.sc,8)
            serializer.encode_intlst(self.act,8)
        else:
            self.fsm.seq_to_v = serializer.decode_str_to_int()
            self.offS = serializer.decode_intlst(8)
            self.offE = serializer.decode_intlst(8)
            self.props = serializer.decode_intlst(32)
            self.sc = serializer.decode_intlst(8)
            self.act = serializer.decode_intlst(8)

    def find_rule(self,e):
        matches = self.fsm.get_matches(e,True)
        if len(matches) > 0:
            # want the longest match: the last element in the match
            # set.
            return matches[len(matches)-1]
        return None

    def apply_rule(self,e,rule):
        seq,vix = rule
        S = seq[0]
        E = seq[len(seq)-1]
        if trace_rules:
            l = [vcb.spell_sc(0xff & e.sc) for e in seq]
            print "%s. reduce [%s] by  [%s]" % \
                (self.name, ' '.join(l), self.v_tostr(vix))
        for i in range(0,self.offS[vix]):
            S = S.nxt
        for i in range(0,self.offE[vix]):
            E = E.prv
        if self.act[vix] == ReductXfrm.act_skip:
            # a no-op
            return E.nxt
        if self.act[vix] == ReductXfrm.act_reduce:
            R = reduce_terms(S,E,self.props[vix],self.sc[vix])
            return R.nxt
        if self.act[vix] == ReductXfrm.act_set_prop:
            ex = S
            while True:
                ex.set_vp(self.props[vix])
                if ex == E:
                    break
                ex = ex.nxt
            return seq[len(seq)-1].nxt
        assert False

    def do_xfrm(self):
        e = pg.eS
        while e != None:
            rule = self.find_rule(e)
            if rule is not None:
                e = self.apply_rule(e,rule)
            else:
                e = e.nxt


class LeftReductXfrm(ReductXfrm):
    """
    Subclass of ReductXfrm: these reductions require that we be in
    the left (start) context of a syntax-relations region.
    """

    def __init__(self,_name=''):
        ReductXfrm.__init__(self,_name)

    def get_region(self,e):
        """
        Get next region of graph, starting at "e", in which we
        reduce
        """
        while e is not None:
            # skip punctuation, commas, and conjunctions
            if e.check_sc(WP_punct|WP_conj):  
                e = e.nxt
                continue
            S = e
            E = e
            # extend to next punctuation (conjunctions are allowed)
            while e.nxt is not None:
                if e.nxt.check_sc(WP_punct):
                    break
                E = e.nxt
                e = e.nxt
            # find leftmost verb
            ex = S
            v = None
            while True:
                if ex.is_verb():
                    v = ex
                    break
                if ex == E:
                    break
                ex = ex.nxt
            if v is None:
                return None
            return [S,v,E]
        return None

    def do_xfrm(self):
        """ Do left (start) context reductions  """
        region = self.get_region(pg.eS)
        while region is not None:
            [S,v,E] = region
            rule = self.find_rule(S)
            if rule is not None:
                self.apply_rule(S,rule)
            region = self.get_region(E.nxt)



