from abc import ABCMeta
from typing import List

import aiohttp
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg
from databases import Database

from irrexplorer.exceptions import ImporterError
from irrexplorer.state import DataSource, IPNetwork, RouteInfo


class LocalSQLQueryBase(metaclass=ABCMeta):
    """
    Abstract class for query logic common to BGP and RIR stats in the local SQL database.
    Their prefix queries are almost identical, and only depend on the three fields
    defined below, which should be overridden.
    """

    source: DataSource
    table: sa.Table
    prefix_info_field: str

    def __init__(self, database: Database):
        self.database = database

    async def query_prefixes_any(self, prefixes: List[IPNetwork]):
        results = []
        prefixes_cidr = [sa.cast(str(prefix), pg.CIDR) for prefix in prefixes]
        prefix_selectors = [self.table.c.prefix.op("<<=")(p) for p in prefixes_cidr]
        prefix_selectors += [self.table.c.prefix.op(">>")(p) for p in prefixes_cidr]
        # noinspection PyPropertyAccess
        query = self.table.select(sa.or_(*prefix_selectors))
        async for row in self.database.iterate(query=query):
            results.append(
                RouteInfo(
                    source=self.source,
                    prefix=row["prefix"],
                    # May be 'rir' or 'origin' depending on table
                    **{self.prefix_info_field: row[self.prefix_info_field]},
                )
            )
        return results


async def retrieve_url_text(url: str):
    """
    Retrieve `url` and return the text in the response.
    Raises ImporterException if the response status is not 200.
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise ImporterError(f"Failed import from {url}: status {response.status}")
            return await response.text()
