#!/bin/sh
set -eu

output_path="${COYOTE3_NGINX_OUTPUT_PATH:-/etc/nginx/conf.d/default.conf}"
frontend_upstream="${COYOTE3_NGINX_FRONTEND_UPSTREAM:?COYOTE3_NGINX_FRONTEND_UPSTREAM is required}"
api_upstream="${COYOTE3_NGINX_API_UPSTREAM:?COYOTE3_NGINX_API_UPSTREAM is required}"
docs_upstream="${COYOTE3_NGINX_DOCS_UPSTREAM:?COYOTE3_NGINX_DOCS_UPSTREAM is required}"

script_name="${SCRIPT_NAME:-}"
case "$script_name" in
  "")
    ;;
  /*)
    ;;
  *)
    script_name="/$script_name"
    ;;
esac

while [ "$script_name" != "/" ] && [ "${script_name%/}" != "$script_name" ]; do
  script_name="${script_name%/}"
done

cat >"$output_path" <<EOF
server {
    listen 8088;
    server_name _;

    client_max_body_size 200m;

    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_http_version 1.1;
    proxy_read_timeout 120s;

    location /api/ {
        proxy_pass ${api_upstream}/api/;
    }

    location /docs-site/ {
        proxy_pass ${docs_upstream}/;
    }
EOF

if [ -n "$script_name" ] && [ "$script_name" != "/" ]; then
  cat >>"$output_path" <<EOF

    location = ${script_name} {
        return 308 ${script_name}/;
    }

    location ${script_name}/api/ {
        proxy_set_header X-Forwarded-Prefix ${script_name};
        rewrite ^${script_name}(/api/.*)\$ \$1 break;
        proxy_pass ${api_upstream};
    }

    location ${script_name}/docs-site/ {
        proxy_set_header X-Forwarded-Prefix ${script_name};
        rewrite ^${script_name}/docs-site/?(.*)\$ /\$1 break;
        proxy_pass ${docs_upstream};
    }

    location ${script_name}/ {
        proxy_set_header X-Forwarded-Prefix ${script_name};
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        rewrite ^${script_name}(/.*)\$ \$1 break;
        proxy_pass ${frontend_upstream};
    }
EOF
fi

cat >>"$output_path" <<EOF

    location / {
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_pass ${frontend_upstream}/;
    }
}
EOF
