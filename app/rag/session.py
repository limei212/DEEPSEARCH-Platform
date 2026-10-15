from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path

from app.api.context import get_thread_context
from .documents import TaskDocumentIndex

current_index=ContextVar('task_document_index',default=None)


@asynccontextmanager
async def document_scope(directory,*,encoder=None,reuse=False):
    existing=current_index.get()
    if reuse and existing is not None:
        yield existing;return
    index=TaskDocumentIndex(directory,encoder);token=current_index.set(index)
    try:yield index
    finally:
        index.close();current_index.reset(token)


def upload_directory(fallback):
    thread=get_thread_context()
    return Path(__file__).resolve().parents[1]/'updated'/f'session_{thread}' if thread else Path(fallback)
