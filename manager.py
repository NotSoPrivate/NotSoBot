import asyncio
import json
import os
import sys

loop = asyncio.get_event_loop()

#config
shard_count = 16 * 20
chunks = 6


def shard_chunker():
	shards = list(range(shard_count))
	return [shards[i:i + chunks] for i in range(0, len(shards), chunks)]


async def run_process(cmd, r=False):
	proc = await asyncio.create_subprocess_shell(
		cmd, stdout=asyncio.subprocess.PIPE, loop=loop)
	if r:
		data, _ = await proc.communicate()
		return data.decode().strip() if data else None
	await proc.wait()


async def get_containers():
	out = await run_process('docker ps --format "{{.ID}} {{.Names}}"', True)
	return [x.split() for x in out.split('\n')] if out else []


async def is_running(bot):
	cs = await get_containers()
	try:
		an = [x for x in cs if x[1] == bot][0]
		return an
	except IndexError:
		return False


async def start(bot, shards, idx):
	# Remote Debugging Port
	dport = 5000 + idx
	await run_process(f"docker run --name {bot} --restart on-failure:3 --cap-add SYS_PTRACE " \
										f"-e \"SHARDS={shards}\" -e SHARD_COUNT={shard_count} -e TOKENS='{tokens}' " \
										f"-dti -p 127.0.0.1:{dport}:5678 -v ~/discord_logs:/logs notsobot")
	#number of shards * ratelimit + x seconds for init
	time = (chunks * 5) + 15
	await asyncio.sleep(time)


async def stop(bot):
	check = await is_running(bot)
	if check:
		i = check[0]
		await run_process(f'docker stop {i} && docker rm {i}')
		return True


async def restart(bot, shards, idx):
	s = await stop(bot)
	await start(bot, shards, idx)
	base = 'Restarted' if s else 'Started'
	print(f'{base} NotSoBot #{idx}')


async def restart2(bot):
	check = await is_running(bot)
	if check:
		i = check[0]
		await run_process(f'docker restart {i}')
		return True


TARGETS = "../dockprom/prometheus/targets.json"
async def update_prometheus():
	ips = []
	for i in range(len(shard_chunker())):
		bot = fmt_bot(i)
		ip = await run_process(
			"docker inspect --format " \
			f"'{{{{.NetworkSettings.IPAddress}}}}' {bot}",
			True
		)
		ips.append(ip)

	tgs = []
	tgs.append({
		"targets": [f"{ip}:8000" for ip in ips],
		"labels": {
			"job": "bot"
		}
	})

	fn = f"{TARGETS}.new"
	with open(fn, 'w') as f:
		json.dump(tgs, f)
		f.flush()
		os.fsync(f.fileno())

	os.rename(fn, TARGETS)


def fmt_bot(i):
	return f'bot{i}' if i > 9 else f'bot0{i}'


async def main(func, so=None):
	if func == 'selfbot':
		return await restart('selfbot', None, 99)

	shards = shard_chunker()
	if so:
		shards = [shards[so]]

	futs = []
	for i, c in enumerate(shards):
		bot = fmt_bot(i)
		sl = ','.join(map(str, c))
		if func == 'start':
			await start(bot, sl, i)
		elif func == 'stop':
			futs.append(stop(bot))
		elif func == 'restart':
			await restart(bot, sl, i)
		elif func == 'restart2':
			await restart2(bot)

	await asyncio.gather(*futs)

	await update_prometheus()


async def delete_lock():
	import aioredis

	pool = await aioredis.create_redis_pool(
		('192.168.15.16', 6379),
		db=0, password="szHx6cskwZGXg62J",
		maxsize=3
	)

	await pool.delete("identify")

	pool.close()
	await pool.wait_closed()


if __name__ == "__main__":
	op = sys.argv[1] if len(sys.argv) > 1 else 'restart'
	if op == "stop":
		loop.run_until_complete(delete_lock())

	if op in ('start', 'restart'):
		keys = [x for x in os.environ if x.startswith('token_')]
		if not keys:
			quit('import the tokens bro')
		tokens = json.dumps({x[6:]: os.environ[x] for x in keys})

	loop.run_until_complete(
		main(op,
			int(sys.argv[2]) if len(sys.argv) > 2 else None
		)
	)
