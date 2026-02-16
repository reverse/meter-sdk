"""Main client for Meter Scraper API"""

import time
from typing import Any, Dict, List, Optional, Union
import httpx


class MeterError(Exception):
    """Base exception for Meter SDK errors"""
    pass


class MeterClient:
    """Client for interacting with the Meter Scraper API"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.meter.sh"):
        """
        Initialize the Meter client.
        
        Args:
            api_key: Your API key (starts with sk_live_)
            base_url: API base URL (default: https://api.meter.sh)
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0
        )
    
    def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make an HTTP request and handle errors"""
        try:
            response = self.client.request(method, path, json=json, params=params)
            response.raise_for_status()
            return response.json() if response.content else {}
        except httpx.HTTPStatusError as e:
            error_detail = "Unknown error"
            try:
                error_data = e.response.json()
                error_detail = error_data.get("detail", str(e))
            except:
                error_detail = str(e)
            raise MeterError(f"API error: {error_detail}")
        except httpx.RequestError as e:
            raise MeterError(f"Request failed: {str(e)}")
    
    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._request("GET", path, params=params)
    
    def _post(self, path: str, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._request("POST", path, json=json)
    
    def _patch(self, path: str, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._request("PATCH", path, json=json)
    
    def _put(self, path: str, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._request("PUT", path, json=json)

    def _delete(self, path: str) -> Dict[str, Any]:
        return self._request("DELETE", path)
    
    def close(self):
        """Close the HTTP client"""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()
    
    # Strategy Management
    
    def generate_strategy(
        self,
        url: str,
        description: str,
        name: str,
        force_api: bool = False,
        output_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a new extraction strategy.

        Args:
            url: URL to scrape
            description: What to extract
            name: Strategy name
            force_api: Force API-based capture instead of CSS extraction.
                When True, Meter will attempt to identify and capture
                underlying API calls rather than using CSS selectors.
            output_schema: Optional JSON schema describing the desired output
                structure. Example: {"title": "string", "price": "number"}

        Returns:
            Strategy details with preview data. For API-based strategies,
            response includes scraper_type ('api' or 'css') and
            api_parameters (available URL parameters for API scrapers).
        """
        payload = {
            "url": url,
            "description": description,
            "name": name,
            "force_api": force_api
        }
        if output_schema is not None:
            payload["output_schema"] = output_schema
        return self._post("/api/strategies/generate", json=payload)
    
    def refine_strategy(
        self,
        strategy_id: str,
        feedback: str
    ) -> Dict[str, Any]:
        """
        Refine an existing strategy based on feedback.
        
        Args:
            strategy_id: Strategy UUID
            feedback: Feedback to improve the strategy
        
        Returns:
            Refined strategy with updated preview data
        """
        return self._post(f"/api/strategies/{strategy_id}/refine", json={
            "feedback": feedback
        })
    
    def list_strategies(
        self,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List all strategies"""
        return self._get("/api/strategies", params={"limit": limit, "offset": offset})
    
    def get_strategy(self, strategy_id: str) -> Dict[str, Any]:
        """Get a specific strategy"""
        return self._get(f"/api/strategies/{strategy_id}")
    
    def delete_strategy(self, strategy_id: str) -> Dict[str, Any]:
        """Delete a strategy"""
        return self._delete(f"/api/strategies/{strategy_id}")
    
    # Job Execution
    
    def create_job(
        self,
        strategy_id: str,
        url: Optional[str] = None,
        urls: Optional[List[str]] = None,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new scrape job.

        Args:
            strategy_id: Strategy UUID to use
            url: Single URL to scrape (use url OR urls, not both)
            urls: List of URLs to scrape as a batch (use url OR urls, not both)
            parameters: Override API parameters for this job. Only applies to
                API-based strategies. Keys are parameter names from the
                strategy's api_parameters field.

        Returns:
            Job details with status 'pending'. For batch jobs (multiple urls),
            returns batch_id for tracking progress.

        Note:
            You must provide either url or urls, but not both.
        """
        json_data = {"strategy_id": strategy_id}
        if url:
            json_data["url"] = url
        if urls:
            json_data["urls"] = urls
        if parameters:
            json_data["parameters"] = parameters
        return self._post("/api/jobs", json=json_data)

    def execute_job(
        self,
        strategy_id: str,
        url: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create and execute a scrape job synchronously.

        This endpoint creates a job, waits for completion, and returns results.
        Unlike create_job which returns immediately, this waits for the job to finish.
        Useful for synchronous workflows where you want immediate results.

        Args:
            strategy_id: Strategy UUID to use
            url: URL to scrape
            parameters: Override API parameters for this job. Only applies to
                API-based strategies. Keys are parameter names from the
                strategy's api_parameters field.

        Returns:
            Completed job with results

        Raises:
            MeterError: If job fails or times out

        Note:
            This endpoint has a timeout of 3600 seconds (1 hour)
        """
        json_data = {
            "strategy_id": strategy_id,
            "url": url
        }
        if parameters:
            json_data["parameters"] = parameters
        return self._post("/api/jobs/execute", json=json_data)
    
    def get_job(self, job_id: str) -> Dict[str, Any]:
        """Get job status and results"""
        return self._get(f"/api/jobs/{job_id}")
    
    def list_jobs(
        self,
        strategy_id: Optional[str] = None,
        status: Optional[str] = None,
        since: Optional[str] = None,
        schedule_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List jobs with optional filters.

        Args:
            strategy_id: Filter by strategy UUID
            status: Filter by job status
            since: Filter jobs since a timestamp (ISO format or relative like "24h", "7d")
            schedule_id: Filter by schedule UUID
            limit: Maximum number of jobs to return (default: 20)
            offset: Number of jobs to skip (default: 0)

        Returns:
            List of job details
        """
        params = {"limit": limit, "offset": offset}
        if strategy_id:
            params["strategy_id"] = strategy_id
        if status:
            params["status"] = status
        if since:
            params["since"] = since
        if schedule_id:
            params["schedule_id"] = schedule_id
        return self._get("/api/jobs", params=params)
    
    def compare_jobs(
        self,
        job_id: str,
        other_job_id: str
    ) -> Dict[str, Any]:
        """Compare two jobs for changes"""
        return self._get(f"/api/jobs/{job_id}/compare/{other_job_id}")
    
    def get_strategy_history(self, strategy_id: str) -> List[Dict[str, Any]]:
        """Get job history for a strategy"""
        return self._get(f"/api/jobs/strategies/{strategy_id}/history")
    
    def wait_for_job(
        self,
        job_id: str,
        poll_interval: float = 1.0,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Poll a job until it completes.
        
        Args:
            job_id: Job UUID
            poll_interval: Seconds between polls
            timeout: Maximum time to wait (None = no timeout)
        
        Returns:
            Completed job with results
        
        Raises:
            MeterError: If job fails or times out
        """
        start_time = time.time()
        while True:
            job = self.get_job(job_id)
            status = job.get("status")
            
            if status == "completed":
                return job
            if status == "failed":
                error = job.get("error", "Unknown error")
                raise MeterError(f"Job failed: {error}")
            
            if timeout and (time.time() - start_time) > timeout:
                raise MeterError(f"Job timed out after {timeout} seconds")
            
            time.sleep(poll_interval)
    
    # Schedule Management
    
    def create_schedule(
        self,
        strategy_id: str,
        url: Optional[str] = None,
        urls: Optional[List[str]] = None,
        interval_seconds: Optional[int] = None,
        cron_expression: Optional[str] = None,
        webhook_url: Optional[str] = None,
        webhook_metadata: Optional[Dict[str, Any]] = None,
        webhook_secret: Optional[str] = None,
        webhook_type: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a recurring scrape schedule.

        Args:
            strategy_id: Strategy UUID
            url: Single URL to scrape (use url OR urls, not both)
            urls: List of URLs to scrape (use url OR urls, not both)
            interval_seconds: Run every N seconds (or use cron_expression)
            cron_expression: Cron expression (e.g., "0 9 * * *")
            webhook_url: Optional webhook URL to receive scrape results
            webhook_metadata: Custom JSON metadata included in every webhook payload
            webhook_secret: Secret for X-Webhook-Secret header. Auto-generated
                if not provided when webhook_url is set.
            webhook_type: Webhook type: 'standard' or 'slack'. Auto-detected
                from URL if not specified.
            parameters: Default API parameter overrides for all scheduled runs.
                Only applies to API-based strategies. Keys are parameter names
                from the strategy's api_parameters field.

        Returns:
            Schedule details. If a webhook secret was auto-generated, it will be
            included in the response (shown only once).

        Note:
            You must provide either url or urls, but not both.
        """
        json_data = {"strategy_id": strategy_id}
        if url:
            json_data["url"] = url
        if urls:
            json_data["urls"] = urls
        if interval_seconds:
            json_data["interval_seconds"] = interval_seconds
        if cron_expression:
            json_data["cron_expression"] = cron_expression
        if webhook_url:
            json_data["webhook_url"] = webhook_url
        if webhook_metadata is not None:
            json_data["webhook_metadata"] = webhook_metadata
        if webhook_secret is not None:
            json_data["webhook_secret"] = webhook_secret
        if webhook_type is not None:
            json_data["webhook_type"] = webhook_type
        if parameters:
            json_data["parameters"] = parameters
        return self._post("/api/schedules", json=json_data)
    
    def list_schedules(self) -> List[Dict[str, Any]]:
        """List all schedules"""
        return self._get("/api/schedules")
    
    def update_schedule(
        self,
        schedule_id: str,
        enabled: Optional[bool] = None,
        url: Optional[str] = None,
        urls: Optional[List[str]] = None,
        interval_seconds: Optional[int] = None,
        cron_expression: Optional[str] = None,
        webhook_url: Optional[str] = None,
        webhook_metadata: Optional[Dict[str, Any]] = None,
        webhook_secret: Optional[str] = None,
        webhook_type: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update a schedule.

        Args:
            schedule_id: Schedule UUID
            enabled: Enable or disable the schedule
            url: Update single URL to scrape
            urls: Update to multiple URLs to scrape
            interval_seconds: Update interval in seconds
            cron_expression: Update cron expression
            webhook_url: Update webhook URL for scrape results
            webhook_metadata: Update custom JSON metadata for webhook payloads
            webhook_secret: Update webhook secret. Pass empty string "" to
                regenerate the secret.
            webhook_type: Update webhook type: 'standard' or 'slack'
            parameters: Update default API parameter overrides for scheduled runs.
                Only applies to API-based strategies.

        Returns:
            Updated schedule details

        Note:
            Setting url will clear urls, and vice versa.
        """
        json_data = {}
        if enabled is not None:
            json_data["enabled"] = enabled
        if url is not None:
            json_data["url"] = url
        if urls is not None:
            json_data["urls"] = urls
        if interval_seconds is not None:
            json_data["interval_seconds"] = interval_seconds
        if cron_expression is not None:
            json_data["cron_expression"] = cron_expression
        if webhook_url is not None:
            json_data["webhook_url"] = webhook_url
        if webhook_metadata is not None:
            json_data["webhook_metadata"] = webhook_metadata
        if webhook_secret is not None:
            json_data["webhook_secret"] = webhook_secret
        if webhook_type is not None:
            json_data["webhook_type"] = webhook_type
        if parameters is not None:
            json_data["parameters"] = parameters
        return self._patch(f"/api/schedules/{schedule_id}", json=json_data)
    
    def delete_schedule(self, schedule_id: str) -> Dict[str, Any]:
        """Delete a schedule"""
        return self._delete(f"/api/schedules/{schedule_id}")

    def regenerate_webhook_secret(self, schedule_id: str) -> Dict[str, Any]:
        """
        Regenerate the webhook secret for a schedule.

        Returns the new secret once — store it securely.
        The secret will not be shown again in any other response.

        Args:
            schedule_id: Schedule UUID

        Returns:
            Response with schedule_id and the new webhook_secret

        Raises:
            MeterError: If schedule has no webhook URL configured
        """
        return self._post(f"/api/schedules/{schedule_id}/webhook-secret/regenerate")

    def get_schedule_changes(
        self,
        schedule_id: str,
        mark_seen: bool = True,
        filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get all unseen changes for a schedule (pull-based change detection).

        Returns jobs where content has changed compared to previous run.
        By default, marks returned changes as seen (like reading an email).

        Args:
            schedule_id: Schedule UUID
            mark_seen: Whether to mark changes as seen (default: True)
            filter: Lucene-style keyword filter for results. Filters individual
                items within each job's results array. Examples:
                - "+trump +tariff" - items with both keywords (AND)
                - "trump elon" - items with either keyword (OR)
                - "+trump -biden" - items with trump but not biden
                - '"elon musk"' - items with exact phrase

        Returns:
            Response with changed jobs, count, and whether they were marked as seen.
            If filter is applied, only matching result items are included.
        """
        params = {"mark_seen": mark_seen}
        if filter:
            params["filter"] = filter
        return self._get(f"/api/schedules/{schedule_id}/changes", params=params)

    # Workflow Management

    def create_workflow(self, workflow: "Workflow") -> Dict[str, Any]:
        """
        Create a workflow from a Workflow object.

        Args:
            workflow: Workflow object defining the DAG structure

        Returns:
            Created workflow details including workflow ID
        """
        from .workflow import Workflow as WorkflowClass
        if not isinstance(workflow, WorkflowClass):
            raise MeterError("workflow must be a Workflow object")
        return self._post("/api/workflows", json=workflow.to_dict())

    def run_workflow(
        self,
        workflow_or_id: Union["Workflow", str],
        force: bool = False,
        wait: bool = True,
        timeout: float = 3600
    ) -> Dict[str, Any]:
        """
        Run a workflow. Accepts either a Workflow object or workflow_id string.

        Args:
            workflow_or_id: Workflow object (creates then runs) or workflow_id string
            force: Force re-run, skipping change detection (default: False)
            wait: Block until completion (default: True)
            timeout: Maximum time to wait in seconds (default: 3600)

        Returns:
            If wait=True: Completed run with results
            If wait=False: Run details with status 'pending' or 'running'

        Example:
            # Create and run a new workflow
            workflow = Workflow("My Scraper")
            index = workflow.start("index", strategy_id, urls=["https://example.com"])
            result = client.run_workflow(workflow)

            # Run an existing workflow by ID
            result = client.run_workflow("workflow-uuid-here")

            # Force re-run (skip change detection)
            result = client.run_workflow("workflow-uuid", force=True)
        """
        from .workflow import Workflow as WorkflowClass

        if isinstance(workflow_or_id, WorkflowClass):
            created = self.create_workflow(workflow_or_id)
            workflow_id = created["id"]
        else:
            workflow_id = workflow_or_id

        run = self._post(f"/api/workflows/{workflow_id}/run", json={"force": force})

        if wait:
            return self.wait_for_workflow(workflow_id, run["id"], timeout=timeout)
        return run

    def wait_for_workflow(
        self,
        workflow_id: str,
        run_id: str,
        poll_interval: float = 5.0,
        timeout: float = 3600
    ) -> Dict[str, Any]:
        """
        Poll a workflow run until it completes.

        Args:
            workflow_id: Workflow UUID
            run_id: Run UUID
            poll_interval: Seconds between polls (default: 5.0)
            timeout: Maximum time to wait in seconds (default: 3600)

        Returns:
            Completed run with results

        Raises:
            MeterError: If run fails or times out
        """
        start_time = time.time()
        while True:
            run = self.get_workflow_run(workflow_id, run_id)
            status = run.get("status")

            if status == "completed":
                return run
            if status == "failed":
                error = run.get("error", "Unknown error")
                raise MeterError(f"Workflow run failed: {error}")
            if status == "cancelled":
                raise MeterError("Workflow run was cancelled")

            if (time.time() - start_time) > timeout:
                raise MeterError(f"Workflow run timed out after {timeout} seconds")

            time.sleep(poll_interval)

    def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get workflow details.

        Args:
            workflow_id: Workflow UUID

        Returns:
            Workflow details including nodes and edges
        """
        return self._get(f"/api/workflows/{workflow_id}")

    def list_workflows(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List all workflows.

        Args:
            limit: Maximum number of workflows to return (default: 50)
            offset: Number of workflows to skip (default: 0)

        Returns:
            List of workflow details
        """
        return self._get("/api/workflows", params={"limit": limit, "offset": offset})

    def update_workflow(
        self,
        workflow_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        enabled: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Update a workflow.

        Args:
            workflow_id: Workflow UUID
            name: Update workflow name
            description: Update workflow description
            enabled: Enable or disable the workflow

        Returns:
            Updated workflow details
        """
        json_data: Dict[str, Any] = {}
        if name is not None:
            json_data["name"] = name
        if description is not None:
            json_data["description"] = description
        if enabled is not None:
            json_data["enabled"] = enabled
        return self._put(f"/api/workflows/{workflow_id}", json=json_data)

    def delete_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Delete a workflow.

        Args:
            workflow_id: Workflow UUID

        Returns:
            Deletion confirmation
        """
        return self._delete(f"/api/workflows/{workflow_id}")

    def cancel_workflow_run(self, workflow_id: str, run_id: str) -> Dict[str, Any]:
        """
        Cancel a running workflow run.

        Args:
            workflow_id: Workflow UUID
            run_id: Run UUID

        Returns:
            Cancelled run details
        """
        return self._post(f"/api/workflows/{workflow_id}/runs/{run_id}/cancel")

    def get_workflow_run(self, workflow_id: str, run_id: str) -> Dict[str, Any]:
        """
        Get run details with node executions.

        Args:
            workflow_id: Workflow UUID
            run_id: Run UUID

        Returns:
            Run details including status, node results, and final_results
        """
        return self._get(f"/api/workflows/{workflow_id}/runs/{run_id}")

    def list_workflow_runs(
        self,
        workflow_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List run history for a workflow.

        Args:
            workflow_id: Workflow UUID
            limit: Maximum number of runs to return (default: 20)
            offset: Number of runs to skip (default: 0)

        Returns:
            List of run details
        """
        return self._get(
            f"/api/workflows/{workflow_id}/runs",
            params={"limit": limit, "offset": offset}
        )

    def get_workflow_output(
        self,
        workflow_id: str,
        flat: bool = False
    ) -> Dict[str, Any]:
        """
        Get the latest completed run's results.

        By default returns results grouped by strategy within each URL,
        with cleaned labels (e.g. "purchasing reps" instead of "script:purchasing_reps").

        Args:
            workflow_id: Workflow UUID
            flat: If True, return flat per-URL results instead of grouped by strategy

        Returns:
            Latest run results. Default format:
                final_results_by_url_grouped: {url: {strategy_label: [items]}}
            With flat=True:
                final_results_by_url: {url: [items]}

        Raises:
            MeterError: If no completed runs exist
        """
        params = {}
        if flat:
            params["flat"] = "true"
        return self._get(f"/api/workflows/{workflow_id}/runs/latest/output", params=params)

    # Workflow Scheduling

    def schedule_workflow(
        self,
        workflow_id: str,
        interval_seconds: Optional[int] = None,
        cron_expression: Optional[str] = None,
        webhook_url: Optional[str] = None,
        webhook_metadata: Optional[Dict[str, Any]] = None,
        webhook_secret: Optional[str] = None,
        webhook_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Schedule a workflow to run on interval or cron.

        Args:
            workflow_id: Workflow UUID
            interval_seconds: Run every N seconds (or use cron_expression)
            cron_expression: Cron expression (e.g., "0 9 * * *" for daily at 9am)
            webhook_url: Optional webhook URL to receive results
            webhook_metadata: Custom JSON metadata included in every webhook payload
            webhook_secret: Secret for X-Webhook-Secret header
            webhook_type: Webhook type: 'standard' or 'slack' (default: 'standard')

        Returns:
            Schedule details

        Example:
            # Run every hour
            client.schedule_workflow(workflow_id, interval_seconds=3600)

            # Run daily at 9am
            client.schedule_workflow(workflow_id, cron_expression="0 9 * * *")

            # Run hourly with webhook notification
            client.schedule_workflow(
                workflow_id,
                interval_seconds=3600,
                webhook_url="https://myapp.com/webhook"
            )

            # With metadata passed through to every webhook payload
            client.schedule_workflow(
                workflow_id,
                interval_seconds=3600,
                webhook_url="https://myapp.com/webhook",
                webhook_metadata={"project": "my-project", "env": "prod"}
            )
        """
        json_data: Dict[str, Any] = {}
        if interval_seconds is not None:
            json_data["interval_seconds"] = interval_seconds
        if cron_expression is not None:
            json_data["cron_expression"] = cron_expression
        if webhook_url is not None:
            json_data["webhook_url"] = webhook_url
        if webhook_metadata is not None:
            json_data["webhook_metadata"] = webhook_metadata
        if webhook_secret is not None:
            json_data["webhook_secret"] = webhook_secret
        if webhook_type is not None:
            json_data["webhook_type"] = webhook_type
        return self._post(f"/api/workflows/{workflow_id}/schedules", json=json_data)

    def list_workflow_schedules(self, workflow_id: str) -> List[Dict[str, Any]]:
        """
        List schedules for a workflow.

        Args:
            workflow_id: Workflow UUID

        Returns:
            List of schedule details
        """
        return self._get(f"/api/workflows/{workflow_id}/schedules")

    def update_workflow_schedule(
        self,
        workflow_id: str,
        schedule_id: str,
        enabled: Optional[bool] = None,
        interval_seconds: Optional[int] = None,
        cron_expression: Optional[str] = None,
        webhook_url: Optional[str] = None,
        webhook_metadata: Optional[Dict[str, Any]] = None,
        webhook_secret: Optional[str] = None,
        webhook_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update a workflow schedule.

        Args:
            workflow_id: Workflow UUID
            schedule_id: Schedule UUID
            enabled: Enable or disable the schedule
            interval_seconds: Update interval in seconds
            cron_expression: Update cron expression
            webhook_url: Update webhook URL
            webhook_metadata: Update custom JSON metadata for webhook payloads
            webhook_secret: Update webhook secret
            webhook_type: Update webhook type: 'standard' or 'slack'

        Returns:
            Updated schedule details
        """
        json_data: Dict[str, Any] = {}
        if enabled is not None:
            json_data["enabled"] = enabled
        if interval_seconds is not None:
            json_data["interval_seconds"] = interval_seconds
        if cron_expression is not None:
            json_data["cron_expression"] = cron_expression
        if webhook_url is not None:
            json_data["webhook_url"] = webhook_url
        if webhook_metadata is not None:
            json_data["webhook_metadata"] = webhook_metadata
        if webhook_secret is not None:
            json_data["webhook_secret"] = webhook_secret
        if webhook_type is not None:
            json_data["webhook_type"] = webhook_type
        return self._patch(
            f"/api/workflows/{workflow_id}/schedules/{schedule_id}",
            json=json_data
        )

    def delete_workflow_schedule(
        self,
        workflow_id: str,
        schedule_id: str
    ) -> Dict[str, Any]:
        """
        Delete a workflow schedule.

        Args:
            workflow_id: Workflow UUID
            schedule_id: Schedule UUID

        Returns:
            Deletion confirmation
        """
        return self._delete(f"/api/workflows/{workflow_id}/schedules/{schedule_id}")

