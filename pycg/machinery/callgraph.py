#
# Copyright (c) 2020 Vitalis Salis.
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
import logging

logger = logging.getLogger(__name__)


class CallGraph(object):
    def __init__(self):
        self.cg = {}
        self.cg_extended = {}
        self.modnames = {}
        self.ep = None
        self.entrypoints = []

        self.function_line_numbers = dict()

    def add_node(self, name, modname=""):
        if not isinstance(name, str):
            raise CallGraphError("Only string node names allowed")
        if not name:
            raise CallGraphError("Empty node name")
        
        #logger.info(f"AN: {name} -- mod: {modname}")
        if not name in self.cg:
            #logger.info(f"AN1: {name} -- mod: {modname}")
            self.cg[name] = set()
            self.cg_extended[name] = {
                'dsts' : [],
                'meta' : {
                    'modname' : modname
                }
            }
            self.modnames[name] = modname
        #else:
            #logger.info(f"AN1.1: {name} --- {self.cg[name]}")

        if name in self.cg and not self.modnames[name]:
            #logger.info(f"AN3: {name} -- mod: {modname}")
            self.modnames[name] = modname
        else:
            #logger.info(f"AN4: {self.modnames[name]}")
            #logger.info(f"AN5: {self.cg_extended[name]}")
            if not self.cg_extended[name]['meta']['modname']:
                #logger.info("AN6")
                self.cg_extended[name]['meta']['modname'] = modname
            #else:
                #logger.info("AN7")

    def add_edge(self, src, dest, lineno=-1, mod="", ext_mod=""):
        self.add_node(src, mod)
        self.add_node(dest)
        self.cg[src].add(dest)

        #logger.debug("Adding edge")
        self.cg_extended[src]['dsts'].append(
            {
                "dst": dest,
                "lineno": lineno,
                "mod" : mod,
                "ext_mod" : ext_mod
            }
        )
        #logger.debug(self.cg_extended[src])

    def get(self):
        return self.cg

    def get_extended(self):
        return self.cg_extended

    def get_edges(self):
        output = []
        for src in self.cg:
            for dst in self.cg[src]:
                output.append([src, dst])
        return output

    def get_modules(self):
        return self.modnames

    def add_entrypoint(self, ep, modname=""):
        self.ep = ep
        self.ep_mod = modname
        self.entrypoints.append((ep, modname))
        #if not "entrypoints" in self.cg_extended:
        #    self.cg_extended['entrypoints'] = []
        #self.cg_extended['entrypoints'].append((ep, modname))


class CallGraphError(Exception):
    pass
