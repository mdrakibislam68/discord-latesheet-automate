from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SigninHandler(ABC):
    @abstractmethod
    async def handle_signin(self, data: dict[str, Any]) -> None:
        ...
