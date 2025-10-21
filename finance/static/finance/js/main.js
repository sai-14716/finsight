// This file contains JavaScript code for the FinSIGHT application. 
// It handles user interactions, AJAX requests for syncing transactions, 
// and dynamic updates to the dashboard and charts.

document.addEventListener('DOMContentLoaded', function() {
    // Function to sync transactions
    document.getElementById('sync-transactions').addEventListener('click', function() {
        fetch('/api/sync-transactions/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ force_sync: true })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Transactions synced successfully!');
                location.reload(); // Reload the page to see updated transactions
            } else {
                alert('Error syncing transactions: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
        });
    });

    // Function to get CSRF token
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                // Check if this cookie string begins with the desired name
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Additional JavaScript functionalities can be added here
});