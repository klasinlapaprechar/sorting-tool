"""
__init__.py
===========
Package root for the MRI Sorting Tool (``sorting_tool``).

HOW THIS FITS IN
----------------
Imported as ``import sorting_tool`` or via ``python -m sorting_tool``.
Exposes the package version string used by setuptools / pip metadata.
Runtime entry is ``sorting_tool.__main__`` → ``sorting_tool.app.run_app``.

HOW TO EXTEND
-------------
* Bump the release version: change ``__version__`` here and keep it in sync
  with ``pyproject.toml`` / ``setup.cfg`` if present.
* Re-export public helpers at package level (optional)::

      from sorting_tool.metadata import extract_meta
      # then users can ``from sorting_tool import extract_meta``
* Keep this file free of heavy imports so ``import sorting_tool`` stays cheap.
"""

__version__ = "0.1.0"
