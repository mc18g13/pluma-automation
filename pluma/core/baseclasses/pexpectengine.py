import pexpect
import pexpect.fdpexpect

from typing import List

from pluma.core.baseclasses import ConsoleEngine, MatchResult
from .logging import Logger

log = Logger()


class PexpectEngine(ConsoleEngine):
    def __init__(self, linesep: str = None, encoding: str = None, raw_logfile: str = None):
        super().__init__(linesep=linesep, encoding=encoding,
                         raw_logfile=raw_logfile)
        self._pex = None

    def _open_process(self, command: str):
        self._pex = pexpect.spawn(command, timeout=0.01)
        self._on_opened()

    def _open_fd(self, fd):
        self._pex = pexpect.fdpexpect.fdspawn(fd=fd, timeout=0.5)
        self._on_opened()

    def _on_opened(self):
        self._pex.timeout = 0.5

        if self.raw_logfile:
            assert self._raw_logfile_fd
            self._pex.logfile = self._raw_logfile_fd

    @property
    def is_open(self):
        return bool(self._pex and self._pex.isalive())

    def _close_fd(self):
        # Nothing to do, FD closed at a higher level
        self._pex = None

    def _close_process(self):
        self._pex.sendintr()
        self._pex = None

    def send(self, data: str):
        assert self.is_open
        self._pex.send(data)

    def send_control(self, char: str):
        assert self.is_open

        code_ascii_value = ord(char.upper()) - ord('A') + 1
        if code_ascii_value not in range(1, 27):
            raise AttributeError('Control character must be A-Z')

        code = bytes([code_ascii_value])
        self._pex.send(code)

    def _read_from_console(self) -> str:
        received = ''
        try:
            while 1:
                received += self.decode(
                    self._pex.read_nonblocking(1, 0.01))
        except pexpect.TIMEOUT:
            pass
        except pexpect.EOF:
            pass

        return received

    def wait_for_match(self, match: List[str], timeout: int = None) -> MatchResult:
        '''Wait a maximum duration of 'timeout' for a matching regex'''
        assert self.is_open

        timeout = timeout or self._pex.timeout

        if not isinstance(match, list):
            match = [match]

        log.debug(f'Waiting up to {timeout}s for patterns: {match}...')

        matched_regex = None
        try:
            index = self._pex.expect(match, timeout)
            matched_regex = match[index]
        except pexpect.EOF:
            pass
        except pexpect.TIMEOUT:
            pass

        if matched_regex:
            log.debug(f'Matched {matched_regex}')
        else:
            log.debug('No match found before timeout or EOF')

        # Pexpect exposes received via '.before'
        received = self._pex.before
        if matched_regex:
            matched_text = self._pex.after
            received += matched_text
        else:
            matched_regex = None
            matched_text = None

        return MatchResult(regex_matched=matched_regex,
                           text_matched=self.decode(matched_text),
                           text_received=self.decode(received))

    def interact(self):
        assert self.is_open
        self._pex.interact()
