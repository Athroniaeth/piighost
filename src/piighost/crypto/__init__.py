"""Cryptographic primitives: keyed hashing and reversible encryption.

Used to protect PII in a persistent store: the hasher keys a value one-way, the
cipher encrypts it reversibly. Each lives in its own subpackage.
"""
