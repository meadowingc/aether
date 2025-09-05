# Run Phoenix in dev
dev:
	mix phx.server

# Initial setup (deps + migrate) in dev
setup:
	mix deps.get && mix ecto.migrate

# Run prod migrations (requires env vars + built release or Mix in prod)
migrate:
	MIX_ENV=prod mix ecto.migrate

assets:
	MIX_ENV=prod mix assets.deploy

# Full production release build
# Requires env vars:
#   SECRET_KEY_BASE (mix phx.gen.secret)
#   DATABASE_PATH (absolute path to sqlite file)
#   PHX_SERVER=true
# Optional: PORT (default 4000), ADMIN_USER, ADMIN_PASS
release:
	MIX_ENV=prod mix deps.get --only prod
	MIX_ENV=prod mix compile
	MIX_ENV=prod mix assets.deploy
	MIX_ENV=prod mix release --overwrite

	cp .env _build/prod/rel/aether_phx/.env

# Start release (expects _build/prod/rel/aether_phx created by release)
run-prod: release
	_build/prod/rel/aether_phx/bin/aether_phx eval "AetherPhx.Release.migrate"
	PORT=$${PORT:-4000} PHX_HOST=aether.meadow.cafe PHX_SERVER=true _build/prod/rel/aether_phx/bin/aether_phx start

# Start with IEx attached (daemonized code introspection)
daemon:
	cd _build/prod/rel/aether_phx && PORT=$${PORT:-4000} ./bin/aether_phx start_iex

# Remote console into running node
console:
	cd _build/prod/rel/aether_phx && ./bin/aether_phx remote

# Clean build artifacts
clean:
	mix clean && rm -rf _build/prod
