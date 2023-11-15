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
        document = None
        # the very first rule rewrites 0 to the file name
        while token := next(tokens, None):
            match token:
                case yaml.StreamEndToken():
                    return
                case yaml.StreamStartToken():
                    document = self.transform_document(tokens)
                case yaml.DocumentStartToken():
                    meta = Meta(token, token)
                    tokens = itertools.chain([token], tokens)
                    rw_term = self.transform_document(tokens)
                    rw_part = self.rewrite_part(meta, [
                         False, [0, 0, rw_term], None])
                    rw_name = ""
                    self.rewrite(meta, [False, rw_name, document, rw_part])

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
                    term = self.term_ref(meta, [token.value])
                    return term

    def transform_mapping(self, tokens: Iterator[yaml.Token]):
        """parallel keys and key->value rules"""
        mapping_token, entry = None, None
        while token := next(tokens, None):
            match token:
                case yaml.BlockEndToken():
                    return entry
                case yaml.BlockMappingStartToken():
                    mapping_token = token
                    entry = self.transform_mapping_entry(tokens)
                case yaml.KeyToken():
                    tokens = itertools.chain([token], tokens)
                    new_entry = self.transform_mapping_entry(tokens)
                    # TODO multiple entries
                    entry = self.par([entry, new_entry])

    def transform_mapping_entry(self, tokens: Iterator[yaml.Token]):
        """a key->value sequential rule with key as rule name"""
        key_token, key = None, None
        while token := next(tokens, None):
            match token:
                case yaml.KeyToken():
                    key_token = token
                    key = self.transform_object(tokens)
                case yaml.ValueToken():
                    value = self.transform_object(tokens)
                    meta = Meta(key_token, token)
                    return self.seq(meta, [key, value])

    def transform_sequence(self, tokens: Iterator[yaml.Token]):
        """anonymous sequential composition of an arbitrary number of objects"""
        start_token = None
        sequence = None
        while token := next(tokens, None):
            match token:
                case yaml.BlockEndToken():
                    return sequence
                case yaml.BlockSequenceStartToken():
                    start_token = token
                    sequence = self.transform_object(tokens)
                case _:
                    tokens = itertools.chain([token], tokens)
                    value = self.transform_object(tokens)
                    meta = Meta(start_token, token)
                    sequence = self.seq(meta, [sequence, value])
