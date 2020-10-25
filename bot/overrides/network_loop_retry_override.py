from time import sleep

from telegram import TelegramError
from telegram.error import NetworkError, InvalidToken, RetryAfter, TimedOut


def _network_loop_retry(self, action_cb, onerr_cb, description, interval):
    """Perform a loop calling `action_cb`, retrying after network errors.

    Stop condition for loop:
        `self.running` evaluates False
        or return value of `action_cb` evaluates False.

    Args:
        action_cb (:obj:`callable`):
            Network oriented callback function to call.
        onerr_cb (:obj:`callable`):
            Callback to call when TelegramError is caught. Receives the
            exception object as a parameter.
        description (:obj:`str`):
            Description text to use for logs and exception raised.
        interval (:obj:`float` | :obj:`int`):
            Interval to sleep between each call to `action_cb`.

    """
    self.logger.debug('Start network loop retry %s', description)
    cur_interval = interval
    while self.running:
        try:
            if not action_cb():
                break
        except RetryAfter as e:
            self.logger.info('%s', e)
            cur_interval = 0.5 + e.retry_after
        except TimedOut as toe:
            self.logger.debug('Timed out %s: %s', description, toe)
            # If failure is due to timeout, we should retry asap.
            cur_interval = 0
        except NetworkError as e:
            self.logger.error('%s', e)
            minimum_cur_interval = cur_interval if cur_interval >= 10 else 10
            cur_interval = self._increase_poll_interval(minimum_cur_interval)
        except InvalidToken as pex:
            self.logger.error('Invalid token; aborting')
            raise pex
        except TelegramError as te:
            self.logger.error('Error while %s: %s', description, te)
            onerr_cb(te)
            cur_interval = self._increase_poll_interval(cur_interval)
        else:
            cur_interval = interval

        if cur_interval:
            sleep(cur_interval)
