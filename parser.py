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

import pg
from defs import *
from msnode import *
import lexer
import vcb
from vcb import sc_dct
import serializer
from parseReduct import ReductXfrm, LeftReductXfrm
from parseSr import *
from srxfrm import SrXfrm
from source import *
import xfrm
from attribution import set_attributions
import os
import sys

"""
"buildGraph" in module "Pg" constructs our initial parse graph: a
doubly-linked list of nodes representing individual words. Parsing
then procedes in 2 phases: reduction, and syntax relations. In
reduction, we replace short sequences of nodes with a single node, so
simple phrases like "the girl" and "didn't go" are parsed as units. In
syntax relations, we walk the top-level nodes of the graph and
recognize syntax relations between nodes.

Both phases are implemented using "Xfrms". A transform implements
one or more rules. It walks the graph until it finds one or more
nodes to which a rule applies. It then passes the nodes (and/or rule)
over to its "applyRule" method, which makes some modification to the
graph and returns the node at which the walk is to resume.

After the parse graph is fully defined, we have a full and complete
representation of the parse. But parse graph nodes ill suited to an
API, plus they consume a lot of memory. So the final step is to do a
top down walk of the parse graph, constructing a new and simplified
version of the parse using nodes of type Nd.
"""

# version info
version = "1.0"
def serialize_version(mode):
    global version
    if mode == 'r':
        version,vcb.version = serializer.decode_str().split(' ')
    else:
        serializer.encode_str("%s %s" % (version,vcb.version))

# test/dev option
def set_trace_parse(enable):
    xfrm.traceparse = enable

# the transforms
xfrms = []
xfrms.append(ReductXfrm('init'))
xfrms.append(LeftReductXfrm('leftinit'))
xfrms.append(LeftReductXfrm('queryhead'))
xfrms.append(ReductXfrm('vphr'))
xfrms.append(ReductXfrm('detphr'))
xfrms.append(ReductXfrm('conj'))
xfrms.append(BindPreps('bindPreps'))
xfrms.append(SrXfrm('sr'))
xfrms.append(QueryXfrm('query'))
xfrms.append(SvToQXfrm('svToQ'))
xfrms.append(InvertQXfrm('invertQ'))
xfrms.append(ValidateSpans('validateSpans'))
xfrms.append(InferSubjects('inferSubjects'))
xfrms.append(ReduceSrClauses('reduceSrClauses'))

def get_xfrm(name):
    """ get xfrm given name """
    for x in xfrms:
        if x.name == name:
            return x
    return None

def serialize(mode):
    """ read/write the parser (and vocabulary) """
    serialize_version(mode)
    vcb.serialize(mode)    
    for x in xfrms:
        x.serialize(mode)

def printme(fp):
    """ print parser rules """
    if fp is None:
        fp = sys.stdout
    for x in xfrms:
        x.printme(fp)

def parse_src(content_provider,delegate=None,maxlines=-1):
    """
    Parse source -- either a file or a str (but not both).
    If "delegate" is None, we return a list of parse nodes
    giving the parse. If delegate is defined, we read and
    parse the source in sections, passing the parse of each
    section over to the delegate for processing.
    This is the main entry function for parsing.
    """
    # The parse is a list of parse nodes
    nds = []
    # we parse in sections
    src = Source(content_provider)
    while src.get_section():
        blklst = lexer.get_parse_blks(src.sect_text,src.sect_lno)
        pnlst = parse_blklst(blklst,None)
        nds.extend(get_parse_nodes(pnlst,None,-1))
        # If a delegate is defined, pass the node collection
        # over the processing and start over.
        if delegate is not None and \
            src.lno - src.sect_lno > maxlines:
            # process the nodes, then start a new section
            delegate(nds)
            nds = []
    return nds

def parse_blklst(blklst,parent):
    """
    parse a list of blocks. Returns a list of Pn's.
    """
    pnlst = []
    for blk in blklst:
        if blk.sublst != None:
            # A quote or parenthesized text. Create appropriate
            # container node. Choices are "quote-block" or "paren-block".
            sc = vcb.lkup_sc('QuoteBlk')
            if blk.bracket == '(':
                sc = vcb.lkup_sc('ParenBlk')
            pn = pg.Pn(-1,blk.S,blk.E)
            pn.sc = sc
            pnlst.append(pn)
            pn.sublst = parse_blklst(blk.sublst,pn)
        else:
            # parse and add nodes to "pnds".
            pnlst.extend(parse_blk(blk))
    # rewrite "pnLst" to get attributions
    pnlst = set_attributions(pnlst)
    return pnlst

def parse_blk(blk):
    """ parse a block. Returns a list of Pn's. """
    pg.build_graph(blk)
    if xfrm.traceparse:
        pg.printme(None,"initial graph")
    for x in xfrms:
        try:
            x.do_xfrm()
            if xfrm.traceparse:
                pg.printme(None,"post " + x.name)
        except ParseErr:
            # if an xfrm throws an exception, we just continue on
            # to the next. The try/except mechanism is needed by the
            # tools that build the parse tables.
            pass
    return pg.get_root_nodes() 

def get_nd_kind(e,form):
    """ get the "kind" attribute for a parse node """
    sc_sp = vcb.spell_sc(e.sc)
    if sc_sp == "QuoteBlk":
        return NdKind.quote
    if sc_sp == "ParenBlk":
        return NdKind.paren
    if e.check_sc(WP_punct):
        return NdKind.punct 
    if form == NdForm.queryclause or \
        form == NdForm.queryphrase or \
        form == NdForm.queryword:
        return NdKind.query
    if e.is_verb():
        sub = e.get_subnodes([SR_agent,SR_topic,SR_exper])
        if len(sub) > 0:
            # something is in a subject role.
            if sub[0].check_sc(WP_query):
                return NdKind.query
            if len(e.rel[SR_vadj]) > 0 and \
                e.rel[SR_vadj][0].test_vroot("let"):
                return NdKind.imper
            if not e.check_vp(VP_gerund):
                return NdKind.assertion
        elif e.v_iso_sub is not None and \
            e.v_iso_sub.msnode is not None:
            # pick it up from our peer
            return e.v_iso_sub.msnode.kind
        elif e.check_vp(VP_root):
            return NdKind.imper
        elif e.check_vp(VP_passive) and \
            len(e.rel[SR_theme]) > 0:
            return NdKind.assertion
    # return default
    return NdKind.x

def get_nd_form(e,text):
    """ get the "form" attribute for a parse node """
    if e.is_container():
        return NdForm.x
    if e.check_sc(WP_punct):
        if text == '.' or \
            text == '?' or \
            text == '!' or \
            text == ':' or \
            text == ';':
            return NdForm.terminator
        elif text == ',':
            return NdForm.comma
        return NdForm.x
    if e.is_verb():
        # "sub": set of terms in subject clause
        sub = e.get_subnodes([SR_agent,SR_topic,SR_exper])
        if e.v_iso_sub is not None:
            # this is subject-verb
            return NdForm.verbclause
        elif e.check_vp(VP_query):
            # explicitly marked as query
            return NdForm.queryclause
        elif len(sub) == 0:
            if e.check_vp(VP_gerund|VP_inf|VP_root):
                return NdForm.action
        # default is "verb-clause"
        return NdForm.verbclause
    if len(e.wrds) == 1:
        # a word. Default is "X", but look for useful cases.
        wrd = e.get_wrd(0)
        if vcb.check_prop(wrd,WP_query):
            return NdForm.queryword
        if vcb.check_prop(wrd,WP_n|WP_detw):
            return NdForm.n
        if vcb.check_prop(wrd,WP_conj):
            return NdForm.conjword
        if vcb.check_prop(wrd,WP_mod):
            return NdForm.mod
        # use default
        return NdForm.x
    # a phrase. possessive? ("John's cat")
    poss_contract = vcb.lkup("'s",False)
    if poss_contract in e.wrds:
        return NdForm.n
    # compound modifier? ("very happy", "sad and miserable")
    is_mod = True
    for wrd in e.wrds:
        if not vcb.check_prop(wrd,WP_mod|WP_conj):
            is_mod = False
            break
    if is_mod:
        return NdForm.mod
    # conjunction phrase? ("boys and girls")
    for wrd in e.wrds:
        if vcb.check_prop(wrd,WP_conj):
            return NdForm.conjphrase
            break
    # remaining tests based on first word
    wrd = e.get_wrd(0)
    if vcb.check_prop(wrd,WP_query):
        # "how many", "what time"
        return NdForm.queryphrase
    if vcb.check_prop(wrd,WP_dets|WP_detw):
        return NdForm.n
    # default
    return NdForm.x

def remap_sr(sr):
    """ Helper for getParseNodes """
    if sr == SR_agent:
        return NdKind.agent
    if sr == SR_topic:
        return NdKind.topic
    if sr == SR_exper:
        return NdKind.exper
    if sr == SR_theme:
        return NdKind.theme
    if sr == SR_auxtheme:
        return NdKind.auxtheme
    if sr == SR_modifies or sr == SR_ladj:
        return NdKind.qual
    if sr == SR_attribution:
        return NdKind.attribution
    return -1

def remap_vp(v):
    """ Helper for getParseNodes """
    msv = 0
    if (v & VP_neg) != 0:
        msv |= VP.neg
    if (v & VP_past) != 0:
        msv |= VP.past
    if (v & VP_present) != 0:
        msv |= VP.present
    if (v & VP_future) != 0:
        msv |= VP.future
    if (v & VP_subjunctive) != 0:
        msv |= VP.subjunctive
    if (v & VP_perfect) != 0:
        msv |= VP.perfect
    return msv

def get_parse_nodes(lst,parent,sr):
    """
    This method accepts a list of graph nodes, and returns a
    corresponding list of parse nodes.
    """
    nds = []
    for e in lst:
        if e.msnode is not None:
            nds.append(e.msnode)
            continue
        # create a parse node and add to "nds".
        text = lexer.src[e.S:e.E+1] if e.is_verb() \
            else vcb.spell(e.wrds)
        form = get_nd_form(e,text)
        if sr != -1:
            assert parent is not None
            kind = remap_sr(sr)
            assert kind != -1
        else:
            kind = get_nd_kind(e,form)
        nd = e.msnode = Nd(kind,form,text,parent)
        nds.append(nd)
        # get content for containder nodes (quotes and parens)
        if e.is_container():
            nd.subnodes.extend(get_parse_nodes(e.sublst,nd,-1))
        # get subnodes
        for i in range(SR_nwordtoverb):
            if len(e.rel[i]) > 0 and remap_sr(i) != -1:
                nd.subnodes.extend(get_parse_nodes(e.rel[i],nd,i))
        if len(e.head)>0:
            nd.head = vcb.spell(e.head)
        if len(e.verbs)>0:
            nd.vroots = vcb.spell(e.verbs)
        if len(e.vqual)>0:
            nd.vqual = vcb.spell(e.vqual)
        if len(e.adverbs)>0:
            nd.adverbs = vcb.spell(e.adverbs)
        if e.vprops != 0:
            if form != NdForm.action:
                nd.vprops = remap_vp(e.vprops)
        locS = e.S
        locE = e.E
        nd.lineS = lexer.lno_map[locS]
        nd.colS = lexer.col_map[locS]
        nd.lineE = lexer.lno_map[locE]
        nd.colE = lexer.col_map[locE]
    return nds

def do_attributions(nds):
    """
    Attribute quotes
    """
    _nds = []
    i = 0
    while i < len(nds):
        if msndRE.match(nds,
            'quote agentSaid comma|terminator agentSaid quote',i):
            q1 = nds[i]
            q1.attribution = nds[i+1]
            q2 = nds[i+4]
            q2.attribution = nds[i+3]
            _nds.append(q1)
            _nds.append(q2)
            i += 5
            continue
        if msndRE.match(nds,
            'quote agentSaid commma|terminator quote',i):
            q1 = nds[i]
            q1.attribution = nds[i+1]
            q2 = nds[i+3]
            q2.attribution = nds[i+1]
            _nds.append(q1)
            _nds.append(q2)
            i += 4
            continue
        if msndRE.match(nds,
            'agentSaid commma quote',i):
            q = nds[i+2]
            q.attribution = nds[i]
            _nds.append(q)
            i += 3
            continue
        if msndRE.match(nds,
            'quote agentSaid',i):
            q = nds[i]
            q.attribution = nds[i+1]
            _nds.append(q)
            i += 3
            continue
        _nds.append(nds[i])
        i += 1
    return _nds









