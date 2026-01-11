"""
Loan Decision System v2 - Main Orchestrator

Runs the complete pipeline:
1. Extract data from Excel (Python)
2. Evaluate each factor (LLM - parallel)
3. Aggregate results (Python)
4. Make decision (Python)
5. Generate output (Python)
"""
import argparse
import os
import sys
from datetime import datetime
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.panel import Panel

from config.llm_config import LLMConfig
from core.data_extractor import DataExtractor
from core.evaluators import LLMEnsembleEvaluator, run_all_evaluations, run_evaluations_sync
from core.aggregator import aggregate_results
from core.decision_engine import make_decision
from output.generator import OutputGenerator

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Loan Decision System v2")
    parser.add_argument("--input", "-i", required=True, help="Input Excel file")
    parser.add_argument("--model", "-m", default="llama3.1:8b", help="Ollama model")
    parser.add_argument("--sequential", "-s", action="store_true", help="Run evaluations sequentially")
    parser.add_argument("--output-dir", "-o", default="output", help="Output directory")
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        console.print(f"[red]Error: File not found: {args.input}[/red]")
        return 1
    
    console.print(Panel.fit(
        "[bold blue]Loan Decision System v2[/bold blue]\n"
        "[dim]LLM Ensemble Architecture with Deterministic Verification[/dim]",
        title="Starting Pipeline"
    ))
    
    try:
        # =========================================
        # LAYER 1: Data Extraction (Python)
        # =========================================
        console.print("\n[bold cyan]Layer 1:[/bold cyan] Extracting data from Excel...")
        
        extractor = DataExtractor(args.input)
        data = extractor.extract()
        
        # Show extracted data summary
        table = Table(title="Extracted Data", show_header=False, box=None)
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Applicant", data.applicant_name)
        table.add_row("Loan Amount", f"${data.loan_amount:,.0f}")
        table.add_row("Credit Score", str(data.credit_score))
        table.add_row("Annual Income", f"${data.annual_income:,.0f}")
        table.add_row("DTI Ratio", f"{data.dti_ratio}%")
        table.add_row("Liquid Assets", f"${data.liquid_assets:,.0f}")
        console.print(table)
        
        # =========================================
        # LAYER 2: LLM Ensemble Evaluations
        # =========================================
        console.print("\n[bold cyan]Layer 2:[/bold cyan] Running LLM ensemble evaluations...")
        
        # Create ensemble evaluator
        evaluator = LLMEnsembleEvaluator(
            roles=["factor_analyzer", "risk_synthesizer", "decision_maker"],
            use_threshold_override=True,
            confidence_override_threshold=0.7
        )
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console
        ) as progress:
            task = progress.add_task("Evaluating 16 factors with ensemble...", total=100)
            
            if args.sequential:
                evaluations = run_evaluations_sync(evaluator, data)
            else:
                evaluations = run_all_evaluations(evaluator, data)
            
            progress.update(task, completed=100)
        
        console.print(f"[green]✓ Completed {len(evaluations)} evaluations[/green]")
        
        # =========================================
        # LAYER 3: Aggregation (Python)
        # =========================================
        console.print("\n[bold cyan]Layer 3:[/bold cyan] Aggregating results...")
        
        results = aggregate_results(evaluations)
        
        # Show evaluation summary
        table = Table(title="Evaluation Results")
        table.add_column("Status", style="bold")
        table.add_column("Count", justify="right")
        table.add_row("[green]PASS[/green]", str(results.pass_count))
        table.add_row("[yellow]REVIEW[/yellow]", str(results.review_count))
        table.add_row("[red]FAIL[/red]", str(results.fail_count))
        table.add_row("", "")
        table.add_row("[bold]Weighted Score[/bold]", f"[bold]{results.weighted_score}%[/bold]")
        table.add_row("[bold]Avg Risk Score[/bold]", f"[bold]{results.average_risk_score:.1f}[/bold]")
        table.add_row("[bold]Avg Confidence[/bold]", f"[bold]{results.average_confidence:.2f}[/bold]")
        console.print(table)
        
        # =========================================
        # LAYER 4: Decision (Python)
        # =========================================
        console.print("\n[bold cyan]Layer 4:[/bold cyan] Applying business rules...")
        
        decision = make_decision(results)
        
        # Show decision
        if decision.decision == "APPROVED":
            style = "green"
        elif decision.decision == "REJECTED":
            style = "red"
        else:
            style = "yellow"
        
        console.print(Panel(
            f"[bold {style}]{decision.decision}[/bold {style}]\n\n"
            f"[dim]Rule:[/dim] {decision.rule_applied} - {decision.rule_description}\n"
            f"[dim]Risk Level:[/dim] {decision.risk_level}\n\n"
            f"[dim]Recommendation:[/dim]\n{decision.recommendation}",
            title="Final Decision",
            border_style=style
        ))
        
        # =========================================
        # LAYER 5: Output Generation (Python)
        # =========================================
        console.print("\n[bold cyan]Layer 5:[/bold cyan] Generating output files...")
        
        generator = OutputGenerator(args.output_dir)
        
        excel_path = generator.generate_excel(data, results, decision)
        json_path = generator.generate_json(data, results, decision)
        
        console.print(f"[green]✓ Excel:[/green] {excel_path}")
        console.print(f"[green]✓ JSON:[/green] {json_path}")
        
        # Final summary
        console.print(Panel(
            f"[bold]Pipeline Complete[/bold]\n\n"
            f"Applicant: {data.applicant_name}\n"
            f"Decision: [{style}]{decision.decision}[/{style}]\n"
            f"Score: {results.weighted_score}% | Risk: {results.average_risk_score:.1f} | Conf: {results.average_confidence:.2f}\n"
            f"Output: {excel_path}",
            title="Summary",
            border_style="blue"
        ))
        
        return 0
        
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
