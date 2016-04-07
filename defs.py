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
This module defineds constants (mostly bitmasks for various kinds of
properties) used throughout the package.
"""

# trace the parse
trace_parse = False

""" Word properties """
# parts-of-speach
WP_conj =      0x1
WP_clprep =    0x2
WP_qualprep =  0x4
WP_prep =      0x8
WP_n =         0x10
WP_noun =      0x20
WP_adj =       0x40
WP_sub =       0x80
WP_x =         0x100
WP_verb =      0x200
WP_adv =       0x400
# "mr","mrs", etc.
WP_abbrev =    0x800
# "can't"
WP_contraction = 0x1000
# who/what/why/when/where/how
WP_query =     0x2000
# strong ("a") and weak ("that") determinants
WP_dets =      0x4000
WP_detw =      0x8000
# punctuation
WP_punct =     0x10000
# clause modifiers
WP_clmod =     0x20000
# "(why) did .."; and "(why) is..."
WP_qhead =     0x80000
WP_beqhead =   0x100000
# A number: "1821"
WP_num =       0x200000
# Attribution verb for quotation: "he said"
WP_attribution =  0x400000

# "Modifier" -- either adjective or adverb
WP_mod = WP_adv|WP_adj


def WPtoStr(m):
    """ Dump word props """
    s = []
    if (m & WP_conj) != 0: s.append("CONJ")
    if (m & WP_clprep) != 0: s.append("CLPREP")
    if (m & WP_qualprep) != 0: s.append("QUALPREP")
    if (m & WP_prep) != 0: s.append("PREP")
    if (m & WP_n) != 0: s.append("N")
    if (m & WP_noun) != 0: s.append("NOUN")
    if (m & WP_adj) != 0: s.append("ADJ")
    if (m & WP_sub) != 0: s.append("SUB")
    if (m & WP_x) != 0: s.append("X")
    if (m & WP_verb) != 0: s.append("VERB")
    if (m & WP_abbrev) != 0: s.append("ABBREV")
    if (m & WP_contraction) != 0: s.append("CONTRACTION")
    if (m & WP_query) != 0: s.append("QUERY")
    if (m & WP_dets) != 0: s.append("DETS")
    if (m & WP_detw) != 0: s.append("DETW")
    if (m & WP_punct) != 0: s.append("PUNCT")
    if (m & WP_clmod) != 0: s.append("CLMOD")
    if (m & WP_qhead) != 0: s.append("QHEAD")
    if (m & WP_beqhead) != 0: s.append("BEQHEAD")
    if (m & WP_adv) != 0: s.append("ADV")
    if (m & WP_num) != 0: s.append("NUM")
    if (m & WP_attribution) != 0: s.append("ATTRIBUTION")
    return ' '.join(s)

""" Verb properties """
VP_neg = 0x1
VP_adj = 0x2
VP_past = 0x4
VP_present = 0x8
VP_future = 0x10
VP_perfect = 0x20
VP_subjunctive = 0x40
VP_inf = 0x80
VP_root = 0x100
VP_gerund = 0x200
VP_passive = 0x400
VP_negcontraction = 0x800
VP_prelude = 0x1000
VP_vpq = 0x2000
VP_avgt = 0x4000
VP_ave = 0x8000
VP_evt = 0x10000
VP_isq = 0x20000
VP_notmodified = 0x40000
VP_nosubject =   0x80000
VP_participle =  0x100000
VP_query =       0x200000
VP_farprep =     0x400000

VP_tensemask = VP_past|VP_present|VP_future|VP_subjunctive
VP_semanticmask = VP_neg|VP_prelude

def VPtoStr(m,delim):
    """ Dump verb props """
    s = []
    if (m & VP_neg) != 0: s.append("not")
    if (m & VP_adj) != 0: s.append("adj")
    if (m & VP_past) != 0: s.append("past")
    if (m & VP_present) != 0: s.append("present")
    if (m & VP_future) != 0: s.append("future")
    if (m & VP_perfect) != 0: s.append("perfect")
    if (m & VP_subjunctive) != 0: s.append("subj")
    if (m & VP_inf) != 0: s.append("inf")
    if (m & VP_root) != 0: s.append("root")
    if (m & VP_gerund) != 0: s.append("ger")
    if (m & VP_passive) != 0: s.append("passive")
    if (m & VP_negcontraction) != 0: s.append("NegContraction")
    if (m & VP_prelude) != 0: s.append("prelude")
    if (m & VP_vpq) != 0: s.append("vpq")
    if (m & VP_avgt) != 0: s.append("avgt")
    if (m & VP_ave) != 0: s.append("ave")
    if (m & VP_evt) != 0: s.append("evt")
    if (m & VP_isq) != 0: s.append("isQ")
    if (m & VP_notmodified) != 0: s.append("notModified")
    if (m & VP_nosubject) != 0: s.append("noSubject")
    if (m & VP_participle) != 0: s.append("participle")
    if (m & VP_query) != 0: s.append("query")
    if (m & VP_farprep) != 0: s.append("farprep")
    return delim.join(s)

""" Syntax-relations """
SR_agent = 0
SR_topic = 1
SR_exper = 2
SR_theme = 3
SR_auxtheme = 4
SR_modifies = 5
SR_isqby = 6
SR_attribution = 7
SR_ladj = 8
SR_vadj = 9
SR_prelude = 10
# This used for a word that is in the scope of a verb, but its
# relation is undefined.
SR_undef = 11
# Total number of relations, word->verb
SR_nwordtoverb = 12
# these are computational (not part of the syntax model proper)
SR_sub = 12
SR_obj = 13
# names for roles
SRids = ["agent","topic","exper","theme","auxTheme",
    "qual","isqby","attribution","ladj","vadj",
    "prelude","undef","sub","obj"]

class ParseErr(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

