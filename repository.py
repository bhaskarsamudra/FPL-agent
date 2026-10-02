"""
Repository contracts for FPL-Agent persistence.

The rest of the application should depend on repository behaviour rather
than knowing which database technology is being used.

SQLite is the first implementation, but the same contract can later be
implemented by another database backend.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from typing import Any, Iterable


class RepositoryError(Exception):
    """Base exception for persistence-layer errors."""


class Repository(ABC):
    """
    Abstract persistence contract.

    Domain/business code should depend on this abstraction rather than
    executing SQL directly.
    """

    @abstractmethod
    def execute(
        self,
        sql: str,
        parameters: Iterable[Any] = (),
    ) -> int:
        """
        Execute a write statement.

        Returns:
            Number of affected rows.
        """
        raise NotImplementedError

    @abstractmethod
    def fetch_one(
        self,
        sql: str,
        parameters: Iterable[Any] = (),
    ) -> Any:
        """
        Execute a query and return one row, or None.
        """
        raise NotImplementedError

    @abstractmethod
    def fetch_all(
        self,
        sql: str,
        parameters: Iterable[Any] = (),
    ) -> list[Any]:
        """
        Execute a query and return all rows.
        """
        raise NotImplementedError

    @abstractmethod
    def transaction(self) -> AbstractContextManager:
        """
        Return a context manager representing a database transaction.

        Successful completion commits.
        Exceptions roll back.
        """
        raise NotImplementedError