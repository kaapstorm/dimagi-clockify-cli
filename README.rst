Dimagi Clockify CLI
===================

A Clockify command line interface, for the way Dimagi uses it.


Usage
-----

Start clocking time to the "gtd_meeting" bucket::

    $ dcl gtd_meeting

Stop clocking time::

    $ dcl stop

Start clocking time to the "jamaica" bucket since 14:00::

    $ dcl jamaica --since 14:00


Requirements
------------

* Python 3.8 or higher


Installation
------------

Clone the repository::

    $ git clone https://github.com/kaapstorm/dimagi-clockify-cli.git
    $ cd dimagi-clockify-cli

Create and activate a virtual environment::

    $ python3 -m venv venv
    $ source venv/bin/activate

Install::

    $ pip install .


Configuration
-------------

1. Create a config directory::

       $ mkdir ~/.config/dimagi-clockify-cli

   To use a different config directory, set an environment
   variable named ``DCL_CONFIG_DIR`` to the directory you prefer.

2. Copy the template config file to
   ``~/.config/dimagi-clockify-cli/config.yaml`` (or
   ``$DCL_CONFIG_DIR/config.yaml``)::

       $ cp config.template.yaml ~/.config/dimagi-clockify-cli/config.yaml

3. Edit your ``config.yaml`` file to set up your buckets.
