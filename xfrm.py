# Copyright 2012 Al Cramer
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
import serializer

# true-> write trace info to stdout
traceparse = False

class Xfrm():
    """
    Parsing is implemented as a series of transforms of the
    parse graph. Each transform is implented as a class, whose
    "doXfrm" method roes the work. Some transforms are purely
    programmatic, while others ure data tables: these implement
    "serialize".
    """
    def __init__(self,_name):
        self.name = _name

    def do_xfrm(self):
        pass

    def serialize(self,mode):
        pass

    def printme(self,fp):
        fp.write('Xfrm %s\n' % self.name)
