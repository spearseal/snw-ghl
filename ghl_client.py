"""
GoHighLevel API Client
Handles authentication and data retrieval from GoHighLevel
"""
import requests
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from config import settings
from hipaa_compliance import hipaa_manager

GHL_API_VERSION = '2021-07-28'
GHL_CONVERSATIONS_API_VERSION = '2021-04-15'


def ghl_request_headers(
    api_key: str,
    api_version: Optional[str] = None,
) -> Dict[str, str]:
    """Headers required by the GoHighLevel LeadConnector API."""
    return {
        'Authorization': f'Bearer {api_key}',
        'Version': api_version or GHL_API_VERSION,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }


class GHLClient:
    """
    Client for interacting with GoHighLevel API
    Supports OAuth 2.0 and Private Integration Token authentication
    """
    
    def __init__(self, config: Optional[Dict[str, str]] = None):
        config = config or {}
        self.api_key = config.get('api_key') or settings.ghl_api_key
        self.base_url = config.get('base_url') or settings.ghl_api_base_url
        self.location_id = config.get('location_id') or settings.ghl_location_id
        self.api_version = config.get('api_version') or settings.ghl_api_version
        self.session = requests.Session()
        self.session.headers.update(ghl_request_headers(self.api_key, self.api_version))
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(getattr(logging, settings.log_level, logging.INFO))
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        retry_count: int = 0,
        api_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to GHL API with retry logic
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint
            params: Query parameters
            data: Request body data
            retry_count: Current retry attempt
            
        Returns:
            Response JSON data
        """
        url = f"{self.base_url}{endpoint}"
        extra_headers = (
            {'Version': api_version}
            if api_version
            else None
        )
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=data,
                headers=extra_headers,
                timeout=30
            )
            
            response.raise_for_status()
            
            # Log successful access
            hipaa_manager.log_audit_event('ghl_api_access', {
                'endpoint': endpoint,
                'method': method,
                'status': response.status_code
            })
            
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP Error: {e}")
            hipaa_manager.log_audit_event('ghl_api_error', {
                'endpoint': endpoint,
                'error': str(e),
                'status_code': e.response.status_code if e.response else None
            })
            
            # Retry on server errors
            if e.response and e.response.status_code >= 500 and retry_count < settings.max_retries:
                self.logger.warning(f"Retrying request (attempt {retry_count + 1})")
                return self._make_request(
                    method, endpoint, params, data, retry_count + 1, api_version
                )
            
            raise
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request Error: {e}")
            hipaa_manager.log_audit_event('ghl_api_error', {
                'endpoint': endpoint,
                'error': str(e)
            })
            raise
    
    def get_contacts(
        self,
        limit: int = 100,
        start_after: Optional[str] = None,
        query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve contacts from GoHighLevel
        
        Args:
            limit: Number of contacts to retrieve
            start_after: Cursor for pagination
            query: Search query for contacts
            
        Returns:
            List of contact records
        """
        params = {'limit': limit}
        
        if start_after:
            params['startAfter'] = start_after
            
        if query:
            params['query'] = query
            
        if self.location_id:
            params['locationId'] = self.location_id
        
        self.logger.info(f"Fetching {limit} contacts from GHL")
        
        response = self._make_request('GET', '/contacts/', params=params)
        
        contacts = response.get('contacts', [])
        
        # Log data retrieval
        hipaa_manager.log_audit_event('ghl_data_retrieval', {
            'entity': 'contacts',
            'count': len(contacts),
            'timestamp': datetime.utcnow().isoformat()
        })
        
        return contacts
    
    def get_contact_by_id(self, contact_id: str) -> Dict[str, Any]:
        """
        Retrieve a specific contact by ID
        
        Args:
            contact_id: Contact ID
            
        Returns:
            Contact record
        """
        self.logger.info(f"Fetching contact {contact_id} from GHL")
        
        response = self._make_request('GET', f'/contacts/{contact_id}')
        
        hipaa_manager.log_audit_event('ghl_data_retrieval', {
            'entity': 'contact',
            'contact_id': hipaa_manager.mask_sensitive_data(contact_id),
            'timestamp': datetime.utcnow().isoformat()
        })
        
        return response.get('contact', {})
    
    def get_conversations(
        self,
        limit: int = 100,
        start_after: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve conversations from GoHighLevel
        
        Args:
            limit: Number of conversations to retrieve
            start_after: Cursor for pagination
            
        Returns:
            List of conversation records
        """
        if not self.location_id:
            raise ValueError('GoHighLevel location_id is required to fetch conversations')

        params: Dict[str, Any] = {
            'locationId': self.location_id,
            'limit': limit,
        }
        
        if start_after:
            params['startAfterId'] = start_after
        
        self.logger.info(f"Fetching {limit} conversations from GHL")
        
        response = self._make_request(
            'GET',
            '/conversations/search',
            params=params,
            api_version=GHL_CONVERSATIONS_API_VERSION,
        )
        
        conversations = response.get('conversations', [])
        
        hipaa_manager.log_audit_event('ghl_data_retrieval', {
            'entity': 'conversations',
            'count': len(conversations),
            'timestamp': datetime.utcnow().isoformat()
        })
        
        return conversations
    
    def get_opportunities(
        self,
        limit: int = 100,
        start_after: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve opportunities/deals from GoHighLevel
        
        Args:
            limit: Number of opportunities to retrieve
            start_after: Cursor for pagination
            
        Returns:
            List of opportunity records
        """
        if not self.location_id:
            raise ValueError('GoHighLevel location_id is required to fetch opportunities')

        params: Dict[str, Any] = {
            'location_id': self.location_id,
            'limit': limit,
        }
        
        if start_after:
            params['startAfterId'] = start_after
        
        self.logger.info(f"Fetching {limit} opportunities from GHL")
        
        response = self._make_request('GET', '/opportunities/search', params=params)
        
        opportunities = response.get('opportunities', [])
        
        hipaa_manager.log_audit_event('ghl_data_retrieval', {
            'entity': 'opportunities',
            'count': len(opportunities),
            'timestamp': datetime.utcnow().isoformat()
        })
        
        return opportunities
    
    def send_email(
        self,
        contact_id: str,
        subject: str,
        html: str,
        from_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send an email to a contact via GHL Conversations API."""
        if not contact_id:
            raise ValueError('contact_id is required')
        if not subject.strip():
            raise ValueError('subject is required')
        if not html.strip():
            raise ValueError('html body is required')

        payload: Dict[str, Any] = {
            'type': 'Email',
            'contactId': contact_id,
            'subject': subject,
            'html': html,
        }
        if from_email:
            payload['emailFrom'] = from_email

        self.logger.info(f"Sending email to GHL contact {contact_id}")
        response = self._make_request(
            'POST',
            '/conversations/messages',
            data=payload,
            api_version=GHL_CONVERSATIONS_API_VERSION,
        )
        hipaa_manager.log_audit_event('ghl_email_sent', {
            'contact_id': hipaa_manager.mask_sensitive_data(contact_id),
            'timestamp': datetime.utcnow().isoformat(),
        })
        return response

    def get_all_data(self) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, str]]:
        """
        Retrieve all relevant data from GoHighLevel
        Fetches contacts, conversations, and opportunities
        
        Returns:
            Dictionary containing all data types
        """
        self.logger.info("Fetching all data from GHL")
        
        all_data = {
            'contacts': [],
            'conversations': [],
            'opportunities': []
        }
        entity_errors: Dict[str, str] = {}

        try:
            contacts = []
            start_after = None
            while True:
                batch = self.get_contacts(limit=settings.batch_size, start_after=start_after)
                if not batch:
                    break
                contacts.extend(batch)
                if len(batch) < settings.batch_size:
                    break
                start_after = batch[-1].get('id')
            all_data['contacts'] = contacts
        except Exception as e:
            self.logger.error(f"Failed to fetch GHL contacts: {e}")
            entity_errors['contacts'] = str(e)

        try:
            all_data['conversations'] = self.get_conversations(limit=settings.batch_size)
        except Exception as e:
            self.logger.error(f"Failed to fetch GHL conversations: {e}")
            entity_errors['conversations'] = str(e)

        try:
            all_data['opportunities'] = self.get_opportunities(limit=settings.batch_size)
        except Exception as e:
            self.logger.error(f"Failed to fetch GHL opportunities: {e}")
            entity_errors['opportunities'] = str(e)

        if entity_errors and not any(all_data.values()):
            details = '; '.join(f'{k}: {v}' for k, v in entity_errors.items())
            raise RuntimeError(f'Failed to fetch any GHL data ({details})')
        
        hipaa_manager.log_audit_event('ghl_full_sync', {
            'contacts_count': len(all_data['contacts']),
            'conversations_count': len(all_data['conversations']),
            'opportunities_count': len(all_data['opportunities']),
            'entity_errors': entity_errors or None,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        return all_data, entity_errors
