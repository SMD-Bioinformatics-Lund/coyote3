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

output_path=/etc/nginx/conf.d/default.conf

cat >/etc/nginx/conf.d/observability.conf <<'EOF'
access_log syslog:server=monitor:5514,tag=ui,severity=info combined;
error_log syslog:server=monitor:5514,tag=ui error;
EOF

if [ -n "$script_name" ] && [ "$script_name" != "/" ]; then
  cat >"$output_path" <<EOF
server {
    listen 3000;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

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
  cat >"$output_path" <<'EOF'
server {
    listen 3000;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
EOF
fi

exec "$@"
