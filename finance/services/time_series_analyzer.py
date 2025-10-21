# finance/analysis/time_series_analyzer.py
"""
Modular Time Series Analysis for recurring payment detection and anomaly detection.
Built with statsmodels and scikit-learn for easy replacement with DL models.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Tuple, Optional

from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler

from django.db.models import QuerySet
from finance.models import Transaction, PendingRecurringConfirmation


class TimeSeriesAnalyzer:
    """Main class for time series analysis of financial transactions"""
    
    def __init__(self, user):
        self.user = user
        self.transactions = None
        self.df = None
        
    def load_data(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None):
        """Load transaction data into pandas DataFrame"""
        queryset = Transaction.objects.filter(user=self.user)
        
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
            
        self.transactions = queryset.order_by('date')
        
        # Convert to DataFrame
        data = list(self.transactions.values(
            'id', 'date', 'amount', 'description', 'category__name', 'is_recurring'
        ))
        
        if not data:
            self.df = pd.DataFrame()
            return self.df
            
        self.df = pd.DataFrame(data)
        self.df['date'] = pd.to_datetime(self.df['date'])
        self.df = self.df.rename(columns={'category__name': 'category'})
        self.df = self.df.sort_values('date')
        
        return self.df
    
    def analyze_seasonality(self, freq: str = 'D') -> Dict:
        """
        Analyze seasonality patterns in spending using ACF and seasonal decomposition.
        
        Args:
            freq: Frequency for resampling ('D' for daily, 'W' for weekly, 'M' for monthly)
        
        Returns:
            Dictionary with seasonality analysis results
        """
        if self.df is None or len(self.df) == 0:
            return {'error': 'No data available'}
        
        # Resample to daily spending
        daily_spending = self.df.set_index('date').resample('D')['amount'].sum().fillna(0)
        
        if len(daily_spending) < 14:
            return {'error': 'Insufficient data for seasonality analysis (need at least 14 days)'}
        
        result = {
            'daily_spending': daily_spending,
            'mean': float(daily_spending.mean()),
            'std': float(daily_spending.std()),
            'has_strong_seasonality': False
        }
        
        # Perform seasonal decomposition if we have enough data
        if len(daily_spending) >= 30:
            try:
                decomposition = seasonal_decompose(
                    daily_spending, 
                    model='additive', 
                    period=7,  # Weekly seasonality
                    extrapolate_trend='freq'
                )
                
                result['trend'] = decomposition.trend
                result['seasonal'] = decomposition.seasonal
                result['residual'] = decomposition.resid
                
                # Check if seasonality is strong (seasonal component variance > 10% of total)
                seasonal_var = decomposition.seasonal.var()
                total_var = daily_spending.var()
                
                if total_var > 0:
                    result['seasonality_strength'] = float(seasonal_var / total_var)
                    result['has_strong_seasonality'] = result['seasonality_strength'] > 0.1
                
            except Exception as e:
                result['decomposition_error'] = str(e)
        
        return result
    
    def detect_recurring_patterns(self, min_occurrences: int = 3, 
                                  amount_tolerance: float = 0.05) -> List[Dict]:
        """
        Detect recurring payment patterns using clustering and frequency analysis.
        
        Args:
            min_occurrences: Minimum number of times a pattern must occur
            amount_tolerance: Tolerance for amount variation (5% default)
        
        Returns:
            List of detected recurring patterns
        """
        if self.df is None or len(self.df) < min_occurrences:
            return []
        
        patterns = []
        
        # Group by similar descriptions (fuzzy matching could be added)
        for description, group in self.df.groupby('description'):
            if len(group) < min_occurrences:
                continue
            
            # Check if amounts are similar
            amounts = group['amount'].values
            mean_amount = np.mean(amounts)
            
            # Check if all amounts are within tolerance
            within_tolerance = all(
                abs(amt - mean_amount) / mean_amount <= amount_tolerance 
                for amt in amounts
            )
            
            if not within_tolerance:
                continue
            
            # Analyze time intervals between transactions
            dates = group['date'].values
            intervals = np.diff(dates).astype('timedelta64[D]').astype(int)
            
            if len(intervals) == 0:
                continue
            
            # Detect frequency
            frequency = self._detect_frequency(intervals)
            
            if frequency:
                confidence = self._calculate_confidence(intervals, frequency)
                
                if confidence > 0.7:  # 70% confidence threshold
                    patterns.append({
                        'description': description,
                        'amount': float(mean_amount),
                        'frequency': frequency,
                        'confidence': confidence,
                        'occurrences': len(group),
                        'transaction_ids': group['id'].tolist(),
                        'last_date': group['date'].max(),
                        'category': group['category'].iloc[0] if 'category' in group else None
                    })
        
        # Sort by confidence
        patterns.sort(key=lambda x: x['confidence'], reverse=True)
        
        return patterns
    
    def _detect_frequency(self, intervals: np.ndarray) -> Optional[str]:
        """Detect payment frequency from intervals between transactions"""
        if len(intervals) == 0:
            return None
        
        median_interval = np.median(intervals)
        
        # Define frequency thresholds (with tolerance)
        frequencies = [
            (7, 2, 'weekly'),           # 7 days ± 2 days
            (14, 3, 'biweekly'),        # 14 days ± 3 days
            (30, 5, 'monthly'),         # 30 days ± 5 days
            (91, 7, 'quarterly'),       # 91 days ± 7 days
            (365, 14, 'annual'),        # 365 days ± 14 days
        ]
        
        for target, tolerance, name in frequencies:
            if abs(median_interval - target) <= tolerance:
                return name
        
        return None
    
    def _calculate_confidence(self, intervals: np.ndarray, frequency: str) -> float:
        """Calculate confidence score for detected frequency"""
        if len(intervals) == 0:
            return 0.0
        
        frequency_days = {
            'weekly': 7,
            'biweekly': 14,
            'monthly': 30,
            'quarterly': 91,
            'annual': 365
        }
        
        expected = frequency_days.get(frequency, 30)
        
        # Calculate coefficient of variation
        mean_interval = np.mean(intervals)
        std_interval = np.std(intervals)
        
        if mean_interval == 0:
            return 0.0
        
        cv = std_interval / mean_interval
        
        # Lower CV means higher confidence
        # Also consider how close intervals are to expected frequency
        mean_error = abs(mean_interval - expected) / expected
        
        confidence = max(0, 1 - cv - mean_error)
        
        return float(confidence)
    
    def get_discretionary_spending(self) -> pd.DataFrame:
        """Filter out recurring transactions to get discretionary spending"""
        if self.df is None or len(self.df) == 0:
            return pd.DataFrame()
        
        # Filter out recurring transactions
        discretionary = self.df[self.df['is_recurring'] == False].copy()
        
        return discretionary
    
    def detect_anomalies(self, n_std: float = 2.0, window: int = 30) -> List[Dict]:
        """
        Detect spending anomalies using rolling statistics.
        
        Args:
            n_std: Number of standard deviations for anomaly threshold
            window: Rolling window size in days
        
        Returns:
            List of detected anomalies
        """
        discretionary = self.get_discretionary_spending()
        
        if len(discretionary) == 0:
            return []
        
        # Group by date and sum amounts
        daily_spending = discretionary.groupby('date')['amount'].sum().reset_index()
        daily_spending = daily_spending.set_index('date')
        
        # Create complete date range
        date_range = pd.date_range(
            start=daily_spending.index.min(),
            end=daily_spending.index.max(),
            freq='D'
        )
        daily_spending = daily_spending.reindex(date_range, fill_value=0)
        
        # Calculate rolling statistics
        rolling_mean = daily_spending['amount'].rolling(window=window, min_periods=1).mean()
        rolling_std = daily_spending['amount'].rolling(window=window, min_periods=1).std()
        
        # Calculate threshold
        threshold = rolling_mean + (n_std * rolling_std)
        
        # Find anomalies
        anomalies = []
        for date, amount in daily_spending['amount'].items():
            if amount > threshold[date] and amount > 0:
                # Get transactions for this date
                date_transactions = discretionary[discretionary['date'] == date]
                
                anomalies.append({
                    'date': date,
                    'amount': float(amount),
                    'threshold': float(threshold[date]),
                    'mean': float(rolling_mean[date]),
                    'std': float(rolling_std[date]),
                    'z_score': float((amount - rolling_mean[date]) / rolling_std[date]) if rolling_std[date] > 0 else 0,
                    'transactions': date_transactions.to_dict('records')
                })
        
        return anomalies
    
    def calculate_spending_threshold(self, window: int = 30) -> Dict:
        """Calculate average and threshold for discretionary spending"""
        discretionary = self.get_discretionary_spending()
        
        if len(discretionary) == 0:
            return {
                'avg_daily_spending': 0,
                'threshold': 0,
                'std': 0
            }
        
        # Group by date
        daily_spending = discretionary.groupby('date')['amount'].sum()
        
        # Calculate statistics
        avg_daily = daily_spending.mean()
        std_daily = daily_spending.std()
        
        # Threshold at 2 standard deviations
        threshold = avg_daily + (2 * std_daily)
        
        return {
            'avg_daily_spending': float(avg_daily),
            'threshold': float(threshold),
            'std': float(std_daily)
        }


class ForecastEngine:
    """Engine for forecasting future spending"""
    
    def __init__(self, user):
        self.user = user
        
    def forecast_next_month(self) -> Dict:
        """
        Generate a 30-day financial forecast.
        
        Returns:
            Dictionary with forecast details
        """
        from finance.models import RecurringPayment
        
        today = datetime.now().date()
        forecast_end = today + timedelta(days=30)
        
        # Get confirmed recurring payments
        recurring_payments = RecurringPayment.objects.filter(
            user=self.user,
            is_active=True,
            confirmed_by_user=True
        )
        
        # Calculate deterministic spend (recurring payments)
        deterministic_spend = 0
        payment_schedule = []
        
        for payment in recurring_payments:
            # Calculate occurrences in the next 30 days
            occurrences = self._calculate_occurrences(payment, today, forecast_end)
            
            for occurrence_date in occurrences:
                deterministic_spend += float(payment.amount)
                payment_schedule.append({
                    'date': occurrence_date,
                    'name': payment.name,
                    'amount': float(payment.amount),
                    'category': payment.category.name if payment.category else 'Uncategorized'
                })
        
        # Calculate discretionary spend projection
        analyzer = TimeSeriesAnalyzer(self.user)
        analyzer.load_data(start_date=today - timedelta(days=90))  # Last 90 days
        
        threshold_info = analyzer.calculate_spending_threshold()
        avg_daily_discretionary = threshold_info['avg_daily_spending']
        projected_discretionary = avg_daily_discretionary * 30
        
        # Total forecast
        total_forecast = deterministic_spend + projected_discretionary
        
        return {
            'forecast_period': {
                'start': today,
                'end': forecast_end
            },
            'deterministic_spend': deterministic_spend,
            'projected_discretionary': projected_discretionary,
            'total_forecast': total_forecast,
            'payment_schedule': sorted(payment_schedule, key=lambda x: x['date']),
            'avg_daily_discretionary': avg_daily_discretionary,
            'unusual_spending_threshold': threshold_info['threshold']
        }
    
    def _calculate_occurrences(self, payment: 'RecurringPayment', 
                               start_date: datetime, end_date: datetime) -> List[datetime]:
        """Calculate occurrence dates for a recurring payment in the given period"""
        occurrences = []
        
        current_date = max(start_date, payment.start_date)
        
        while current_date <= end_date:
            if payment.end_date and current_date > payment.end_date:
                break
            
            if payment.frequency == 'monthly':
                # Add payment on the due_day of each month
                try:
                    payment_date = current_date.replace(day=payment.due_day)
                    if start_date <= payment_date <= end_date:
                        occurrences.append(payment_date)
                except ValueError:
                    # Handle invalid day (e.g., Feb 30)
                    pass
                
                # Move to next month
                if current_date.month == 12:
                    current_date = current_date.replace(year=current_date.year + 1, month=1)
                else:
                    current_date = current_date.replace(month=current_date.month + 1)
            
            elif payment.frequency == 'weekly':
                # Find next occurrence of the due day (0=Monday, 6=Sunday)
                days_ahead = payment.due_day - current_date.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                payment_date = current_date + timedelta(days=days_ahead)
                
                if start_date <= payment_date <= end_date:
                    occurrences.append(payment_date)
                
                current_date = payment_date + timedelta(days=7)
            
            elif payment.frequency == 'biweekly':
                days_ahead = payment.due_day - current_date.weekday()
                if days_ahead <= 0:
                    days_ahead += 14
                payment_date = current_date + timedelta(days=days_ahead)
                
                if start_date <= payment_date <= end_date:
                    occurrences.append(payment_date)
                
                current_date = payment_date + timedelta(days=14)
            
            elif payment.frequency == 'quarterly':
                # Add 3 months
                month = current_date.month + 3
                year = current_date.year
                if month > 12:
                    month -= 12
                    year += 1
                
                try:
                    payment_date = current_date.replace(year=year, month=month, day=payment.due_day)
                    if start_date <= payment_date <= end_date:
                        occurrences.append(payment_date)
                except ValueError:
                    pass
                
                current_date = payment_date
            
            elif payment.frequency == 'annual':
                # Add 1 year
                try:
                    payment_date = current_date.replace(year=current_date.year + 1)
                    if start_date <= payment_date <= end_date:
                        occurrences.append(payment_date)
                except ValueError:
                    pass
                
                current_date = payment_date
            
            else:
                break
        
        return occurrences