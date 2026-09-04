# Deployment and recovery

The supported production shape is one xassemble container behind Caddy. Caddy is the only
service with published ports; the application and its SQLite volume remain private to the
Compose network.

## First deployment

Prerequisites:

- a Linux VM with Docker Engine and the Compose plugin;
- a DNS record for the application hostname pointing to the VM;
- inbound TCP ports 80 and 443, and UDP port 443, allowed by the firewall.

Create the production environment file and replace both example values:

```sh
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
editor .env
```

The secret must remain stable across restarts; changing it immediately invalidates every login.

> **User-management schema upgrade:** this release intentionally has no migration for databases
> created by an earlier version. Back up anything you need, remove the old application database,
> deploy the new version, and create the first account with
> `docker compose run --rm --no-deps xassemble xassemble-user add admin --name "Administrator" --admin`.
Do not commit `.env`.

Build and start the services, then create the first user interactively:

```sh
docker compose up -d --build --wait
docker compose exec xassemble xassemble-user add editor --name "Example Editor"
docker compose ps
```

Caddy obtains and renews the public TLS certificate for `XASSEMBLE_HOST`. The application uses
secure session cookies in this deployment. Visit `https://<XASSEMBLE_HOST>/health` and expect
`{"status":"ok"}`. A 503 response means the process is running but SQLite failed its integrity
check.

Upgrade by taking a backup, pulling the reviewed source revision, and rebuilding:

```sh
docker compose exec -T xassemble xassemble-db backup /tmp/pre-upgrade.sqlite3
mkdir -p backups
docker compose cp xassemble:/tmp/pre-upgrade.sqlite3 ./backups/pre-upgrade.sqlite3
docker compose exec -T xassemble rm -f /tmp/pre-upgrade.sqlite3
docker compose up -d --build --wait
```

## Back up

`xassemble-db backup` uses SQLite's online backup API, so it produces a consistent snapshot while
the application is serving requests. The command then performs an integrity check and verifies
the xassemble tables before atomically publishing the backup file.

Run the backup in the application container, copy it off the VM, and remove the temporary copy:

```sh
mkdir -p backups
stamp=$(date -u +%Y%m%dT%H%M%SZ)
docker compose exec -T xassemble xassemble-db backup /tmp/xassemble-$stamp.sqlite3
docker compose cp xassemble:/tmp/xassemble-$stamp.sqlite3 ./backups/xassemble-$stamp.sqlite3
docker compose exec -T xassemble rm -f /tmp/xassemble-$stamp.sqlite3
```

The `backups/` directory is ignored by Git, but a backup on the same VM is not disaster recovery.
Copy it to encrypted storage on a separate system and apply an appropriate retention policy.
Periodically perform the restore drill below on a non-production VM.

## Restore

Restore replaces all users, document sets, source Word files, version history, and generation
history with the contents of the selected snapshot. Stop the application first; restoring under
a running process is unsupported.

From the repository directory, with the chosen backup under `./backups`:

```sh
docker compose stop xassemble
docker compose run --rm --no-deps \
  --volume "./backups:/backups:ro" \
  xassemble xassemble-db restore /backups/xassemble-YYYYMMDDTHHMMSSZ.sqlite3 --confirm-replace
docker compose run --rm --no-deps xassemble xassemble-db check
docker compose up -d --wait xassemble
```

Confirm that `/health` is healthy, log in, and download a current questionnaire and template.
Keep the pre-restore database backup until this verification is complete.

## Operational notes

- Persistent application state lives in the Compose volume named `xassemble-data`.
- Do not copy the live SQLite file directly. Use `xassemble-db backup`.
- `docker compose down` preserves named volumes; `docker compose down --volumes` deletes them.
- Run `docker compose logs xassemble` and `docker compose logs caddy` when diagnosing startup or
  certificate failures.
- The runtime container uses an unprivileged user. Do not change ownership of `/data` on a live
  volume unless recovery specifically requires it.
- Run `scripts/container-smoke-test.ps1` on Windows to build an isolated stack and verify startup,
  database-aware health, and persistence across an application restart. Its temporary Compose
  project and volumes are removed afterward.
