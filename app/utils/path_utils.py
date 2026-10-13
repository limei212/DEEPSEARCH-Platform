"""
文件路径解析工具

负责把模型或工具返回的虚拟路径、上传文件路径和相对路径统一转换为本地绝对路径
后续文件读取、Markdown 生成和 PDF 转换工具都可以复用这里的解析规则
"""

import os
from pathlib import Path
from typing import Optional


def resolve_path(filename: str, session_dir: Optional[str] = None) -> str:
    """
    解析文件路径，并尽量把任务产物限制在当前会话目录中

    :param filename: 模型、工具或用户传入的文件名/路径
    :param session_dir: 当前任务的会话目录
    :return: 解析后的绝对路径
    """
    path = Path(filename)
    path_str = filename.replace("\\", "/")

    # 大模型常返回 /workspace、/mnt/data 这类沙箱路径，本地项目需要先剥离虚拟前缀
    for prefix in ["/workspace", "/mnt/data", "/home/user"]:
        if path_str.startswith(prefix):
            cleaned = path_str[len(prefix) :].lstrip("/")
            path = Path(cleaned)
            path_str = str(path).replace("\\", "/")
            break

    # 有任务上下文时，文件访问必须留在该任务目录内。
    if session_dir:
        session_path = Path(session_dir).resolve()
        if '..' in path.parts or '~' in path.parts:
            raise ValueError('拒绝访问任务工作目录之外的文件')
        if not path.is_absolute() and session_path.name in path.parts:
            position = list(path.parts).index(session_path.name)
            path = Path(*path.parts[position+1:])
        elif not path.is_absolute() and path.parts and path.parts[0] == 'output':
            path = Path(path.name)
        if os.name == 'nt' and path_str.startswith('/') and not path.drive:
            path = Path(path_str.lstrip('/'))
        candidate = (session_path / path).resolve()
        if not candidate.is_relative_to(session_path):
            raise ValueError('拒绝访问任务工作目录之外的文件')
        return str(candidate)

    if "updated/" in path_str:
        idx = path_str.find("updated/")
        relative_part = path_str[idx:]
        return str(Path(relative_part).resolve())

    return str(path.resolve())
