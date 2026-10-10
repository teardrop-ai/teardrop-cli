"""Marketplace agent registration validation and test commands."""

from __future__ import annotations

from json import JSONDecodeError
from typing import Annotated

import typer

app = typer.Typer(
    name="agent-registration",
    help="Validate and test your agent endpoint before publishing.",
    no_args_is_help=True,
)


def _make_request(agent_url: str):
    from pydantic import ValidationError
    from teardrop import MarketplaceAgentRegistrationRequest

    from teardrop_cli.formatting import print_error

    try:
        return MarketplaceAgentRegistrationRequest(agent_url=agent_url)
    except ValidationError as exc:
        print_error("--agent-url must contain between 1 and 2048 characters.")
        raise typer.Exit(2) from exc


@app.command()
def preview(
    agent_url: Annotated[
        str, typer.Option("--agent-url", help="Agent endpoint URL (1 to 2048 characters).")
    ],
    as_json: Annotated[
        bool, typer.Option("--json", help="Output the complete response as JSON.")
    ] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Validate agent registration without writing registration data."""
    from pydantic import ValidationError as PydanticValidationError
    from teardrop import TeardropError

    from teardrop_cli import config
    from teardrop_cli.formatting import print_error, print_json, print_table, spinner

    request = _make_request(agent_url)

    try:
        with spinner("Previewing agent registration…"), config.get_sync_client(base_url) as client:
            response = client.preview_agent_registration(request)
    except (JSONDecodeError, PydanticValidationError, TeardropError) as exc:
        print_error(f"Unable to preview agent registration: {exc}")
        raise typer.Exit(1) from exc

    if as_json:
        print_json(response.model_dump(mode="json"))
        return

    rows = [
        ["registrable", "true" if response.registrable else "false"],
        ["detail", response.detail if response.detail is not None else "null"],
    ]
    if response.price_per_task_usdc is not None:
        rows.append(["price_per_task_usdc", str(response.price_per_task_usdc)])
    print_table(["Field", "Value"], rows, title="Agent Registration Preview")


@app.command()
def test(
    agent_url: Annotated[
        str, typer.Option("--agent-url", help="Agent endpoint URL (1 to 2048 characters).")
    ],
    as_json: Annotated[
        bool, typer.Option("--json", help="Output the complete response as JSON.")
    ] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Send one real, unpaid message and show the agent's test checks."""
    from pydantic import ValidationError as PydanticValidationError
    from teardrop import TeardropError

    from teardrop_cli import config
    from teardrop_cli.formatting import (
        print_error,
        print_json,
        print_table,
        print_warning,
        spinner,
    )

    request = _make_request(agent_url)
    client = config.get_sync_client(base_url)
    print_warning(
        "This sends one real message, but it is unpaid and unbilled. Nothing is signed or "
        "settled; a priced agent's expected HTTP 402 is not a charge to you."
    )

    try:
        with spinner("Testing agent registration…"), client:
            response = client.test_agent_registration(request)
    except (JSONDecodeError, PydanticValidationError, TeardropError) as exc:
        print_error(f"Unable to test agent registration: {exc}")
        raise typer.Exit(1) from exc

    if as_json:
        print_json(response.model_dump(mode="json"))
        return

    print_table(
        ["Field", "Value"],
        [["passed", "true" if response.passed else "false"]],
        title="Agent Registration Test",
    )
    if response.checks:
        print_table(
            ["Name", "Status", "Detail"],
            [[check.name, check.status, check.detail] for check in response.checks],
            title="Checks",
        )
