"""
This module implements regular-expression matching for the parser. The
match method accepts a sequence of terms ("src") and a string
representation of a regexpr ("re"). Each re term matches to zero or
more src terms. If the match is successful, the method returns true
and write the match results to "matchResult".

Qualifiers:
re terms accept the qualifiers "?" , "+", and "*".

"?" means the term is optional. If including this term in the matched
sequence yields a complete match, we include it; if excluding the term
yields a complete match, we exclude it.

"*" means "zero or more", "+" means "one or more". The match is
semi-greedy. In general an re term consumes as many source terms as it
can; but if consuming less allows us to complete the match, then it
yields the minimal number of required terms to its successors.

Variants:
An re term containing bars ("a|b|c") specifies three match variants
("a","b", or "c"). We always accept the first term in the variants
list that yields a match.Note that if a qualifier appears at the end
of a variants list, it applies to the list as a whole. It's illegal to
qualify a term inside a variants list: you can't say "A|B?|C".

Nested re's:
Surrounding one or more terms with square brackets specifies a nested
re. You can also declare an re ("%myName") using "declRe" and then
refer to it in another re.

class ReMatch is abstract: you must implement the "matchTerm" method.
"""
from defs import *
import vcb
import lexer
import re
# qualifiers for re terms
_is_option = 0x1
_zero_or_more = 0x2
_one_or_more = 0x4

class ReMatch:
    def __init__(self):
        self.match_result = None
        self.redct = {}

    def match_term(self,state,re_term):
        """
        Match terms in src, against the reTerm. Returns None if
        no-match; otherwise it returns a list of the src terms
        consumed in the match. This method is a stub: derived classes
        should override.
        """
        return None

    def update_state(self,state,consumed):
        """
        Update state: "consumed" contains the source terms just
        consumed in matching a term. Returns the updated state. In the
        default version, "src" is a list of nodes, and "state" is just
        an index into the list.
        """
        return state + len(consumed)

    def match(self,_src,_re,initial_state=0):
        """
        match a list of terms in "src" against a regular expression.
        Returns True if the match is complete, and writes the match
        terms to "matchResult". There's one element in matchResult for
        each element in the re. Each element is a list, and contains
        the term(s) that matched the re term.
        """
        self.src = _src
        self.match_result = []
        reLst = self.redct.get(_re)
        if reLst is None:
            # compile the re and install in the dictionary
            reLst = self.compile_re(_re)
            self.redct[_re] = reLst
        return self.match_lst(\
            initial_state,\
            reLst,self.match_result)

    def find_closer(self,src,i):
        """ helper for compile_re_term: finding closing bracket """
        closer = ']'
        i += 1
        if i >= len(src):
            return -1
        while i < len(src):
            if src[i]==closer:
                return i
            if src[i] == '[':
                E = self.find_closer(src,i)
                if E == -1:
                    i += 1
                else:
                    i = E + 1
                continue
            i += 1
        return -1

    def compile_re_term(self,variants,src,i):
        """
        Helper for "compileRe": compile a term and add to variants
        list
        """
        lsrc = len(src)
        c0 = src[i]
        if c0 == '[':
            # nested re
            E = self.find_closer(src,i)
            assert E != -1
            reName = '%' + src[i:E+1]
            self.decl_re(reName,src[i+1:E])
            variants.append(reName)
            return E+1
        # id's can start with "%" (that's the name of a nested re). We
        # also allow elements in {,:!_}
        if c0=='%' or c0=='_' or c0.isalnum() or c0 == '!' or c0 == ':':
            # grab id chars
            E = i
            while (E+1)<lsrc and \
                (src[E+1].isalnum() or \
                src[E+1] == '_' or \
                src[E+1] == ':' or \
                src[E+1] == ',' or \
                src[E+1] == '!'):
                E += 1
            variants.append(src[i:E+1])
            return E+1
        if c0 == '.':
            # match any
            variants.append('.')
            return i+1
        # error
        assert False,"Malformed reg.expr"

    def compile_re(self,src):
        """ compile re from source """
        # "reLst" is a list of match-terms. Each term is a pair:
        # [props,variants]. props gives the qualifiers (if any) and
        # variants is a list of variants for the term.
        reLst = []
        # canonicalize space
        src = src.strip()
        reBar = re.compile(r'\s*\|\s*')
        src = reBar.sub('|',src)
        lsrc = len(src)
        i = 0
        while i<lsrc:
            while src[i] == ' ':
                i += 1
                continue
            variants = []
            term = [0,variants]
            reLst.append(term)
            # collect alternatives for this term
            while i<lsrc:
                i = self.compile_re_term(variants,src,i)
                if i>=lsrc:
                    break
                c = src[i]
                i += 1
                if c == '|':
                    # get additional alternatives
                    continue
                # if c is a qualifier, it ends the term
                if c == '*':
                    term[0] = _zero_or_more
                elif c == '+':
                    term[0] = _one_or_more
                elif c == '?':
                    term[0] = _is_option
                # this term is complete: advance to next
                break
        return reLst

    def decl_re(self,reName,_re):
        """
        declare an re: it can then appears as a term in a larger re.
        Our convention requires that name start with "%".
        """
        assert reName.startswith("%")
        self.redct[reName] = self.compile_re(_re)

    def match_lst(self,state,reLst,mat_lst):
        """
        Match terms in src against terms in "reLst". Returns True if
        the match is complete, and writes the match terms to "matLst".
        There's one element in matLst, for each element in the re.
        """
        ix_re = len(mat_lst)
        if ix_re == len(reLst):
            # the match is complete
            return True
        # Loop thru match terms until we hit a qualified term (or are
        # match complete)
        while True:
            (props,variants) = reLst[ix_re]
            if props != 0:
                break
            terms = self.match_variants(state,variants)
            if terms is None:
                # match failed
                return False
            mat_lst.append(terms)
            state = self.update_state(state,terms)
            ix_re += 1
            if ix_re == len(reLst):
                # the match is complete
                return True
        # The match term is qualified, so there are multiple ways
        # source terms can be matched to it. Each way is called a
        # "mode". Find all possible modes.
        modes = []
        terms_consumed = []
        if props & (_zero_or_more|_is_option):
            modes.append([])
        statex = state
        while True:
            terms = self.match_variants(statex,variants)
            if terms is None:
                break
            terms_consumed.extend(terms)
            modes.append(terms_consumed[:])
            statex = self.update_state(statex,terms)
            if props & _is_option:
                break
        if len(modes) == 0:
            # There's no way to match this term: match has failed
            return False
        # Find the longest mode that completes the match.
        n_mat_lst = len(mat_lst)
        i = len(modes)-1
        while i >= 0:
            # purge matLst of terms added in previous iterations
            mat_lst[:] = mat_lst[:n_mat_lst]
            # accept the match associated with this mode, then try to
            # complete the match.
            mat_lst.append(modes[i])
            newstate = self.update_state(state,modes[i])
            if self.match_lst(newstate,reLst,mat_lst):
                return True
            i -= 1
        # match failed
        return False

    def match_variant(self,state,v):
        """ Match a variant """
        if v.startswith('%'):
            # a nested re
            terms = []
            if not self.match_lst(state,self.redct[v],terms):
                return None
        else:
            terms = self.match_term(state,v)
            if terms is None:
                return None
        leaves = []
        self.get_leaves(leaves,terms)
        return leaves

    def match_variants(self,state,variants):
        """
        Match terms in src, starting at term specified by "state",
        against the variants. Returns a list of the terms consumed in
        the match: None means no-match. The method searches the
        variants list in left-to-right order, and accepts the first
        successful variant encountered.
        """
        for v in variants:
            terms = self.match_variant(state,v)
            if terms is not None:
                return terms
        return None

    def get_leaves(self,leaves,tree):
        """ linearize a tree (or list of trees) """
        if isinstance(tree,list):
            for e in tree:
                self.get_leaves(leaves,e)
        else:
            leaves.append(tree)
    # test/dev
    def dump_match(self):
        for i in range(len(self.match_result)):
            tmp = [str(e.h) for e in self.match_result[i]]
            print '%d. %s' % (i, ','.join(tmp))

class PnRE(ReMatch):
    """
    Regular expression machinary for parser: match list of Pn
    (parse nodes) against a regular expression.
    """
    def __init__(self):
        ReMatch.__init__(self)
        self.verb = None
        self.src = None
        self.decl_re("%qualObjTerm","X Prep X")
        self.decl_re("%immedObjTerm","[%qualObjTerm|X]")

    def mr(self,i):
        """
        Convenience function: get first node in match term "i"
        """
        return self.match_result[i][0]

    def get_grammatical_sub(self,e):
        """
        helper for matchTerm: get first term in the (grammatical)
        subject for v
        """
        if e.is_verb():
            if len(e.rel[SR_topic]) > 0:
                return e.rel[SR_topic][0]
            if len(e.rel[SR_agent]) > 0:
                return e.rel[SR_agent][0]
            if len(e.rel[SR_exper]) > 0:
                return e.rel[SR_exper][0]
        return None

    def match_term(self,state,re_term):
        # "state" is an index into "self.src" (a list of Pn's)
        if state >= len(self.src):
            return None
        term = self.src[state]
        if re_term == ".":
            # match any
            return [term]
        if re_term.startswith("_"):
            # a literal
            if re_term[1:] == vcb.spell(term.wrds[0]):
                return [term]
            return None
        if re_term == "Prep":
            # any kind of prep
            if vcb.check_sc_prop(term.sc,WP_prep):
                return [term]
            return None
        if re_term == "Mod":
            # any kind of Mod
            if vcb.check_sc_prop(term.sc,WP_mod):
                return [term]
            return None
        if re_term == "VAdj":
            # verb-adjunct
            # MUSTDO: change to test on sc
            if term.check_vp(VP_adj):
                return [term]
            return None
        if re_term == "X":
            # a noun or modifier
            if vcb.spell_sc(term.sc) == 'X':
                return [term]
            return None

        # specific verbs for verb-phrases
        if re_term == "Be":
            return [term] if term.test_vroot('be') else None
        if re_term == "Have":
            return [term] if term.test_vroot('have') else None
        if re_term == "Do":
            return [term] if term.test_vroot('do') else None
        if re_term == "Get":
            return [term] if term.test_vroot('get') else None

        # "TickS" is "'s": can be an abbrev for "is" (or marker
        # for possession).
        if re_term == "TickS":
            return [term] if vcb.spell_sc(term.sc) == "'s" else None

        # any old verb
        if re_term == "V":
	    # a verb
            if term.is_verb():
                return [term]
            return None

        # small verb constructs

        if re_term == "SubVerb":
            # a verb with a (grammatical) subject
            sub = self.get_grammatical_sub(term)
            if sub is not None:
                if sub.E < term.vS:
                    return [term]
            return None
        if re_term == "VerbNoSub":
            # a verb with no subject
            if term.is_verb() and \
                self.match_term(state,"SubVerb") is None:
                return [term]
            return None
        if re_term == "VerbSub":
            # verb-subject-optional object:
            # appears in aquery contexts
            sub = self.get_grammatical_sub(term)
            if sub is not None:
                if sub.S > term.vE:
                    return [term]
            return None

        # attrbutions
        if re_term == "QuoteBlk":
            if term.sc == vcb.lkup_sc("QuoteBlk"):
                return [term]
            return None      
        if re_term == "Comma":
            if term.sc == vcb.lkup_sc("Comma"):
                return [term]
            return None
        if re_term == "Terminator":
            if term.sc == vcb.lkup_sc("Punct"):
                text = vcb.spell(term.wrds)
                if text == '.' or \
                    text == '?' or \
                    text == '!' or \
                    text == ':' or \
                    text == ';':
                    return [term]
            return None
        if re_term == "AgentSaid":        
            if term.is_verb():
                if vcb.check_prop(term.verbs[0],WP_attribution):
                    return [term]
            return None


        # next line is dev code
        assert False, 'debug1: %s' % re_term
        return None

pnRE = PnRE()

# unit testing this subclass implements "matchTerm"
class _ut_match(ReMatch):
    def __init__(self):
        ReMatch.__init__(self)

    def match_term(self,state,re_term):
        if state < len(self.src) and self.src[state] == re_term:
            return [self.src[state]]
        return None

if __name__ == '__main__':
    # Unit test
    utm = _ut_match()
    assert utm.match(['a','b'],"a b")
    assert utm.match_result == [['a'],['b']]

    assert not utm.match(['a','c'],"a b")

    assert utm.match(['a','b'],"c? a b")
    assert utm.match_result == [[],['a'],['b']]

    assert utm.match(['a','b'],"a? a b")
    assert utm.match_result == [[],['a'],['b']]

    assert utm.match(['a','b'],"a c* b")
    assert utm.match_result == [['a'],[],['b']]

    assert utm.match(['a','b', 'b'],"a b*")
    assert utm.match_result == [['a'],['b','b']]

    assert utm.match(['a','b'],"a|b c* b")
    assert utm.match_result == [['a'],[],['b']]

    assert utm.match(['c'],"c* c")
    assert utm.match_result == [[],['c']]

    assert utm.match(['b','c'],"a|b c* c|b")
    assert utm.match_result == [['b'],[],['c']]

    assert not utm.match(['b','c'],"a+ c")

    assert utm.match(['b','c'],"b+ c")
    assert utm.match_result == [['b'],['c']]

    assert utm.match(['b','b','c'],"b+ c")
    assert utm.match_result == [['b','b'],['c']]

    utm.decl_re("%bc","b+ c")
    assert utm.match(['b','b','c'],"%bc")
    assert utm.match_result == [['b','b'],['c']]

    utm.decl_re("%ab","a b")
    utm.decl_re("%abc","a b c")
    assert utm.match(['a','b','c','d'],"%abc|%ab d")
    assert utm.match_result == [['a','b','c'],['d']]
    assert utm.match(['a','b','d'],"%abc|%ab d")
    assert utm.match_result == [['a','b'],['d']]

    assert utm.match(['a','b','c'],"a [b c]")
    assert utm.match_result == [['a'],['b','c']]

    print "pass unit test"

