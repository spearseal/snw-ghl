"""
Main integration script for GoHighLevel + Snowflake with HIPAA compliance
Orchestrates data extraction, transformation, and loading
"""
import logging
import sys
from datetime import datetime
from typing import Optional
from ghl_client import GHLClient
from snowflake_loader import SnowflakeLoader
from hipaa_compliance import hipaa_manager
from config import settings


def setup_logging():
    """Configure application logging"""
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


def run_sync():
    """
    Main sync function
    Extracts data from GHL, transforms it, and loads to Snowflake
    """
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("=" * 80)
        logger.info("Starting GHL to Snowflake Sync")
        logger.info("=" * 80)
        
        # Log sync start
        hipaa_manager.log_audit_event('sync_start', {
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Initialize GHL client
        logger.info("Initializing GoHighLevel client...")
        ghl_client = GHLClient()
        
        # Initialize Snowflake loader
        logger.info("Initializing Snowflake loader...")
        snowflake_loader = SnowflakeLoader()
        snowflake_loader.connect()
        
        try:
            # Extract data from GHL
            logger.info("Extracting data from GoHighLevel...")
            ghl_data = ghl_client.get_all_data()
            
            logger.info(f"Extracted {len(ghl_data['contacts'])} contacts")
            logger.info(f"Extracted {len(ghl_data['conversations'])} conversations")
            logger.info(f"Extracted {len(ghl_data['opportunities'])} opportunities")
            
            # Load data to Snowflake
            logger.info("Loading data to Snowflake...")
            snowflake_loader.load_all_data(ghl_data)
            
            # Log sync completion
            hipaa_manager.log_audit_event('sync_complete', {
                'contacts_count': len(ghl_data['contacts']),
                'conversations_count': len(ghl_data['conversations']),
                'opportunities_count': len(ghl_data['opportunities']),
                'timestamp': datetime.utcnow().isoformat()
            })
            
            logger.info("=" * 80)
            logger.info("Sync completed successfully")
            logger.info("=" * 80)
            
        finally:
            # Ensure Snowflake connection is closed
            snowflake_loader.disconnect()
            
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        hipaa_manager.log_audit_event('sync_failed', {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        })
        raise


def run_incremental_sync(last_sync_timestamp: Optional[str] = None):
    """
    Run incremental sync (fetch only changed data)
    
    Args:
        last_sync_timestamp: Timestamp of last sync
    """
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Starting incremental sync...")
        
        hipaa_manager.log_audit_event('incremental_sync_start', {
            'last_sync': last_sync_timestamp,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Initialize clients
        ghl_client = GHLClient()
        snowflake_loader = SnowflakeLoader()
        snowflake_loader.connect()
        
        try:
            # For incremental sync, you would need to implement
            # logic to fetch only changed data based on timestamps
            # This is a placeholder for future enhancement
            
            logger.info("Incremental sync not yet implemented")
            logger.info("Falling back to full sync...")
            
            # Fall back to full sync
            run_sync()
            
        finally:
            snowflake_loader.disconnect()
            
    except Exception as e:
        logger.error(f"Incremental sync failed: {e}")
        hipaa_manager.log_audit_event('incremental_sync_failed', {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        })
        raise


def verify_data_integrity():
    """
    Verify data integrity between GHL and Snowflake
    Compares hashes to ensure data consistency
    """
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Starting data integrity verification...")
        
        hipaa_manager.log_audit_event('integrity_check_start', {
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # This would implement logic to:
        # 1. Sample data from GHL
        # 2. Sample corresponding data from Snowflake
        # 3. Decrypt Snowflake data
        # 4. Compare hashes
        
        logger.info("Data integrity verification not yet implemented")
        
    except Exception as e:
        logger.error(f"Integrity verification failed: {e}")
        hipaa_manager.log_audit_event('integrity_check_failed', {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        })
        raise


if __name__ == "__main__":
    setup_logging()
    
    import argparse
    
    parser = argparse.ArgumentParser(
        description='GHL to Snowflake Integration with HIPAA Compliance'
    )
    parser.add_argument(
        '--mode',
        choices=['full', 'incremental', 'verify'],
        default='full',
        help='Sync mode: full, incremental, or verify'
    )
    parser.add_argument(
        '--last-sync',
        type=str,
        help='Last sync timestamp for incremental sync'
    )
    
    args = parser.parse_args()
    
    if args.mode == 'full':
        run_sync()
    elif args.mode == 'incremental':
        run_incremental_sync(args.last_sync)
    elif args.mode == 'verify':
        verify_data_integrity()
