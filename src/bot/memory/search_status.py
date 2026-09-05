"""Partial retrieval is evidence with a coverage limit, not an empty search."""


class IncompleteMemorySearch(Exception):
    def __init__(self, unavailable: list[str], results: list[dict]):
        super().__init__("; ".join(unavailable))
        self.results = results
