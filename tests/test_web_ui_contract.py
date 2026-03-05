"""
Structural HTML contract tests for web UI shell.

Ensures the frontend HTML contains required IDs and sections for screenshot parity.
These tests validate structure only; no JS behavior is tested here.
"""

from pathlib import Path


def _load_html() -> str:
    """Load the main web HTML template."""
    html_path = Path(__file__).parent.parent / "src" / "legacylens" / "web" / "index.html"
    return html_path.read_text(encoding="utf-8")


def test_web_shell_contains_screenshot_sections() -> None:
    """Verify core screenshot-parity sections exist with correct IDs."""
    html = _load_html()

    # Required IDs per UI parity spec
    required_ids = [
        "dataset-strip",
        "query-kpis",
        "analytics-panel",
        "query-log-list",
        "sources-title",
    ]

    missing = []
    for elem_id in required_ids:
        if f'id="{elem_id}"' not in html:
            missing.append(elem_id)

    assert not missing, f"Missing required HTML IDs: {', '.join(missing)}"


def test_web_shell_contains_analytics_chart_mounts() -> None:
    """Verify analytics chart mount points exist for later wiring."""
    html = _load_html()

    # Chart mount IDs: placeholder divs for future chart rendering
    chart_mounts = [
        "similarity-chart",
        "division-chart",
        "chunk-type-chart",
    ]

    missing = []
    for mount_id in chart_mounts:
        if f'id="{mount_id}"' not in html:
            missing.append(mount_id)

    assert not missing, f"Missing chart mount IDs: {', '.join(missing)}"


def test_web_shell_contains_kpi_stat_elements() -> None:
    """Verify KPI row has stat placeholder elements."""
    html = _load_html()

    # KPI stat IDs should be present
    kpi_stats = [
        "stat-latency",
        "stat-top1",
        "stat-hybrid",
        "stat-hits",
    ]

    missing = []
    for stat_id in kpi_stats:
        if f'id="{stat_id}"' not in html:
            missing.append(stat_id)

    assert not missing, f"Missing KPI stat IDs: {', '.join(missing)}"


def test_web_shell_contains_query_log_structure() -> None:
    """Verify query log list container exists."""
    html = _load_html()

    # Query log should have a list container
    assert 'id="log-entries"' in html, "Missing query log entries container (id='log-entries')"

    # Should also have clear button
    assert 'id="clear-log-btn"' in html, "Missing clear log button (id='clear-log-btn')"


def test_web_shell_contains_dataset_structure() -> None:
    """Verify dataset strip has required elements."""
    html = _load_html()

    # Dataset list container
    assert 'id="dataset-list"' in html, "Missing dataset list container (id='dataset-list')"

    # Dataset label
    assert 'id="dataset-label"' in html, "Missing dataset label (id='dataset-label')"


def test_web_shell_has_dark_theme_css_classes() -> None:
    """Verify CSS classes for dark console layout exist."""
    css_path = Path(__file__).parent.parent / "src" / "legacylens" / "web" / "styles.css"
    css = css_path.read_text(encoding="utf-8")

    # Key dark theme selectors should be present
    required_selectors = [
        ".kpi-row",
        ".kpi-card",
        ".dataset-strip",
        ".analytics-panel",
        ".chart-mount",
        ".query-log",
        ".log-entry",
    ]

    missing = []
    for selector in required_selectors:
        if selector not in css:
            missing.append(selector)

    assert not missing, f"Missing CSS selectors: {', '.join(missing)}"


def test_web_shell_responsive_mobile_rules() -> None:
    """Verify responsive mobile breakpoints are defined."""
    css_path = Path(__file__).parent.parent / "src" / "legacylens" / "web" / "styles.css"
    css = css_path.read_text(encoding="utf-8")

    # Should have mobile breakpoints
    assert "@media (max-width: 980px)" in css, "Missing tablet breakpoint"
    assert "@media (max-width: 640px)" in css, "Missing mobile breakpoint"
