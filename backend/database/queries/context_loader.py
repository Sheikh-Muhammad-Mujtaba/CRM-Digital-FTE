import pathlib

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.knowledge import KnowledgeBase


async def load_markdown_context(session: AsyncSession, context_dir: str = "context") -> int:
    """
    Minimal context loader for local bootstrap.
    Embedding generation is handled by the agent search flow and can be extended
    to precompute vectors in a batch job.
    """
    root = pathlib.Path(context_dir)
    if not root.exists():
        return 0

    count = 0
    for file_path in root.glob("*.md"):
        content = file_path.read_text(encoding="utf-8").strip()
        if not content:
            continue
        session.add(KnowledgeBase(title=file_path.stem, content=content))
        count += 1
    await session.commit()
    return count
