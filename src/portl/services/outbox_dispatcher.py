"""
Outbox dispatcher for transactional event delivery.

Delivers events stored in the outbox table after transaction commit.
"""

import httpx
import json
import logging

logger = logging.getLogger(__name__)


class OutboxDispatcher:
    """
    Synchronous outbox dispatcher for immediate delivery after commit.
    
    Features:
    - SELECT ... FOR UPDATE SKIP LOCKED for concurrent safety
    - Idempotency header support
    - HTTP delivery via httpx
    - Automatic retry tracking
    """
    
    def __init__(self, connection):
        """
        Initialize dispatcher with database connection.
        
        Args:
            connection: PostgresDestinationConnector instance
        """
        self.connection = connection
    
    def flush_for_run(self, run_id: str, batch_size: int = 50):
        """
        Flush all pending outbox events for a specific run.
        
        Processes events in batches, marks them as delivered or failed.
        
        Args:
            run_id: Job run identifier
            batch_size: Maximum events to process per batch
        """
        logger.info(f"Flushing outbox events for run {run_id}")
        
        events = self.connection.fetch_pending_outbox_events(run_id, batch_size)
        
        if not events:
            logger.debug(f"No pending outbox events for run {run_id}")
            return
        
        logger.info(f"Processing {len(events)} outbox events")
        
        for event_id, delivery_type, payload_json, idempotency_key in events:
            try:
                payload = json.loads(payload_json)
                
                if delivery_type == 'api.call':
                    self._deliver_api_call(payload, idempotency_key)
                elif delivery_type == 'lambda.invoke':
                    self._deliver_lambda(payload, idempotency_key)
                else:
                    raise ValueError(f"Unknown delivery type: {delivery_type}")
                
                # Mark as delivered
                self.connection.mark_outbox_delivered(event_id)
                self.connection._connection.commit()
                
                logger.info(f"Successfully delivered outbox event {event_id}")
                
            except Exception as e:
                logger.error(f"Failed to deliver outbox event {event_id}: {e}")
                self.connection.mark_outbox_failed(event_id, str(e))
                self.connection._connection.commit()
    
    def _deliver_api_call(self, payload: dict, idempotency_key: str):
        """
        Deliver API call event via HTTP.
        
        Args:
            payload: Event payload with method, url, headers, body
            idempotency_key: Idempotency key for delivery
            
        Raises:
            httpx.HTTPError: If HTTP request fails
        """
        method = payload['method']
        url = payload['url']
        headers = payload.get('headers', {}).copy()
        body = payload.get('body')
        
        # Add idempotency key
        headers['Idempotency-Key'] = idempotency_key
        
        logger.debug(f"Delivering API call: {method} {url}")
        
        response = httpx.request(
            method=method,
            url=url,
            headers=headers,
            json=body,
            timeout=30.0
        )
        
        response.raise_for_status()
        logger.debug(f"API call delivered successfully: {response.status_code}")
    
    def _deliver_lambda(self, payload: dict, idempotency_key: str):
        """
        Deliver Lambda invocation event.
        
        Args:
            payload: Event payload with function details
            idempotency_key: Idempotency key for delivery
        """
        # TODO: Implement Lambda delivery with boto3
        raise NotImplementedError("Lambda delivery not yet implemented")

