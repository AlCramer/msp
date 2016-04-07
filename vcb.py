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
import re
import serializer
import os

class Int16PairToInt8():
    """
    Serializable mapping, (int16,int16)->int8. This utility class
    used by the vocabulary to represent the mapping
    (prep,verb)->fitness, where fitness measures the
    strength of the association.
    """
    def __init__(self):
        self.pair_to_v = {}

    def lkup(self,l1,l2):
        v = self.pair_to_v.get('%d %d' % (l1,l2))
        return -1 if v is None else v

    def add(self,l1,l2,v):
        self.pair_to_v['%d %d' % (l1,l2)] = v

    def serialize(self,mode):
        if mode == 'w':
            l1lst = []
            l2lst = []
            rlst = []
            for key,v in self.pair_to_v.iteritems():
                l1,l2 = key.split(' ')
                l1lst.append(int(l1))
                l2lst.append(int(l2))
                rlst.append(v)
            serializer.encode_intlst(l1lst,16)
            serializer.encode_intlst(l2lst,16)
            serializer.encode_intlst(rlst,8)
        else:
            l1lst = serializer.decode_intlst(16)
            l2lst = serializer.decode_intlst(16)
            rlst = serializer.decode_intlst(8)
            self.pair_to_v = {}
            for i in range(len(l1lst)):
                l1 = l1lst[i]
                l2 = l2lst[i]
                self.pair_to_v['%d %d' % (l1,l2)] = rlst[i]

class WordVariant():
    """
    "softly" is a variant of "soft", "looked" is a variant of "look".
    This data structure records the root and props of the variant
    """
    root_key = 0
    props = 0
    vprops = 0

class RewriteRules():
    """
    A rewrite rule specifies a lhs ("target"), and a rhs
    ("replacement"). Both are sequences, giving indices into the
    dictionary. We apply a rule by recognizing a lhs in the token
    sequence and replacing it with the rhs. 
    """
    def __init__(self):
        # "lhs" and "rhs" are parallel lists of token sequences.
        # lhs[i] and rhs[i] define rule "i": if we see the sequence
        # lhs[i] during tokenization, we replace it with the sequence
        # rhs[i].
        self.lhs = []
        self.rhs = []
        # This is a mapping, wrdIx->{ruleIx}. "wrdIx" is the dictionary
        # index for a word. "ruleIx" is the index of a rewrite rule,
        # such that the lhs of the rules starts with that word.
        self.index = []

    def serialize(self,mode):
        if mode == 'w':
            serializer.encode_lstlst(self.lhs,16)
            serializer.encode_lstlst(self.rhs,16)
            serializer.encode_lstlst(self.index,16)
        else:
            self.lhs = serializer.decode_lstlst(16)
            self.rhs = serializer.decode_lstlst(16)
            self.index = serializer.decode_lstlst(16)

class Dict():
    """
    This class encapsulates 3 mappings: word->index, index->word, and
    index->props. "word" is a the spelling for an entry; "index" is
    the index assigned to an entry; "props" is a bitmask.
    """
    def __init__(self):
        # spelling->index
        self.sp_to_ix = {}
        # index->spelling
        self.spelling = []
        # index->props
        self.props = []

    def get_n(self):
        # get number of entries
        return len(self.spelling)

    def lkup(self,sp,create_if_missing):
        """ lookup "sp", returning the index for its entry """
        ix = self.sp_to_ix.get(sp)
        if ix != None:
            return ix
        if not create_if_missing:
            return 0
        ix = len(self.spelling)
        self.sp_to_ix[sp] = ix
        self.spelling.append(sp);
        self.props.append(0);
        return ix

    def serialize(self,mode):
        """ serialize  the dictionary """
        global sp_to_ix,spelling,props
        if mode == 'w':
            serializer.encode_strlst(self.spelling)
            serializer.encode_intlst(self.props,32)
        else:
            self.spelling = serializer.decode_strlst()
            self.sp_to_ix = {}
            for i in range(len(self.spelling)):
                self.sp_to_ix[self.spelling[i]] = i
            self.props = serializer.decode_intlst(32)

    def spell(self,ix_or_lst):
        """ get spelling """
        if not isinstance(ix_or_lst,list):
            return self.spelling[ix_or_lst]
        tmp = []
        for e in ix_or_lst:
            tmp.append(self.spelling[e])
        return ' '.join(tmp)

    def set_prop(self,ix,v):
        """ set prop """
        self.props[ix] |= v

    def check_prop(self,ix,v):
        """ check prop """
        return (ix != 0) and ((self.props[ix] & v) != 0)

"""
This module contains our vocabulary. "dict" is a dictionary, defining
the mappings word->index, index->word, and index->properties.
Additional data structures provide more information about entries.
These are:
1. "vprops" -- verb props for the entry,
2. "_def" -- key of some other entry in the lexicon, which
is the "definition" of this word. Sometimes a word is defined to
itself.
3. "synClass" -- syntax-class for the word.
4. Prep<->Verbassociations -- is a prep associated with a verb? The
association maybe an indirect object phrase ("I gave the apple
TO the girl"); or it might be a common modifier clause
("I walked TO the store").
5. Rewrite Rules -- rules for replacing one set of words with
another during tokenization.
"""
# Our dictionary
dct = Dict()
def get_n():
    return dct.get_n();
# verb properties
vprops = []
# definitions for entries.
_def = []
# syntax class for entries.
synclass = []
# rewrite rules A rewrite rule specifies a lhs ("target"), and a rhs
# ("replacement"). Both are sequences, giving indices into the
# dictionary. We apply a rule by recognizing a lhs in the token
# sequence and replacing it with the rhs. 
rwrules = RewriteRules()
# mapping, (prep,verb)->fitness.
# prep and verb are dictionary indices. fitness is an int value
# giving the strength of the association between the prep and
# verb. 0 means means no association.
prep_verb_fitness = Int16PairToInt8()
# The syntax-class dictionary
sc_dct = Dict()
# sc singeltons
sc_singletons = []
# version info: readin from "lexicon.txt"
version = "?"

def serialize(mode):
    global vprops,_def,rwrules,sc_singletons
    global synclass
    dct.serialize(mode)
    if mode == 'w':
        serializer.encode_intlst(vprops,32) 
        serializer.encode_intlst(_def,32)
        serializer.encode_intlst(synclass,32)
        serializer.encode_strlst(sc_singletons)
    else:
        vprops = serializer.decode_intlst(32)
        _def = serializer.decode_intlst(32)
        synclass = serializer.decode_intlst(32)
        sc_singletons = serializer.decode_strlst()
    sc_dct.serialize(mode)
    rwrules.serialize(mode)
    prep_verb_fitness.serialize(mode)

def lkup(sp,create_if_missing):
    """ lookup "sp", returning the key for its entry """
    global _def,synclass,rwrules
    ix = dct.lkup(sp,False)
    if ix != 0:
        return ix
    if not create_if_missing:
        return 0
    ix = dct.lkup(sp,True)
    vprops.append(0);
    _def.append(0);
    synclass.append(0)
    rwrules.index.append(None)
    return ix

def define(sp,_props,vprops,_def):
    """ define an entry """
    ix = lkup(sp,True)
    set_prop(ix,_props)
    set_vp(ix,vprops)
    if _def != 0:
        # this def overrides any previous def
        set_def(ix,_def)
    else:
        # if this entry has no definition, define to self
        if get_def(ix) == 0:
            set_def(ix,ix)
    return ix

def spell(ix_or_lst):
    """ get spelling """
    if not isinstance(ix_or_lst,list):
        return dct.spell(ix_or_lst)
    wrds = ix_or_lst
    if len(wrds)==0:
        return ''
    buf = dct.spell(wrds[0])
    i = 1
    while i < len(wrds):
        sp = dct.spell(wrds[i])
        i += 1
        clast = buf[len(buf)-1]
        if clast.isalnum() and sp[0].isalnum():
            buf += ' '
        buf += sp
    reWantSp1 = re.compile(r'([\.\?\!\;\:\-\)]+)(\w+)')
    buf = reWantSp1.sub(r'\1 \2',buf)
    reWantSp2 = re.compile(r'(\w+)([\$])')
    buf = reWantSp2.sub(r'\1 \2',buf)
    return buf

def set_vp(ix,v):
    """ set prop """
    vprops[ix] |= v

def check_vp(ix,v):
    """ check prop """
    return (ix != 0) and ((vprops[ix] & v) != 0)

def get_vprops(ix):
    """ get props """
    return vprops[ix]

def get_def(ix):
    """ get def for ix """
    return _def[ix]

def set_def(ix,v):
    """ set def for ix """
    _def[ix] = v

def get_props(ix):
    """ get props """
    return dct.props[ix]

def set_prop(ix,v):
    """ set prop """
    dct.set_prop(ix,v)

def check_prop(ix,v):
    """ check prop """
    return dct.check_prop(ix,v)

def get_prep_verb_fitness(prep,verb):
    """ get strength of association between prep and verb """
    return prep_verb_fitness.lkup(prep,verb)

def is_verb_variant(wrd,v):
    """
    is an unknown word a variant of a known verb? We expect the
    lower-case spelling of the unknown word.
    """
    l = len(wrd)
    # if this the not-contraction for a verb? ("isn't", "didn't")
    if (l >= 5) and wrd.endswith("n't"):
        test = wrd[0 : l-3]
        # some cases are irregular...
        v_key = lkup(test,False)
        if v_key != 0:
            v.props |= WP_verb
            v.vprops = VP_negcontraction | get_vprops(v_key)
            v.vprops &= ~VP_root
            v.root_key = get_def(v_key)
            return True
    # "...ing"
    if (l >= 5) and wrd.endswith("ing"):
        root = wrd[0 : l-3]
        # "wanting"
        key = lkup(root,False)
        if check_vp(key,VP_root):
            v.props |= WP_verb
            v.root_key = key
            v.vprops |= VP_gerund
            return True
        # "hating"
        test = root + "e"
        key = lkup(test,False)
        if check_vp(key,VP_root):
            v.props |= WP_verb
            v.root_key = key
            v.vprops |= VP_gerund
            return True
        # "shipping"
        lroot =len(root)
        if root[lroot-1] == root[lroot-2]:
            test = root[0:lroot]
            key = lkup(test,False)
            if check_vp(key,VP_root):
                v.props |= WP_verb
                v.root_key = key
                v.vprops |= VP_gerund
                return True
    # "...ed"
    if (l >= 4) and wrd.endswith("ed"):
        root = wrd[0 : l-2]
        lroot = len(root)
	# "wanted"
        key = lkup(root, False)
        if check_vp(key,VP_root):
            v.props |= WP_verb
            v.root_key = key
            v.vprops |= VP_participle|VP_past
            return True
        # "hated"
        key = lkup(root + "e",False)
        if check_vp(key,VP_root):
            v.props |= WP_verb
            v.root_key = key
            v.vprops |= VP_participle|VP_past
            return True
        # "shipped"
        if root[lroot-1] == root[lroot-2]:
            test = root[0:lroot]
            key = lkup(test,False)
            if check_vp(key,VP_root):
                v.props |= WP_verb
                v.root_key = key
                v.vprops |= VP_participle|VP_past
                return True
    # "...es"
    if (l >= 4) and wrd.endswith("es"):
        # "watches"
        test = wrd[0 : l-2]
        if test == "be":
            # "bees"
            return False
        key = lkup(test,False)
        if check_vp(key,VP_root):
            v.props |= WP_verb
            v.root_key = key
            v.vprops |= VP_present
            return True
    # "eats"
    if (l >= 3) and wrd.endswith("s"):
        test = wrd[0 : l-1]
        key = lkup(test, False)
        if check_vp(key,VP_root):
            v.props |= WP_verb
            v.root_key = key
            v.vprops |= VP_present
            return True
    return False

def is_word_variant(wrd,v):
    """
    is an unknown word a variant of a known word? We expect the
    lower-case spelling of the unknown word.
    """
    # check for verb variants
    is_verb_var = is_verb_variant(wrd,v)
    # check non-verb forms. 
    l = len(wrd)
    # is word an adverb form of a known modifier?
    if (l >= 5) and  wrd.endswith("ly"):
        test = wrd[0 : l-2]
        root_key = lkup(test,False)
        if check_prop(root_key,WP_mod):
            v.props |= WP_adv
            if v.root_key == 0:
                v.root_key = root_key
            return True
    # a simple plural of a noun (cat->cats) ?
    if (l >= 4) and  wrd.endswith("s"):
        test = wrd[:-1]
        root_key = lkup(test,False)
        if check_prop(root_key,WP_noun):
            v.props |= WP_noun
            if v.root_key == 0:
                v.root_key = root_key
            return True
    # mod variants: (strong->strongest), (strange->strangest)
    if (l >= 6) and  wrd.endswith("est"):
        test = wrd[:-3]
        root_key = lkup(test,False)
        if check_prop(root_key,WP_mod):
            v.props |= WP_adj
            if v.root_key == 0:
                v.root_key = root_key
            return True
        test += "e"
        root_key = lkup(test,False)
        if check_prop(root_key,WP_mod):
            v.props |= WP_adj
            if v.root_key == 0:
                v.root_key = root_key
            return True
    # mod variants: (strong->stronger), (strange->stranger)
    if (l >= 6) and  wrd.endswith("er"):
        test = wrd[:-2]
        root_key = lkup(test,False)
        if check_prop(root_key,WP_mod):
            v.props |= WP_adj
            if v.root_key == 0:
                v.root_key = root_key
            return True
        test += "e"
        root_key = lkup(test,False)
        if check_prop(root_key,WP_mod):
            v.props |= WP_adj
            if v.root_key == 0:
                v.root_key = root_key
            return True
    return is_verb_var

def get_sc_desc(i):
    """ get synclass spelling for entry "i" """
    # most tests based on word/verb props, but some require that we look at
    # the spelling
    sp = spell(i)
    if check_prop(i,WP_dets):
        return "DetS"
    # conjunctions
    if sp == 'and' or sp == 'or':
        return "AndOr"
    if check_prop(i,WP_conj):
        return "Conj"
    if check_prop(i,WP_query):
        return "Query"
    if check_vp(i,VP_gerund):
        return "Ger"
    if check_vp(i,VP_participle):
        return "Part"
    # collect classes for this entry (there may be > 1)
    l = []
    # determinants
    if check_prop(i,WP_detw):
        l.append("DetW")
    # preps
    if check_prop(i,WP_clprep):
        l.append("ClPrep")
    elif check_prop(i,WP_qualprep):
        l.append("QualPrep")
    elif check_prop(i,WP_prep):
        l.append("Prep")
    # nouns
    if check_prop(i,WP_noun):
        l.append("Noun")
    # names
    if check_prop(i,WP_n):
        l.append("N")
    # mods
    if check_prop(i,WP_adj):
        l.append("Adj")
    if check_prop(i,WP_adv):
        l.append("Adv")
    if check_prop(i,WP_clmod):
        l.append("ClMod")
    # verb-adjuncts and verbs
    if check_prop(i,WP_verb):
        if check_vp(i,VP_adj):
            l.append("VAdj")
        else:
            l.append("V")
    if len(l) == 0:
        l.append("X")
    return '|'.join(l)

def get_vocab(sp):
    """ get entry for word "sp", create if needed """
    if sp == 'lines':
        debug1 = 1
    ix = lkup(sp,False)
    if ix != 0:
        return ix
    ix = lkup(sp,True)
    # need a def for this word. Does the lower case version exist?
    sp_lc = sp.lower()
    if sp_lc != sp:
        ix_lc = lkup(sp_lc,False)
        if ix_lc != 0:
            # this is our def. Set and transfer props
            set_def(ix,ix_lc)
            set_prop(ix,get_props(ix_lc))
            set_vp(ix,get_vprops(ix_lc))
            synclass[ix] = synclass[ix_lc]
            return ix
    # is this word a variant of a known word?
    wv = WordVariant()
    if is_word_variant(sp_lc,wv):
        set_def(ix,wv.root_key)
        set_prop(ix,wv.props)
        set_vp(ix,wv.vprops)
        synclass[ix] = sc_dct.lkup(get_sc_desc(ix),False)
        assert synclass[ix] != 0
        return ix
    # define to self
    set_def(ix,ix)
    synclass[ix] = sc_dct.lkup("X",False)
    return ix

def spell_sc(ix_or_lst):
    """ get spelling for syntax class """
    return sc_dct.spell(ix_or_lst)

def lkup_sc(sc_sp):
    """ get index for sc, given its spelling """
    return sc_dct.lkup(sc_sp,False)

def is_sc_for_verb(i):
    """ is "sc" a synclass for a verb? """
    return sc_dct.check_prop(i,WP_verb)

def check_sc_prop(sc_ix, m):
    """ check props (WP_xxx) for sc's """
    return sc_dct.check_prop(sc_ix,m)

def sc_tostr(i):
    """ return spelling+props for sc """
    sc_props = sc_dct.props[i]
    return "%s(%s)" % (sc_dct.spell(i),WPtoStr(sc_props))

def is_sc_singleton(i):
    """ is sc a singleton? """
    return sc_dct.spell(i) in sc_singletons

def test_rewrite(rix,toks,i):
    """
    does rewrite rule "rix" apply to tok sequence "toks"
    starting at element "i"?
    """
    n_lhs = len(rwrules.lhs[rix])
    if i + n_lhs > len(toks):
        return False
    for j in range(0,n_lhs):
        if rwrules.lhs[rix][j] != get_def(toks[i+j]):
            return False
    return True

def find_rewrite(toks,i):
    """ find rewrite rule that applies to toks[i] """
    rules = rwrules.index[get_def(toks[i])]
    if rules != None:
        for rix in rules:
            if test_rewrite(rix,toks,i):
                return rix
    return None

def get_rhs_rewrite(rix,want_upper):
    """ get rhs tokens for rewrite rule """
    rhs = rwrules.rhs[rix][:]
    if want_upper:
        # want upper-case start for rhs[0]
        spx = spell(rhs[0])
        c0 = spx[0].upper()
        spx = c0 + spx[1:]
        rhs[0] = get_vocab(spx)
    return rhs

def print_rewrite_rule(i):
    """ print a rewrite rules """
    print 'rule%d. %s : %s' % \
        (i,spell(rwrules.lhs[i]),spell(rwrules.rhs[i]))

def print_rewrite_rules():
    """ print the rewrite rules """
    print "lexicon rewrite rules:"
    for i in range(0,len(rwrules.lhs)):
        print_rewrite_rule(i)
    print "index:"
    for i in range(0,len(rwrules.index)):
        if rwrules.index[i] is not None:
            myrules = ','.join([str(e) for e in rwrules.index[i]])
            print '%d. %s -> {%s}' % \
                (i,spell(i),myrules) 


def print_prep_verb_fitness(self):
    """ print (prep,verb)->fitness mapping. """
    print "Preps-for-verbs:"
    tmp = []
    for key,cnt in self.prep_verb_fitness.pair_to_v.iteritems():
        _pix,_vix = key.split(" ")
        sp_prep = spell(int(pix))
        sp_verb = spell(int(vix))
        tmp.append('%s,%s : %d', sp_prep,sp_verb,cnt)
    tmp.sort()
    for e in tmp:
        print e

def print_entries(max_entries):
    """ print first "maxEntries" entries """
    print "N: ",get_n()
    if max_entries > get_n():
        max_entries = get_n()
    for i in range(0,max_entries):
        print str(i) , "." , spell(i) , " ",
        print "def: " , get_def(i) , " ",
        print "props: " , WPtoStr(get_props(i))
    print_rewrite_rules()
    print_prep_verb_fitness()

def print_wrd_info(sp):
    """ print info about a word """
    i = get_vocab(sp)
    print "ix:" , str(i) ,
    print "def:" , get_def(i) ,
    print "spDef:" , spell(get_def(i)) ,
    print "props:" , WPtoStr(get_props(i))
    sc_ix = synclass[i]
    print "sc:" , sc_dct.spell(sc_ix),
    sc_props = sc_dct.props[sc_ix]
    print "scProps:", WPtoStr(sc_props)
    if rwrules.index[i] is not None:
        print "rewrite rules:"
        for rix in rwrules.index[i]:
            print_rewrite_rule(rix)
    for key,cnt in prep_verb_fitness.pair_to_v.iteritems():        
        _pix,_vix = key.split(" ")
        pix = int(_pix)
        vix = int(_vix)
        sp_prep = spell(pix)
        sp_verb = spell(vix)
        if i == pix or i == vix:
            print '%s,%s : %d' % \
                (sp_prep,sp_verb,cnt)
    print ""

def print_synclasses():
    """ print syn-classes, plus first 12 entries assigned to that class """
    cases = []
    for i in range(0,sc_dct.get_n()):
        cases.append([])
    for i in range(get_n()):
        sc = synclass[i]
        my_cases = cases[sc]
        if len(my_cases) < 12:
            my_cases.append(spell(i))
    for i in range(sc_dct.get_n()):
        print str(i), get_sc_spelling(i)
        my_cases = cases[i]
        if len(my_cases) < 6:
            print ' '.join(my_cases)
        else:
            print ' '.join(my_cases[0:6])
            print ' '.join(my_cases[6:])

def unit_test():
    """
    loop on user input, printing info about words.
    """
    while True:
        wrd = raw_input("Enter word: ")
        if wrd == 'q' or wrd == "quit":
            return
        print_wrd_info(wrd)
        print ''

