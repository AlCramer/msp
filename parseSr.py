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
import lexer
import vcb
from vcb import sc_dct
import serializer
from rematch import *
from xfrm import *
import os
import sys

"""
This module defines transforms that establish syntax relations.
"""

class BindPreps(Xfrm):
    """
    Bind preps to verbs
    """
    def bind_prep(self,e):
        # e is the prep to be bound
        ep = e
        prep = ep.get_wrd(0)
        v0,fit0 = None,-1
        v1,fit1 = None,-1
        ex = ep.prv
        # Walk left, to a max of 2 verbs; punctuation and
        # conjunctions terminate the walk.
        while ex != None:
            if ex.check_sc(WP_conj|WP_punct):
                break
            if vcb.is_sc_for_verb(ex.sc):
                if v0 is None:
                    v0 = ex
                    fit0 = vcb.get_prep_verb_fitness(prep,v0.get_vroot())
                elif v1 is None:
                    v1 = ex
                    fit1 = vcb.get_prep_verb_fitness(prep,v1.get_vroot())
                    break
            ex  = ex.prv
        if fit1 > fit0:
            ep.sc = vcb.lkup_sc("FarPrep")
            v1.set_vp(VP_farprep)
            return v1.prv
        return e.prv

    def do_xfrm(self):
        e = pg.eE
        while e != None:
            if e.h == 6:
                debug = 1
            if e.check_sc(WP_prep):
                e = self.bind_prep(e);
            else:
                e = e.prv

class QueryXfrm(Xfrm):
    """
    Transform query constructs ("why did she leave"). 
    """
    def do_xfrm(self):    
        e = pg.eS
        while e != None:
            # is "e" a verb-adjunct ("did she leave", "why did she leave")
            if e.sr == SR_vadj:
                # transfer relevant attributes to scope verb
                v = e.scope
                v.unset_scope()
                v.vprops = e.vprops & VP_tensemask
                if not e.test_vroot(\
                    ['be','have','do','will','shall']):
                    v.vqual.append(e.get_wrd(0))
                # is e "why did..."?
                if len(e.rel[SR_isqby]) > 0:
                    qwrd = e.rel[SR_isqby][0]
                    qwrd.set_scope(v,SR_isqby)
                # mark main verb as a query
                v.set_vp(VP_query)
            elif e.check_sc(WP_qhead|WP_beqhead):
                # mark "e" as query
                e.set_vp(VP_query)
            e = e.nxt

class SvToQXfrm(Xfrm):
    """
    Context dependent transform of subject-verb to qualified
    expression.
    """

    def in_sub_role(self,e):
        """ Can "e" be in a subject role? """
        return e.sr == SR_agent or \
             e.sr == SR_exper or \
             e.sr == SR_topic

    def is_avgt_obj_term(self,e):
        """ is "e" an object term in an avgt expression? """
        if e.sr == SR_theme or e.sr == SR_auxtheme:
            if len(e.scope.rel[SR_theme]) > 0 and \
                len(e.scope.rel[SR_auxtheme]) > 0:
                # We're an object term in AGVT context: "I gave
                # the guy sitting there an apple".
                return True
        return False


    def find_verb(self,e):
        """
        Returns verb node to be transformed: we're currently
        at "e" in a right-to-left traversal of the graph
        """
        if e.check_vp(VP_gerund):
            if self.in_sub_role(e) or self.is_avgt_obj_term(e):
                # "the girl sitting there" in subject or avgt object role
                return e
        elif e.check_vp(VP_participle):
            if e.scope is not None:
                if self.in_sub_role(e) or self.is_avgt_obj_term(e):
                    # "the strongest wind ever recorded" in subject or
                    # avgt object role
                    return e
        elif vcb.check_sc_prop(e.sc, WP_query) and \
            self.in_sub_role(e) and \
            len(e.scope.rel[SR_isqby]) == 0:
            # "who ate the cake".
            return e.scope
        return None

    def do_xfrm(self):
        e = pg.eS
        while e != None:
            v = self.find_verb(e)
            if v is not None:
                if len(v.rel[SR_agent]) > 0:
                    v.reset_rel(SR_agent,SR_isqby)
                elif len(v.rel[SR_exper]) > 0:
                    v.reset_rel(SR_exper,SR_isqby)
                elif len(v.rel[SR_topic]) > 0:
                    v.reset_rel(SR_topic,SR_isqby)
                e = v.nxt
            else:
                e = e.nxt
        pg.validate_rel()

class InvertQXfrm(Xfrm):
    """
    Invert Q expressions. Given "the girl you saw", [the girl] gets
    the (sr,scope) attributes of the verb, and the verb becomes a
    modifier of [the girl].
    """

    def invert_q(self,q):
        # q is the node to be qualified
        v = q.scope
        q.scope = v.scope
        q.sr = v.sr
        if v.check_vp(VP_inf) and len(v.rel[SR_agent]) > 0:
            # "a cake good enough to eat"
            # The pattern is [Nexpr Adj Inf] and the tree is:
            # Adj modifies Nexpr; Inf modifies Adj
            sub = v.rel[SR_agent][0]
            sub.set_scope(q,SR_modifies)
            v.set_scope(sub,SR_modifies)
        else:
            v.sr = SR_modifies
            v.scope = q
        return q.nxt

    def do_xfrm(self):
        e = pg.eS
        while e != None:
            if e.sr == SR_isqby:
                e = self.invert_q(e)
            else:
                e = e.nxt
        # TODO: needed?
        pg.validate_rel()

class ValidateSpans(Xfrm):
    """
    Called after the domains of verb expressions have been defined:
    adjust nodes spans accordingly.
    """
    def do_xfrm(self):
        pg.validate_span()        

class InferSubjects(Xfrm):
    """
    In general syntax relations don't cross puctuation and conjunction
    ("and","or") boundaries. This analysis catches several
    common patterns:
    "They left today, running as fast as they could"
    "I saw Sally drinking rum and smoking reefer"
    """
    def do_xfrm(self):
        # get sequence of verbs + top scope nodes
        seq = []
        e = pg.eS
        while e is not None:
            if e.is_verb() or e.scope is None:
                seq.append(e)
            e = e.nxt
        pnRE.decl_re("%commaPhr","[_, _and|_or|_but? _then?]")
        pnRE.decl_re("%conjPhr","_and|_or|_but _then?")
        while len(seq) >= 2:
            #pg.print_pnlst(seq)
            if pnRE.match(seq,"SubVerb %commaPhr|%conjPhr Mod? VerbNoSub|VerbSub"):
                e = pnRE.match_result[0][0]
                ex = pnRE.match_result[3][0]
                pg.reduce_head(pnRE.match_result[1][0],ex)
                # ex is given same scope, syntax role, and relations as
                # its peer.
                scope = e.scope
                ex.scope = scope
                ex.sr = e.sr
                if scope is not None:
                    rel_ix = scope.get_rel(e);
                    if rel_ix != -1:
                         scope.rel[rel_ix].append(ex)
                # ex's subject roles are derived from its peer. "subject"
                # roles are : topic, agent, and experiencer. In testing,
                # order is important: check agent before exper, because
                # of AVE
                erole = -1
                if len(e.rel[SR_topic]) > 0:
                    erole = SR_topic
                if len(e.rel[SR_agent]) > 0:
                    erole = SR_agent
                if len(e.rel[SR_exper]) > 0:
                    erole = SR_exper
                if erole != -1:
                    if pnRE.match([ex],"VerbSub"):
                        # default role assignment classed this as a query:
                        # "have you the time". Slide the roles down the
                        # hierarchy.
                        ex.rel[SR_modifies] = ex.rel[SR_theme]
                        ex.rel[SR_theme] = ex.rel[SR_agent]
                    # compute role for ex 
                    exrole = SR_agent
                    if ex.check_vp(VP_passive|VP_participle) or \
                        ex.test_vroot('be'):
                        exrole = SR_topic
                    elif ex.test_verb_form(VP_evt):
                        exrole = SR_exper
                    exrole = erole
                    if ex.test_verb_form(VP_evt):
                        exrole = SR_exper
                    ex.rel[exrole] = e.rel[erole]
                # advance
                ex_ix = seq.index(ex)
                seq = seq[ex_ix:]
                continue
            seq = seq[1:]

class ReduceSrClauses(Xfrm):
    """
    Conjoin words in the same sr context to form phrases
    """

    def __init__(self,name):
        Xfrm.__init__(self,name)

    def reduce_clauses(self,lst):
        if len(lst) == 0:
            return
        # recurse thru child clauses
        for e in lst:
            for sr_clause in e.rel:
                self.reduce_clauses(sr_clause)
        # merge sequences of prep's
        prep_mask = WP_prep|WP_qualprep|WP_clprep
        l1 = [lst[0]]
        for e in lst[1:]:
            last = l1[len(l1)-1]
            if last.check_sc(prep_mask) and \
                e.check_sc(prep_mask) and \
                e.is_leaf():
                last.wrds.extend(e.wrds)
                last.E = e.E
                pg.remove_node(e)
                continue
            l1.append(e)
        # rewrite l1 to "lst", merging word sequences
        del lst[:]
        i = 0
        while i < len(l1):
            e = l1[i]
            i += 1
            if e.check_sc(WP_punct):
                lst.append(e)
                continue
            # "e" is a word. It starts a phrase (which may consist solely
            # of this word).
            S = e
            if S.check_sc(prep_mask|WP_conj):
                # bind this to the word that follows (if there is a word)
                if i<len(l1) and not l1[i].check_sc(WP_punct):
                    l1[i].head.extend(S.wrds)
                    pg.remove_node(S)
                    S = l1[i]
                    i += 1
            # "i" is at term that follows S. If S is a leaf, merge any
            # leaves that follow.
            if S.is_leaf():
                while i<len(l1):
                    if l1[i].check_sc(WP_punct|WP_verb) or not l1[i].is_leaf():
                        break
                    S.wrds.extend(l1[i].wrds)
                    pg.remove_node(l1[i])
                    i += 1
            # add S to the lst
            lst.append(S)

    def do_xfrm(self):
        self.reduce_clauses(pg.get_root_nodes())   


