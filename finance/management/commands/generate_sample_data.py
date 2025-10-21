# finance/management/commands/generate_sample_data.py
"""
Management command to generate sample transaction data for testing.
Usage: python manage.py generate_sample_data --username=testuser --days=90
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import random

from finance.models import Transaction, Category, UserProfile


class Command(BaseCommand):
    help = 'Generate sample transaction data for testing'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='Username to generate data for')
        parser.add_argument('--days', type=int, default=90, help='Number of days of data to generate')

    def handle(self, *args, **kwargs):
        username = kwargs['username']
        days = kwargs['days']
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User "{username}" not found'))
            return
        
        # Ensure user has a profile
        UserProfile.objects.get_or_create(user=user)
        
        # Get categories
        categories = list(Category.objects.all())
        if not categories:
            self.stdout.write(self.style.WARNING('No categories found. Run setup_categories first.'))
            return
        
        # Define recurring transactions (monthly)
        recurring_transactions = [
            ('Netflix Subscription', 15.99, 'Entertainment', 15),
            ('Spotify Premium', 9.99, 'Entertainment', 10),
            ('Gym Membership', 50.00, 'Fitness', 1),
            ('Internet Bill', 79.99, 'Bills & Utilities', 5),
            ('Phone Bill', 45.00, 'Bills & Utilities', 20),
        ]
        
        # Define typical discretionary spending
        discretionary_patterns = [
            ('Whole Foods', (30, 80), 'Groceries', 3),  # 3 times per week
            ('Starbucks', (5, 12), 'Coffee Shops', 5),  # 5 times per week
            ('Local Restaurant', (20, 50), 'Restaurants', 2),  # 2 times per week
            ('Uber', (10, 30), 'Transportation', 4),  # 4 times per week
            ('Amazon', (15, 150), 'Shopping', 1),  # Once per week
            ('Target', (25, 100), 'Shopping', 1),
            ('Gas Station', (40, 60), 'Gas & Fuel', 1),
        ]
        
        created_count = 0
        today = timezone.now().date()
        
        # Generate recurring transactions for each month
        for day_offset in range(days):
            date = today - timedelta(days=day_offset)
            
            # Add recurring payments on their due days
            for name, amount, cat_name, due_day in recurring_transactions:
                if date.day == due_day:
                    category = Category.objects.filter(name=cat_name).first()
                    Transaction.objects.create(
                        user=user,
                        description=name,
                        amount=amount,
                        date=date,
                        category=category,
                        is_recurring=True,
                        recurring_frequency='monthly'
                    )
                    created_count += 1
            
            # Add discretionary transactions based on patterns
            for name, amount_range, cat_name, weekly_freq in discretionary_patterns:
                # Determine if transaction should occur today
                if random.random() < (weekly_freq / 7):
                    category = Category.objects.filter(name=cat_name).first()
                    amount = random.uniform(amount_range[0], amount_range[1])
                    
                    Transaction.objects.create(
                        user=user,
                        description=name,
                        amount=round(amount, 2),
                        date=date,
                        category=category,
                        is_recurring=False
                    )
                    created_count += 1
            
            # Occasionally add an anomaly (unusual high spending)
            if random.random() < 0.05:  # 5% chance
                anomaly_transactions = [
                    ('Electronics Store', (300, 800), 'Shopping'),
                    ('Concert Tickets', (150, 300), 'Entertainment'),
                    ('Emergency Repair', (200, 500), 'General Services'),
                    ('Medical Visit', (150, 400), 'Healthcare'),
                ]
                
                name, amount_range, cat_name = random.choice(anomaly_transactions)
                category = Category.objects.filter(name=cat_name).first()
                amount = random.uniform(amount_range[0], amount_range[1])
                
                Transaction.objects.create(
                    user=user,
                    description=name,
                    amount=round(amount, 2),
                    date=date,
                    category=category,
                    is_recurring=False,
                    is_anomaly=True
                )
                created_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'\nGenerated {created_count} transactions for user "{username}"'))
        self.stdout.write(self.style.SUCCESS(f'Date range: {today - timedelta(days=days)} to {today}'))


