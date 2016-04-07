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
import nd
import serializer
import sys

class FSM:
    """
    FSM: finite state machine. We use fsm's to recognize sequences
    of int values. Each recognized sequence has some associated value
    (an int). FSM's come in two flavors: left-to-right, and
    right-to-left. Left-to-right machines walk left-to-right thru
    a list of inputs, recognizing sequences. Right-to-left machines walk
    right-to-left thru the inputs list.
    Our main method is "get_sequences(inputs,i)". This returns a list
    of the value associated with each recognized sequences. For a
    left-to-right machine, these are the sequences that start at
    inputs[i]. For a right-to-left machine, these are the sequences
    that end at inputs[i].
    
    """
    def __init__(self, nbits_seq_term,left_to_right):
        self.left_to_right = left_to_right
        # for serialization
        self.nbits_seq_term = nbits_seq_term
        # states. Each state is a set of inputs: on the i_th input,
        # we transit to that state.
        self.states = []
        # mapping, seq->V
        self.seq_to_v = {}

    def set_max_seq_len(self,max_seq_len):
        for i in range(0,max_seq_len):
            self.states.append(set())

    def serialize(self,mode):
        # Note: caller is responsible for serializing "seq_to_v".
        # We just serialize the states. 
        if mode == 'w':
            serializer.encode_lstset(self.states,self.nbits_seq_term)
        else:
            self.states = serializer.decode_lstset(self.nbits_seq_term)
            if self.states is None:
                self.states = []
            
    def add_seq(self,seq):
        """ Add a sequence """
        assert len(seq) <= len(self.states)
        seq_sp = ' '.join([str(e) for e in seq])
        if not self.left_to_right:
            seq = seq[:]
            seq.reverse()
        for i in range(0,len(seq)):
            self.states[i].add(seq[i])
            
    def _get_sequences_ltor(self,inputs,i):
        """
        Walk thru "inputs", finding all sequences that start at
        input[i]. Returns a list of the values assigned to the
        recognized sequences.
        """
        # our result: list of values assigned to recognized sequences
        hits = []
        # spelling for sequences
        seq_sp = ''
        # index into states
        j = 0
        while i< len(inputs) and \
            j< len(self.states) and \
            self.states[j] is not None:
            if not inputs[i] in self.states[j]:
                # cannot enter state "j": done
                break
            if j == 0:
                seq_sp = str(inputs[i])
            else:
                seq_sp = seq_sp + ' ' + str(inputs[i])
            if seq_sp in self.seq_to_v:
                hits.append(self.seq_to_v[seq_sp])
            i += 1
            j += 1
        return hits
    
    def _get_sequences_rtol(self,inputs,i):
        """
        Walk thru "inputs", finding all sequences that end at
        input[i]. Returns a list of the values assigned to the
        recognized sequences.
        """
        # our result: list of values assigned to recognized sequences
        hits = []
        # spelling for sequences
        seq_sp = ''
        # index into states
        j = 0
        while i >= 0 and \
            j< len(self.states) and \
            self.states[j] is not None:
            if not inputs[i] in self.states[j]:
                # cannot enter state "j": done
                break
            if j == 0:
                seq_sp = str(inputs[i])
            else:
                seq_sp = str(inputs[i]) + ' ' + seq_sp
            if seq_sp in self.seq_to_v:
                hits.append(self.seq_to_v[seq_sp])
            i -= 1
            j += 1
        return hits
    
    def get_sequences(self,inputs,i):
        """
        Recognize sequences contained in "inputs", returning
        list of the values associated the recognized sequences.
        If this machine is left-to-right, each recognized sequence
        starts at inputs[i]. If this machine is right-to-left, each
        ends at inputs[i].
        """
        if self.states is None:
            return []
        if self.left_to_right:
            return self._get_sequences_ltor(inputs,i)
        else:
            return self._get_sequences_rtol(inputs,i)
        
        
    def get_matches(self,e,left_to_right):
        """
        "e" is a node in a doubly linked list. Each node has an "sc"
        attribute, drawn from the same enumeration set as our
        sequences. We're interested in node-sequences whose "sc"
        values match the sequences known to the FSM. This method
        finds all such sequences that start at "e". It returns a list
        of [node-sequence,value] pairs. If "leftToRight", we start at
        "e" and procede left-to-right; otherwise we start at e and
        move right-to-left.
        """
        if len(self.states) == 0 or e is None:
            return []
        # our result: a list of [node-sequence,value] pairs
        matches = []
        # sequence of nodes
        ndseq = []
        # spelling for sc-sequence
        seq_sp = ''
        # index into states
        i = 0
        while e is not None and \
            i< len(self.states) and \
            self.states[i] is not None:
            if not e.sc in self.states[i]:
                # cannot enter state "i": done
                break
            ndseq.append(e)
            if i != 0:
                seq_sp += ' '
            seq_sp += str(e.sc)
            if seq_sp in self.seq_to_v:
                v = self.seq_to_v[seq_sp]
                matches.append([ndseq[:],v])
            i += 1
            if left_to_right:
                e = e.nxt
            else:
                e = e.prv
        return matches
        
    def print_match(self,m):
        if len(m) == 0:
            print "no matches"
            return
        print 'N match results: %d' % len(m)
        for i in range(0,len(m)):
            mx = m[i]
            nds = mx[0]
            v = mx[1]
            print 'match %d.\n%s -> %d\n' % \
                (i,str([e.sc for e in nds]),v)

    def printme(self,fp):
        if fp is None:
            fp = sys.stdout
        # states
        for i in range(0,len(self.states)):
            # inputs
            fp.write('state %d.\n' % i)
            s = self.states[i]
            fp.write('inputs: %s\n' % str(s))
        # seq->v
        fp.write('mappings. seq->v:\n')
        lst = []
        for key,v in self.seq_to_v.iteritems():
            # skip the null entry
            if key == '_null_':
                continue
            lst.append('%s -> %d\n' % (key,v))
        lst.sort()
        for e in lst:
            fp.write(e)

    def printstats(self,fp,title=None):
        if fp is None:
            fp = sys.stdout
        if title is not None:
            fp.write('%s\n' % title)
        nstates = len(self.states)
        ninputs = 0
        for s in self.states:
            ninputs += len(s)
        in_per_state = 0.0
        if nstates > 0:
            in_per_state = float(ninputs)/float(nstates)
        fp.write('N states: %d avInputs:%.2f N sequences:%d\n' % \
            (nstates,in_per_state,len(self.seq_to_v)))

def ut_sm():
    def add_seq_v(sm,seq,v):
        seq_sp = ' '.join([str(e) for e in seq])    
        sm.seq_to_v[seq_sp] = v
        sm.add_seq(seq) 
    sm = FSM(8,True)
    sm.set_max_seq_len(3)
    add_seq_v(sm,[0,1],0)
    add_seq_v(sm,[0,1,2],0)
    add_seq_v(sm,[0,2,2],1)
    sm.printme(None)
    # test getMatches
    nd0 = nd.Nd()
    nd1 = nd.Nd()
    nd2 = nd.Nd()
    nd.Nd.connect(nd0,nd1)
    nd.Nd.connect(nd1,nd2)
    nd0.sc = 0
    nd1.sc = 1
    nd2.sc = 2
    print "Match test 1"
    m = sm.get_matches(nd0,True)
    sm.print_match(m)

    # serialize, read back in as sm1, and repeat
    # match test
    serializer.init("ut.dat","w")
    sm.serialize("w")
    serializer.fini()

    sm1 = FSM(8,True)
    serializer.init("ut.dat","r")
    sm1.serialize("r")
    serializer.fini()
    print "Match test 2 (should yield same results)"
    m = sm.get_matches(nd0,True)
    sm1.print_match(m)

if __name__ == '__main__':
    ut_sm()

