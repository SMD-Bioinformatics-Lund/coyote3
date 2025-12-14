# Troubleshooting

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| Access denied on sample | Assay mismatch | Add user to the correct assay/assay_group |
| CSRF errors | Missing `SECRET_KEY`/cookie issues | Ensure correct SECRET_KEY and HTTPS in prod |
| LDAP bind fails | Wrong LDAP_* settings | Verify host, bind DN, and secret |
| Slow pages | Missing indexes or heavy queries | Add Mongo indexes, review handler queries |
| Print broken | Missing fonts/assets | Check `print_layout.html` and static paths |

Collect logs from `logs/YYYY/MM/DD/*.log` and correlate with request timestamps.
