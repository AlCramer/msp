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

class Nd:
    """ Generic node """
    def __init__(self,S = -1,E = -1):
        # span attributes
        self.S = S
        self.E = E
        # list structure
        self.prv = self.nxt = None
        self.sublst = None

    def setSp(self,S,E):
        self.S = S
        self.E = E

    @classmethod
    def connect(cls,lhs,rhs):
        if lhs != None:
            lhs.nxt = rhs
        if rhs != None:
            rhs.prv = lhs

