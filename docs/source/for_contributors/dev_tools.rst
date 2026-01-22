Local Tooling
=============

Clone the repo and run, from the root directory:

.. code-block:: console

    uv sync

This will generate the virtual environment for the package. Then
set up your pre-commits.

.. code-block:: console

    uv run pre-commit install

The pre-commits will run a linter and formatter that must pass before pre-commits
are accepted.

Local Tests
------------

In git bash run:

.. code-block:: console

    tools/test.sh
    tools/test.sh open

The open command will launch a view of a webpage with
missing code coverage highlighted.

You should also run the code linters periodically to keep your
code-style consistent.

.. code-block:: console

    tools/lint.sh

Local Documentation
-------------------

Clean the local documentation build (this needs to be run sometimes
if you are modifying the documentation and it gets into a broken state). It will reset the build directories and the next call to
build it will be completely from scratch.

.. code-block:: console

    tools/docs.sh clean


To build a copy of the documentation based on your current changes.

.. code-block:: console

    tools/docs.sh html

Alternatively, you can build the versioned documentation, which is generated
from the stable and development branch heads, along with any semantically versioned
tags. This will not build the current copy of the documentation unless it is tagged and/or
you are on the stable or development branches.

.. code-block:: console

    tools/docs.sh html-multiversioned

Serve the build files (this will freeze the console).
Files are served on localhost on port 8000. Only you can see this
documentation.

.. code-block:: console

    tools/docs.sh serve

Open the webpage (in a seperate console).
You can also click the link that appears in the console
after serving.

.. code-block:: console

    tools/docs.sh open


Code Profiling
--------------
You can profile test scripts. This will launch a localhost webpage
on port 8080. Test scripts should go in the tests directory.

.. code-block:: console

    tools/profile.sh tests/<test_script_name.py>

