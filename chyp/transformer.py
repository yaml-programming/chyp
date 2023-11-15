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
        """documents give rewriting rules"""
        tokens: Iterator[yaml.Token] = iter(tokens)
        document_name = None
        # the very first rule rewrites 0 to the file name
        while token := next(tokens, None):
            match token:
                case yaml.StreamEndToken():
                    return document_name
                case yaml.StreamStartToken():
                    document_name = self.transform_document(tokens)
                case yaml.DocumentStartToken():
                    meta = Meta(token, token)
                    tokens = itertools.chain([token], tokens)
                    term = self.term_ref(meta, [document_name])
                    rw_part_name = self.transform_document(tokens)
                    rw_term = self.term_ref(meta, [rw_part_name])
                    rw_part = self.rewrite_part(meta, [
                         False, [0, 0, rw_term], None])
                    self.rewrite(meta, [False, document_name, term, rw_part])

    def transform_document(self, tokens: Iterator[yaml.Token]):
        document_name = None
        while token := next(tokens, None):
            match token:
                case yaml.DocumentEndToken() | yaml.StreamEndToken():
                    return document_name
                case yaml.DocumentStartToken():
                    return self.transform_object(tokens)
                case _:
                    tokens = itertools.chain([token], tokens)
                    return self.transform_object(tokens)

    def transform_object(self, tokens: Iterator[yaml.Token]):
        """parallel (mapping) and sequential compositions of scalars"""
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
        """user-specified names. remember: only connectivity matters."""
        while token := next(tokens, None):
            match token:
                case yaml.ScalarToken():
                    meta = Meta(token, token)
                    self.gen(meta, [token.value, [('', 1)], [('', 1)], None])
                    return token.value

    def transform_mapping(self, tokens: Iterator[yaml.Token]):
        """parallel keys and key->value rules"""
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
        """a key->value sequential rule"""
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
        """sequential composition of an arbitrary number of objects"""
        rw_name = None
        while token := next(tokens, None):
            match token:
                case yaml.BlockEndToken():
                    meta = Meta(token, token)
                    self.def_statement(meta, [rw_name, term, None])
                    return rw_name
                case yaml.BlockSequenceStartToken():
                    rw_name = self.transform_object(tokens)
                    meta = Meta(token, token)
                    term = self.term_ref(meta, [rw_name])
                case _:
                    value_name = self.transform_object(tokens)
                    meta = Meta(token, token)
                    value = self.term_ref(meta, [value_name])
                    term = self.seq(meta, [term, value])
