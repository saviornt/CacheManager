Installation
============

Prerequisites
-------------

CacheManager requires Python 3.12 or higher.

Installing from PyPI
--------------------

To install CacheManager from PyPI:

.. code-block:: bash

    pip install cache-manager

Installing from Source
----------------------

To install CacheManager from source:

.. code-block:: bash

    git clone https://github.com/username/CacheManager.git
    cd CacheManager
    pip install -e .

Optional Dependencies
---------------------

For additional features, you can install extra dependencies:

.. code-block:: bash

    # For Redis support
    pip install cache-manager[redis]

    # For compression support
    pip install cache-manager[compression]

    # For all optional dependencies
    pip install cache-manager[all] 