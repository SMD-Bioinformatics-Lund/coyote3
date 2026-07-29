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
    absolute_redirect off;
    port_in_redirect off;
    server_name_in_redirect off;

    # Resolve Docker service names at request time so a deliberate upstream
    # recreate cannot leave Nginx pinned to an obsolete container IP address.
    resolver 127.0.0.11 valid=10s ipv6=off;
    resolver_timeout 5s;
    set \$frontend_target "${frontend_upstream}";
    set \$api_target "${api_upstream}";
    set \$docs_target "${docs_upstream}";

    client_max_body_size 200m;

    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_http_version 1.1;
    proxy_read_timeout 120s;
EOF

if [ -n "$script_name" ] && [ "$script_name" != "/" ]; then
  cat >>"$output_path" <<EOF

    location /api/ {
        if (\$http_x_forwarded_prefix != "${script_name}") {
            return 404;
        }
        proxy_set_header X-Forwarded-Prefix ${script_name};
        proxy_pass \$api_target;
    }

    location /docs-site/ {
        if (\$http_x_forwarded_prefix != "${script_name}") {
            return 404;
        }
        proxy_set_header X-Forwarded-Prefix ${script_name};
        rewrite ^/docs-site/?(.*)\$ /\$1 break;
        proxy_pass \$docs_target;
    }

    location = ${script_name} {
        proxy_set_header X-Forwarded-Prefix ${script_name};
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_pass \$frontend_target${script_name}/;
    }

    location ${script_name}/api/ {
        proxy_set_header X-Forwarded-Prefix ${script_name};
        rewrite ^${script_name}(/api/.*)\$ \$1 break;
        proxy_pass \$api_target;
    }

    location ${script_name}/docs-site/ {
        proxy_set_header X-Forwarded-Prefix ${script_name};
        rewrite ^${script_name}/docs-site/?(.*)\$ /\$1 break;
        proxy_pass \$docs_target;
    }

    location ${script_name}/ {
        proxy_set_header X-Forwarded-Prefix ${script_name};
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_pass \$frontend_target;
    }

    location / {
        if (\$http_x_forwarded_prefix != "${script_name}") {
            return 404;
        }
        proxy_set_header X-Forwarded-Prefix ${script_name};
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        rewrite ^/\$ ${script_name}/ break;
        rewrite ^(.+)\$ ${script_name}\$1 break;
        proxy_pass \$frontend_target;
    }
EOF
else
  cat >>"$output_path" <<EOF

    location /api/ {
        proxy_pass \$api_target;
    }

    location /docs-site/ {
        rewrite ^/docs-site/?(.*)\$ /\$1 break;
        proxy_pass \$docs_target;
    }

    location / {
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_pass \$frontend_target/;
    }
EOF
fi

cat >>"$output_path" <<EOF
}
EOF
