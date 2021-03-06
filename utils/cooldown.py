# -*- coding: utf-8 -*-
"""
The MIT License (MIT)

Copyright (c) 2015-2016 Rapptz

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

import time

__all__ = ['Cooldown', 'CooldownMapping']

class Cooldown:
	__slots__ = ['rate', 'per', '_window', '_tokens', '_last']

	def __init__(self, rate, per):
		self.rate = int(rate)
		self.per = float(per)
		self._window = 0.0
		self._tokens = self.rate
		self._last = 0.0

	def is_rate_limited(self):
		current = time.time()
		self._last = current

		# first token used means that we start a new rate limit window
		if self._tokens == self.rate:
			self._window = current

		# check if our window has passed and we can refresh our tokens
		if current > self._window + self.per:
			self._tokens = self.rate
			self._window = current

		# check if we're rate limited
		if self._tokens == 0:
			return self.per - (current - self._window)

		# we're not so decrement our tokens
		self._tokens -= 1

		# see if we got rate limited due to this token change, and if
		# so update the window to point to our current time frame
		if self._tokens == 0:
			self._window = current

	def reset(self):
		self._tokens = self.rate
		self._last = 0.0

	def copy(self):
		return Cooldown(self.rate, self.per)

	def __repr__(self):
		return '<Cooldown rate: {0.rate} per: {0.per} window: {0._window} tokens: {0._tokens}>'.format(self)

class CooldownMapping:
	def __init__(self, original):
		self._cache = {}
		self._cooldown = original

	def _bucket_key(self, ctx):
		return getattr(ctx.guild, 'id', ctx.author.id)

	def _verify_cache_integrity(self):
		# we want to delete all cache objects that haven't been used
		# in a cooldown window. e.g. if we have a  command that has a
		# cooldown of 60s and it has not been used in 60s then that key should be deleted
		current = time.time()
		dead_keys = [k for k, v in self._cache.items() if current > v._last + v.per]
		for k in dead_keys:
			del self._cache[k]

	def get_bucket(self, ctx):
		self._verify_cache_integrity()
		key = self._bucket_key(ctx)
		if key not in self._cache:
			bucket = self._cooldown.copy()
			self._cache[key] = bucket
		else:
			bucket = self._cache[key]

		return bucket