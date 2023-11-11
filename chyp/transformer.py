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
                    return self.transform_scalar(token)

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
                    self.transform_dispatch_gen(token, tokens)
                case yaml.ValueToken():
                    self.transform_dispatch_gen(token, tokens)
                case yaml.ScalarToken():
                    self.transform_scalar(token)
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
        entry_token = None
        entry_token_name = None
        tokens = itertools.chain([left_token], tokens)
        while token := next(tokens, None):
            match token:
                case yaml.ScalarToken() if not entry_token_name:
                    entry_token = token
                    entry_token_name = token.value
                case yaml.BlockEndToken():
                    return
                case yaml.StreamEndToken():
                    return
                case _ if entry_token_name:
                    meta = Meta(entry_token, entry_token)
                    self.transform_mapping_entry(entry_token, tokens)
                    entry_ref = self.term_ref(entry_token, [entry_token_name])
                    # self.gen(meta, [entry_token_name, [], [], None])
                    meta = Meta(entry_token, entry_token)
                    self.rule(meta, [entry_token_name, entry_ref, False, entry_ref])

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
                    meta = Meta(key_token, key_token)
                    self.gen(meta, [key_token_name, [], [], None])
                case yaml.ScalarToken() if not value_token_name:
                    value_token = token
                    value_token_name = token.value
                    meta = Meta(value_token, value_token)
                    self.gen(meta, [value_token_name, [], [], None])
                case _ if key_token_name and value_token_name:
                    meta = Meta(left_token, token)
                    key_ref = self.term_ref(key_token, [key_token_name])
                    value_ref = self.term_ref(value_token, [value_token_name])
                    return self.rule(meta,
                        ["rule", key_ref, False, value_ref])
                case _:
                    return

    def transform_gen(self, token: yaml.ScalarToken, tokens: Tokens):
        while token := next(tokens, None):
            self.transform_mapping(None, tokens)
        meta = Meta(token, token)
        return self.gen(meta, [token.value, self.id([None])])

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
        key_token_name = None
        tokens = itertools.chain([gen_token], tokens)
        while token := next(tokens, None):
            match token:
                case yaml.BlockMappingStartToken():
                    continue
                case yaml.BlockEndToken():
                    if key_token and value_token:
                        meta = Meta(key_token, token)
                        self.gen(meta,
                            [key_token.value, [(key_token.value, 1)], [(value_token.value, 1)], None])
                    return
                case yaml.BlockEndToken():
                    if key_token and value_token:
                        meta = Meta(key_token, token)
                        self.gen(meta,
                            [key_token.value, [(key_token.value, 1)], [(value_token.value, 1)], None])
                    return
                case yaml.KeyToken():
                    key_token = token
                    key_token_name = token.value
                    self.transform_dispatch_gen(key_token, tokens)
                case yaml.ValueToken():
                    value_token = token
                    self.transform_dispatch_gen(value_token, tokens)
                case yaml.ScalarToken() if not key_token:
                    meta = Meta(token, token)
                    self.gen(meta, [token.value, [], [(token.value, 1)], None])
                case yaml.ScalarToken() if not value_token:
                    meta = Meta(token, token)
                    self.gen(meta, [token.value, [(token.value, 1)], [(key_token_name, 1)], None])
                case _:
                    if not key_token:
                        key_token = token
                        self.transform_gen_dispatch(key_token, tokens)
                    elif not value_token:
                        value_token = token
                        self.transform_gen_dispatch(value_token, tokens)
