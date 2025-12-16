/**
 * pm6 Admin GUI - Main JavaScript
 */

// Utility function to make API calls
async function apiCall(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        },
    });
    return response.json();
}

// Refresh functions for different pages
function refreshSimulations() {
    location.reload();
}

function refreshAgents(simName) {
    fetch(`/api/simulations/${simName}/agents`)
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                const container = document.getElementById('agents-list');
                if (container) {
                    let html = '';
                    if (data.agents.length === 0) {
                        html = '<tr><td colspan="5" class="empty-state">No agents registered</td></tr>';
                    } else {
                        data.agents.forEach(agent => {
                            html += `
                                <tr>
                                    <td>${agent.name}</td>
                                    <td>${agent.role}</td>
                                    <td>${agent.model}</td>
                                    <td>${agent.controlledBy}</td>
                                    <td>
                                        <a href="/simulations/${simName}/agents/${agent.name}/edit" class="btn btn-sm">Edit</a>
                                        <form action="/simulations/${simName}/agents/${agent.name}/delete" method="POST" style="display:inline">
                                            <button type="submit" class="btn btn-sm btn-danger" onclick="return confirm('Delete this agent?')">Delete</button>
                                        </form>
                                    </td>
                                </tr>
                            `;
                        });
                    }
                    container.innerHTML = html;
                }
            }
        });
}

function refreshEvents(simName) {
    fetch(`/api/simulations/${simName}/events/history`)
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                const container = document.getElementById('event-history');
                if (container) {
                    let html = '';
                    if (data.events.length === 0) {
                        html = '<div class="empty-state">No events yet</div>';
                    } else {
                        data.events.forEach(event => {
                            html += `
                                <div class="event-item">
                                    <span class="event-name">${event.name}</span>
                                    <span class="event-source">[${event.source}]</span>
                                    <pre>${JSON.stringify(event.data, null, 2)}</pre>
                                </div>
                            `;
                        });
                    }
                    container.innerHTML = html;
                }
            }
        });
}

function refreshStats(simName) {
    fetch(`/api/simulations/${simName}/stats`)
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                const container = document.getElementById('sim-stats');
                if (container) {
                    container.innerHTML = `<pre>${JSON.stringify(data.stats, null, 2)}</pre>`;
                }
            }
        });
}

// Auto-scroll to bottom of results
function scrollToResults() {
    const results = document.getElementById('test-results');
    if (results) {
        results.scrollTop = results.scrollHeight;
    }
}

// Confirmation dialogs
function confirmDelete(message) {
    return confirm(message || 'Are you sure you want to delete this?');
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Add confirmation to delete forms
    document.querySelectorAll('form[data-confirm]').forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!confirm(this.dataset.confirm)) {
                e.preventDefault();
            }
        });
    });
});
