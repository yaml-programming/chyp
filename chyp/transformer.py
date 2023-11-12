from dataclasses import dataclass
import itertools
from typing import Iterator
import yaml

Tokens = Iterator[yaml.Token]

def v_args(meta=False):
    return lambda f: f


@dataclass
class Meta:
    start_token: yaml.Token
    end_token: yaml.Token

    def __post_init__(self):
        self.empty = True
        self.start_pos: int | None = self.start_token.start_mark.index
        self.line: int | None = self.start_token.start_mark.line
        self.column: int | None = self.start_token.start_mark.column
        self.end_line: int | None = self.end_token.end_mark.line
        self.end_column: int | None = self.end_token.end_mark.column
        self.end_pos: int | None = self.end_token.end_mark.index
        # orig_expansion = None #: 'List[TerminalDef]' | None = None
        # self.match_tree: bool | None = None


class YamlTransformer:
    def transform(self, tokens: Iterator[yaml.Token]):
        token = next(tokens, None)
        self.transform_dispatch(token, tokens)

    def transform_dispatch(self, left_token: yaml.Token | None, tokens: Iterator[yaml.Token]):
        tokens = itertools.chain([left_token], tokens)
        while token := next(tokens, None):
            match token:
                # case yaml.BlockSequenceStartToken():
                #     self.transform_sequence(token, tokens)
                case yaml.BlockMappingStartToken():
                    return self.transform_mapping(token, tokens)
                case yaml.ScalarToken() if token.value == 'gen':
                    return self.transform_dispatch_gen(token, tokens)
                case yaml.ScalarToken():
                    meta = Meta(token, token)
                    return self.gen(meta, [token.value, [('', 1)], [('', 1)], None])

    def transform_dispatch_gen(self,
                               gen_token: yaml.ScalarToken | None,
                               tokens: Iterator[yaml.Token]):
        while token := next(tokens, None):
            match token:
                # case yaml.BlockSequenceStartToken():
                #     self.transform_sequence(token, tokens)
                case yaml.BlockMappingStartToken():
                    self.transform_gen_mapping(token, tokens)
                    return
                case yaml.KeyToken():
                    continue
                case yaml.ValueToken():
                    continue
                case yaml.ScalarToken():
                    meta = Meta(token, token)
                    self.gen(meta, [token.value, [], [], None])
                    return

    def transform_sequence(self,
                           left_token: yaml.BlockSequenceStartToken,
                           tokens: Iterator[yaml.Token]):
        seq = []
        while token := next(tokens, None):
            match token:
                case yaml.BlockEndToken():
                    meta = Meta(token, token)
                    if len(seq) == 0:
                        return self.term_hole(meta, seq)
                    if len(seq) == 1:
                        return self.term_hole(meta, seq)
                    left = seq[0]
                    right = seq[1]

                    rule = self.rule(
                        meta,
                        ['', left, True, right])
                    return self.show(meta, [rule])

                case yaml.BlockEntryToken():
                    right = self.transform_dispatch(tokens)
                    seq.append(right)

    def transform_mapping(self,
                          left_token: yaml.BlockMappingStartToken,
                          tokens: Iterator[yaml.Token]):
        key_token = None
        tokens = itertools.chain([left_token], tokens)
        while token := next(tokens, None):
            match token:
                case yaml.ScalarToken() if token.value == 'gen':
                    return self.transform_gen_mapping(left_token, tokens)
                case yaml.ScalarToken() if not key_token:
                    key_token = token
                case yaml.BlockEndToken():
                    return
                case yaml.StreamEndToken():
                    return
                case _ if key_token:
                    self.transform_mapping_entry(key_token, tokens)
                    # meta = Meta(key_token, key_token)
                    # entry_ref = self.term_ref(meta, [key_token_name])
                    # # self.gen(meta, [entry_token_name, [], [], None])
                    # meta = Meta(key_token, key_token)
                    # self.rule(meta, [key_token_name, entry_ref, False, entry_ref])

    def transform_mapping_entry(self,
                                left_token: yaml.ValueToken,
                                tokens: Iterator[yaml.Token]):
        key_token, value_token = None, None
        key_token_name, value_token_name = None, None
        tokens = itertools.chain([left_token], tokens)
        while token := next(tokens, None):
            match token:
                case yaml.KeyToken():
                    key_token = token
                case yaml.ValueToken():
                    value_token = token
                case yaml.ScalarToken() if not key_token_name:
                    key_token = token
                    key_token_name = token.value
                case yaml.ScalarToken() if not value_token_name:
                    value_token = token
                    value_token_name = token.value
                case _ if key_token_name and value_token_name:
                    meta = Meta(key_token, key_token)
                    self.gen(meta, [key_token_name, [], [], None])
                    meta = Meta(value_token, value_token)
                    self.gen(meta, [value_token_name, [], [], None])
                    meta = Meta(left_token, token)
                    key_ref = self.term_ref(key_token, [key_token_name])
                    value_ref = self.term_ref(value_token, [value_token_name])
                    return self.seq(meta,
                        [key_ref, value_ref])
                case _:
                    return

    def transform_gen_mapping(self, gen_token: yaml.ScalarToken, tokens: Tokens):
        while token := next(tokens, None):
            match token:
                case yaml.BlockEndToken():
                    return
                case _:
                    self.transform_gen_mapping_entry(gen_token, tokens)

    def transform_gen_mapping_entry(self,
                                gen_token: yaml.ValueToken,
                                tokens: Iterator[yaml.Token]):
        key_token, value_token = None, None
        key_token_name, value_token_name = None, None
        tokens = itertools.chain([gen_token], tokens)
        while token := next(tokens, None):
            match token:
                case yaml.BlockMappingStartToken():
                    continue
                case yaml.BlockEndToken() if key_token_name and value_token_name:
                    meta = Meta(key_token, key_token)
                    self.gen(meta, [key_token_name, [('', 1)], [('', 1)], None])
                    meta = Meta(value_token, value_token)
                    self.gen(meta, [value_token_name, [('', 1)], [('', 1)], None])

                    key_ref = self.term_ref(key_token, [key_token_name])
                    value_ref = self.term_ref(value_token, [value_token_name])
                    meta = Meta(gen_token, token)
                    self.rule(meta, [key_token_name, key_ref, False, value_ref])
                    key_token_name, value_token_name = None, None
                case yaml.KeyToken():
                    key_token = token
                case yaml.ValueToken():
                    value_token = token
                case yaml.ScalarToken() if not key_token_name:
                    key_token = token
                    key_token_name = token.value
                case yaml.ScalarToken() if not value_token_name:
                    value_token = token
                    value_token_name = token.value
                case _:
                    return
