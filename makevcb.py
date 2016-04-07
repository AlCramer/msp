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

"""
Initialize vocabulary from "lexicon.txt", an ascii file containing
information about words (lists of verbs, etc.).
"""

import re
from defs import *
import vcb
from vcb import WordVariant,RewriteRules
import serializer
import parser
import os


# rewrite rules. We collect rules of the form
# "<lhs terms> : <rhs terms>"
# as we process the file "lexicon.txt", then create
# vcb's "rwrules" attribute when the collection is complete.
rwrules_raw = []

def define_rewrite_rules(rules):
    # ensure all terms are defined in the vocab
    for rule in rwrules_raw:
        for t in rule:
            if t != ":":
                define(t,0,0)
    # initialize the index for the rules collection
    rules.index = [None]*vcb.get_n()
    # define the lhs & rhs side of each rule
    for rule in rwrules_raw:
        lhs = []
        rhs = []
        targ = lhs
        for t in rule:
            if t == ':':
                targ = rhs
            else:
                targ.append(vcb.lkup(t,False))
        # "rix": index of new rule.
        rix = len(rules.lhs)
        rules.lhs.append(lhs)
        rules.rhs.append(rhs)
        # "key": first token, lhs. Add rix to rules.index[key]
        key = lhs[0]
        if rules.index[key] is None:
            rules.index[key] = [rix]
        else:
            # index entries are sorted, longest-lhs first
            ix_insert = -1
            lst = rules.index[key]
            for i in range(0,len(lst)):
                _rix = lst[i]
                if len(lhs) >= len(rules.lhs[_rix]):
                    ix_insert = i
                    break
            if ix_insert != -1:
                lst.insert(ix_insert,rix)
            else:
                lst.append(rix)

def add_prep_verb_fitness(terms):
    """ add a prep->{verb} mapping """
    # get prep
    pkey = vcb.define(terms[0],WP_prep,0,0)
    # collect verbs
    i = 2        # skip ":" after prep
    while i<len(terms):
        verb = terms[i]
        cnt = 1
        if '=' in terms[i]:
            verb,_cnt = terms[i].split('=')
            cnt = int(_cnt)
        vkey = vcb.lkup(verb,False)
        if vkey is 0 or not vcb.check_vp(vkey,VP_root):
            # print 'prepToVerbs: skipped %s,%s' %(terms[0],terms[i])
            pass
        else:
            vcb.prep_verb_fitness.add(pkey,vkey,cnt)
        i += 1

def define(sp,props,vprops):
    """
    create entry for word and set props. If word is already defined,
    just add the props to the existing entry
    """
    key = vcb.lkup(sp,False)
    if key != 0:
        vcb.set_prop(key,props)
        vcb.set_vp(key,vprops)
        return
    key = vcb.define(sp,props,vprops,0)
    _def = vcb.get_def(key)
    if _def == key:
        # is this word a variant of some other entry?
        v = WordVariant()
        if vcb.is_word_variant(sp,v):
            vcb.set_def(key,v.root_key)
            vcb.set_prop(key,v.props)
            vcb.set_vp(key,v.vprops)

def define_words(props,vprops,root,lst):
    """
    define a group of words: props and root apply to all
    members in list
    """
    for sp in lst.split():
        vcb.define(sp,props,vprops,root)

def read_lexicon():
    """ Get lines from the ASCII file of lexical info """
    # This code assumes the ascii file "lexicon.txt" lives
    # in the same directory as this script.
    dn = os.path.dirname(os.path.realpath(__file__))
    f = open(os.path.join(dn,"lexicon.txt"),'r')
    fstr = f.read()
    f.close()
    fstr = fstr.replace('\r',' ')
    rePlus = re.compile(r'\+[ ]*\n')
    fstr = rePlus.sub(' ',fstr);
    return fstr.split('\n')

def add_verb(terms):
    """
    Add a verb. First word is the root. If verb is irregular,
    remaining terms are:
    3rdPersonPresent past-simple past-perfect gerund. Ex:
    "go goes went gone going".
    """
    root_key = \
        vcb.define(terms[0], WP_verb,VP_root|VP_present,0)
    i = 1
    if i<len(terms) and terms[i] != ':':
        # forms for verbs "goes"
        vcb.define(terms[i], WP_verb,VP_present,root_key)
        i += 1
        # "went"
        vcb.define(terms[i], WP_verb,VP_past,root_key)
        i += 1
        # "gone"
        vcb.define(terms[i], WP_verb,VP_past,root_key)
        i += 1
        # "going"
        vcb.define(terms[i], WP_verb,VP_gerund,root_key)
        i += 1
    if i<len(terms):
        # get syntax form
        i += 1
        if terms[i] =="AVE":
            vcb.set_vp(root_key,VP_ave)
        elif terms[i] == "EVT":
            vcb.set_vp(root_key,VP_evt)
        elif terms[i] == "AVGT":
            vcb.set_vp(root_key,VP_avgt)
        elif terms[i] == "VPQ":
            vcb.set_vp(root_key,VP_vpq)
        else:
            assert False

def assign_synclasses():
    """
    assign a syntax class to each word in the vocabulary
    """
    vcb.synclass = [0]
    for i in range(1,vcb.get_n()):
        sp = vcb.spell(i)
        sc_ix = vcb.sc_dct.lkup(sp,False)
        if sc_ix == 0:
            sc_desc = vcb.get_sc_desc(i)
            sc_ix = vcb.sc_dct.lkup(sc_desc,False)
            if sc_ix == 0:
                print \
                    "Warning: could not assign syntax class to \"%s\"" % \
                    sp
                sc_ix = vcb.sc_dct.lkup('X',False)
        vcb.synclass.append(sc_ix)
    debug = 1

def create_vcb():
    """ initialize vocabulary from an ASCII file of lexical info """
    # reallocate data structures: the make process will have
    # read in old versions.
    vcb.dct = vcb.Dict()
    vcb.vprops = []
    vcb._def = []
    vcb.synclass = []
    vcb.rwrules = RewriteRules()
    vcb.prep_verb_fitness = vcb.Int16PairToInt8()
    # By convention an index of "0" means "no entry" on a lookup. Make
    # a dummy entry for 0, so any subsequent entries will have key > 0
    vcb.define("_NULL_",0,0,0)
    # create entries for various forms of "be": be being am are is was
    # were been
    root_key = vcb.define("be", \
        WP_verb,VP_root|VP_present,0)
    vcb.define("being",WP_verb,VP_gerund,root_key)
    # present tense forms. "'s" is a contraction for "is"
    define_words(WP_verb,VP_present,root_key,\
        "am are is 's")
    # past tense forms
    define_words(WP_verb,VP_past,root_key,
        "was were been")
    # create entry for "'d" as a verb adjunct
    vcb.define("'d",WP_verb,VP_adj,0)
    # create entries for "and" and "or"
    define_words(WP_conj, 0, 0, "and or")
    # create entries for verb-phrase-adjuncts
    define_words(WP_verb, VP_adj, 0,
        "will shall would should may might ought")
    vcb.define("can",WP_verb,VP_adj|VP_present,0)
    vcb.define("could",WP_verb,VP_adj|VP_past,0)
    # define entries for pronouns. Note "her" is a special case:
    # it's a weak determinant ("I saw her", "I saw her mother").
    define_words(WP_n, 0, 0,
        "i you we he she they it")
    define_words(WP_n, 0, 0,
        "me you him them us it")
    vcb.define("her",WP_detw,0,0)
    # create entries for words mapping to distinct synclasses
    for sp in vcb.sc_singletons:
        vcb.define(sp,0,0,0)

    # read additional lexical info from file.
    state = ""
    props = 0
    lines = read_lexicon()
    for line in lines:
        line = line.strip()
        if line.startswith("/"):
            continue;
        if line.startswith(">>Version"):
            vcb.version = line[len(">>Version"):].strip()
            continue
        terms = line.split()
        if len(terms) == 0:
            continue;
        w0 = terms[0]
        if w0[0] == ">":
            if w0 == ">>Rewrite":
                state = w0
            elif w0 == ">>Verbs":
                state = w0
            elif w0 == ">>Contractions":
                state = w0
            elif w0 == ">>PrepVerbs":
                state = w0
            else:
                # everything else sets a prop for a word.
                state = "props"
                if w0 == ">>Nouns":
                    props = WP_noun
                elif w0 == ">>Conjunctions":
                    props = WP_conj
                elif w0 == ">>DetStrong":
                    props = WP_dets
                elif w0 == ">>DetWeak":
                    props = WP_detw
                elif w0 == ">>Names":
                    props = WP_n
                elif w0 == ">>Abbrev":
                    props = WP_abbrev
                elif w0 == ">>Adjectives":
                    props = WP_adj
                elif w0 == ">>Prepositions":
                    props = WP_prep
                elif w0 == ">>ClausePreps":
                    props = WP_clprep
                elif w0 == ">>QualPreps":
                    props = WP_qualprep
                elif w0 == ">>Query":
                    props = WP_query
                elif w0 == ">>ClauseModifiers":
                    props = WP_clmod
                elif w0 == ">>Adverbs":
                    props = WP_adv
                elif w0 == ">>Attribution":
                    props = WP_attribution
                else:
                    assert False, \
                        'malformed lexicon. unknown control %s' % w0
            continue
        if state == "props":
            if len(terms) > 1 and props != WP_abbrev:
                # create respell rule mapping multiple tokens to a
                # single token, then set the props for the single
                # token
                lhs = ' '.join(terms)
                terms.append(":")
                terms.append(lhs)
                rwrules_raw.append(terms)
                w0 = lhs
            define(w0, props, 0)
        elif state == ">>Verbs":
            add_verb(terms)
        elif state == ">>Contractions" or \
            state == ">>Rewrite":
            # For the contraction case, mark the word as a
            # contraction.
            if state == ">>Contractions":
                root_key = vcb.define(w0,WP_contraction,0,0)
            rwrules_raw.append(terms)
        elif state == ">>PrepVerbs":
            add_prep_verb_fitness(terms)

    # end loop over lines

    # define rewrite rules
    define_rewrite_rules(vcb.rwrules)

if __name__== '__main__':
    # read "msp.dat"
    serializer.init("msp.dat",'r')
    parser.serialize('r')
    serializer.fini()
    # re-create the vocabulary from the ascii file "lexicon.txt"
    create_vcb()
    assign_synclasses()
    # write out "msp.dat"
    serializer.init("msp.dat",'w')
    parser.serialize('w')
    serializer.fini()
    print 'rewrote "msp.dat"'
    #vcb.printSynClasses()
    vcb.print_rewrite_rules()    
    # enable this code to test interactively
    print 'Testing vocab: enter "q" to quit'
    vcb.unit_test()


