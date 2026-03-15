import sys
from dataclasses import dataclass
from pathlib import Path

import grpc

_RETRIEVAL_PATH = Path.home() / "dev" / "ai" / "retrieval"
if str(_RETRIEVAL_PATH) not in sys.path:
    sys.path.insert(0, str(_RETRIEVAL_PATH))

from v1 import retrieval_pb2, retrieval_pb2_grpc


@dataclass(slots=True)
class TokenCount:
    tokens: int
    words: int
    chars: int


class TokenCounter:
    def __init__(self, grpc_target: str = "localhost:50051"):
        self._channel = grpc.insecure_channel(grpc_target)
        self._stub = retrieval_pb2_grpc.CatholicEmbeddingServiceStub(self._channel)

    def count(self, text: str) -> TokenCount:
        if not text:
            return TokenCount(tokens=0, words=0, chars=0)

        words = len(text.split())
        chars = len(text)

        try:
            request = retrieval_pb2.CountTokensRequest(input=text)
            response = self._stub.CountTokens(request, timeout=2.0)
            tokens = response.tokens
        except grpc.RpcError:
            tokens = int(words * 1.3)

        return TokenCount(tokens=tokens, words=words, chars=chars)

    def close(self):
        self._channel.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
