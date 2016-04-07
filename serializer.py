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

import array
import os

"""
We use two files of serialized data structures. "vcb.dat" initializes
the vocabulary, and "parser.dat" provides the parse rules. We don't
use language specific serialization methods, because the package is
ported to multiple languages, so it's best to create our own binary
format.
"""
# file name
fn = ''
# mode ('r' or 'w')
mode = ''
# array of bytes, written to/read from file
ary = None
# serialization index
ix_ary = 0

def get_filepath(_fn):
    """
    Get filepath given filename: the code expects the file to reside
    in the same directory as this file.
    """
    dn = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(dn,_fn)

def init(_fn,_mode):
    """ init the serialization: specify file name and mode ('r' or 'w') """
    global fn,mode,ary,ix_ary
    fn = _fn
    mode = _mode
    ary = array.array('B')
    ix_ary = 0
    if mode == 'r':
        fp = open(get_filepath(fn),"rb")
        ary.fromstring(fp.read())
        fp.close()

def fini():
    """ complete the serialization """
    global mode, ary
    if mode == 'w':
        fp = open(get_filepath(fn),"wb")
        fp.write(ary.tostring())
        fp.close()
    ary = None
# int encodings

def encode_int(v,n_bits=32):
    """ encode an int """
    if n_bits==8:
        ary.append(0xff & v)
    elif n_bits == 16:
        ary.append(0xff & (v>>8))
        ary.append(0xff & v)
    else:
        ary.append(0xff & (v>>24))
        ary.append(0xff & (v>>16))
        ary.append(0xff & (v>>8))
        ary.append(0xff & v)

def decode_int(n_bits=32):
    """ decode an int """
    global ary,ix_ary
    if n_bits==8:
        v =  ary[ix_ary]
        ix_ary += 1
    elif n_bits == 16:
        v = (ary[ix_ary] << 8) |\
            ary[ix_ary+1]
        ix_ary += 2
    else:
        v = (ary[ix_ary] << 24) |\
            (ary[ix_ary+1] << 16) |\
            (ary[ix_ary+2] << 8) |\
            ary[ix_ary+3]
        ix_ary += 4
    return v
# string encodings

def encode_str(s):
    """ encode a string """
    global ary
    ary.append(len(s))
    for i in range(0,len(s)):
        ary.append(ord(s[i]))

def decode_str():
    """ decode a string """
    global ary,ix_ary
    slen = ary[ix_ary]
    ix_ary += 1
    s = ary[ix_ary : ix_ary+slen].tostring()
    ix_ary += slen
    return s

def encode_strlst(lst):
    """ encode a list of str's """
    global ary
    encode_int(len(lst))
    for s in lst:
        ary.append(len(s))
        for i in range(0,len(s)):
            ary.append(ord(s[i]))

def decode_strlst():
    """ decode a list of str's """
    global ary,ix_ary
    lst = []
    N = decode_int()
    for j in range(0,N):
        slen = ary[ix_ary]
        ix_ary += 1
        lst.append(ary[ix_ary : ix_ary+slen].tostring())
        ix_ary += slen
    return lst

# List encodings

def encode_intlst(lst,n_bits):
    """ encode a list of int's """
    encode_int(len(lst),16)
    for e in lst:
        encode_int(e,n_bits)

def decode_intlst(n_bits):
    """ decode a lits of int's """
    lst = []
    N = decode_int(16)
    for cnt in range(0,N):
        lst.append(decode_int(n_bits))
    return lst

def encode_lstlst(lst,n_bits):
    """ encode a list of int-list's. """
    if lst == None:
        encode_int(0,16)
        return
    encode_int(len(lst),16)
    for v in lst:
        len_v = 0 if v is None else len(v)
        encode_int(len_v,16)
        if v is not None:
            for e in v:
                encode_int(e,n_bits)

def decode_lstlst(n_bits):
    """
    decode a list of int-list's. An empty int-list is decoded as
    "None" (not as an empty list).
    """
    lstlst = []
    N = decode_int(16)
    if N == 0:
        return None
    for i in range(N):
        len_v = decode_int(16)
        if len_v == 0:
            lstlst.append(None)
            continue
        v = []
        for j in range(len_v):
            v.append(decode_int(n_bits))
        lstlst.append(v)
    return lstlst

def encode_lstset(lst,n_bits):
    """ encode a list of sets. """
    if lst == None:
        encode_int(0,16)
        return
    encode_int(len(lst),16)
    for v in lst:
        len_v = 0 if v is None else len(v)
        encode_int(len_v,16)
        if v is not None:
            for e in v:
                encode_int(e,n_bits)

def decode_lstset(n_bits):
    """
    decode a list of sets. An empty set-list is decoded as
    "None" (not as an empty list).
    """
    lstset = []
    N = decode_int(16)
    if N == 0:
        return None
    for i in range(N):
        len_v = decode_int(16)
        if len_v == 0:
            lstset.append(None)
            continue
        v = set()
        for j in range(len_v):
            v.add(decode_int(n_bits))
        lstset.append(v)
    return lstset

# Mapping, str->16-bit int. This is implemented as a hashtable.
def encode_str_to_int(ht):
    encode_int(len(ht))
    for key,v in ht.iteritems():
        encode_str(key)
        encode_int(v,16)
        
def decode_str_to_int():    
    N = decode_int()
    ht = {}
    for i in range(0,N):
        key = decode_str()
        ht[key] = decode_int(16)
    return ht
    
# Probability tables. These are implemented as dictionaries:
# mapping str->log(probabilty), where "prob" runs from 0..1.0

def encode_log_prob(v):
    if v < 0.0:
        v = -v
    if v > 0xfffe:
        v = 0xfffe
    v *= float(0xffff)
    encode_int(int(v))

def decode_log_prob():
    v = float(decode_int())
    v /= 0xffff
    if v > 0:
        v = -v
    return v

def encode_log_prob_tbl(tbl):
    encode_int(len(tbl))
    for key,v in tbl.iteritems():
        encode_str(key)
        encode_log_prob(v)

def decode_log_prob_tbl():
    tbl = {}
    N = decode_int()
    for i in range(0,N):
        key = decode_str()
        tbl[key] = decode_log_prob()
    return tbl

if __name__== '__main__':
    i = 123
    intlst = [1,2]
    strlst = ['a','ab']
    lstlst = [[1,2],[3]]
    init('x.dat','w')
    encode_int(i)
    encode_intlst(intlst,32)
    encode_strlst(strlst)
    encode_lstlst(lstlst,16)
    fini()
    init('x.dat','r')
    i2 = decode_int()
    intlst2 = decode_intlst(32)
    strlst2 = decode_strlst()
    lstlst2 = decode_lstlst(16)
    fini()
    assert i == i2
    assert intlst == intlst2
    assert strlst == strlst2
    assert lstlst == lstlst2

