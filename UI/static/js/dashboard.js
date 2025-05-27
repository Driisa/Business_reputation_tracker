document.addEventListener('DOMContentLoaded', function() {
    const dashboardContainer = document.getElementById('dashboard-container');
    if (!dashboardContainer) return;

    const companyMentions = Array.from(document.querySelectorAll('#mentions-table tbody tr')).map(row => ({
        title: row.cells[0].textContent,
        date: new Date(row.cells[1].textContent),
        contentType: row.cells[2].textContent,
        sentimentScore: parseFloat(row.cells[3].textContent),
        sentiment: row.cells[4].textContent,
        summary: row.dataset.summary
    }));

    // Initialize filters
    initializeFilters(companyMentions);

    // Create initial charts
    createSentimentTrendChart(companyMentions);
    createContentTypeChart(companyMentions);

    // Add filter event listener
    document.getElementById('apply-filters').addEventListener('click', function() {
        const filteredData = filterData(companyMentions);
        updateCharts(filteredData);
        updateStats(filteredData);
    });

    // Initialize modal functionality
    const modal = document.getElementById('summaryModal');
    const modalSummary = document.getElementById('modalSummary');
    const closeBtn = document.getElementsByClassName('close')[0];

    // Add click event to table rows
    document.querySelectorAll('.clickable-row').forEach(row => {
        row.addEventListener('click', function() {
            modalSummary.textContent = this.dataset.summary;
            modal.style.display = 'block';
        });
    });

    // Close modal when clicking the close button
    closeBtn.onclick = function() {
        modal.style.display = 'none';
    }

    // Close modal when clicking outside
    window.onclick = function(event) {
        if (event.target == modal) {
            modal.style.display = 'none';
        }
    }

    // Initialize sidebar toggle functionality
    const sidebar = document.querySelector('.sidebar');
    const toggleButton = document.getElementById('sidebarToggle');
    const toggleIcon = document.getElementById('toggleIcon');
    const mainContent = document.querySelector('.main-content');

    toggleButton.addEventListener('click', function() {
        sidebar.classList.toggle('collapsed');
        mainContent.style.marginLeft = sidebar.classList.contains('collapsed') ? '40px' : '270px';
        toggleIcon.classList.toggle('fa-chevron-right');
        toggleIcon.classList.toggle('fa-chevron-left');
    });
});

function initializeFilters(data) {
    // Get unique content types (handling multiple types per mention)
    const contentTypes = new Set();
    data.forEach(mention => {
        mention.contentType.split('/').forEach(type => {
            contentTypes.add(type.trim());
        });
    });

    // Get unique sentiments
    const sentiments = new Set(data.map(mention => mention.sentiment));

    // Populate content type filter with toggle items
    const contentTypeFilter = document.getElementById('content-type-filter');
    contentTypeFilter.className = 'filter-options';
    Array.from(contentTypes).sort().forEach(type => {
        const toggleItem = document.createElement('div');
        toggleItem.className = 'toggle-item active';
        toggleItem.dataset.value = type;
        toggleItem.textContent = type;
        
        toggleItem.addEventListener('click', function() {
            this.classList.toggle('active');
        });
        
        contentTypeFilter.appendChild(toggleItem);
    });

    // Populate sentiment filter with toggle items
    const sentimentFilter = document.getElementById('sentiment-filter');
    sentimentFilter.className = 'filter-options';
    Array.from(sentiments).sort().forEach(sentiment => {
        const toggleItem = document.createElement('div');
        toggleItem.className = 'toggle-item active';
        toggleItem.dataset.value = sentiment;
        toggleItem.textContent = sentiment;
        
        toggleItem.addEventListener('click', function() {
            this.classList.toggle('active');
        });
        
        sentimentFilter.appendChild(toggleItem);
    });

    // Set date range
    if (data.length > 0) {
        const dates = data.map(m => m.date);
        const minDate = new Date(Math.min(...dates));
        const maxDate = new Date(Math.max(...dates));

        document.getElementById('start-date').value = minDate.toISOString().split('T')[0];
        document.getElementById('end-date').value = maxDate.toISOString().split('T')[0];
    }
}

function filterData(data) {
    const startDate = new Date(document.getElementById('start-date').value);
    const endDate = new Date(document.getElementById('end-date').value);
    const selectedTypes = Array.from(document.getElementById('content-type-filter').querySelectorAll('.toggle-item.active')).map(item => item.dataset.value);
    const selectedSentiments = Array.from(document.getElementById('sentiment-filter').querySelectorAll('.toggle-item.active')).map(item => item.dataset.value);
    
    // Return empty array if no filters are selected
    if (selectedTypes.length === 0 || selectedSentiments.length === 0) {
        return [];
    }

    return data.filter(mention => {
        const date = mention.date;
        const types = mention.contentType.split('/').map(t => t.trim());
        const dateInRange = date >= startDate && date <= endDate;
        const typeMatch = types.some(t => selectedTypes.includes(t));
        const sentimentMatch = selectedSentiments.includes(mention.sentiment);
        return dateInRange && typeMatch && sentimentMatch;
    });
}

function createSentimentTrendChart(data) {
    // Sort data by date
    const sortedData = [...data].sort((a, b) => a.date - b.date);

    const trace = {
        x: sortedData.map(d => d.date),
        y: sortedData.map(d => d.sentimentScore),
        mode: 'lines+markers',
        name: 'Sentiment Score',
        line: {
            color: 'var(--secondary)',
            width: 2
        },
        marker: {
            size: 6,
            color: sortedData.map(d => {
                if (d.sentimentScore > 0.33) return 'var(--positive)';
                if (d.sentimentScore < -0.33) return 'var(--negative)';
                return 'var(--neutral)';
            })
        }
    };

    const layout = {
        title: 'Sentiment Score Over Time',
        xaxis: {
            title: 'Date',
            tickformat: '%Y-%m-%d'
        },
        yaxis: {
            title: 'Sentiment Score',
            range: [-1, 1]
        },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        hovermode: 'closest'
    };

    Plotly.newPlot('sentiment-time-graph', [trace], layout);
}

function createContentTypeChart(data) {
    // Count content types (splitting multiple types)
    const typeCount = {};
    let totalTypes = 0;

    data.forEach(mention => {
        const types = mention.contentType.split('/').map(t => t.trim());
        types.forEach(type => {
            typeCount[type] = (typeCount[type] || 0) + 1;
            totalTypes++;
        });
    });

    // Convert to percentages
    const labels = Object.keys(typeCount);
    const values = labels.map(label => (typeCount[label] / totalTypes) * 100);

    // Define a consistent color palette
    const colors = [
        'var(--primary)',
        'var(--secondary)',
        'var(--accent)',
        'var(--dark)',
        '#FF6B6B',
        '#4ECDC4',
        '#45B7D1',
        '#96CEB4'
    ];

    const trace = {
        type: 'pie',
        labels: labels,
        values: values,
        textinfo: 'percent',
        hoverinfo: 'label+percent',
        marker: {
            colors: colors.slice(0, labels.length)
        }
    };

    const layout = {
        title: 'Content Type Distribution',
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        showlegend: true,
        legend: {
            x: 1.1,
            y: 0.5,
            orientation: 'vertical',
            xanchor: 'left',
            font: {
                size: 12
            }
        }
    };

    Plotly.newPlot('content-type-chart', [trace], layout);
}

function updateCharts(data) {
    createSentimentTrendChart(data);
    createContentTypeChart(data);
    updateTable(data);
}

function updateStats(data) {
    document.getElementById('total-mentions').textContent = data.length;
    const avgSentiment = data.length > 0 
        ? data.reduce((sum, d) => sum + d.sentimentScore, 0) / data.length
        : 0;
    document.getElementById('avg-sentiment').textContent = avgSentiment.toFixed(2);
}

function updateTable(data) {
    const rows = document.querySelectorAll('#mentions-table tbody tr');
    const filteredTitles = new Set(data.map(d => d.title));
    
    rows.forEach(row => {
        const title = row.cells[0].textContent;
        if (filteredTitles.has(title)) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

// Modal functionality
const modal = document.getElementById('summaryModal');
const modalSummary = document.getElementById('modalSummary');
const closeBtn = document.getElementsByClassName('close')[0];

// Add click event to table rows
document.querySelectorAll('.clickable-row').forEach(row => {
    row.addEventListener('click', function() {
        modalSummary.textContent = this.dataset.summary;
        modal.style.display = 'block';
    });
});

// Close modal when clicking the close button
closeBtn.onclick = function() {
    modal.style.display = 'none';
}

// Close modal when clicking outside
window.onclick = function(event) {
    if (event.target == modal) {
        modal.style.display = 'none';
    }
}

// Sidebar toggle functionality
document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.querySelector('.sidebar');
    const toggleButton = document.getElementById('sidebarToggle');
    const toggleIcon = document.getElementById('toggleIcon');
    const mainContent = document.querySelector('.main-content');

    toggleButton.addEventListener('click', function() {
        sidebar.classList.toggle('collapsed');
        mainContent.style.marginLeft = sidebar.classList.contains('collapsed') ? '40px' : '270px';
        toggleIcon.classList.toggle('fa-chevron-right');
        toggleIcon.classList.toggle('fa-chevron-left');
    });
});

// Sidebar toggle functionality
document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.querySelector('.sidebar');
    const toggleButton = document.getElementById('sidebarToggle');
    const toggleIcon = document.getElementById('toggleIcon');
    const mainContent = document.querySelector('.main-content');

    toggleButton.addEventListener('click', function() {
        sidebar.classList.toggle('collapsed');
        mainContent.style.marginLeft = sidebar.classList.contains('collapsed') ? '40px' : '270px';
        toggleIcon.classList.toggle('fa-chevron-right');
        toggleIcon.classList.toggle('fa-chevron-left');
    });
});
