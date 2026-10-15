"""
CLI entry point for Website Health & Quality Inspector.
"""

import sys
import asyncio
from pathlib import Path
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .config import SiteConfig
from .runner import AuditRunner
from .reporter.html import HTMLReporter
from .reporter.json_rep import JSONReporter
from .reporter.markdown import MarkdownReporter
from .models import IssueSeverity

console = Console()


@click.group()
def cli():
    """Website Health & Quality Inspector powered by Playwright."""
    pass


@cli.command("audit")
@click.option("--config", "-c", "config_file", type=click.Path(exists=True), help="Path to YAML configuration file.")
@click.option("--url", "-u", help="Direct URL of the target website to inspect.")
@click.option("--crawl", is_flag=True, default=False, help="Enable automatic same-domain crawling.")
@click.option("--max-pages", default=10, type=int, help="Maximum pages to visit when crawling.")
@click.option("--output-dir", "-o", default="reports", help="Directory where reports and screenshots will be saved.")
@click.option("--headed", is_flag=True, default=False, help="Launch browser in headed mode (visible UI).")
def audit(config_file, url, crawl, max_pages, output_dir, headed):
    """Run full website health audit and produce HTML, JSON, and Markdown reports."""
    if not config_file and not url:
        console.print("[bold red]錯誤：[/bold red] 請提供 --config <path.yaml> 或 --url <https://...>")
        sys.exit(1)

    if config_file:
        config = SiteConfig.from_yaml(config_file)
    else:
        config = SiteConfig.from_url(url=url, crawl=crawl, max_pages=max_pages)

    if headed:
        config.headless = False

    console.print(
        Panel.fit(
            f"[bold cyan]網站全方位健康檢查工具[/bold cyan]\n"
            f"[dim]目標名稱:[/dim] {config.name}\n"
            f"[dim]目標網址:[/dim] {config.base_url}\n"
            f"[dim]檢查頁面數:[/dim] {len(config.routes)} 頁 (自動爬取: {'開啟' if config.crawl_enabled else '關閉'})\n"
            f"[dim]報告輸出目錄:[/dim] {output_dir}",
            border_style="cyan"
        )
    )

    runner = AuditRunner(config=config, output_dir=output_dir)

    with console.status("[bold green]Playwright 正在巡檢各頁面...[/bold green]", spinner="dots"):
        report = asyncio.run(runner.run())

    # Generate Reports
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    html_file = out_path / "report.html"
    json_file = out_path / "report.json"
    md_file = out_path / "report.md"

    HTMLReporter.export(report, html_file)
    JSONReporter.export(report, json_file)
    MarkdownReporter.export(report, md_file)

    # Print summary table
    s = report.summary
    table = Table(title="巡檢統計摘要 (Audit Summary)", border_style="dim")
    table.add_column("指標", style="bold")
    table.add_column("數值", justify="right")

    table.add_row("總受測頁面", str(s.total_pages))
    table.add_row("正常通過 (Passed)", f"[green]{s.passed_pages}[/green]")
    table.add_row("異常頁面 (Failed)", f"[red]{s.failed_pages}[/red]" if s.failed_pages else "0")
    table.add_row("致命問題 (Critical)", f"[bold red]{s.total_critical}[/bold red]" if s.total_critical else "0")
    table.add_row("警告項目 (Warning)", f"[yellow]{s.total_warning}[/yellow]" if s.total_warning else "0")
    table.add_row("總耗時", f"{s.duration_seconds} 秒")
    console.print(table)

    # Print per-page quick breakdown
    page_table = Table(title="頁面檢測明細 (Per-Page Status)", border_style="dim")
    page_table.add_column("路徑", style="cyan")
    page_table.add_column("HTTP", justify="center")
    page_table.add_column("耗時", justify="right")
    page_table.add_column("狀態", justify="center")
    page_table.add_column("問題數", justify="right")

    for p in report.pages:
        status_str = "[bold red]FAIL[/bold red]" if p.has_critical else ("[yellow]WARN[/yellow]" if p.has_warning else "[green]PASS[/green]")
        page_table.add_row(
            p.route_path,
            str(p.http_status or "N/A"),
            f"{p.load_time_ms}ms",
            status_str,
            str(len(p.issues))
        )
    console.print(page_table)

    console.print(f"\n[bold green]✓ 檢查完成！已產生三種格式報告：[/bold green]")
    console.print(f"  • HTML 儀表板: [bold underline]{html_file.resolve()}[/bold underline]")
    console.print(f"  • Markdown 摘要: [bold underline]{md_file.resolve()}[/bold underline]")
    console.print(f"  • JSON 完整資料: [bold underline]{json_file.resolve()}[/bold underline]\n")

    if s.total_critical > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    cli()
