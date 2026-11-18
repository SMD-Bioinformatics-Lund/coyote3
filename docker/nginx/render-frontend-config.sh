#!/bin/sh
set -eu

script_name="${SCRIPT_NAME:-}"
case "$script_name" in
  "") ;;
  /*) ;;
  *) script_name="/$script_name" ;;
esac

while [ "$script_name" != "/" ] && [ "${script_name%/}" != "$script_name" ]; do
  script_name="${script_name%/}"
done

config_directory="${COYOTE4_FRONTEND_NGINX_DIRECTORY:-/etc/nginx/conf.d}"
output_path="$config_directory/default.conf"
frontend_root="${COYOTE4_FRONTEND_ROOT:-/usr/share/nginx/html}"
listen_address="${COYOTE4_FRONTEND_LISTEN:-3000}"
syslog_target="${COYOTE4_SYSLOG_TARGET:-monitor:5514}"

cat >"$config_directory/observability.conf" <<EOF
access_log syslog:server=${syslog_target},tag=ui,severity=info combined;
error_log syslog:server=${syslog_target},tag=ui error;
EOF

cat >"$config_directory/frontend-compression.conf" <<'EOF'
gzip on;
gzip_vary on;
gzip_proxied any;
gzip_comp_level 5;
gzip_min_length 1024;
gzip_types text/css application/javascript application/json image/svg+xml;
EOF

if [ -n "$script_name" ] && [ "$script_name" != "/" ]; then
  cat >"$output_path" <<EOF
server {
    listen ${listen_address};
    server_name _;
    root "${frontend_root}";
    index index.html;
    add_header Cache-Control "no-cache";

    location ^~ ${script_name}/assets/ {
        rewrite ^${script_name}/(.*)\$ /\$1 break;
        try_files \$uri =404;
        add_header Cache-Control "public, max-age=31536000, immutable";
    }

    location = ${script_name} {
        try_files /index.html =404;
    }

    location = ${script_name}/ {
        try_files /index.html =404;
    }

    location ${script_name}/ {
        rewrite ^${script_name}/(.*)\$ /\$1 break;
        try_files \$uri @frontend_shell;
    }

    location @frontend_shell {
        try_files /index.html =404;
    }

    location / {
        return 404;
    }
}
EOF
else
  cat >"$output_path" <<EOF
server {
    listen ${listen_address};
    server_name _;
    root "${frontend_root}";
    index index.html;
    add_header Cache-Control "no-cache";

    location ^~ /assets/ {
        try_files \$uri =404;
        add_header Cache-Control "public, max-age=31536000, immutable";
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF
fi

exec "$@"
