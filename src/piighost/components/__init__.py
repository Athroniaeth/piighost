"""Pluggable pipeline components: each is a port with its adapters.

Detection, overlap resolution, expansion, linking, entity resolution,
placeholder factories, anonymization, and guard rails. Each lives in its own
subpackage and is imported directly, for example from
piighost.components.detector.
"""
