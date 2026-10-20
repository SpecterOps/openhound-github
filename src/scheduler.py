"""Start the BloodHound Enterprise scheduler for the configured collector."""

import logging

import dlt

from openhound.scheduler.service import Service

logger = logging.getLogger(__name__)


def start() -> None:
    collector_name = dlt.config["destination.bloodhoundenterprise.collector_name"]
    logger.info("Initializing service for collector '%s'.", collector_name)
    service = Service(
        bhe_uri=dlt.secrets["destination.bloodhoundenterprise.url"],
        token_key=dlt.secrets["destination.bloodhoundenterprise.token_key"],
        token_id=dlt.secrets["destination.bloodhoundenterprise.token_id"],
        collector_name=collector_name,
    )
    service.start()


if __name__ == "__main__":
    start()
