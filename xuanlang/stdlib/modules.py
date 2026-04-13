from __future__ import annotations

import base64
import gzip
import hashlib
import math
import platform
import socket
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote, unquote

from ..runtime.ai import (
    KVCache,
    attention,
    layer_norm,
    quantize_int8,
    sparse_prune,
    token_hash,
    transformer_step,
)
from ..runtime.tensor import Tensor, quantize_int4


def build_stdlib_registry() -> dict[str, SimpleNamespace]:
    数学 = SimpleNamespace(
        平方=lambda x: x * x,
        开方=math.sqrt,
        绝对=abs,
        最大=max,
        最小=min,
        平均=lambda values: sum(values) / len(values) if values else 0,
    )
    张量 = SimpleNamespace(
        张=Tensor.from_value,
        relu=lambda x: Tensor.from_value(x).relu(),
        软最大=lambda x: Tensor.from_value(x).softmax(),
        量化4=lambda x: quantize_int4(Tensor.from_value(x)),
    )
    系统 = SimpleNamespace(
        时刻=time.time,
        平台=platform.platform,
        处理器=platform.processor,
        系统名=platform.system,
    )
    时间 = SimpleNamespace(
        秒=time.time,
        睡=time.sleep,
        纳秒=time.time_ns,
    )
    IO = SimpleNamespace(
        读=lambda path: Path(path).read_text(encoding="utf-8"),
        写=lambda path, text: Path(path).write_text(text, encoding="utf-8"),
        存在=lambda path: Path(path).exists(),
    )
    编码 = SimpleNamespace(
        哈希=lambda text: hashlib.sha256(str(text).encode("utf-8")).hexdigest(),
        Base64=lambda text: base64.b64encode(str(text).encode("utf-8")).decode("utf-8"),
        解Base64=lambda text: base64.b64decode(str(text).encode("utf-8")).decode("utf-8"),
        链接编码=lambda text: quote(str(text)),
        链接解码=lambda text: unquote(str(text)),
    )
    压缩 = SimpleNamespace(
        压=lambda text: gzip.compress(str(text).encode("utf-8")),
        解=lambda data: gzip.decompress(data).decode("utf-8"),
    )
    网络 = SimpleNamespace(
        主机名=socket.gethostname,
        地址=lambda host: socket.gethostbyname(host),
    )
    AI = SimpleNamespace(
        缓存=lambda size=256: KVCache(max_entries=size),
        注意=attention,
        归一=layer_norm,
        转步=transformer_step,
        稀疏=sparse_prune,
        量化4=lambda x: quantize_int4(Tensor.from_value(x)),
        量化8=quantize_int8,
        哈希=token_hash,
    )
    数据 = SimpleNamespace(
        键=lambda mapping: list(dict(mapping).keys()),
        值=lambda mapping: list(dict(mapping).values()),
        项=lambda mapping: list(dict(mapping).items()),
        有=lambda mapping, key: key in dict(mapping),
        取=lambda mapping, key, default=None: dict(mapping).get(key, default),
        置=lambda mapping, key, value: _set_mapping_value(mapping, key, value),
        并=lambda left, right: {**dict(left), **dict(right)},
    )
    return {
        "标准.数学": 数学,
        "标准.张量": 张量,
        "标准.系统": 系统,
        "标准.时间": 时间,
        "标准.IO": IO,
        "标准.编码": 编码,
        "标准.压缩": 压缩,
        "标准.网络": 网络,
        "标准.AI": AI,
        "标准.数据": 数据,
    }


def _set_mapping_value(mapping: dict[object, object], key: object, value: object) -> dict[object, object]:
    mapping[key] = value
    return mapping
