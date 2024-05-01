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
from typing import Dict, Optional, Union

logger = logging.getLogger(__name__)


class ModuleManager:
    __slots__ = ["internal", "external"]

    def __init__(self) -> None:
        self.internal: Dict[str, Module] = {}
        self.external: Dict[str, Module] = {}

    def create(self, name: str, fname: Optional[str], external=False) -> "Module":
        logger.debug("In ModuleManager.create")
        mod = Module(name, fname)
        if external:
            self.external[name] = mod
        else:
            self.internal[name] = mod
        return mod

    def get(self, name: str):
        logger.debug("In ModuleManager.get")
        if name in self.internal:
            return self.internal[name]
        if name in self.external:
            return self.external[name]

    def get_internal_modules(self):
        logger.debug("In ModuleManager.get_internal_modules")
        return self.internal

    def get_external_modules(self):
        logger.debug("In ModuleManager.get_external_modules")
        return self.external


class Module:
    slots = ["name", "filename", "methods"]

    def __init__(self, name: str, filename: Optional[str]) -> None:
        logger.debug("In Module.__init__")
        self.name = name
        self.filename = filename
        self.methods: Dict[str, Dict[str, Union[str, int, None]]] = {}

    def get_name(self) -> str:
        logger.debug("In Module.get_name")
        return self.name

    def get_filename(self) -> Optional[str]:
        logger.debug("In Module.get_filename")
        return self.filename

    def get_methods(self):
        logger.debug("In Module.get_methods")
        return self.methods

    def add_method(
        self, method: str, first: Optional[int] = None, last: Optional[int] = None
    ):
        logger.debug("In Module.add_method")
        if not self.methods.get(method, None):
            self.methods[method] = {"name": method, "first": first, "last": last}
