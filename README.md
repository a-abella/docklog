# docklog
Tail multiple Docker container logs simultaneously with `docker-compose logs` style output, like you'd expect `docker logs` should.

Specify the Docker daemon to connect to with the `DOCKER_HOST=...` environment variable. Defaults to `unix://var/run/docker.sock`

![Sample output](https://i.imgur.com/qLUovZF.gif)

```
usage: docklog.py [-h] [-t] [-n TAIL] [-s] CONTAINER [CONTAINER ...]

Simultaneously stream the logs of up to eight Docker containers

positional arguments:
  CONTAINER             Container names or IDs

optional arguments:
  -h, --help            show this help message and exit
  -t, --timestamps, --time
                        Prepend timestamps to log lines
  -n TAIL, --tail TAIL  Number of lines to show from end (default 10)
  -s, --static          Do not follow; print tail lines and exit
```

```
DOCKER_HOST=$swarm_host ./docklog.py --tail=20 --timestamps $(docker ps --filter "name=nginx" --format "{{.ID}}")
```
