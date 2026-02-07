"""Workflow classes for DAG-based scraping pipelines"""

from typing import Any, Dict, List, Optional


class Filter:
    """Pythonic filter builder for workflow edges."""

    @staticmethod
    def contains(field: str, value: str, case_sensitive: bool = False) -> dict:
        return {"field": field, "operator": "contains", "value": value, "case_sensitive": case_sensitive}

    @staticmethod
    def not_contains(field: str, value: str, case_sensitive: bool = False) -> dict:
        return {"field": field, "operator": "not_contains", "value": value, "case_sensitive": case_sensitive}

    @staticmethod
    def equals(field: str, value: str, case_sensitive: bool = False) -> dict:
        return {"field": field, "operator": "equals", "value": value, "case_sensitive": case_sensitive}

    @staticmethod
    def not_equals(field: str, value: str, case_sensitive: bool = False) -> dict:
        return {"field": field, "operator": "not_equals", "value": value, "case_sensitive": case_sensitive}

    @staticmethod
    def regex_match(field: str, pattern: str, case_sensitive: bool = False) -> dict:
        return {"field": field, "operator": "regex_match", "value": pattern, "case_sensitive": case_sensitive}

    @staticmethod
    def exists(field: str) -> dict:
        return {"field": field, "operator": "exists"}

    @staticmethod
    def not_exists(field: str) -> dict:
        return {"field": field, "operator": "not_exists"}

    @staticmethod
    def gt(field: str, value: str) -> dict:
        return {"field": field, "operator": "gt", "value": value}

    @staticmethod
    def lt(field: str, value: str) -> dict:
        return {"field": field, "operator": "lt", "value": value}

    @staticmethod
    def all(*conditions) -> dict:
        """Combine conditions with AND logic."""
        return {"mode": "all", "conditions": list(conditions)}

    @staticmethod
    def any(*conditions) -> dict:
        """Combine conditions with OR logic."""
        return {"mode": "any", "conditions": list(conditions)}


class WorkflowNode:
    """
    A node in a workflow DAG.

    Nodes represent scraping operations using a specific strategy.
    Start nodes have static URLs, downstream nodes extract URLs from upstream results.
    """

    def __init__(
        self,
        workflow: "Workflow",
        name: str,
        strategy_id: str,
        urls: Optional[List[str]] = None,
        url_field: Optional[str] = None,
        parameter_config: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a workflow node.

        Args:
            workflow: Parent Workflow object
            name: Unique node identifier within the workflow
            strategy_id: Strategy UUID to use for scraping
            urls: Static URLs for start nodes
            url_field: Field name to extract URLs from upstream results (for downstream nodes)
            parameter_config: Optional parameter mapping configuration
            parameters: Optional static API parameter overrides
        """
        self.workflow = workflow
        self.name = name
        self.strategy_id = strategy_id
        self.urls = urls
        self.url_field = url_field
        self.parameter_config = parameter_config
        self.parameters = parameters

    def then(
        self,
        name: str,
        strategy_id: str,
        url_field: str = None,
        parameter_config: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        filter: Optional[Dict[str, Any]] = None,
    ) -> "WorkflowNode":
        """
        Chain a downstream node that extracts URLs from this node's results.

        Args:
            name: Unique node identifier
            strategy_id: Strategy UUID for the downstream scraper
            url_field: Field name in this node's results containing URLs to scrape
            parameter_config: Optional parameter mapping configuration
            parameters: Optional static API parameter overrides
            filter: Optional filter condition or config (use Filter class to build)

        Returns:
            The new downstream WorkflowNode (for further chaining)

        Example:
            index = workflow.start("index", strategy_id, urls=["https://example.com"])
            details = index.then("details", detail_strategy_id, url_field="detail_url")

            # With filter
            details = index.then("details", detail_strategy_id, url_field="link",
                                 filter=Filter.contains("link", "article"))
        """
        node = WorkflowNode(self.workflow, name, strategy_id,
                            url_field=url_field, parameter_config=parameter_config,
                            parameters=parameters)
        self.workflow._nodes.append(node)

        edge = {
            "source_node_key": self.name,
            "target_node_key": name
        }

        if filter:
            # Check if it's already a full config (has "conditions" key)
            if "conditions" in filter:
                edge["filter_config"] = filter
            else:
                # Single condition - wrap it
                edge["filter_config"] = {"mode": "all", "conditions": [filter]}

        self.workflow._edges.append(edge)
        return node

    def to_dict(self) -> Dict[str, Any]:
        """Serialize node for API request."""
        if self.urls:  # Start node with static URLs
            result = {
                "node_key": self.name,
                "strategy_id": self.strategy_id,
                "input_type": "static_urls",
                "static_urls": self.urls
            }
        elif self.url_field:  # Downstream node extracting URLs from upstream
            result = {
                "node_key": self.name,
                "strategy_id": self.strategy_id,
                "input_type": "upstream_urls",
                "url_field": self.url_field
            }
        else:  # Downstream node using parameter mapping (no URL extraction)
            result = {
                "node_key": self.name,
                "strategy_id": self.strategy_id,
                "input_type": "upstream_data"
            }

        if self.parameters:
            result["static_parameters"] = self.parameters
        if self.parameter_config:
            result["parameter_config"] = self.parameter_config

        return result


class Workflow:
    """
    A DAG-based workflow that chains scraping strategies together.

    Workflows allow you to create pipelines where the output of one scraper
    feeds into the next. For example, scrape an index page to get links,
    then scrape each detail page.

    Example:
        workflow = Workflow("Job Scraper")
        index = workflow.start("index", index_strategy_id, urls=["https://jobs.com"])
        details = index.then("details", detail_strategy_id, url_field="job_link")

        result = client.run_workflow(workflow)
    """

    def __init__(self, name: str, description: Optional[str] = None):
        """
        Initialize a new workflow.

        Args:
            name: Workflow name
            description: Optional description of what the workflow does
        """
        self.name = name
        self.description = description
        self._nodes: List[WorkflowNode] = []
        self._edges: List[Dict[str, str]] = []

    def start(
        self,
        name: str,
        strategy_id: str,
        urls: List[str],
        parameters: Optional[Dict[str, Any]] = None,
    ) -> WorkflowNode:
        """
        Create the starting node with static URLs.

        Args:
            name: Unique node identifier
            strategy_id: Strategy UUID to use for scraping
            urls: List of URLs to scrape
            parameters: Optional static API parameter overrides

        Returns:
            The starting WorkflowNode (chain with .then() for downstream nodes)

        Example:
            workflow = Workflow("My Workflow")
            index = workflow.start("index", strategy_id, urls=["https://example.com"])
        """
        node = WorkflowNode(self, name, strategy_id, urls=urls, parameters=parameters)
        self._nodes.append(node)
        return node

    def to_dict(self) -> Dict[str, Any]:
        """Serialize workflow for API request."""
        return {
            "name": self.name,
            "description": self.description,
            "nodes": [n.to_dict() for n in self._nodes],
            "edges": self._edges
        }
