"""Data access. Every SQL statement in the project lives under this package.

Repositories add and flush but never commit - the service that owns the unit
of work decides when the transaction ends.
"""
