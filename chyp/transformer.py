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
        self.start_pos: int | None = self.start_token.start_mark.index
        self.line: int | None = self.start_token.start_mark.line
        self.column: int | None = self.start_token.start_mark.column
        self.end_line: int | None = self.end_token.end_mark.line
        self.end_column: int | None = self.end_token.end_mark.column
        self.end_pos: int | None = self.end_token.end_mark.index


class YamlTransformer:
    def transform(self, tokens):
        tokens: Iterator[yaml.Token] = iter(tokens)
        stream_name = None
        while token := next(tokens, None):
            match token:
                case yaml.StreamEndToken():
                    return
                case yaml.StreamStartToken():
                    stream_name = self.transform_document(tokens)
                case _:
                    tokens = itertools.chain([token], tokens)
                    stream_name = self.transform_document(tokens)
                    self.transform_document(tokens)

    def transform_document(self, tokens: Iterator[yaml.Token]):
        document_name = None
        while token := next(tokens, None):
            match token:
                case yaml.DocumentEndToken() | yaml.StreamEndToken():
                    return document_name
                case yaml.DocumentStartToken():
                    document_name = self.transform_object(tokens)
                case _:
                    tokens = itertools.chain([token], tokens)
                    document_name = self.transform_object(tokens)

    def transform_object(self, tokens: Iterator[yaml.Token]):
        while token := next(tokens, None):
            match token:
                case yaml.BlockMappingStartToken():
                    tokens = itertools.chain([token], tokens)
                    return self.transform_mapping(tokens)
                case yaml.BlockSequenceStartToken():
                    tokens = itertools.chain([token], tokens)
                    return self.transform_sequence(tokens)
                case yaml.ScalarToken():
                    tokens = itertools.chain([token], tokens)
                    return self.transform_scalar(tokens)

    def transform_scalar(self, tokens: Iterator[yaml.Token]):
        while token := next(tokens, None):
            match token:
                case yaml.ScalarToken():
                    meta = Meta(token, token)
                    self.gen(meta, [token.value, [('', 1)], [('', 1)], None])
                    return token.value

    def transform_mapping(self, tokens: Iterator[yaml.Token]):
        """A term with parallel keys and key->value rules"""
        mapping_token, mapping_name = None, None
        while token := next(tokens, None):
            match token:
                case yaml.BlockEndToken():
                    return mapping_name
                case yaml.BlockMappingStartToken():
                    mapping_token = token
                case yaml.KeyToken():
                    tokens = itertools.chain([token], tokens)
                    # TODO multiple entries
                    mapping_name = self.transform_mapping_entry(tokens)

    def transform_mapping_entry(self, tokens: Iterator[yaml.Token]):
        """a key->value rule"""
        key_token, key_name = None, None
        while token := next(tokens, None):
            match token:
                case yaml.KeyToken():
                    key_token = token
                    key_name = self.transform_object(tokens)
                case yaml.ValueToken():
                    # key_meta = Meta(key_token, key_token)
                    # key = self.term_ref(key_meta, [key_name])
                    value_name = self.transform_object(tokens)
                    value_meta = Meta(token, token)
                    value = self.term_ref(value_meta, [value_name]) \
                            if value_name else self.id0([None])
                    meta = Meta(key_token, token)
                    self.def_statement(meta, [key_name, value, None])
                    return key_name

    def transform_sequence(self, tokens: Iterator[yaml.Token]):
        """A term with parallel keys and key->value rules"""
        start_token = None
        rw_name = None
        rw_part_names = []
        while token := next(tokens, None):
            match token:
                case yaml.BlockEndToken():
                    meta = Meta(start_token, token)
                    term = self.term_ref(meta, [rw_name])
                    rw_parts = [self.rewrite_part(meta,
                                                  [False, [0, 0, None],
                                                  ['rule', [rw_name]], None])
                                for rw_name in rw_part_names]
                    self.rewrite(meta, [False, rw_name, term, *rw_parts])
                    return rw_name
                case yaml.BlockSequenceStartToken():
                    start_token = token
                    rw_name = self.transform_object(tokens)
                case _:
                    value_name = self.transform_object(tokens)
                    rw_part_names.append(value_name)
