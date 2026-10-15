import os
import threading
from functools import lru_cache
from pathlib import Path

import numpy as np


class FastEmbedder:
    max_tokens = 448

    def __init__(self):
        from fastembed import TextEmbedding
        from tokenizers import Tokenizer
        name=os.getenv('DOCUMENT_EMBEDDING_MODEL','BAAI/bge-small-zh-v1.5')
        cache=Path(__file__).resolve().parents[2]/'.model-cache/fastembed'
        self.model=TextEmbedding(model_name=name,cache_dir=str(cache),threads=2)
        # 独立 tokenizer 不启用截断；原模型 tokenizer 保留推理配置。
        self.tokenizer=Tokenizer.from_str(self.model.model.tokenizer.to_str())
        self.tokenizer.no_truncation();self.tokenizer.no_padding()
        self.lock=threading.Lock()

    def token_count(self,text):return len(self.tokenizer.encode(text).ids)

    def embed_documents(self,texts):
        with self.lock:return np.asarray(list(self.model.passage_embed(texts,batch_size=16)),dtype=np.float32)

    def embed_query(self,text):
        with self.lock:return np.asarray(list(self.model.query_embed(text))[0],dtype=np.float32)


@lru_cache(maxsize=1)
def _load_encoder():
    try:return FastEmbedder()
    except Exception as error:
        raise ValueError('中文检索模型尚未准备好。请检查首次模型下载是否完成或网络是否可用；不会自动改用其他检索方式。'+type(error).__name__) from error


_initialization_lock=threading.Lock()

def get_encoder():
    with _initialization_lock:return _load_encoder()
