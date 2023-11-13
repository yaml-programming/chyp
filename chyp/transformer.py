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
    def transform(self, tokens):
        tokens: Iterator[yaml.Token] = iter(tokens)
        while token := next(tokens, None):
            match token:
                case yaml.StreamEndToken():
                    return
                case _:
                    self.transform_dispatch(tokens)

    def transform_dispatch(self, tokens: Iterator[yaml.Token]):
        while token := next(tokens, None):
            match token:
                case yaml.BlockMappingStartToken():
                    return self.transform_mapping(tokens)
                # case yaml.ScalarToken() if token.value == 'gen':
                #     return self.transform_dispatch_gen(tokens)
                case yaml.ScalarToken():
                    return self.transform_scalar(token)

    def transform_scalar(self, token: yaml.Token):
        meta = Meta(token, token)
        self.gen(meta, [token.value, [('', 1)], [('', 1)], None])
        return token.value

    # def transform_dispatch_gen(self,
    #                            tokens: Iterator[yaml.Token]):
    #     while token := next(tokens, None):
    #         match token:
    #             case yaml.BlockMappingStartToken():
    #                 self.transform_gen_mapping(tokens)
    #                 return

    def transform_mapping(self, tokens: Iterator[yaml.Token]):
        """A term with parallel keys and key->value rules"""
        key_token, value_token = None, None
        key_name, value_name = None, None
        while token := next(tokens, None):
            match token:
                case yaml.BlockEndToken():
                    return
                case yaml.KeyToken():
                    tokens = itertools.chain([token], tokens)
                    self.transform_mapping_entry(tokens)

    def transform_mapping_entry(self, tokens: Iterator[yaml.Token]):
        """a key->value rule"""
        key_token, key_name = None, None
        while token := next(tokens, None):
            match token:
                case yaml.KeyToken():
                    key_token = token
                    key_name = self.transform_dispatch(tokens)
                case yaml.ValueToken():
                    key_meta = Meta(key_token, key_token)
                    key = self.term_ref(key_meta, [key_name])
                    value_name = self.transform_dispatch(tokens)
                    value_meta = Meta(token, token)
                    value = self.term_ref(value_meta, [value_name]) if value_name else self.id0([None])
                    meta = Meta(key_token, token)
                    self.rule(meta, [key_name, key, False, value])
                    return key_name
