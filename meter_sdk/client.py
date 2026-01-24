"""Main client for Meter Scraper API"""

import time
from typing import Any, Dict, List, Optional
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
        force_api: bool = False
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

        Returns:
            Strategy details with preview data. For API-based strategies,
            response includes scraper_type ('api' or 'css') and
            api_parameters (available URL parameters for API scrapers).
        """
        return self._post("/api/strategies/generate", json={
            "url": url,
            "description": description,
            "name": name,
            "force_api": force_api
        })
    
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
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List jobs with optional filters"""
        params = {"limit": limit, "offset": offset}
        if strategy_id:
            params["strategy_id"] = strategy_id
        if status:
            params["status"] = status
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
        return self._get(f"/api/strategies/{strategy_id}/history")
    
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
            parameters: Default API parameter overrides for all scheduled runs.
                Only applies to API-based strategies. Keys are parameter names
                from the strategy's api_parameters field.

        Returns:
            Schedule details

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
        if parameters is not None:
            json_data["parameters"] = parameters
        return self._patch(f"/api/schedules/{schedule_id}", json=json_data)
    
    def delete_schedule(self, schedule_id: str) -> Dict[str, Any]:
        """Delete a schedule"""
        return self._delete(f"/api/schedules/{schedule_id}")

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

