from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright

BASE = "http://localhost:6817"
PREFIX = "/coyote3_dev"
LOGIN_USERS = [
    ("coyote3.admin@skane.se", "Coyote3.Admin"),
    ("coyote3.admin", "Coyote3.Admin"),
]
SEED_PATHS = [
    f"{PREFIX}/",
    f"{PREFIX}/dashboard/",
    f"{PREFIX}/samples",
    f"{PREFIX}/public/assay-catalog",
    f"{PREFIX}/search/tiered_variants",
    f"{PREFIX}/admin/",
    f"{PREFIX}/admin/users",
    f"{PREFIX}/admin/roles",
    f"{PREFIX}/admin/permissions",
    f"{PREFIX}/admin/asp/manage",
    f"{PREFIX}/admin/aspc",
    f"{PREFIX}/admin/genelists",
    f"{PREFIX}/admin/schemas",
]


def normalize_href(current_url: str, href: str) -> str | None:
    """Normalize href.

    Args:
        current_url (str): Value for ``current_url``.
        href (str): Value for ``href``.

    Returns:
        str | None: The function result.
    """
    href = (href or "").strip()
    if (
        not href
        or href.startswith("#")
        or href.startswith("javascript:")
        or href.startswith("mailto:")
    ):
        return None
    full = urljoin(current_url, href)
    parsed = urlparse(full)
    if parsed.scheme not in {"http", "https"}:
        return None
    if parsed.netloc and parsed.netloc != urlparse(BASE).netloc:
        return None
    return full


def collect_targets(page) -> tuple[list[str], list[tuple[str, str]]]:
    """Handle collect targets.

    Args:
        page: Value for ``page``.

    Returns:
        tuple[list[str], list[tuple[str, str]]]: The function result.
    """
    urls: set[str] = set()
    actions: list[tuple[str, str]] = []

    hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))")
    for href in hrefs:
        target = normalize_href(page.url, href)
        if target:
            urls.add(target)

    form_actions = page.eval_on_selector_all(
        "form[action]", "els => els.map(e => e.getAttribute('action'))"
    )
    for action in form_actions:
        target = normalize_href(page.url, action)
        if target:
            actions.append(("POST", target))

    button_actions = page.eval_on_selector_all(
        "button[formaction], input[formaction]",
        "els => els.map(e => e.getAttribute('formaction'))",
    )
    for action in button_actions:
        target = normalize_href(page.url, action)
        if target:
            actions.append(("POST", target))

    onclicks = page.eval_on_selector_all(
        "[onclick]", "els => els.map(e => e.getAttribute('onclick'))"
    )
    for js in onclicks:
        if not js:
            continue
        match = re.search(r"location(?:\.href)?\s*=\s*['\"]([^'\"]+)['\"]", js)
        if match:
            target = normalize_href(page.url, match.group(1))
            if target:
                urls.add(target)

    return sorted(urls), actions


def main() -> None:
    """Handle main.

    Returns:
        None.
    """
    results: dict[str, object] = {
        "login_success": False,
        "login_user": None,
        "checked_get": [],
        "checked_post": [],
        "broken": [],
        "notes": [],
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        initial = page.goto(BASE + f"{PREFIX}/", wait_until="domcontentloaded", timeout=30000)
        if initial is None:
            results["broken"].append({"method": "GET", "url": BASE + "/", "status": "NO_RESPONSE"})

        for user, pwd in LOGIN_USERS:
            page.goto(BASE + f"{PREFIX}/", wait_until="domcontentloaded", timeout=30000)
            if page.locator("input[name='username']").count() == 0:
                continue
            page.fill("input[name='username']", user)
            page.fill("input[name='password']", pwd)
            page.click("button[type='submit']")
            page.wait_for_timeout(1200)
            current_url = page.url
            if (
                "/dashboard" in current_url
                or "/samples" in current_url
                or "/?next=" not in current_url
            ):
                content = page.content().lower()
                if "invalid credentials" not in content and "login failed" not in content:
                    results["login_success"] = True
                    results["login_user"] = user
                    break

        if not results["login_success"]:
            results["notes"].append(
                "Could not authenticate with known local credentials; crawl is limited to guest-visible routes."
            )

        to_visit = [urljoin(BASE, path) for path in SEED_PATHS]
        # Pull sample-specific DNA/RNA paths from the samples page so we can validate deep links too.
        try:
            page.goto(
                urljoin(BASE, f"{PREFIX}/samples"), wait_until="domcontentloaded", timeout=30000
            )
            sample_links, _ = collect_targets(page)
            sample_specific = [
                link
                for link in sample_links
                if "/dna/sample/" in link
                or "/rna/sample/" in link
                or "/coyote3_dev/dna/sample/" in link
                or "/coyote3_dev/rna/sample/" in link
            ]
            to_visit.extend(sample_specific[:30])
            if not sample_specific:
                results["notes"].append("No sample-specific DNA/RNA links were found on /samples.")
        except Exception as exc:  # noqa: BLE001
            results["notes"].append(f"Failed to extract sample links from /samples: {exc}")

        seen: set[str] = set()
        max_pages = 120

        while to_visit and len(seen) < max_pages:
            url = to_visit.pop(0)
            if url in seen:
                continue
            seen.add(url)
            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
                status = response.status if response is not None else "NO_RESPONSE"
                results["checked_get"].append({"url": url, "status": status})
                if isinstance(status, int) and status >= 400:
                    results["broken"].append({"method": "GET", "url": url, "status": status})
                    continue

                links, actions = collect_targets(page)
                prioritized_links: list[str] = []
                secondary_links: list[str] = []
                for link in links:
                    if link in seen or link in to_visit:
                        continue
                    path = urlparse(link).path
                    if path.startswith("/public/gene/"):
                        continue
                    if path.startswith(
                        (
                            "/dashboard",
                            "/samples",
                            "/dna",
                            "/rna",
                            "/admin",
                            "/public",
                            "/search",
                            "/profile",
                            "/handbook",
                            "/cov",
                            "/coyote3_dev",
                        )
                    ):
                        if path.startswith(
                            (
                                "/dashboard",
                                "/samples",
                                "/dna",
                                "/rna",
                                "/admin",
                                "/profile",
                                "/cov",
                                "/coyote3_dev/dashboard",
                                "/coyote3_dev/samples",
                                "/coyote3_dev/dna",
                                "/coyote3_dev/rna",
                                "/coyote3_dev/admin",
                                "/coyote3_dev/profile",
                                "/coyote3_dev/cov",
                            )
                        ):
                            prioritized_links.append(link)
                        else:
                            secondary_links.append(link)
                to_visit.extend(prioritized_links + secondary_links)

                request_client = context.request
                for method, target in actions:
                    head_response = request_client.fetch(target, method="HEAD")
                    probe_status = head_response.status
                    if probe_status in (405, 501):
                        get_response = request_client.get(target)
                        probe_status = get_response.status
                    results["checked_post"].append({"url": target, "probe_status": probe_status})
                    if probe_status >= 500:
                        results["broken"].append(
                            {"method": method, "url": target, "status": probe_status}
                        )
            except Exception as exc:  # noqa: BLE001
                results["broken"].append(
                    {"method": "GET", "url": url, "status": f"EXCEPTION: {exc}"}
                )

        browser.close()

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
