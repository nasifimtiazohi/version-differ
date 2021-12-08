version-differ
===========================

|PyPI| |Python Version| |License| |Read the Docs| |Build| |Tests| |Codecov| |pre-commit| |Black|

.. |PyPI| image:: https://img.shields.io/pypi/v/version-differ.svg
   :target: https://pypi.org/project/version-differ/
   :alt: PyPI
.. |Python Version| image:: https://img.shields.io/pypi/pyversions/version-differ
   :target: https://pypi.org/project/version-differ
   :alt: Python Version
.. |License| image:: https://img.shields.io/github/license/nasifimtiazohi/version-differ
   :target: https://opensource.org/licenses/MIT
   :alt: License
.. |Read the Docs| image:: https://img.shields.io/readthedocs/version-differ/latest.svg?label=Read%20the%20Docs
   :target: https://version-differ.readthedocs.io/
   :alt: Read the documentation at https://version-differ.readthedocs.io/
.. |Build| image:: https://github.com/nasifimtiazohi/version-differ/workflows/Build%20version-differ%20Package/badge.svg
   :target: https://github.com/nasifimtiazohi/version-differ/actions?workflow=Package
   :alt: Build Package Status
.. |Tests| image:: https://github.com/nasifimtiazohi/version-differ/workflows/Run%20version-differ%20Tests/badge.svg
   :target: https://github.com/nasifimtiazohi/version-differ/actions?workflow=Tests
   :alt: Run Tests Status
.. |Codecov| image:: https://codecov.io/gh/nasifimtiazohi/version-differ/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/nasifimtiazohi/version-differ
   :alt: Codecov
.. |pre-commit| image:: https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white
   :target: https://github.com/pre-commit/pre-commit
   :alt: pre-commit
.. |Black| image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://github.com/psf/black
   :alt: Black


Features
--------

* Given any two versions of a package, returns the list of changed files with the count of loc_added and loc_removed in each file.

* Covers eight ecosystems, namely Cargo, Composer, Go, Maven, npm, NuGet, pip, and RubyGems.

* For Cargo, Composer, Maven, npm, pip, and RubyGems, version-differ downloads source code for a version of a package directly from the respective package registries to measure the diff.

* For Go and NuGet, it clones the source code repository, applies some heuristics to detect package specific files, and measures the diff.

* diffing is performed using native git-diff, ignores black lines (does not ignore comments).



Installation
------------

You can install *version-differ* via pip_ from PyPI_:

.. code:: console

   $ pip install version-differ


Usage
-----

Please see the `Command-line Reference <Usage_>`_ for details.


Credits
-------

This package was created with cookietemple_ using Cookiecutter_ based on Hypermodern_Python_Cookiecutter_.

.. _cookietemple: https://cookietemple.com
.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _PyPI: https://pypi.org/
.. _Hypermodern_Python_Cookiecutter: https://github.com/cjolowicz/cookiecutter-hypermodern-python
.. _pip: https://pip.pypa.io/
.. _Usage: https://version-differ.readthedocs.io/en/latest/usage.html
