# Copyright 2014 Al Cramer
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
from msnode import *
import vcb
from rematch import pnRE
import os
import sys

"""
This module implements attribution ("Blah," he said", 
"Why?", she asked")
"""

# helper for "setAttributions"
def set_attribution(quote,attr):
    # re tree structure: two quotes can share the same attribution.
    # We choose first quote as parent.
    scope = attr.scope
    if scope is not None and \
        scope.get_rel(attr) != SR_attribution:
        attr.unset_scope()
    if scope is None:
        attr.set_scope(quote,SR_attribution)
    else:
         quote.rel[SR_attribution].append(attr)
    # convert "said he" to "he said"
    if len(attr.rel[SR_agent]) == 0 and \
        len(attr.rel[SR_theme]) > 0:
        attr.rel[SR_agent] = attr.rel[SR_theme]
        attr.rel[SR_theme] = []

def set_attributions(nds):
    """
    Attribute quotes
    """
    # Rewrite node list, setting attributions
    _nds = []
    i = 0
    while i < len(nds):
        if pnRE.match(nds,
            "QuoteBlk AgentSaid Comma|Terminator agentSaid QuoteBlk",i):
            q1 = pnRE.mr(0) 
            set_attribution(q1,pnRE.mr(1))
            q2 = nds[i+4]
            set_attribution(q2,pnRE.mr(3))
            _nds.append(q1)
            _nds.append(q2)
            i += 5
            continue
        if pnRE.match(nds,
            "QuoteBlk AgentSaid Comma|Terminator QuoteBlk",i):
            q1 = pnRE.mr(0)
            set_attribution(q1,pnRE.mr(1))
            q2 = pnRE.mr(3)
            set_attribution(q2,pnRE.mr(1))
            _nds.append(q1)
            _nds.append(q2)
            i += 4
            continue
        if pnRE.match(nds,
            "AgentSaid Comma QuoteBlk",i):
            q = pnRE.mr(2)
            set_attribution(q,pnRE.mr(0))
            _nds.append(q)
            i += 3
            continue
        if pnRE.match(nds,
            "QuoteBlk Comma? AgentSaid",i):
            q = pnRE.mr(0)
            set_attribution(q,pnRE.mr(2))
            _nds.append(q)
            i += 3
            continue
        _nds.append(nds[i])
        i += 1
    return _nds


