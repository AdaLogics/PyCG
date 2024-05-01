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

from pycg import utils
from pycg.machinery.pointers import LiteralPointer, NamePointer

logger = logging.getLogger(__name__)

from typing import Dict, Set, Optional


class DefinitionManager:
    def __init__(self) -> None:
        self.defs: Dict[str, Definition] = {}

    def create(self, ns: str, def_type) -> "Definition":
        if not ns or not isinstance(ns, str):
            raise DefinitionError("Invalid namespace argument")
        if not def_type in Definition.types:
            raise DefinitionError("Invalid def type argument")
        if self.get(ns):
            raise DefinitionError("Definition already exists")

        self.defs[ns] = Definition(ns, def_type)
        return self.defs[ns]

    def assign(self, ns: str, defi: "Definition"):
        self.defs[ns] = Definition(ns, defi.get_type())
        self.defs[ns].merge(defi)

        # if it is a function def, we need to create a return pointer
        if defi.is_function_def():
            return_ns = utils.join_ns(ns, utils.constants.RETURN_NAME)
            self.defs[return_ns] = Definition(return_ns, utils.constants.NAME_DEF)
            self.defs[return_ns].get_name_pointer().add(
                utils.join_ns(defi.get_ns(), utils.constants.RETURN_NAME)
            )

        return self.defs[ns]

    def get(self, ns) -> Optional["Definition"]:
        if ns in self.defs:
            return self.defs[ns]
        else:
            return None

    def get_defs(self) -> Dict[str, "Definition"]:
        return self.defs

    def handle_function_def(self, parent_ns: str, fn_name: str):
        full_ns = utils.join_ns(parent_ns, fn_name)
        defi = self.get(full_ns)
        if not defi:
            defi = self.create(full_ns, utils.constants.FUN_DEF)
            defi.decorator_names = set()

        return_ns = utils.join_ns(full_ns, utils.constants.RETURN_NAME)
        if not self.get(return_ns):
            self.create(return_ns, utils.constants.NAME_DEF)

        return defi

    def handle_class_def(self, parent_ns, cls_name):
        full_ns = utils.join_ns(parent_ns, cls_name)
        defi = self.get(full_ns)
        if not defi:
            defi = self.create(full_ns, utils.constants.CLS_DEF)

        return defi

    def transitive_closure(self) -> Dict[str, Set[str]]:
        closured: Dict[str, Set[str]] = {}

        def dfs(defi: Definition):
            # bottom
            if not closured.get(defi.get_ns(), None) == None:
                return closured[defi.get_ns()]
            name_pointer = defi.get_name_pointer()
            new_set = set()

            if not name_pointer.get():
                new_set.add(defi.get_ns())

            closured[defi.get_ns()] = new_set

            for name in name_pointer.get():
                if not self.defs.get(name, None):
                    continue
                items = dfs(self.defs[name])
                if not items:
                    items = set([name])
                new_set.update(items)

            closured[defi.get_ns()] = new_set
            return closured[defi.get_ns()]

        for ns, current_def in self.defs.items():
            if closured.get(current_def.get_ns(), None) == None:
                dfs(current_def)

        return closured

    def complete_definitions(self):
        # THE MOST expensive part of this tool's process
        # TODO: IMPROVE COMPLEXITY
        def update_pointsto_args(pointsto_args, arg, name: str):
            changed_something = False
            if arg == pointsto_args:
                return False
            for pointsto_arg in pointsto_args:
                if not self.defs.get(pointsto_arg, None):
                    continue
                if pointsto_arg == name:
                    continue
                pointsto_arg_def = self.defs[pointsto_arg].get_name_pointer()
                if pointsto_arg_def == pointsto_args:
                    continue

                # sometimes we may end up with a cycle
                if pointsto_arg in arg:
                    arg.remove(pointsto_arg)

                for item in arg:
                    if not item in pointsto_arg_def.get():
                        if self.defs.get(item, None) != None:
                            changed_something = True
                    # HACK: this check shouldn't be needed
                    # if we remove this the following breaks:
                    # x = lambda x: x + 1
                    # x(1)
                    # since on line 184 we don't discriminate between literal values and name values
                    if not self.defs.get(item, None):
                        continue
                    pointsto_arg_def.add(item)
            return changed_something

        logger.info("Def-Iterating %d defs"%(len(self.defs)))
        if len(self.defs) > 9000:
            logger.info("The definition list is too large. This is likely to take forever. Avoid this step")
            return

        for i in range(len(self.defs)):
            #logger.info("Def-idx-%d"%(i))
            changed_something = False
            for ns, current_def in self.defs.items():
                #logger.info("Def-idx2-%d"%(idx2))
                # the name pointer of the definition we're currently iterating
                current_name_pointer = current_def.get_name_pointer()
                #print("Name point: %s"%(str(current_name_pointer)))
                # iterate the names the current definition points to items
                # for name in current_name_pointer.get():
                for name in current_name_pointer.get().copy():

                    # get the name pointer of the points to name
                    if not self.defs.get(name, None):
                        continue
                    if name == ns:
                        continue

                    pointsto_name_pointer = self.defs[name].get_name_pointer()
                    # iterate the arguments of the definition we're currently iterating
                    for arg_name, arg in current_name_pointer.get_args().items():
                        pos = current_name_pointer.get_pos_of_name(arg_name)
                        if not pos is None:
                            pointsto_args = pointsto_name_pointer.get_pos_arg(pos)
                            if not pointsto_args:
                                pointsto_name_pointer.add_pos_arg(pos, None, arg)
                                continue
                        else:
                            pointsto_args = pointsto_name_pointer.get_arg(arg_name)
                            if not pointsto_args:
                                pointsto_name_pointer.add_arg(arg_name, arg)
                                continue
                        changed_something = changed_something or update_pointsto_args(pointsto_args, arg, current_def.get_ns())
            if not changed_something:
                break


class Definition:
    __slots__ = ["fullns", "name_pointer", "lit_pointer", "def_type", "decorator_names"]
    types = [
        utils.constants.FUN_DEF,
        utils.constants.MOD_DEF,
        utils.constants.NAME_DEF,
        utils.constants.CLS_DEF,
        utils.constants.EXT_DEF,
    ]

    def __init__(self, fullns: str, def_type) -> None:
        self.fullns = fullns
        self.name_pointer = NamePointer()
        self.lit_pointer = LiteralPointer()
        self.def_type = def_type

    def get_type(self):
        return self.def_type

    def is_function_def(self) -> bool:
        return self.def_type == utils.constants.FUN_DEF

    def is_module_def(self) -> bool:
        return self.def_type == utils.constants.MOD_DEF

    def is_name_def(self) -> bool:
        return self.def_type == utils.constants.NAME_DEF

    def is_class_def(self) -> bool:
        return self.def_type == utils.constants.CLS_DEF

    def is_ext_def(self) -> bool:
        return self.def_type == utils.constants.EXT_DEF

    def is_callable(self) -> bool:
        return self.is_function_def() or self.is_ext_def()

    def get_lit_pointer(self) -> LiteralPointer:
        return self.lit_pointer

    def get_name_pointer(self) -> NamePointer:
        return self.name_pointer

    def get_name(self) -> str:
        return self.fullns.rpartition(".")[-1]

    def get_ns(self) -> str:
        return self.fullns

    def merge(self, to_merge: "Definition") -> None:
        self.name_pointer.merge(to_merge.name_pointer)
        self.lit_pointer.merge(to_merge.lit_pointer)


class DefinitionError(Exception):
    pass
