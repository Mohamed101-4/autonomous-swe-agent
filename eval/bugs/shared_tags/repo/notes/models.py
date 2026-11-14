from dataclasses import dataclass, field


@dataclass
class Note:
    title: str
    body: str = ""
    tags: list[str] = field(default_factory=list)
