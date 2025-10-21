# finance/services/plaid_service.py
"""
Plaid API integration for syncing transactions.
Uses Plaid Sandbox environment for development.
"""

import plaid
from plaid.api import plaid_api
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest

from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from finance.models import Transaction, Category, UserProfile


class PlaidService:
    """Service class for Plaid API interactions"""
    
    def __init__(self):
        """Initialize Plaid client"""
        configuration = plaid.Configuration(
            host=plaid.Environment.Sandbox,
            api_key={
                'clientId': settings.PLAID_CLIENT_ID,
                'secret': settings.PLAID_SECRET,
            }
        )
        
        api_client = plaid.ApiClient(configuration)
        self.client = plaid_api.PlaidApi(api_client)
    
    def create_link_token(self, user) -> str:
        """
        Create a Link token for Plaid Link initialization.
        
        Args:
            user: Django User object
        
        Returns:
            Link token string
        """
        try:
            request = LinkTokenCreateRequest(
                user=LinkTokenCreateRequestUser(
                    client_user_id=str(user.id)
                ),
                client_name="FinSIGHT",
                products=[Products("transactions")],
                country_codes=[CountryCode("US")],
                language='en',
            )
            
            response = self.client.link_token_create(request)
            return response['link_token']
        
        except plaid.ApiException as e:
            print(f"Error creating link token: {e}")
            raise
    
    def exchange_public_token(self, public_token: str) -> str:
        """
        Exchange a public token for an access token.
        
        Args:
            public_token: Public token from Plaid Link
        
        Returns:
            Access token
        """
        try:
            request = ItemPublicTokenExchangeRequest(
                public_token=public_token
            )
            
            response = self.client.item_public_token_exchange(request)
            return response['access_token']
        
        except plaid.ApiException as e:
            print(f"Error exchanging public token: {e}")
            raise
    
    def sync_transactions(self, user, force_full_sync: bool = False) -> Dict:
        """
        Sync transactions from Plaid for a user.
        
        Args:
            user: Django User object
            force_full_sync: If True, sync all transactions (ignore last_sync_date)
        
        Returns:
            Dictionary with sync results
        """
        try:
            profile = UserProfile.objects.get(user=user)
            
            if not profile.plaid_access_token:
                return {
                    'success': False,
                    'error': 'No Plaid access token found. Please connect your account first.'
                }
            
            # Determine date range
            end_date = datetime.now().date()
            
            if force_full_sync or not profile.last_sync_date:
                # Get last 90 days of transactions
                start_date = end_date - timedelta(days=90)
            else:
                # Get transactions since last sync
                start_date = profile.last_sync_date.date()
            
            # Fetch transactions from Plaid
            transactions = self._fetch_transactions(
                profile.plaid_access_token,
                start_date,
                end_date
            )
            
            # Process and save transactions
            result = self._process_transactions(user, transactions)
            
            # Update last sync date
            profile.last_sync_date = timezone.now()
            profile.save()
            
            return {
                'success': True,
                'transactions_added': result['added'],
                'transactions_updated': result['updated'],
                'sync_date': timezone.now(),
                'date_range': {
                    'start': start_date,
                    'end': end_date
                }
            }
        
        except UserProfile.DoesNotExist:
            return {
                'success': False,
                'error': 'User profile not found.'
            }
        except plaid.ApiException as e:
            return {
                'success': False,
                'error': f'Plaid API error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }
    
    def _fetch_transactions(self, access_token: str, start_date: datetime, 
                           end_date: datetime) -> List[Dict]:
        """
        Fetch transactions from Plaid API.
        
        Args:
            access_token: Plaid access token
            start_date: Start date for transactions
            end_date: End date for transactions
        
        Returns:
            List of transaction dictionaries
        """
        all_transactions = []
        
        try:
            request = TransactionsGetRequest(
                access_token=access_token,
                start_date=start_date,
                end_date=end_date,
                options=TransactionsGetRequestOptions(
                    count=500,
                    offset=0
                )
            )
            
            response = self.client.transactions_get(request)
            all_transactions.extend(response['transactions'])
            
            # Handle pagination
            total_transactions = response['total_transactions']
            while len(all_transactions) < total_transactions:
                request.options.offset = len(all_transactions)
                response = self.client.transactions_get(request)
                all_transactions.extend(response['transactions'])
        
        except plaid.ApiException as e:
            print(f"Error fetching transactions: {e}")
            raise
        
        return all_transactions
    
    def _process_transactions(self, user, transactions: List[Dict]) -> Dict:
        """
        Process and save transactions to database.
        
        Args:
            user: Django User object
            transactions: List of transaction dictionaries from Plaid
        
        Returns:
            Dictionary with processing results
        """
        added = 0
        updated = 0
        
        for txn in transactions:
            # Get or create category
            category = self._get_or_create_category(txn)
            
            # Check if transaction already exists
            plaid_id = txn.get('transaction_id')
            
            defaults = {
                'description': txn.get('name', 'Unknown'),
                'amount': abs(float(txn.get('amount', 0))),
                'date': datetime.strptime(txn.get('date'), '%Y-%m-%d').date(),
                'category': category,
            }
            
            if plaid_id:
                transaction, created = Transaction.objects.update_or_create(
                    user=user,
                    plaid_transaction_id=plaid_id,
                    defaults=defaults
                )
                
                if created:
                    added += 1
                else:
                    updated += 1
            else:
                # Create new transaction without plaid_id (shouldn't happen normally)
                Transaction.objects.create(
                    user=user,
                    **defaults
                )
                added += 1
        
        return {
            'added': added,
            'updated': updated
        }
    
    def _get_or_create_category(self, transaction: Dict) -> Category:
        """
        Get or create a category from Plaid transaction data.
        
        Args:
            transaction: Transaction dictionary from Plaid
        
        Returns:
            Category object
        """
        # Get primary category from Plaid
        plaid_category = None
        category_name = 'Uncategorized'
        
        if 'personal_finance_category' in transaction:
            pfc = transaction['personal_finance_category']
            if isinstance(pfc, dict) and 'primary' in pfc:
                plaid_category = pfc['primary']
                category_name = self._format_category_name(plaid_category)
        elif 'category' in transaction and transaction['category']:
            # Fallback to old category format
            plaid_category = transaction['category'][0] if transaction['category'] else None
            if plaid_category:
                category_name = plaid_category.replace('_', ' ').title()
        
        # Get or create category
        category, _ = Category.objects.get_or_create(
            name=category_name,
            defaults={
                'plaid_category': plaid_category,
                'icon': self._get_category_icon(category_name)
            }
        )
        
        return category
    
    def _format_category_name(self, plaid_category: str) -> str:
        """Format Plaid category name for display"""
        # Convert FOOD_AND_DRINK to Food & Drink
        return plaid_category.replace('_', ' ').title().replace('And', '&')
    
    def _get_category_icon(self, category_name: str) -> str:
        """Get emoji icon for category"""
        icon_map = {
            'Food & Drink': '🍔',
            'Transportation': '🚗',
            'Shopping': '🛍️',
            'Entertainment': '🎬',
            'Travel': '✈️',
            'Healthcare': '🏥',
            'Bills & Utilities': '💡',
            'Income': '💰',
            'Transfer': '💸',
            'Rent': '🏠',
            'General Services': '🔧',
            'Personal Care': '💅',
            'Education': '📚',
            'Fitness': '💪',
        }
        
        return icon_map.get(category_name, '💳')


# Utility function for easy access
def get_plaid_service() -> PlaidService:
    """Get an instance of PlaidService"""
    return PlaidService()