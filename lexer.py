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

import re
from defs import *
from nd import Nd
import vcb

import os
import serializer


"""
Lexer for the package. We break the source up into "blocks"
(convenient chunks for parsing), then turn sequences of words and
punctuation into sequences of tokens (indices into our vocubulary
dictionary)
"""
# the source we're going to lex
src = None
# mapping, source index-> line number
lno_map = None
# mapping, source index-> column number
col_map = None
# lexing functions

def is_wrd_char(i,E,src):
    """
    is src[i] a word char? Letters a word chars, as are digits and a
    few other chars.
    """
    if i>E:
        return False
    c = src[i]
    if c.isalnum() or c=="_" or c=='\'':
        return True
    if c == '-':
        # is this a hyphen?
        return (i>0) and src[i-1].isalnum() and \
            (i+1 <= E) and src[i+1].isalnum()
    return False

def is_dot_letter_seq(i,E,src):
    """
    helper for "lexWrd": is src[i] a period followed by a single
    letter/digit?
    """
    if i+2<=E and src[i] == '.' and src[i+1].isalnum():
        return i+2 >= E or not src[i+2].isalnum()
    return False

def lex_wrd(i,E,src):
    """ lex a word, starting at src[i]: return index of last char """
    # lex numbers: "1,200.00". Here we accept periods and commas.
    S = i
    if src[i].isdigit():
        while i+1<E:
            if src[i+1].isdigit():
                i += 1
                continue
            if src[i+1] == '.' or src[i+1] == ',':
                if src[i].isdigit() and \
                    i+2<=E and src[i+2].isdigit():
                    i += 2
                    continue
            break
        while is_wrd_char(i+1,E,src):
            i += 1
        return i
    # abbreviations like "B.C.", "U.S.A"
    if is_dot_letter_seq(i+1,E,src):
        while is_dot_letter_seq(i+1,E,src):
            i += 2
        # include trailing "." if present
        if i+1 <= E and src[i+1] == '.':
            i += 1
        return i
    # default cases: just consume all word chars
    while is_wrd_char(i+1,E,src):
        i += 1
    # is this "Mr."? May need to bind a trailing period.
    if i+1<=E and src[i+1]=='.':
        sp = src[S:i+1]
        tok = vcb.lkup(sp.lower(),False)
        if vcb.check_prop(tok,WP_abbrev):
            i += 1
    return i

def append_contract(S,sp,toks,tok_loc):
    """ append token(s) for word "sp", expanding contractions as needed """
    # is there a rewrite rule for this word?
    key = vcb.lkup(sp.lower(),False)
    if key != 0 :
        test = [key]
        rule = vcb.find_rewrite(test,0)
        if rule != None:
            rhs = vcb.get_rhs_rewrite(rule,sp[0].isupper())
            for e in rhs:
                toks.append(e)
                tok_loc.append(S)
        return
    # split on ticks
    terms = sp.split("'")
    if len(terms) == 2:
        # some canonical cases: exceptions are handled by rewrite
        # rules
        t0 = terms[0]
        t1 = terms[1]
        t0lc = t0.lower()
        t1lc = t1.lower()
        l0 = len(t0)
        if l0 > 2 and t0lc.endswith('n') and t1lc == 't' :
            # "wouldn't"
            toks.append(vcb.get_vocab(t0[0:l0-1]))
            toks.append(vcb.get_vocab("not"))
            tok_loc.extend((S,S))
            return
        if l0 >= 1 and t1lc == 're' :
            # "we're"
            toks.append(vcb.get_vocab(t0))
            toks.append(vcb.get_vocab("are"))
            tok_loc.extend((S,S))
            return
        if l0 >= 1 and t1lc == 'll' :
            # "we'll"
            toks.append(vcb.get_vocab(t0))
            toks.append(vcb.get_vocab("will"))
            tok_loc.extend((S,S))
            return
        if l0 >= 1 and t1lc == 've' :
            # "we've"
            toks.append(vcb.get_vocab(t0))
            toks.append(vcb.get_vocab("have"))
            tok_loc.extend((S,S))
            return
        # "'s" and "'d" are context dependant and are resolved during
        # the parse
        if t1lc == 's' or t1lc == 'd' :
            toks.append(vcb.get_vocab(t0))
            toks.append(vcb.get_vocab("'" + t1))
            tok_loc.extend((S,S))
            return
    # default is to accept construct as a single word
    toks.append(vcb.get_vocab(sp))
    tok_loc.append(S)

def apply_rewrite_rules(toks,tok_loc):
    """ rewrite token sequence, applying rewrite rules """
    _toks = toks
    _tok_loc = tok_loc
    toks = []
    tok_loc = []
    i = 0
    while i<len(_toks):
        rix = vcb.find_rewrite(_toks,i)
        if rix != None:
            # For token-location, we have to approximate. All terms in
            # the rewrite are assigned location of first term of lhs,
            # except for last term in the rewrite; that gets location
            # of last term in lhs.
            n_lhs = len(vcb.rwrules.lhs[rix])
            SfirstTerm = _tok_loc[i]
            SlastTerm = _tok_loc[i+n_lhs-1]
            want_upper = vcb.spell(_toks[i]).isupper()
            terms = vcb.get_rhs_rewrite(rix,want_upper)
            for j in range(0,len(terms)):
                S = SlastTerm if j == len(terms) -1 else SfirstTerm
                toks.append(terms[j])
                tok_loc.append(S)
            i += n_lhs
        else:
            toks.append(_toks[i])
            tok_loc.append(_tok_loc[i])
            i += 1
    return (toks,tok_loc)

def canbe_proper_name(i,toks):
    if i>=len(toks):
        return False
    sp = vcb.spell(toks[i])
    if len(sp)>1 and sp[0].isupper() and sp[1].islower():
        # Camel case. Are we at the start of a sentence?
        at_start = False
        if i == 0:
            at_start = True
        else:
            sp_prv = vcb.spell(toks[i-1])
            if not sp_prv.isalpha():
                at_start = True
        if at_start:
            # If this word is known to our vocabulary, we in
            # general reject it; exception is for words marked as names.
            props = vcb.get_props(toks[i])
            if (props & WP_n) != 0:
                return True
            return props == 0            
        # Capitalized word, preceded by non-cap: accept
        return True
    return False

def canbe_mi(i,toks):
    if i+1>=len(toks):
        return False
    sp = vcb.spell(toks[i])
    spnxt = vcb.spell(toks[i+1])
    return len(sp)==1 and sp[0].isupper() and spnxt=='.'

def rewrite_proper_names(toks,tok_loc):
    """ rewrite token sequence, so "John F.Kennedy" becomes a single token """
    _toks = toks
    _tok_loc = tok_loc
    toks = []
    tok_loc = []
    i = 0
    while i<len(_toks):
        if canbe_proper_name(i,_toks):
            S = i
            E = i
            sp_seq = [vcb.spell(_toks[S])]
            while True:
                if canbe_proper_name(E+1,_toks):
                    sp_seq.append(vcb.spell(_toks[E+1]))
                    E += 1
                    continue
                if canbe_mi(E+1,_toks):
                    sp_seq.append(vcb.spell(_toks[E+1])+'.')
                    E += 2
                    continue
                break
            if E > S:
                sp_all = ' '.join(sp_seq)
                toks.append(vcb.get_vocab(sp_all))
                tok_loc.append(_tok_loc[i])
                i = E + 1
                continue
        toks.append(_toks[i])
        tok_loc.append(_tok_loc[i])
        i += 1
    return (toks,tok_loc)

def lex():
    """
    tokenize source text. Returns
    (toks,tokLoc). "toks" is a list of tokens (indices into the
    vocabulary's dictionary. "tokLoc[i]" gives the index in the source
    text for the first character of the i_th token.
    """
    # "E": max value, index into src
    E = len(src)-1
    if src is None:
        return ([],[])
    toks = []
    tok_loc = []
    _get_vocab = vcb.get_vocab
    i = 0
    while i <= E:
        # Consume white space.
        c = src[i]
        if (c==' ') or (c=='\t') or \
            (c=='\r') or (c=='\n'):
            i += 1
            continue
        # start index for this token
        S = i
        if src[i] == '-':
            # multiple dashes lex as a single token
            while i <= E and src[i] == '-':
                i += 1
            toks.append(_get_vocab(src[S:i]))
            tok_loc.append(S)
            continue
        if src[i] == '$' and is_wrd_char(i+1,E,src):
            # $ binds to the word that follows: advance i and fall
            # thru to code below.
            i += 1
        if is_wrd_char(i,E,src):
            # a word
            ixE = lex_wrd(i,E,src)
            sp = src[S:ixE+1]
            if sp.count("'") == 0:
                toks.append(vcb.get_vocab(sp))
                tok_loc.append(i)
            else:
                append_contract(i,sp,toks,tok_loc)
            i = ixE + 1
            continue
        # everything else lexes as a single token.
        toks.append(_get_vocab(src[i]))
        tok_loc.append(S)
        i += 1
    # rewrite as per the rules defined in "vcb.txt"
    toks,tok_loc = apply_rewrite_rules(toks,tok_loc)
    # collapse "John F. Kennedy" into a single token
    return rewrite_proper_names(toks,tok_loc)

def is_opener(tok):
    """ does 'tok' open a nested block? """
    sp = vcb.spell(tok)
    return sp=='(' or sp=='{' or sp=='[' or sp=='\'' or sp=='"'

def find_closer(toks,i):
    """ find closer for nested block """
    sp_opener = vcb.spell(toks[i])
    # this initialization corrct for single and double quotes
    closer = toks[i]
    if sp_opener == '{':
        closer = vcb.lkup('}',True)
    elif sp_opener == '[':
        closer = vcb.lkup(']',True)
    elif sp_opener == '(':
        closer = vcb.lkup(')',True)
    i += 1
    while i<len(toks):
        if toks[i]==closer:
            return i
        if is_opener(toks[i]):
            E = find_closer(toks,i)
            if E == -1:
                i += 1
            else:
                i = E + 1
            continue
        i += 1
    return -1

class ParseBlk(Nd):
    """ Parse block """
    def __init__(self,toks,tok_loc):
        Nd.__init__(self,-1,-1)
        self.toks = toks
        self.tok_loc = tok_loc
        # parenthesized text and quotes are represented as containers
        # "bracket" is the bracket character -- quote, left paren, etc.
        self.sublst = None
        self.bracket = ''

def print_blk_toks(lst,indent=0):
    mar = ''
    for i in range(0,indent):
        mar += '  '
    for b in lst:
        if b.sublst is not None:
            print '%sNested blk. bracket: %s' % (mar,b.bracket)
            print_blklst(b.sublst,indent+1)
        else:
            print '%sParseBlk. toks:' % mar
            for i in range(0,len(b.toks)):
               S = b.tok_loc[i]
               print '%slno: %d col:%d' % (mar,lno_map[S],col_map[S])
               print '%s%s\n' % (mar,vcb.spell(b.toks[i]))
               
def print_blklst(lst,indent=0):
    mar = ''
    for i in range(0,indent):
        mar += '  '
    for b in lst:
        if b.sublst is not None:
            print '%sParseBlk. bracket: %s' % (mar,b.bracket)
            print_blklst(b.sublst,indent+1)
        else:
            print '%sParseBlk:' % mar
            print '%s%s' % (mar,vcb.spell(b.toks))
    
def _get_parse_blks(toks,tok_loc):
    """
    Recursively break a token sequence into a sequence of blocks for
    parsing.
    """
    lst = []
    i = 0
    while i < len(toks):
        if is_opener(toks[i]):
            E = find_closer(toks,i)
            if E == -1:
                # malformed: skip this character and continue
                i += 1
                continue
            # A quote or parenthesized text.Get content
            content = _get_parse_blks(toks[i+1:E], tok_loc[i+1:E])
            if len(content) > 0:
                blk = ParseBlk(None,None)
                blk.setSp(i+1,E-1)
                blk.bracket = vcb.spell(toks[i])        
                blk.sublst = content
                lst.append(blk)
        else:
            E = i
            while E+1 < len(toks) :
                if is_opener(toks[E+1]):
                    break;
                E += 1
            blk = ParseBlk(toks[i:E+1], tok_loc[i:E+1])
            blk.setSp(i,E)
            lst.append(blk)
        i = E + 1
    return lst

def get_parse_blks(source_text,lno):
    """
    Break source into a sequence of blocks for parsing. "sourceText"
    is a chunk taken from some larger text. "lno" gives the line
    number at which this chunk starts.
    """
    global lno_map, col_map, src
    # create copy of source and get the line and column mappings.
    src = source_text[:]
    lno_map = []
    col_map = []
    col = 1
    for c in src:
        lno_map.append(lno)
        col_map.append(col)
        col += 1
        if c == '\n':
            lno += 1
            col = 1
    # Some texts use single ticks as quote marks, creating confusion
    # between quote marks and contraction ticks. So we change
    # single-tick quote marks to double-tick marks. First create a version
    # of the source in which contraction ticks are encoded to '~'.
    src = src[:]
    src = re.compile(r"(\w+)'(\w+)").sub(r'\1~\2',src)
    src = re.compile(r"''(\w+)").sub(r"'~\1",src)
    src = re.compile(r"(\w+)''").sub(r"\1~'",src)
    # some irregular forms
    src = src.replace("'em","~em")
    src = src.replace("'tis","~tis")
    src = src.replace("'twas","~twas")
    src = src.replace("'twill","~twill")
    # any remaining single ticks are treated as quotes: convert
    # to standard double-quote mark convention
    src = src.replace("'","\"")
    # change '~' back to single tick
    src = src.replace("~","'")
    # lex the source
    toks,tok_loc = lex()
    # create the parse blocks
    return _get_parse_blks(toks,tok_loc)        

# Unit testing 
def _ut_lex_parse_blks(txt):
    blks = get_parse_blks(txt,1)
    print_blklst(blks,0)
    
# unit test: tokenize some text and print result
if __name__== '__main__':
    dn = os.path.dirname(os.path.realpath(__file__))
    # This test requires "map.dat", which contains the
    # serialized vocabulary.
    fn = os.path.join(dn,"msp.dat")
    serializer.init(fn,'r')
    version = serializer.decode_str()
    vcb.serialize("r")
    serializer.fini()
##    # start dev code
##    vcb.print_wrd_info('strongest')
##    # end dev code

    txt = \
"""
"Good day (Fuck You!!!)", we said (not really meaning it).
"""
    txt = txt.strip()
    _ut_lex_parse_blks(txt)

