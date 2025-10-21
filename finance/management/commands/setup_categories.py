# finance/management/commands/setup_categories.py
"""
Management command to set up initial categories.
Usage: python manage.py setup_categories
"""

from django.core.management.base import BaseCommand
from finance.models import Category


class Command(BaseCommand):
    help = 'Set up initial spending categories'

    def handle(self, *args, **kwargs):
        categories = [
            ('Food & Drink', '🍔', 'FOOD_AND_DRINK'),
            ('Transportation', '🚗', 'TRANSPORTATION'),
            ('Shopping', '🛍️', 'GENERAL_MERCHANDISE'),
            ('Entertainment', '🎬', 'ENTERTAINMENT'),
            ('Travel', '✈️', 'TRAVEL'),
            ('Healthcare', '🏥', 'MEDICAL'),
            ('Bills & Utilities', '💡', 'LOAN_PAYMENTS'),
            ('Rent', '🏠', 'RENT_AND_UTILITIES'),
            ('Income', '💰', 'INCOME'),
            ('Transfer', '💸', 'TRANSFER'),
            ('General Services', '🔧', 'GENERAL_SERVICES'),
            ('Personal Care', '💅', 'PERSONAL_CARE'),
            ('Education', '📚', 'EDUCATION'),
            ('Fitness', '💪', 'FITNESS'),
            ('Groceries', '🛒', 'FOOD_AND_DRINK'),
            ('Gas & Fuel', '⛽', 'TRANSPORTATION'),
            ('Restaurants', '🍽️', 'FOOD_AND_DRINK'),
            ('Coffee Shops', '☕', 'FOOD_AND_DRINK'),
            ('Subscriptions', '📱', 'GENERAL_SERVICES'),
            ('Insurance', '🛡️', 'LOAN_PAYMENTS'),
            ('Uncategorized', '💳', None),
        ]
        
        created_count = 0
        for name, icon, plaid_cat in categories:
            category, created = Category.objects.get_or_create(
                name=name,
                defaults={
                    'icon': icon,
                    'plaid_category': plaid_cat
                }
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created category: {name}'))
        
        self.stdout.write(self.style.SUCCESS(f'\nTotal categories created: {created_count}'))
        self.stdout.write(self.style.SUCCESS(f'Total categories in database: {Category.objects.count()}'))
