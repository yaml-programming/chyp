#     chyp - An interactive theorem prover for string diagrams 
#     Copyright (C) 2022 - Aleks Kissinger
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#    http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os.path
from typing import Dict, Optional, Tuple
import networkx as nx
from nx_yaml import NxSafeLoader
import yaml

from . import state


# cache parse trees for imported files and only re-parse if the file changes
parse_cache: Dict[str, Tuple[float, nx.Graph]] = dict()

def parse(code: str='', file_name: str='', namespace: str='', parent: Optional[state.State] = None) -> state.State:
    global parse_cache

    if parent and parent.namespace:
        if namespace != '':
            namespace = parent.namespace + '.' + namespace
        else:
            namespace = parent.namespace

    parse_data = state.State(namespace, file_name)

    if parent:
        parse_data.graphs = parent.graphs
        parse_data.rules = parent.rules
        parse_data.rewrites = parent.rewrites
        parse_data.errors = parent.errors
        parse_data.rule_sequence = parent.rule_sequence
        parse_data.sequence = parent.sequence
        parse_data.import_depth = parent.import_depth + 1
        if parse_data.import_depth > 255:
            parse_data.errors += [(parent.file_name, -1, "Maximum import depth (255) exceeded. Probably a cyclic import.")]

    try:
        if file_name and not code:
            mtime = os.path.getmtime(file_name)
            if file_name in parse_cache and parse_cache[file_name][0] == mtime:
                tree = parse_cache[file_name][1]
            else:
                with open(file_name) as f:
                    tree = yaml.scan(f, Loader=NxSafeLoader)
                parse_cache[file_name] = (mtime, tree)
        else:
            tree = yaml.scan(code, Loader=NxSafeLoader)
        parse_data.transform(tree)
        parse_data.parsed = True
    except yaml.MarkedYAMLError as e:
        parse_data.errors += [(file_name, e.problem_mark.line, e.problem)]

    if parent:
        parent.sequence = parse_data.sequence

    return parse_data

