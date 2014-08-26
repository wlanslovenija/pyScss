"""py.test plugin configuration."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging

import pytest

import scss
import scss.config

try:
    import fontforge
except ImportError:
    fontforge = None


# Turn on pyscss's logging
console = logging.StreamHandler()
logger = logging.getLogger('scss')
logger.setLevel(logging.ERROR)
logger.addHandler(console)


def pytest_addoption(parser):
    """Add options for filtering which file tests run.

    This has to be done in the project root; py.test doesn't (and can't)
    recursively look for conftest.py files until after it's parsed the command
    line.
    """
    parser.addoption(
        '--include-ruby',
        help='run tests imported from Ruby and sassc, most of which fail',
        action='store_true',
        dest='include_ruby',
    )


def pytest_ignore_collect(path, config):
    # Ruby/sassc tests don't even exist without this option
    if path.basename in ('from_ruby', 'from-sassc'):
        if not config.getoption('include_ruby'):
            return True


def pytest_collect_file(path, parent):
    if path.ext == '.scss':
        parts = str(path).split(path.sep)
        # -4 tests / -3 files / -2 directory / -1 file.scss
        if parts[-4:-2] == ['tests', 'files']:
            return SassFile(path, parent)


class SassFile(pytest.File):
    def collect(self):
        parent_name = self.fspath.dirpath().basename
        if not fontforge and parent_name == 'fonts':
            pytest.skip("font tests require fontforge")

        yield SassItem(str(self.fspath), self)


class SassItem(pytest.Item):
    """A Sass test input file, collected as its own test item.

    A file of the same name but with a .css extension is assumed to contain the
    expected output.
    """
    _nodeid = None

    @property
    def nodeid(self):
        # Rig the nodeid to be "directory::filename", so all the files in the
        # same directory are treated as grouped together
        if not self._nodeid:
            self._nodeid = "{0}::{1}".format(
                self.fspath.dirpath().relto(self.session.fspath),
                self.fspath.basename,
            )
        return self._nodeid

    def reportinfo(self):
        return (
            self.fspath.dirpath(),
            None,
            self.fspath.relto(self.session.fspath),
        )

    def runtest(self):
        scss_file = self.fspath
        css_file = scss_file.new(ext='css')

        with scss_file.open('rb') as fh:
            source = fh.read()
        with css_file.open('rb') as fh:
            # Output is Unicode, so decode this here
            expected = fh.read().decode('utf8')

        scss.config.STATIC_ROOT = str(scss_file.dirpath('static'))

        compiler = scss.Scss(
            scss_opts=dict(style='expanded'),
            search_paths=[
                str(scss_file.dirpath('include')),
                str(scss_file.dirname),
            ],
        )
        actual = compiler.compile(source)

        # Normalize leading and trailing newlines
        actual = actual.strip('\n')
        expected = expected.strip('\n')

        assert expected == actual
